import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Query, Request
from fastapi import HTTPException as FastAPIHTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func, insert, select, update

from app.access import DB, User, require_case
from app.errors import fail
from app.schemas import AssessmentCreate, AssessmentResume
from app.services.assessment import GRAPH_VERSION, TERMINAL
from app.services.assessment_store import snapshot
from app.services.chat import sse

router = APIRouter()


async def require_run(db, t, user_id, case_id, run_id, *, lock=False):
  await require_case(db, t, user_id, case_id)
  query = select(t.case_assessment_runs).where(t.case_assessment_runs.c.id == run_id,
    t.case_assessment_runs.c.case_id == case_id)
  row = (await db.execute(query.with_for_update() if lock else query)).mappings().first()
  if row is None:
    fail(404, "assessment_not_found", "研判任务不存在")
  return dict(row)


def summary(run):
  keys = ("id", "case_id", "created_by", "question", "status", "stage", "revision", "graph_version",
    "model", "prompt_version_id", "input_fingerprint", "questions", "error_code", "created_at", "completed_at")
  return {key: run[key] for key in keys}


async def queue(db, t, run_id, revision):
  return await db.scalar(insert(t.async_jobs).values(job_type="case_assessment", resource_type="assessment",
    resource_id=run_id, payload={}, idempotency_key=f"assessment:{run_id}:{revision}")
    .returning(t.async_jobs.c.id))


@router.post("/cases/{case_id}/assessment-runs", status_code=202)
async def create(case_id: int, payload: AssessmentCreate, request: Request, db: DB, user: User):
  settings, t = request.app.state.settings, request.app.state.db.t
  if not settings.assessment_enabled:
    fail(503, "assessment_disabled", "案件研判暂未开放")
  request.app.state.ai.check(rerank=True)
  await db.execute(select(func.pg_advisory_xact_lock(42701113)))
  await require_case(db, t, user["id"], case_id)
  existing = (await db.execute(select(t.case_assessment_runs).where(
    t.case_assessment_runs.c.created_by == user["id"],
    t.case_assessment_runs.c.client_request_id == payload.client_request_id))).mappings().first()
  if existing:
    if existing["case_id"] != case_id or existing["question"] != payload.question:
      fail(409, "idempotency_conflict", "该请求标识已用于其他研判")
    return summary(existing)
  active = await db.scalar(select(t.case_assessment_runs.c.id).where(
    t.case_assessment_runs.c.case_id == case_id, t.case_assessment_runs.c.created_by == user["id"],
    t.case_assessment_runs.c.status.in_(["pending", "running", "awaiting_input"])))
  if active:
    fail(409, "assessment_in_progress", "已有进行中或待补充的研判，请查看现有任务")
  recent = await db.scalar(select(func.count()).select_from(t.case_assessment_runs).where(
    t.case_assessment_runs.c.created_by == user["id"],
    t.case_assessment_runs.c.created_at >= datetime.now(UTC) - timedelta(minutes=1)))
  if recent >= settings.per_user_requests_per_minute:
    fail(429, "rate_limited", "请求过于频繁，请稍后重试")
  prompt_id = await db.scalar(select(t.prompt_versions.c.id).where(
    t.prompt_versions.c.prompt_key == "case_assessment", t.prompt_versions.c.status == "active"))
  if not prompt_id:
    fail(503, "prompt_not_ready", "研判提示词尚未配置")
  _, fingerprint = await snapshot(db, t, user["id"], case_id)
  run = (await db.execute(insert(t.case_assessment_runs).values(case_id=case_id, created_by=user["id"],
    client_request_id=payload.client_request_id, question=payload.question, graph_version=GRAPH_VERSION,
    prompt_version_id=prompt_id, model=settings.deepseek_model, input_fingerprint=fingerprint,
    remaining_seconds=settings.assessment_timeout_seconds).returning(t.case_assessment_runs))).mappings().one()
  job_id = await queue(db, t, run["id"], 1)
  await db.execute(insert(t.audit_logs).values(user_id=user["id"], action="assessment.created",
    resource_type="assessment", resource_id=run["id"]))
  await db.commit()
  return {**summary(run), "job_id": job_id}


@router.get("/cases/{case_id}/assessment-runs")
async def history(case_id: int, request: Request, db: DB, user: User,
                  before_id: int | None = None, limit: int = Query(20, ge=1, le=100)):
  t = request.app.state.db.t
  await require_case(db, t, user["id"], case_id)
  query = select(t.case_assessment_runs).where(t.case_assessment_runs.c.case_id == case_id)
  if before_id:
    query = query.where(t.case_assessment_runs.c.id < before_id)
  rows = (await db.execute(query.order_by(t.case_assessment_runs.c.id.desc()).limit(limit + 1))).mappings().all()
  return {"items": [summary(row) for row in rows[:limit]],
    "next_cursor": rows[limit - 1]["id"] if len(rows) > limit else None}


@router.get("/cases/{case_id}/assessment-runs/{run_id}")
async def get(case_id: int, run_id: int, request: Request, db: DB, user: User):
  t, settings = request.app.state.db.t, request.app.state.settings
  run = await require_run(db, t, user["id"], case_id, run_id)
  _, fingerprint = await snapshot(db, t, user["id"], case_id)
  steps = (await db.execute(select(t.case_assessment_steps.c.status, t.case_assessment_steps.c.usage)
    .where(t.case_assessment_steps.c.run_id == run_id, t.case_assessment_steps.c.kind == "model"))).mappings().all()
  usage = None
  cost = None
  if steps and all(step["status"] == "completed" and step["usage"] is not None for step in steps):
    usage = {key: sum(step["usage"].get(key, 0) for step in steps) for key in
      ("input_tokens", "output_tokens", "cached_tokens", "cache_miss_tokens")}
    if settings.input_usd_per_million is not None and settings.output_usd_per_million is not None:
      cost = (Decimal(usage["input_tokens"]) * settings.input_usd_per_million
        + Decimal(usage["output_tokens"]) * settings.output_usd_per_million) / 1000000
  return {**summary(run), "report": run["report"], "sources": run["sources"], "usage": usage,
    "cost_usd": cost, "model_calls": run["model_calls"], "tool_calls": run["tool_calls"],
    "inputs_current": fingerprint == run["input_fingerprint"]}


