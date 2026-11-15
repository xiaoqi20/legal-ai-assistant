from datetime import UTC, datetime

from fastapi import APIRouter, Query, Request
from sqlalchemy import insert, select, update

from app.access import DB, User, case_scope, require_case
from app.errors import fail
from app.schemas import CaseCreate, Retrieval
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
  t = request.app.state.db.t
  row = await require_case(db, t, user["id"], case_id)
  parties = (await db.execute(select(t.case_parties).where(t.case_parties.c.case_id == case_id)
    .order_by(t.case_parties.c.side, t.case_parties.c.sort_order, t.case_parties.c.id))).mappings().all()
  party_rows = [dict(party) for party in parties]
  return row | {
    "parties": party_rows,
    "our_parties": [party["name"] for party in party_rows if party["side"] == "our"],
    "opponent_parties": [party["name"] for party in party_rows if party["side"] == "opponent"],
  }


@router.post("/cases", status_code=201)
async def create_case(payload: CaseCreate, request: Request, db: DB, user: User):
  t = request.app.state.db.t
  row = (await db.execute(insert(t.cases).values(
    owner_user_id=user["id"],
    title=payload.title,
    case_type=payload.case_type,
    procedure=payload.procedure,
    summary=payload.summary,
    claim=payload.claim,
    handling_identity=payload.handling_identity,
    party_role_label=payload.party_role_label,
  ).returning(t.cases))).mappings().one()

  party_rows = []
  for side, names in (("our", payload.our_parties), ("opponent", payload.opponent_parties)):
    party_rows.extend({
      "case_id": row["id"],
      "party_role": _party_role(payload.party_role_label, side),
      "party_type": "person",
      "name": name,
      "side": side,
      "sort_order": order,
    } for order, name in enumerate(names))
  if party_rows:
    await db.execute(insert(t.case_parties), party_rows)

  client = request.client
  await db.execute(insert(t.audit_logs).values(
    user_id=user["id"], action="case.created", resource_type="case", resource_id=row["id"],
    ip=client.host if client else None,
    user_agent=request.headers.get("user-agent"),
    metadata={"case_type": payload.case_type, "procedure": payload.procedure},
  ))
  await db.commit()
  return dict(row) | {
    "parties": party_rows,
    "our_parties": payload.our_parties,
    "opponent_parties": payload.opponent_parties,
  }


def _party_role(role_label: str | None, side: str) -> str:
  """Keep legal party roles where the intake form gives an unambiguous role."""
  role = (role_label or "").strip()
  pairs = {
    "原告": ("plaintiff", "defendant"),
    "被告": ("defendant", "plaintiff"),
    "申请人": ("applicant", "respondent"),
    "被申请人": ("respondent", "applicant"),
    "第三人": ("third_party", "other"),
    "行政相对人/原告": ("plaintiff", "other"),
    "利害关系人": ("third_party", "other"),
    "被害人/报案人": ("applicant", "respondent"),
    "犯罪嫌疑人/被告人": ("respondent", "applicant"),
  }
  roles = pairs.get(role)
  if not roles:
    return "other"
  return roles[0] if side == "our" else roles[1]


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
  items = [dict(row) for row in rows]
  if not items:
    return items
  file_query = (
    select(
      t.evidence_item_files.c.evidence_item_id,
      t.files.c.id,
      t.files.c.original_name,
      t.files.c.mime_type,
    ).join(t.files, t.files.c.id == t.evidence_item_files.c.file_id)
    .where(t.evidence_item_files.c.evidence_item_id.in_([row["id"] for row in items]),
           t.files.c.status == "available")
    .order_by(t.evidence_item_files.c.evidence_item_id, t.evidence_item_files.c.sort_order)
  )
  files = (await db.execute(file_query)).mappings().all()
  files_by_item: dict[int, list[dict]] = {}
  for file in files:
    files_by_item.setdefault(file["evidence_item_id"], []).append({
      "id": file["id"], "original_name": file["original_name"], "mime_type": file["mime_type"]
    })
  return [row | {"files": files_by_item.get(row["id"], [])} for row in items]


