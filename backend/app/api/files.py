import uuid
from datetime import UTC, datetime
from pathlib import Path

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Request
from sqlalchemy import insert, select, update

from app.access import DB, User, require_case
from app.errors import fail
from app.schemas import UploadCreate

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
  expected = {"application/pdf": ".pdf", "text/plain": ".txt",
              "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx"}
  if Path(payload.filename).suffix.lower() != expected[payload.mime_type]:
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