@router.post("/cases/{case_id}/assessment-runs/{run_id}/resume", status_code=202)
async def resume(case_id: int, run_id: int, payload: AssessmentResume, request: Request, db: DB, user: User):
  t = request.app.state.db.t
  # Serialize with cancel/worker using the same job -> run lock order.
  await db.execute(select(t.async_jobs.c.id).where(t.async_jobs.c.resource_type == "assessment",
    t.async_jobs.c.resource_id == run_id).order_by(t.async_jobs.c.id).with_for_update())
  run = await require_run(db, t, user["id"], case_id, run_id, lock=True)
  if run["created_by"] != user["id"]:
    fail(403, "assessment_owner_required", "只有发起人可以补充或取消研判")
  if run["status"] != "awaiting_input" or run["revision"] != payload.revision:
    fail(409, "assessment_revision_conflict", "研判状态已变更，请刷新后重试")
  _, fingerprint = await snapshot(db, t, user["id"], case_id)
  if fingerprint != run["input_fingerprint"]:
    await db.execute(update(t.case_assessment_runs).where(t.case_assessment_runs.c.id == run_id)
      .values(status="stale", stage="stale", error_code="stale_inputs", completed_at=datetime.now(UTC)))
    await db.commit()
    fail(409, "stale_inputs", "案件资料已变更，请基于最新资料重新发起研判")
  revision = run["revision"] + 1
  await db.execute(update(t.case_assessment_runs).where(t.case_assessment_runs.c.id == run_id)
    .values(status="pending", stage="queued", revision=revision, resume_payload={"answers": payload.answers}))
  job_id = await queue(db, t, run_id, revision)
  await db.execute(insert(t.audit_logs).values(user_id=user["id"], action="assessment.resumed",
    resource_type="assessment", resource_id=run_id))
  await db.commit()
  return {"id": run_id, "status": "pending", "revision": revision, "job_id": job_id}


@router.post("/cases/{case_id}/assessment-runs/{run_id}/cancel")
async def cancel(case_id: int, run_id: int, request: Request, db: DB, user: User):
  t = request.app.state.db.t
  await db.execute(select(t.async_jobs.c.id).where(t.async_jobs.c.resource_type == "assessment",
    t.async_jobs.c.resource_id == run_id).order_by(t.async_jobs.c.id).with_for_update())
  run = await require_run(db, t, user["id"], case_id, run_id, lock=True)
  if run["created_by"] != user["id"]:
    fail(403, "assessment_owner_required", "只有发起人可以补充或取消研判")
  if run["status"] not in TERMINAL:
    await db.execute(update(t.async_jobs).where(t.async_jobs.c.resource_type == "assessment",
      t.async_jobs.c.resource_id == run_id, t.async_jobs.c.status.in_(["queued", "running"]))
      .values(status="cancelled", finished_at=datetime.now(UTC), lease_token=None, lease_expires_at=None))
    await db.execute(update(t.case_assessment_runs).where(t.case_assessment_runs.c.id == run_id)
      .values(status="cancelled", stage="cancelled", error_code="cancelled", deadline_at=None,
        resume_payload=None, completed_at=datetime.now(UTC)))
    await db.execute(insert(t.audit_logs).values(user_id=user["id"], action="assessment.cancelled",
      resource_type="assessment", resource_id=run_id))
  await db.commit()
  return {"id": run_id, "status": run["status"] if run["status"] in TERMINAL else "cancelled"}


@router.get("/cases/{case_id}/assessment-runs/{run_id}/events")
async def progress(case_id: int, run_id: int, request: Request, user: User,
                   after_id: int = Query(0, ge=0)):
  database = request.app.state.db
  async with database.sessions() as db:
    await require_run(db, database.t, user["id"], case_id, run_id)

  async def events():
    cursor = after_id
    while not await request.is_disconnected():
      async with database.sessions() as db:
        active = await db.scalar(select(database.t.users.c.id).where(database.t.users.c.id == user["id"],
          database.t.users.c.status == "active", database.t.users.c.deleted_at.is_(None)))
        if not active:
          yield sse("error", {"code": "access_revoked"})
          return
        try:
          run = await require_run(db, database.t, user["id"], case_id, run_id)
        except FastAPIHTTPException:
          yield sse("error", {"code": "access_revoked"})
          return
        rows = (await db.execute(select(database.t.case_assessment_steps).where(
          database.t.case_assessment_steps.c.run_id == run_id, database.t.case_assessment_steps.c.kind == "progress",
          database.t.case_assessment_steps.c.id > cursor).order_by(database.t.case_assessment_steps.c.id).limit(100))).mappings().all()
      for row in rows:
        cursor = row["id"]
        yield sse("progress", {"id": cursor, **row["result"]})
      if len(rows) < 100 and (run["status"] in TERMINAL or run["status"] == "awaiting_input"):
        yield sse("done", {"id": run_id, "status": run["status"], "questions": run["questions"]})
        return
      yield b": keepalive\n\n"
      await asyncio.sleep(1)

  return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache",
    "X-Accel-Buffering": "no"})