@router.get("/cases/{case_id}/materials/{material_id}")
async def material(case_id: int, material_id: int, request: Request, db: DB, user: User):
  from app.errors import fail
  from app.services.materials import permissions
  t = request.app.state.db.t
  case_row = await require_case(db, t, user["id"], case_id)
  row = (await db.execute(select(t.evidence_items).where(t.evidence_items.c.id == material_id,
    t.evidence_items.c.case_id == case_id))).mappings().first()
  if not row:
    fail(404, "material_not_found", "材料不存在")
  files = (await db.execute(select(t.files.c.id, t.files.c.original_name, t.files.c.mime_type)
    .join(t.evidence_item_files, t.evidence_item_files.c.file_id == t.files.c.id)
    .where(t.evidence_item_files.c.evidence_item_id == material_id, t.files.c.status == "available")
    .order_by(t.evidence_item_files.c.sort_order))).mappings().all()
  return dict(row) | {"files": [dict(f) for f in files],
    "permissions": await permissions(db, t, user["id"], case_row, row)}


@router.get("/cases/{case_id}/documents")
async def documents(case_id: int, request: Request, db: DB, user: User,
                    keyword: str = Query("", max_length=200), category: str | None = None,
                    limit: int = Query(100, ge=1, le=100), before_id: int | None = None):
  t = request.app.state.db.t
  await require_case(db, t, user["id"], case_id)
  query = select(t.case_documents, t.files.c.original_name, t.files.c.mime_type,
    t.files.c.metadata["parse_status"].as_string().label("parse_status")).join(
    t.files, t.files.c.id == t.case_documents.c.file_id).where(t.case_documents.c.case_id == case_id,
    t.files.c.status == "available", t.case_documents.c.title.icontains(keyword, autoescape=True))
  if category:
    query = query.where(t.case_documents.c.category == category)
  if before_id:
    query = query.where(t.case_documents.c.id < before_id)
  rows = (await db.execute(query.order_by(t.case_documents.c.id.desc()).limit(limit))).mappings().all()
  return [dict(row) for row in rows]


@router.delete("/cases/{case_id}/documents/{document_id}", status_code=204)
async def delete_document(case_id: int, document_id: int, request: Request, db: DB, user: User):
  """Soft-delete a case document file so historical citations and audit logs remain intact."""
  t = request.app.state.db.t
  case_row = await require_case(db, t, user["id"], case_id)
  doc = (await db.execute(
    select(
      t.case_documents.c.id,
      t.case_documents.c.file_id,
      t.case_documents.c.uploaded_by.label("doc_uploaded_by"),
      t.files.c.uploaded_by.label("file_uploaded_by"),
    )
    .select_from(t.case_documents.join(t.files, t.files.c.id == t.case_documents.c.file_id))
    .where(
      t.case_documents.c.id == document_id,
      t.case_documents.c.case_id == case_id,
      t.files.c.status != "deleted",
    )
    .with_for_update()
  )).mappings().first()
  if not doc:
    fail(404, "document_not_found", "文档不存在或已删除")
  uploader = doc["file_uploaded_by"] or doc["doc_uploaded_by"]
  if case_row["owner_user_id"] != user["id"] and uploader != user["id"]:
    fail(403, "document_delete_forbidden", "只有上传人或案件负责人可以删除文档")
  now = datetime.now(UTC)
  await db.execute(
    update(t.files)
    .where(t.files.c.id == doc["file_id"])
    .values(status="deleted", updated_at=now)
  )
  await db.execute(
    update(t.async_jobs)
    .where(
      t.async_jobs.c.resource_type == "file",
      t.async_jobs.c.resource_id == doc["file_id"],
      t.async_jobs.c.status.in_(["queued", "running"]),
    )
    .values(status="cancelled", lease_token=None, lease_expires_at=None, finished_at=now)
  )
  from app.services.materials import refresh_evidence_status
  await refresh_evidence_status(db, t, case_id)
  await db.execute(insert(t.audit_logs).values(
    user_id=user["id"],
    action="file.deleted",
    resource_type="file",
    resource_id=doc["file_id"],
    metadata={"case_id": case_id, "document_id": document_id},
  ))
  await db.commit()


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
  if request.app.state.settings.rerank_enabled and not request.app.state.settings.rerank_api_key.get_secret_value():
    from app.errors import fail
    fail(503, "rerank_not_configured", "重排服务尚未配置")
  request.app.state.ai.check_rerank()
  sources = await retrieve(db, t, request.app.state.ai, request.app.state.settings,
                           user["id"], case_id, payload.query)
  strategy = ("pgvector_cosine+pg_trgm_rrf+bge_rerank_v1"
              if request.app.state.settings.rerank_enabled else "pgvector_cosine+pg_trgm_rrf_v1")
  return {"sources": sources, "strategy": strategy}
