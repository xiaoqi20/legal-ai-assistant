import asyncio
import contextlib
import json
import logging
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import anyio
from fastapi import HTTPException
from sqlalchemy import func, insert, select, update

from app.access import require_conversation
from app.errors import fail
from app.services.agent import AgentEvent, AgentStopped, ToolCallingAgent
from app.services.ai import extract_cache_usage
from app.services.rag import build_context, retrieve
from app.services.tools import CaseTools, ToolAccessDenied

logger = logging.getLogger(__name__)


def sse(event, data):
  return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, separators=(',', ':'))}\n\n".encode()


async def expire_streams(db, t):
  await db.execute(update(t.ai_messages).where(
    t.ai_messages.c.status == "streaming", t.ai_messages.c.lease_expires_at < datetime.now(UTC),
  ).values(status="failed", error_code="stream_lease_expired", completed_at=datetime.now(UTC)))


async def prepare(database, settings, user_id, conversation_id, payload):
  t = database.t
  async with database.sessions.begin() as db:
    # One short global admission transaction enforces limits across all API replicas.
    await db.execute(select(func.pg_advisory_xact_lock(42701113)))
    conversation = await require_conversation(db, t, user_id, conversation_id, lock=True)
    await expire_streams(db, t)
    duplicate = (await db.execute(select(t.ai_messages.c.id).where(
      t.ai_messages.c.conversation_id == conversation_id,
      t.ai_messages.c.client_message_id == payload.client_message_id,
    ))).scalar_one_or_none()
    if duplicate:
      fail(409, "duplicate_message", f"消息已接收，请通过历史接口查询（消息 {duplicate}）")
    in_conversation = (await db.execute(select(t.ai_messages.c.id).where(
      t.ai_messages.c.conversation_id == conversation_id, t.ai_messages.c.status == "streaming",
    ))).scalar_one_or_none()
    if in_conversation:
      fail(409, "generation_in_progress", "当前对话正在生成回答")
    active = (await db.execute(select(func.count()).select_from(t.ai_messages).where(
      t.ai_messages.c.status == "streaming",
    ))).scalar_one()
    jobs = (await db.execute(select(func.count()).select_from(t.async_jobs).where(
      t.async_jobs.c.status == "running", t.async_jobs.c.lease_expires_at > datetime.now(UTC),
    ))).scalar_one()
    if active + jobs >= settings.max_concurrent_streams:
      fail(429, "capacity_exceeded", "当前服务繁忙，请稍后重试")
    recent = (await db.execute(select(func.count()).select_from(t.ai_messages.join(
      t.ai_conversations, t.ai_conversations.c.id == t.ai_messages.c.conversation_id,
    )).where(t.ai_conversations.c.user_id == user_id, t.ai_messages.c.role == "user",
      t.ai_messages.c.created_at >= datetime.now(UTC) - timedelta(minutes=1),
    ))).scalar_one()
    if recent >= settings.per_user_requests_per_minute:
      fail(429, "rate_limited", "请求过于频繁，请稍后重试")
    prompt = (await db.execute(select(t.prompt_versions).where(
      t.prompt_versions.c.prompt_key == "grounded_qa", t.prompt_versions.c.status == "active",
    ))).mappings().first()
    if not prompt:
      fail(503, "prompt_not_ready", "问答提示词尚未配置")
    history = (await db.execute(select(t.ai_messages.c.role, t.ai_messages.c.content)
      .where(t.ai_messages.c.conversation_id == conversation_id,
        t.ai_messages.c.status == "completed", t.ai_messages.c.role.in_(["user", "assistant"]))
      .order_by(t.ai_messages.c.seq.desc()).limit(20))).mappings().all()
    seq = (await db.execute(select(func.coalesce(func.max(t.ai_messages.c.seq), 0)).where(
      t.ai_messages.c.conversation_id == conversation_id))).scalar_one()
    user_message_id = (await db.execute(insert(t.ai_messages).values(
      conversation_id=conversation_id, case_id=conversation["case_id"], seq=seq + 1,
      role="user", content=payload.content, client_message_id=payload.client_message_id,
      completed_at=datetime.now(UTC),
    ).returning(t.ai_messages.c.id))).scalar_one()
    message_id = (await db.execute(insert(t.ai_messages).values(
      conversation_id=conversation_id, case_id=conversation["case_id"], seq=seq + 2,
      role="assistant", status="streaming", model=settings.deepseek_model,
      prompt_version_id=prompt["id"],
      lease_expires_at=datetime.now(UTC) + timedelta(seconds=settings.ai_timeout_seconds + 30),
    ).returning(t.ai_messages.c.id))).scalar_one()
    await db.execute(update(t.ai_conversations).where(t.ai_conversations.c.id == conversation_id).values(
      message_count=t.ai_conversations.c.message_count + 2,
      last_message_at=datetime.now(UTC),
      title=payload.content[:50] if conversation["message_count"] == 0 and conversation["title"] == "未命名对话" else conversation["title"],
    ))
    return {"conversation": conversation, "message_id": message_id,
            "user_message_id": user_message_id, "prompt": dict(prompt),
            "history": [dict(item) for item in reversed(history)]}


