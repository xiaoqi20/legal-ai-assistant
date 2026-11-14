import uuid
from datetime import UTC, datetime
from pathlib import Path

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Request
from sqlalchemy import insert, select, update

from app.access import DB, User, require_case
from app.errors import fail
from app.schemas import OcrPageReview, UploadCreate

router = APIRouter()


async def require_file(db, t, user_id, file_id, lock=False):
  query = select(t.files).where(t.files.c.id == file_id, t.files.c.status != "deleted")
  if lock:
    query = query.with_for_update()
  row = (await db.execute(query)).mappings().first()
  if not row:
    fail(404, "file_not_found", "文件不存在或无权访问")
  if row["case_id"] is not None:
    await require_case(db, t, user_id, row["case_id"])
  elif row["uploaded_by"] != user_id:
    fail(404, "file_not_found", "文件不存在或无权访问")
  return dict(row)


@router.post("/files/uploads", status_code=201)
async def create_upload(payload: UploadCreate, request: Request, db: DB, user: User):
  settings, t = request.app.state.settings, request.app.state.db.t
  await require_case(db, t, user["id"], payload.case_id)
  if payload.size_bytes > settings.max_upload_bytes:
    fail(413, "file_too_large", "文件超过上传大小限制")
  expected = {"application/pdf": {".pdf"}, "text/plain": {".txt"},
              "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {".docx"},
              "image/jpeg": {".jpg", ".jpeg"}, "image/png": {".png"}}
  if Path(payload.filename).suffix.lower() not in expected[payload.mime_type]:
    fail(422, "file_type_mismatch", "文件名后缀与类型不匹配")
  row = (await db.execute(insert(t.files).values(
    case_id=payload.case_id, uploaded_by=user["id"], bucket=settings.s3_bucket,
    object_key=f"cases/{payload.case_id}/{uuid.uuid4().hex}", original_name=payload.filename,
    mime_type=payload.mime_type, size_bytes=payload.size_bytes, sha256=payload.sha256,
    metadata={"category": payload.category},
  ).returning(t.files))).mappings().one()
  try:
    upload = await request.app.state.storage.upload_url(row)
  except (BotoCoreError, ClientError):
    fail(503, "storage_unavailable", "存储服务暂不可用")
  await db.commit()
  return {"file_id": row["id"], "upload": upload, "expires_in": 300}


@router.post("/files/{file_id}/complete")
async def complete_upload(file_id: int, request: Request, db: DB, user: User):
  t = request.app.state.db.t
  row = await require_file(db, t, user["id"], file_id, lock=True)
  if row["uploaded_by"] != user["id"]:
    fail(403, "upload_owner_required", "只有上传人可以确认上传")
  existing = (await db.execute(select(t.async_jobs.c.id).where(
    t.async_jobs.c.idempotency_key == f"parse:{file_id}:v1"
  ))).scalar_one_or_none()
  if existing:
    return {"file_id": file_id, "job_id": existing}
  if row["status"] != "uploading":
    fail(409, "invalid_file_state", "文件不在上传中")
  try:
    head = await request.app.state.storage.head(row)
  except (BotoCoreError, ClientError):
    fail(409, "upload_not_found", "未检测到已完成的上传")
  if (head["ContentLength"] != row["size_bytes"] or head.get("ContentType") != row["mime_type"]
      or head.get("Metadata", {}).get("sha256") != row["sha256"]):
    fail(409, "upload_mismatch", "上传文件与申请信息不一致")
  if not head.get("VersionId") or head["VersionId"] == "null":
    fail(503, "storage_versioning_required", "请先为私有存储桶启用版本控制")
  # Worker re-hashes bytes; a signed metadata value alone is not proof of content integrity.
  metadata = {**row["metadata"], "parse_status": "queued"}
  if head.get("VersionId"):
    metadata["version_id"] = head["VersionId"]
  await db.execute(update(t.files).where(t.files.c.id == file_id).values(metadata=metadata))
  job_id = (await db.execute(insert(t.async_jobs).values(
    job_type="document_parse", resource_type="file", resource_id=file_id,
    payload={"requested_by": user["id"]}, idempotency_key=f"parse:{file_id}:v1",
  ).returning(t.async_jobs.c.id))).scalar_one()
  await db.execute(insert(t.audit_logs).values(user_id=user["id"], action="file.upload_completed", resource_type="file", resource_id=file_id))
  await db.commit()
  return {"file_id": file_id, "job_id": job_id}


@router.get("/files/{file_id}")
async def file_status(file_id: int, request: Request, db: DB, user: User):
  t = request.app.state.db.t
  row = await require_file(db, t, user["id"], file_id)
  jobs = (await db.execute(select(t.async_jobs.c.id, t.async_jobs.c.status,
    t.async_jobs.c.attempts, t.async_jobs.c.last_error).where(t.async_jobs.c.resource_type == "file",
    t.async_jobs.c.resource_id == file_id).order_by(t.async_jobs.c.id.desc()))).mappings().all()
  return {key: row[key] for key in ("id", "case_id", "original_name", "status", "metadata")} | {"jobs": [dict(j) for j in jobs]}


