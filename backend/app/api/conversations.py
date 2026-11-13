from datetime import UTC, datetime

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.access import DB, User, require_case, require_conversation
from app.errors import fail
from app.schemas import ConversationCreate, DeleteConversations, Feedback, MessageCreate, Rename
from app.services.chat import events, expire_streams, prepare

router = APIRouter()


@router.post("/conversations", status_code=201)
async def create(payload: ConversationCreate, request: Request, db: DB, user: User):
  t = request.app.state.db.t
  if payload.case_id is not None:
    await require_case(db, t, user["id"], payload.case_id)
  row = (await db.execute(insert(t.ai_conversations).values(
    user_id=user["id"], case_id=payload.case_id, title=payload.title,
    mode="case_qa" if payload.case_id else "assistant",
  ).returning(t.ai_conversations))).mappings().one()
  await db.commit()
  return dict(row)


@router.get("/conversations")
async def history(request: Request, db: DB, user: User,
                  before_id: int | None = None, limit: int = Query(30, ge=1, le=100),
                  keyword: str = Query("", max_length=200)):
  t = request.app.state.db.t
  from sqlalchemy import exists, or_

  from app.access import case_scope
  query = select(t.ai_conversations).where(t.ai_conversations.c.user_id == user["id"],
    t.ai_conversations.c.deleted_at.is_(None), t.ai_conversations.c.status == "active",
    or_(t.ai_conversations.c.case_id.is_(None), exists(select(1).select_from(t.cases).where(
      t.cases.c.id == t.ai_conversations.c.case_id, case_scope(t, user["id"])))),
    t.ai_conversations.c.title.icontains(keyword, autoescape=True))
  if before_id:
    query = query.where(t.ai_conversations.c.id < before_id)
  rows = (await db.execute(query.order_by(t.ai_conversations.c.id.desc()).limit(limit + 1))).mappings().all()
  return {"items": [dict(row) for row in rows[:limit]], "next_cursor": rows[limit - 1]["id"] if len(rows) > limit else None}


@router.patch("/conversations/{conversation_id}")
async def rename(conversation_id: int, payload: Rename, request: Request, db: DB, user: User):
  t = request.app.state.db.t
  await require_conversation(db, t, user["id"], conversation_id, lock=True)
  await db.execute(update(t.ai_conversations).where(t.ai_conversations.c.id == conversation_id).values(title=payload.title))
  await db.commit()
  return {"id": conversation_id, "title": payload.title}


@router.post("/conversations/delete", status_code=204)
async def delete(payload: DeleteConversations, request: Request, db: DB, user: User):
  t = request.app.state.db.t
  ids = sorted(set(payload.ids))
  for conversation_id in ids:
    await require_conversation(db, t, user["id"], conversation_id, lock=True)
  now = datetime.now(UTC)
  await db.execute(update(t.ai_messages).where(t.ai_messages.c.conversation_id.in_(ids),
    t.ai_messages.c.status == "streaming").values(status="cancelled", error_code="conversation_deleted", completed_at=now))
  await db.execute(update(t.ai_conversations).where(t.ai_conversations.c.id.in_(ids)).values(status="deleted", deleted_at=now))
  await db.execute(insert(t.audit_logs), [{"user_id": user["id"], "action": "conversation.soft_deleted",
    "resource_type": "conversation", "resource_id": item_id} for item_id in ids])
  await db.commit()


@router.get("/conversations/{conversation_id}/messages")
async def messages(conversation_id: int, request: Request, db: DB, user: User,
                   before_seq: int | None = None, limit: int = Query(50, ge=1, le=100)):
  t = request.app.state.db.t
  await require_conversation(db, t, user["id"], conversation_id)
  await expire_streams(db, t)
  query = select(t.ai_messages).where(t.ai_messages.c.conversation_id == conversation_id)
  if before_seq:
    query = query.where(t.ai_messages.c.seq < before_seq)
  rows = (await db.execute(query.order_by(t.ai_messages.c.seq.desc()).limit(limit + 1))).mappings().all()
  items = [dict(row) for row in reversed(rows[:limit])]
  if items:
    citations = (await db.execute(select(t.ai_citations).where(
      t.ai_citations.c.message_id.in_([row["id"] for row in items])
    ).order_by(t.ai_citations.c.rank))).mappings().all()
    for item in items:
      item["citations"] = [dict(c) for c in citations if c["message_id"] == item["id"]]
  await db.commit()
  return {"items": items, "next_cursor": rows[limit - 1]["seq"] if len(rows) > limit else None}


@router.post("/conversations/{conversation_id}/messages/stream")
async def stream(conversation_id: int, payload: MessageCreate, request: Request, user: User):
  async with request.app.state.db.sessions() as db:
    conversation = await require_conversation(db, request.app.state.db.t, user["id"], conversation_id)
  request.app.state.ai.check(embeddings=conversation["case_id"] is not None)
  # A separate short session commits messages before headers leave the server.
  prepared = await prepare(request.app.state.db, request.app.state.settings, user["id"], conversation_id, payload)
  return StreamingResponse(events(request, user["id"], payload, prepared), media_type="text/event-stream",
    headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no", "X-Content-Type-Options": "nosniff"})


@router.post("/conversations/{conversation_id}/messages/{message_id}/cancel")
async def cancel(conversation_id: int, message_id: int, request: Request, db: DB, user: User):
  t = request.app.state.db.t
  await require_conversation(db, t, user["id"], conversation_id)
  row = (await db.execute(select(t.ai_messages).where(t.ai_messages.c.id == message_id,
    t.ai_messages.c.conversation_id == conversation_id, t.ai_messages.c.role == "assistant").with_for_update())).mappings().first()
  if not row:
    fail(404, "message_not_found", "消息不存在")
  if row["status"] == "streaming":
    await db.execute(update(t.ai_messages).where(t.ai_messages.c.id == message_id).values(
      status="cancelled", completed_at=datetime.now(UTC), error_code="cancelled"))
  await db.commit()
  return {"message_id": message_id, "status": "cancelled" if row["status"] == "streaming" else row["status"]}


@router.put("/conversations/{conversation_id}/messages/{message_id}/feedback")
async def feedback(conversation_id: int, message_id: int, payload: Feedback, request: Request, db: DB, user: User):
  t = request.app.state.db.t
  await require_conversation(db, t, user["id"], conversation_id)
  row = (await db.execute(select(t.ai_messages.c.id).where(t.ai_messages.c.id == message_id,
    t.ai_messages.c.conversation_id == conversation_id, t.ai_messages.c.role == "assistant"))).scalar_one_or_none()
  if not row:
    fail(404, "message_not_found", "消息不存在")
  query = pg_insert(t.ai_feedback).values(message_id=message_id, user_id=user["id"], **payload.model_dump())
  await db.execute(query.on_conflict_do_update(index_elements=["message_id", "user_id"], set_=payload.model_dump()))
  await db.commit()
  return {"message_id": message_id, **payload.model_dump()}
