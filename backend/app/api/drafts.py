import asyncio
from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import Response
from sqlalchemy import insert, select

from app.access import DB, User, require_case
from app.errors import fail
from app.schemas import DraftSave
from app.services.drafts import export_docx

router = APIRouter()
TYPES = {"complaint_draft", "evidence_catalog"}


async def require_draft(db, t, case_id, draft_id, lock=False):
  query = select(t.case_analyses).where(t.case_analyses.c.id == draft_id,
    t.case_analyses.c.case_id == case_id, t.case_analyses.c.analysis_type.in_(TYPES))
  row = (await db.execute(query.with_for_update() if lock else query)).mappings().first()
  if not row:
    fail(404, "draft_not_found", "文书草稿不存在")
  return dict(row)


@router.get("/cases/{case_id}/drafts")
async def listing(case_id: int, request: Request, db: DB, user: User):
  t = request.app.state.db.t
  await require_case(db, t, user["id"], case_id)
  rows = (await db.execute(select(t.case_analyses).where(t.case_analyses.c.case_id == case_id,
    t.case_analyses.c.analysis_type.in_(TYPES)).order_by(t.case_analyses.c.id.desc()).limit(100))).mappings().all()
  return [dict(row) for row in rows]


@router.get("/cases/{case_id}/drafts/{draft_id}")
async def detail(case_id: int, draft_id: int, request: Request, db: DB, user: User):
  t = request.app.state.db.t
  await require_case(db, t, user["id"], case_id)
  analysis = await require_draft(db, t, case_id, draft_id)
  revisions = (await db.execute(select(t.document_draft_revisions).where(
    t.document_draft_revisions.c.analysis_id == draft_id).order_by(t.document_draft_revisions.c.revision.desc()))).mappings().all()
  sources = (await db.execute(select(t.analysis_sources, t.files.c.original_name, t.files.c.status.label("file_status"),
    t.doc_chunks.c.page_no).join(t.files, t.files.c.id == t.analysis_sources.c.file_id)
    .outerjoin(t.doc_chunks, t.doc_chunks.c.id == t.analysis_sources.c.chunk_id)
    .where(t.analysis_sources.c.analysis_id == draft_id).order_by(t.analysis_sources.c.id))).mappings().all()
  return {"analysis": analysis, "revisions": [dict(row) for row in revisions], "sources": [dict(row) for row in sources]}


@router.put("/cases/{case_id}/drafts/{draft_id}")
async def save(case_id: int, draft_id: int, payload: DraftSave, request: Request, db: DB, user: User):
  t = request.app.state.db.t
  await require_case(db, t, user["id"], case_id)
  analysis = await require_draft(db, t, case_id, draft_id, lock=True)
  if analysis["status"] != "succeeded":
    fail(409, "draft_not_ready", "草稿尚未生成成功")
  latest = (await db.execute(select(t.document_draft_revisions.c.revision).where(
    t.document_draft_revisions.c.analysis_id == draft_id).order_by(t.document_draft_revisions.c.revision.desc()).limit(1))).scalar_one()
  if latest != payload.expected_revision:
    fail(409, "draft_revision_conflict", "草稿已被更新，请刷新后再编辑")
  row = (await db.execute(insert(t.document_draft_revisions).values(case_id=case_id, analysis_id=draft_id,
    revision=latest + 1, title=payload.title, body=payload.body, created_by=user["id"])
    .returning(t.document_draft_revisions))).mappings().one()
  await db.execute(insert(t.audit_logs).values(user_id=user["id"], action="draft.saved",
    resource_type="analysis", resource_id=draft_id, metadata={"revision": latest + 1}))
  await db.commit()
  return dict(row)


@router.get("/cases/{case_id}/drafts/{draft_id}/export")
async def export(case_id: int, draft_id: int, request: Request, db: DB, user: User, revision: int):
  t = request.app.state.db.t
  await require_case(db, t, user["id"], case_id)
  analysis = await require_draft(db, t, case_id, draft_id)
  row = (await db.execute(select(t.document_draft_revisions).where(
    t.document_draft_revisions.c.analysis_id == draft_id,
    t.document_draft_revisions.c.revision == revision))).mappings().first()
  if not row or analysis["status"] != "succeeded":
    fail(404, "draft_revision_not_found", "草稿版本不存在")
  sources = (await db.execute(select(t.files.c.original_name, t.files.c.status, t.doc_chunks.c.page_no)
    .select_from(t.analysis_sources.join(t.files, t.files.c.id == t.analysis_sources.c.file_id)
      .outerjoin(t.doc_chunks, t.doc_chunks.c.id == t.analysis_sources.c.chunk_id))
    .where(t.analysis_sources.c.analysis_id == draft_id).order_by(t.analysis_sources.c.id))).mappings().all()
  if any(s["status"] != "available" for s in sources):
    fail(409, "draft_source_unavailable", "来源材料已删除或不可用，请重新生成并核验草稿")
  binary = await asyncio.to_thread(export_docx, dict(row), analysis, sources)
  await db.execute(insert(t.audit_logs).values(user_id=user["id"], action="draft.exported",
    resource_type="analysis", resource_id=draft_id, metadata={"revision": revision}))
  await db.commit()
  return Response(binary, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote('文书草稿-v' + str(revision) + '.docx')}",
      "Cache-Control": "no-store"})
