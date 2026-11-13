import hashlib
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import and_, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import fail

bearer = HTTPBearer(auto_error=False)


async def session(request: Request):
  async with request.app.state.db.sessions() as db:
    yield db


DB = Annotated[AsyncSession, Depends(session, scope="function")]


async def current_user(
  request: Request, db: DB,
  credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
):
  if not credentials:
    fail(401, "unauthorized", "请先登录")
  t = request.app.state.db.t
  row = (await db.execute(
    select(t.users.c.id, t.user_sessions.c.id.label("session_id"))
    .join(t.user_sessions, t.user_sessions.c.user_id == t.users.c.id)
    .where(
      t.user_sessions.c.refresh_token_hash == hashlib.sha256(credentials.credentials.encode()).hexdigest(),
      t.user_sessions.c.revoked_at.is_(None),
      t.user_sessions.c.expires_at > datetime.now(UTC),
      t.users.c.status == "active", t.users.c.deleted_at.is_(None),
    )
  )).mappings().first()
  if not row:
    fail(401, "unauthorized", "登录已失效，请重新登录")
  return dict(row)


User = Annotated[dict, Depends(current_user)]


def case_scope(t, user_id: int):
  membership = exists(select(1).select_from(
    t.organization_members.join(t.organizations, t.organizations.c.id == t.organization_members.c.org_id)
  ).where(
    t.organization_members.c.org_id == t.cases.c.org_id,
    t.organization_members.c.user_id == user_id,
    t.organization_members.c.status == "active", t.organizations.c.status == "active",
  ))
  return and_(
    t.cases.c.deleted_at.is_(None), t.cases.c.status != "deleted",
    or_(t.cases.c.owner_user_id == user_id, membership),
  )


async def require_case(db, t, user_id: int, case_id: int):
  row = (await db.execute(select(t.cases).where(
    t.cases.c.id == case_id, case_scope(t, user_id)
  ))).mappings().first()
  if not row:
    fail(404, "case_not_found", "案件不存在或无权访问")
  return dict(row)


async def require_conversation(db, t, user_id: int, conversation_id: int, lock=False):
  query = select(t.ai_conversations).where(
    t.ai_conversations.c.id == conversation_id,
    t.ai_conversations.c.user_id == user_id,
    t.ai_conversations.c.deleted_at.is_(None), t.ai_conversations.c.status == "active",
  )
  if lock:
    query = query.with_for_update()
  row = (await db.execute(query)).mappings().first()
  if not row:
    fail(404, "conversation_not_found", "对话不存在或无权访问")
  if row["case_id"] is not None:
    await require_case(db, t, user_id, row["case_id"])
  return dict(row)