async def still_authorized(database, user_id, conversation_id, message_id):
  t = database.t
  async with database.sessions() as db:
    try:
      await require_conversation(db, t, user_id, conversation_id)
    except HTTPException:
      return False
    active = (await db.execute(select(t.users.c.id).where(
      t.users.c.id == user_id, t.users.c.status == "active", t.users.c.deleted_at.is_(None),
    ))).scalar_one_or_none()
    status = (await db.execute(select(t.ai_messages.c.status).where(t.ai_messages.c.id == message_id))).scalar_one()
    return active is not None and status == "streaming"


async def finalize(database, settings, prepared, content, status, code, usage, started, agent_metadata=None):
  t = database.t
  cost = None
  if usage and settings.input_usd_per_million is not None and settings.output_usd_per_million is not None:
    cost = (Decimal(usage.prompt_tokens) * settings.input_usd_per_million
            + Decimal(usage.completion_tokens) * settings.output_usd_per_million) / 1000000
  values = {"content": content, "completed_at": datetime.now(UTC),
            "latency_ms": int((time.monotonic() - started) * 1000),
            "cost_usd": cost, "lease_expires_at": None}
  metadata = {}
  if agent_metadata is not None:
    metadata["agent"] = agent_metadata
  if usage:
    values.update(input_tokens=usage.prompt_tokens, output_tokens=usage.completion_tokens)
    cache_usage = extract_cache_usage(usage)
    if cache_usage:
      metadata["prompt_cache"] = cache_usage
  async with database.sessions.begin() as db:
    current = (await db.execute(select(t.ai_messages.c.status).where(
      t.ai_messages.c.id == prepared["message_id"]).with_for_update())).scalar_one()
    if current == "cancelled":
      status, code = "cancelled", "cancelled"
    elif current != "streaming":
      status, code = current, "stream_lease_expired"
    if agent_metadata is not None:
      metadata["agent"]["stop_reason"] = code or status
    if metadata:
      values["metadata"] = metadata
    values.update(status=status, error_code=code)
    await db.execute(update(t.ai_messages).where(t.ai_messages.c.id == prepared["message_id"]).values(**values))
  return status


async def plain_events(ai, messages):
  upstream = ai.stream(messages)
  try:
    async for chunk in upstream:
      yield AgentEvent("chunk", chunk)
  finally:
    await upstream.aclose()


