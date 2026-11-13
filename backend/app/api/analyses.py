from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Request
from sqlalchemy import func, insert, select, update

from app.access import DB, User, require_case
from app.errors import fail
from app.schemas import AnalysisCreate

router = APIRouter()


@router.post("/cases/{case_id}/analyses", status_code=202)
async def create(case_id: int, payload: AnalysisCreate, request: Request, db: DB, user: User):
  request.app.state.ai.check()
  t = request.app.state.db.t
  await db.execute(select(func.pg_advisory_xact_lock(42701113)))
  await require_case(db, t, user["id"], case_id)
  key = f"analysis:{user['id']}:{payload.client_request_id}"
  existing = (await db.execute(select(t.async_jobs).where(t.async_jobs.c.idempotency_key == key))).mappings().first()
  if existing:
    analysis = (await db.execute(select(t.case_analyses).where(t.case_analyses.c.id == existing["resource_id"]))).mappings().one()
    if analysis["case_id"] != case_id or analysis["analysis_type"] != payload.analysis_type:
      fail(409, "idempotency_conflict", "该请求标识已用于其他分析")
    return {"analysis_id": analysis["id"], "job_id": existing["id"], "status": analysis["status"]}
  active = (await db.execute(select(t.case_analyses.c.id).where(t.case_analyses.c.case_id == case_id,
    t.case_analyses.c.analysis_type == payload.analysis_type, t.case_analyses.c.status.in_(["pending", "running"])))).first()
  if active:
    fail(409, "analysis_in_progress", "同类分析正在处理，请查看现有任务")
  recent = (await db.execute(select(func.count()).select_from(t.case_analyses).where(
    t.case_analyses.c.created_by == user["id"], t.case_analyses.c.created_at > datetime.now(UTC) - timedelta(minutes=1)
  ))).scalar_one()
  if recent >= request.app.state.settings.per_user_requests_per_minute:
    fail(429, "rate_limited", "请求过于频繁，请稍后重试")
  analysis_id = (await db.execute(insert(t.case_analyses).values(case_id=case_id,
    analysis_type=payload.analysis_type, created_by=user["id"]).returning(t.case_analyses.c.id))).scalar_one()
  job_id = (await db.execute(insert(t.async_jobs).values(job_type="case_analysis", resource_type="analysis",
    resource_id=analysis_id, idempotency_key=key).returning(t.async_jobs.c.id))).scalar_one()
  await db.execute(update(t.cases).where(t.cases.c.id == case_id).values(analysis_status="analyzing"))
  await db.commit()
  return {"analysis_id": analysis_id, "job_id": job_id, "status": "pending"}


@router.get("/cases/{case_id}/analyses/{analysis_id}")
async def get(case_id: int, analysis_id: int, request: Request, db: DB, user: User):
  t = request.app.state.db.t
  await require_case(db, t, user["id"], case_id)
  row = (await db.execute(select(t.case_analyses).where(t.case_analyses.c.case_id == case_id,
    t.case_analyses.c.id == analysis_id))).mappings().first()
  if not row:
    fail(404, "analysis_not_found", "分析不存在")
  sources = (await db.execute(select(t.analysis_sources, t.files.c.original_name,
    t.doc_chunks.c.content.label("quote"), t.doc_chunks.c.page_no)
    .join(t.files, t.files.c.id == t.analysis_sources.c.file_id)
    .outerjoin(t.doc_chunks, t.doc_chunks.c.id == t.analysis_sources.c.chunk_id)
    .where(t.analysis_sources.c.analysis_id == analysis_id, t.files.c.status == "available"))).mappings().all()
  return dict(row) | {"sources": [dict(source) for source in sources]}


@router.post("/cases/{case_id}/analyses/{analysis_id}/cancel")
async def cancel(case_id: int, analysis_id: int, request: Request, db: DB, user: User):
  from app.services.case_status import refresh_case_status
  t = request.app.state.db.t
  await require_case(db, t, user["id"], case_id)
  await db.execute(select(t.async_jobs.c.id).where(t.async_jobs.c.resource_type == "analysis",
    t.async_jobs.c.resource_id == analysis_id).with_for_update())
  row = (await db.execute(select(t.case_analyses).where(t.case_analyses.c.id == analysis_id,
    t.case_analyses.c.case_id == case_id).with_for_update())).mappings().first()
  if not row:
    fail(404, "analysis_not_found", "分析不存在")
  if row["created_by"] != user["id"]:
    fail(403, "analysis_owner_required", "只有发起人可以取消分析")
  if row["status"] in {"pending", "running"}:
    await db.execute(update(t.async_jobs).where(t.async_jobs.c.resource_type == "analysis",
      t.async_jobs.c.resource_id == analysis_id, t.async_jobs.c.status.in_(["queued", "running"])).values(
        status="cancelled", lease_token=None, lease_expires_at=None, finished_at=datetime.now(UTC)))
    await db.execute(update(t.case_analyses).where(t.case_analyses.c.id == analysis_id).values(
      status="cancelled", completed_at=datetime.now(UTC)))
    await refresh_case_status(db, t, case_id)
  await db.commit()
  return {"analysis_id": analysis_id, "status": "cancelled" if row["status"] in {"pending", "running"} else row["status"]}
