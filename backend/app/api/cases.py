from fastapi import APIRouter, Query, Request
from sqlalchemy import select

from app.access import DB, User, case_scope, require_case
from app.schemas import Retrieval
from app.services.rag import retrieve

router = APIRouter()


@router.get("/assistant/recommendations")
async def recommendations(user: User):
  return ["请帮我写一份关于民事诉讼的起诉书", "关于民事诉讼的答辩状",
          "别人欠我钱逾期未还怎么办", "怎么样快速收集案件证据"]


@router.get("/cases")
async def cases(request: Request, db: DB, user: User, keyword: str = Query("", max_length=200),
                limit: int = Query(100, ge=1, le=100), before_id: int | None = None):
  t = request.app.state.db.t
  query = select(t.cases).where(case_scope(t, user["id"]), t.cases.c.title.icontains(keyword, autoescape=True))
  if before_id:
    query = query.where(t.cases.c.id < before_id)
  rows = (await db.execute(query.order_by(t.cases.c.id.desc()).limit(limit))).mappings().all()
  # Matches existing frontend CaseSummary[] contract. Cursor is the final returned id.
  return [dict(row) for row in rows]


@router.get("/cases/{case_id}")
async def case(case_id: int, request: Request, db: DB, user: User):
  return await require_case(db, request.app.state.db.t, user["id"], case_id)


@router.get("/cases/{case_id}/evidence-requirements")
async def requirements(case_id: int, request: Request, db: DB, user: User, keyword: str = Query("", max_length=200)):
  t = request.app.state.db.t
  await require_case(db, t, user["id"], case_id)
  rows = (await db.execute(select(t.evidence_requirements).where(t.evidence_requirements.c.case_id == case_id,
    t.evidence_requirements.c.title.icontains(keyword, autoescape=True))
    .order_by(t.evidence_requirements.c.sort_order, t.evidence_requirements.c.id))).mappings().all()
  return [dict(row) | {"collection": "\n".join(filter(None, [row["collection_channel"], row["collection_method"], row["precautions"]]))} for row in rows]


@router.get("/cases/{case_id}/materials")
async def materials(case_id: int, request: Request, db: DB, user: User,
                    requirement_id: int | None = None, category: str | None = None,
                    limit: int = Query(100, ge=1, le=100), before_id: int | None = None):
  t = request.app.state.db.t
  await require_case(db, t, user["id"], case_id)
  query = select(t.evidence_items).where(t.evidence_items.c.case_id == case_id)
  if requirement_id is not None:
    query = query.where(t.evidence_items.c.requirement_id == requirement_id)
  if category:
    query = query.where(t.evidence_items.c.category == category)
  if before_id:
    query = query.where(t.evidence_items.c.id < before_id)
  rows = (await db.execute(query.order_by(t.evidence_items.c.id.desc()).limit(limit))).mappings().all()
  return [dict(row) for row in rows]


@router.get("/cases/{case_id}/materials/{material_id}")
async def material(case_id: int, material_id: int, request: Request, db: DB, user: User):
  from app.errors import fail
  t = request.app.state.db.t
  await require_case(db, t, user["id"], case_id)
  row = (await db.execute(select(t.evidence_items).where(t.evidence_items.c.id == material_id,
    t.evidence_items.c.case_id == case_id))).mappings().first()
  if not row:
    fail(404, "material_not_found", "材料不存在")
  files = (await db.execute(select(t.files.c.id, t.files.c.original_name, t.files.c.mime_type)
    .join(t.evidence_item_files, t.evidence_item_files.c.file_id == t.files.c.id)
    .where(t.evidence_item_files.c.evidence_item_id == material_id, t.files.c.status == "available")
    .order_by(t.evidence_item_files.c.sort_order))).mappings().all()
  return dict(row) | {"files": [dict(f) for f in files]}


@router.get("/cases/{case_id}/documents")
async def documents(case_id: int, request: Request, db: DB, user: User,
                    keyword: str = Query("", max_length=200), category: str | None = None,
                    limit: int = Query(100, ge=1, le=100), before_id: int | None = None):
  t = request.app.state.db.t
  await require_case(db, t, user["id"], case_id)
  query = select(t.case_documents, t.files.c.original_name, t.files.c.mime_type).join(
    t.files, t.files.c.id == t.case_documents.c.file_id).where(t.case_documents.c.case_id == case_id,
    t.files.c.status == "available", t.case_documents.c.title.icontains(keyword, autoescape=True))
  if category:
    query = query.where(t.case_documents.c.category == category)
  if before_id:
    query = query.where(t.case_documents.c.id < before_id)
  rows = (await db.execute(query.order_by(t.case_documents.c.id.desc()).limit(limit))).mappings().all()
  return [dict(row) for row in rows]


@router.get("/cases/{case_id}/analyses")
async def analyses(case_id: int, request: Request, db: DB, user: User):
  t = request.app.state.db.t
  await require_case(db, t, user["id"], case_id)
  rows = (await db.execute(select(t.case_analyses).where(t.case_analyses.c.case_id == case_id)
    .order_by(t.case_analyses.c.created_at.desc()).limit(100))).mappings().all()
  return [dict(row) for row in rows]


@router.post("/cases/{case_id}/retrieval")
async def retrieval(case_id: int, payload: Retrieval, request: Request, db: DB, user: User):
  t = request.app.state.db.t
  await require_case(db, t, user["id"], case_id)
  if not request.app.state.settings.embedding_api_key.get_secret_value():
    from app.errors import fail
    fail(503, "embedding_not_configured", "向量化服务尚未配置")
  sources = await retrieve(db, t, request.app.state.ai, request.app.state.settings,
                           user["id"], case_id, payload.query)
  return {"sources": sources, "strategy": "pgvector_cosine+pg_trgm_rrf_v1"}