async def events(request, user_id, payload, prepared):
  database, settings, ai = request.app.state.db, request.app.state.settings, request.app.state.ai
  t = database.t
  message_id = prepared["message_id"]
  conversation_id = prepared["conversation"]["id"]
  content, sources, usage, code, status = "", [], None, None, "failed"
  started = time.monotonic()
  pending = None
  upstream = None
  agent = None
  last_checkpoint = started
  try:
    yield sse("meta", {"conversation_id": conversation_id, "message_id": message_id,
                       "user_message_id": prepared["user_message_id"], "protocol": "law-sse-v1"})
    async with asyncio.timeout(settings.ai_timeout_seconds):
      if prepared["conversation"]["case_id"] is not None:
        async with database.sessions() as db:
          sources = await retrieve(db, t, ai, settings, user_id,
            prepared["conversation"]["case_id"], payload.content)
        async with database.sessions.begin() as db:
          for source in sources:
            await db.execute(insert(t.ai_citations).values(message_id=message_id, **source))
      yield sse("citations", {"sources": sources})
      messages = build_context(prepared["prompt"]["content"], prepared["history"], payload.content,
                               sources, settings.max_context_chars)
      if settings.tool_calling_enabled and prepared["conversation"]["case_id"] is not None:
        tools = CaseTools(database, ai, settings, user_id, prepared["conversation"]["case_id"], sources)

        async def authorize():
          return await still_authorized(database, user_id, conversation_id, message_id)

        agent = ToolCallingAgent(ai, settings, tools, authorize)
        upstream = agent.events(messages).__aiter__()
      else:
        upstream = plain_events(ai, messages).__aiter__()
      finish_reason = None
      while True:
        if pending is None:
          pending = asyncio.create_task(anext(upstream))
        done, _ = await asyncio.wait({pending}, timeout=1)
        if not await still_authorized(database, user_id, conversation_id, message_id):
          code, status = "cancelled", "cancelled"
          break
        if not done:
          yield b": keepalive\n\n"
          continue
        try:
          event = pending.result()
        except StopAsyncIteration:
          break
        finally:
          pending = None
        if agent is not None:
          usage = agent.usage.total
        if event.kind == "sources":
          additions = event.value[len(sources):]
          if additions:
            async with database.sessions.begin() as db:
              await require_conversation(db, t, user_id, conversation_id)
              for source in additions:
                await db.execute(insert(t.ai_citations).values(message_id=message_id, **source))
            sources = list(event.value)
            yield sse("citations", {"sources": sources})
          continue
        if event.kind == "usage":
          continue
        chunk = event.value
        if chunk.usage is not None:
          usage = agent.usage.total if agent is not None else chunk.usage
        if chunk.choices:
          choice = chunk.choices[0]
          finish_reason = choice.finish_reason or finish_reason
          delta = choice.delta.content or ""
          if len(content) + len(delta) > settings.max_output_chars:
            code = "output_limit"
            break
          if delta:
            content += delta
            yield sse("delta", {"text": delta})
        if time.monotonic() - last_checkpoint >= 1:
          async with database.sessions.begin() as db:
            await db.execute(update(t.ai_messages).where(t.ai_messages.c.id == message_id,
              t.ai_messages.c.status == "streaming").values(content=content))
          last_checkpoint = time.monotonic()
      if status != "cancelled":
        import re
        ranks = {source["rank"] for source in sources}
        if any(int(rank) not in ranks for rank in re.findall(r"\[(\d+)\]", content)):
          code = "invalid_citation"
        if finish_reason == "stop" and content and code is None:
          status = "completed"
        else:
          code = code or ("output_limit" if finish_reason == "length" else "upstream_incomplete")
  except (asyncio.CancelledError, GeneratorExit):
    status, code = "cancelled", "client_disconnected"
    raise
  except TimeoutError:
    code = "generation_timeout"
  except AgentStopped as error:
    code = error.code
  except ToolAccessDenied:
    code, status = "cancelled", "cancelled"
  except Exception as error:
    code = "upstream_error"
    logger.warning("chat_failed message_id=%s type=%s", message_id, type(error).__name__)
  finally:
    # Shield final persistence from ASGI disconnect cancellation.
    with anyio.CancelScope(shield=True):
      if pending:
        pending.cancel()
        with contextlib.suppress(asyncio.CancelledError, StopAsyncIteration, Exception):
          await pending
      if upstream:
        with contextlib.suppress(Exception):
          await upstream.aclose()
      if agent is not None:
        usage = agent.usage.total
      try:
        status = await finalize(database, settings, prepared, content, status, code, usage, started,
          agent.metadata if agent is not None else None)
      except Exception as error:
        logger.error("stream_persistence_failed message_id=%s type=%s", message_id, type(error).__name__)
        # ASGI servers log unhandled stream exceptions. Never include SQL parameters/document text.
        raise RuntimeError("stream_persistence_failed") from None
  if status != "completed":
    yield sse("error", {"code": code or status, "message": "本次回答未完成，可查看历史后重新提问", "retryable": status != "cancelled"})
  usage_payload = (
    {"input_tokens": usage.prompt_tokens, "output_tokens": usage.completion_tokens,
     **extract_cache_usage(usage)}
    if usage else None
  )
  yield sse("done", {"message_id": message_id, "status": status, "usage": usage_payload})