@router.get("/files/{file_id}/ocr")
async def ocr_pages(file_id: int, request: Request, db: DB, user: User):
  t = request.app.state.db.t
  await require_file(db, t, user["id"], file_id)
  pages = (await db.execute(select(t.document_ocr_pages).where(
    t.document_ocr_pages.c.file_id == file_id,
  ).order_by(t.document_ocr_pages.c.page_no))).mappings().all()
  return [dict(page) for page in pages]


@router.put("/files/{file_id}/ocr/{page_no}")
async def review_ocr_page(file_id: int, page_no: int, payload: OcrPageReview,
                          request: Request, db: DB, user: User):
  t = request.app.state.db.t
  await require_file(db, t, user["id"], file_id, lock=True)
  page = (await db.execute(select(t.document_ocr_pages).where(
    t.document_ocr_pages.c.file_id == file_id,
    t.document_ocr_pages.c.page_no == page_no,
  ).with_for_update())).mappings().first()
  if not page:
    fail(404, "ocr_page_not_found", "识别页不存在")
  if page["review_status"] == "approved":
    fail(409, "ocr_page_already_approved", "该页已经确认，不能重复修改")
  corrected = payload.corrected_text.strip()
  if not corrected:
    fail(422, "ocr_text_required", "校对文本不能为空")
  revision = page["revision"] + 1
  await db.execute(insert(t.document_ocr_revisions).values(
    page_id=page["id"], revision=revision, corrected_text=corrected,
    source="human_review", reviewed_by=user["id"],
  ))
  await db.execute(update(t.document_ocr_pages).where(
    t.document_ocr_pages.c.id == page["id"],
  ).values(corrected_text=corrected, review_status="approved", revision=revision,
           reviewed_by=user["id"], reviewed_at=datetime.now(UTC)))
  remaining = (await db.execute(select(t.document_ocr_pages.c.id).where(
    t.document_ocr_pages.c.file_id == file_id,
    t.document_ocr_pages.c.review_status != "approved",
  ))).first()
  queued_job = None
  if not remaining:
    key = f"index:{file_id}:v1"
    queued_job = (await db.execute(select(t.async_jobs.c.id).where(
      t.async_jobs.c.idempotency_key == key,
    ))).scalar_one_or_none()
    if queued_job is None:
      queued_job = (await db.execute(insert(t.async_jobs).values(
        job_type="document_index", resource_type="file", resource_id=file_id,
        payload={"requested_by": user["id"]}, idempotency_key=key,
      ).returning(t.async_jobs.c.id))).scalar_one()
      row = await require_file(db, t, user["id"], file_id, lock=True)
      await db.execute(update(t.files).where(t.files.c.id == file_id).values(
        metadata={**row["metadata"], "parse_status": "index_queued"},
      ))
  await db.execute(insert(t.audit_logs).values(
    user_id=user["id"], action="file.ocr_page_reviewed", resource_type="file", resource_id=file_id,
  ))
  await db.commit()
  return {"file_id": file_id, "page_no": page_no, "revision": revision,
          "review_status": "approved", "index_job_id": queued_job}


@router.get("/files/{file_id}/download")
async def download(file_id: int, request: Request, db: DB, user: User):
  row = await require_file(db, request.app.state.db.t, user["id"], file_id)
  if row["status"] != "available":
    fail(409, "file_not_available", "文件尚未通过完整性校验与解析")
  return {"url": await request.app.state.storage.download_url(row), "expires_in": 120}


@router.post("/files/{file_id}/retry")
async def retry(file_id: int, request: Request, db: DB, user: User):
  t = request.app.state.db.t
  row = await require_file(db, t, user["id"], file_id)
  if row["uploaded_by"] != user["id"]:
    fail(403, "upload_owner_required", "只有上传人可以重试")
  if row["status"] == "quarantined":
    fail(409, "file_quarantined", "文件完整性校验失败，请重新上传")
  changed = await db.execute(update(t.async_jobs).where(
    t.async_jobs.c.resource_type == "file", t.async_jobs.c.resource_id == file_id,
    t.async_jobs.c.status == "dead",
  ).values(status="queued", attempts=0, last_error=None, scheduled_at=datetime.now(UTC)).returning(t.async_jobs.c.id))
  job_id = changed.scalar_one_or_none()
  if job_id is None:
    fail(409, "retry_not_allowed", "任务尚未到达手动重试状态")
  row = await require_file(db, t, user["id"], file_id, lock=True)
  await db.execute(update(t.files).where(t.files.c.id == file_id).values(status="uploading", metadata={**row["metadata"], "parse_status": "queued"}))
  await db.execute(insert(t.audit_logs).values(user_id=user["id"], action="file.retry", resource_type="file", resource_id=file_id))
  await db.commit()
  return {"job_id": job_id}
