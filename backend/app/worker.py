"""PostgreSQL-backed durable document worker. Run separately from the API."""
import asyncio
import hashlib
import logging
import signal
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.access import require_case
from app.config import get_settings
from app.db import Database
from app.services.ai import AI
from app.services.case_status import refresh_case_status
from app.services.documents import parse_isolated, split
from app.services.storage import Storage

logger = logging.getLogger(__name__)


async def claim(database, settings):
  t = database.t
  now = datetime.now(UTC)
  async with database.sessions.begin() as db:
    await db.execute(select(func.pg_advisory_xact_lock(42701113)))
    expired = (await db.execute(select(t.async_jobs).where(
      t.async_jobs.c.status == "running", t.async_jobs.c.lease_expires_at < now,
    ).with_for_update(skip_locked=True))).mappings().all()
    for row in expired:
      await db.execute(update(t.async_jobs).where(t.async_jobs.c.id == row["id"]).values(
        status="dead" if row["attempts"] >= row["max_attempts"] else "queued",
        scheduled_at=now, lease_token=None, lease_expires_at=None, last_error="worker_lease_expired",
      ))
      if row["resource_type"] == "analysis":
        await db.execute(update(t.case_analyses).where(t.case_analyses.c.id == row["resource_id"]).values(
          status="failed" if row["attempts"] >= row["max_attempts"] else "pending", error_message="worker_lease_expired",
        ))
        case_id = (await db.execute(select(t.case_analyses.c.case_id).where(t.case_analyses.c.id == row["resource_id"]))).scalar_one()
        await refresh_case_status(db, t, case_id)
      if row["resource_type"] == "file" and row["attempts"] >= row["max_attempts"]:
        file = (await db.execute(select(t.files).where(t.files.c.id == row["resource_id"]))).mappings().first()
        if file and file["status"] not in {"deleted", "quarantined"}:
          await db.execute(update(t.files).where(t.files.c.id == file["id"]).values(
            status="failed", metadata={**file["metadata"], "parse_status": "dead", "error_code": "worker_lease_expired"},
          ))
    from app.services.chat import expire_streams
    await expire_streams(db, t)
    running_jobs = (await db.execute(select(func.count()).select_from(t.async_jobs).where(t.async_jobs.c.status == "running"))).scalar_one()
    streams = (await db.execute(select(func.count()).select_from(t.ai_messages).where(t.ai_messages.c.status == "streaming"))).scalar_one()
    if running_jobs + streams >= settings.max_concurrent_streams:
      return None
    job = (await db.execute(select(t.async_jobs).where(
      t.async_jobs.c.status == "queued", t.async_jobs.c.scheduled_at <= now,
    ).order_by(t.async_jobs.c.scheduled_at, t.async_jobs.c.id).with_for_update(skip_locked=True).limit(1))).mappings().first()
    if not job:
      return None
    token = uuid.uuid4()
    await db.execute(update(t.async_jobs).where(t.async_jobs.c.id == job["id"]).values(
      status="running", attempts=job["attempts"] + 1, lease_token=token,
      lease_expires_at=now + timedelta(seconds=settings.job_lease_seconds), started_at=now,
    ))
    return dict(job) | {"lease_token": token, "attempts": job["attempts"] + 1}


async def process_job(database, ai, storage, settings, job):
  t = database.t
  if job["job_type"] == "case_analysis":
    from app.services.analysis import process_analysis
    return await process_analysis(database, ai, settings, job)
  if job["job_type"] != "document_parse":
    raise ValueError("unsupported_job_type")
  user_id = job["payload"]["requested_by"]
  async with database.sessions() as db:
    row = (await db.execute(select(t.files).where(t.files.c.id == job["resource_id"]))).mappings().one()
    await require_case(db, t, user_id, row["case_id"])
    active = (await db.execute(select(t.users.c.status).where(t.users.c.id == user_id))).scalar_one()
    if active != "active" or row["status"] in {"deleted", "quarantined"}:
      raise ValueError("resource_unavailable")
    row = dict(row)
  data = await storage.read(row)
  if hashlib.sha256(data).hexdigest() != row["sha256"]:
    raise ValueError("file_hash_mismatch")
  pages = await parse_isolated(data, row["mime_type"], settings.max_document_chars)
  chunks = split(pages, settings.chunk_chars, settings.chunk_overlap, settings.max_chunks)
  for start in range(0, len(chunks), 10):
    batch = chunks[start:start + 10]
    vectors = await ai.embed([chunk["content"] for chunk in batch])
    for chunk, vector in zip(batch, vectors, strict=True):
      chunk.update(embedding=vector, embedding_model=settings.embedding_model,
                   file_id=row["id"], case_id=row["case_id"])
  async with database.sessions.begin() as db:
    # Fencing: an expired/reclaimed worker can never commit stale chunks.
    owned = (await db.execute(select(t.async_jobs.c.id).where(
      t.async_jobs.c.id == job["id"], t.async_jobs.c.lease_token == job["lease_token"],
      t.async_jobs.c.status == "running", t.async_jobs.c.lease_expires_at > datetime.now(UTC),
    ).with_for_update())).scalar_one_or_none()
    if owned is None:
      return
    await require_case(db, t, user_id, row["case_id"])
    current = (await db.execute(select(t.files).where(t.files.c.id == row["id"]).with_for_update())).mappings().one()
    if current["status"] in {"deleted", "quarantined"}:
      raise ValueError("resource_unavailable")
    # Immutable chunks preserve citations; upsert only prevents a replayed job from duplicating them.
    await db.execute(pg_insert(t.doc_chunks).values(chunks).on_conflict_do_nothing(index_elements=["file_id", "chunk_index"]))
    await db.execute(pg_insert(t.case_documents).values(
      case_id=row["case_id"], file_id=row["id"], title=row["original_name"],
      uploaded_by=user_id, category=row["metadata"].get("category", "other"),
    ).on_conflict_do_nothing(index_elements=["case_id", "file_id"]))
    await db.execute(update(t.files).where(t.files.c.id == row["id"]).values(
      status="available", metadata={**current["metadata"], "parse_status": "succeeded", "chunk_count": len(chunks)},
    ))
    await db.execute(update(t.cases).where(t.cases.c.id == row["case_id"]).values(evidence_upload_status="partial"))
    await db.execute(update(t.async_jobs).where(t.async_jobs.c.id == job["id"]).values(
      status="succeeded", finished_at=datetime.now(UTC), lease_token=None, lease_expires_at=None, last_error=None,
    ))
    await db.execute(insert(t.audit_logs).values(user_id=user_id, action="file.indexed", resource_type="file", resource_id=row["id"]))


async def run_once(database, ai, storage, settings):
  job = await claim(database, settings)
  if job is None:
    return False
  try:
    async with asyncio.timeout(settings.job_timeout_seconds):
      processing = asyncio.create_task(process_job(database, ai, storage, settings, job))
      try:
        while not processing.done():
          await asyncio.wait({processing}, timeout=1)
          async with database.sessions() as db:
            current = (await db.execute(select(database.t.async_jobs.c.status).where(database.t.async_jobs.c.id == job["id"])) ).scalar_one()
          if current == "cancelled":
            processing.cancel()
            break
        try:
          await processing
        except asyncio.CancelledError:
          if asyncio.current_task().cancelling():
            raise
      finally:
        if not processing.done():
          processing.cancel()
          import contextlib
          with contextlib.suppress(asyncio.CancelledError):
            await processing
  except Exception as error:
    # Never persist upstream error strings, URLs, keys, or document text.
    code = str(error) if isinstance(error, ValueError) else type(error).__name__
    code = code if code.isidentifier() else "document_processing_failed"
    t = database.t
    dead = job["attempts"] >= job["max_attempts"] or code in {
      "file_hash_mismatch", "invalid_pdf", "encrypted_pdf_not_supported",
      "no_extractable_text_ocr_required", "document_too_large", "too_many_chunks",
      "docx_expansion_limit", "too_many_pages", "resource_unavailable", "no_case_material",
    }
    async with database.sessions.begin() as db:
      owned = (await db.execute(update(t.async_jobs).where(
        t.async_jobs.c.id == job["id"], t.async_jobs.c.lease_token == job["lease_token"],
      ).values(status="dead" if dead else "queued", last_error=code,
        scheduled_at=datetime.now(UTC) + timedelta(seconds=2 ** job["attempts"] * 5),
        lease_token=None, lease_expires_at=None,
      ).returning(t.async_jobs.c.id))).scalar_one_or_none()
      if owned:
        row = (await db.execute(select(t.files).where(t.files.c.id == job["resource_id"]).with_for_update())).mappings().first() if job["resource_type"] == "file" else None
        if job["resource_type"] == "file" and row and row["status"] != "deleted":
          status = "quarantined" if code == "file_hash_mismatch" else "failed" if dead else "uploading"
          await db.execute(update(t.files).where(t.files.c.id == row["id"]).values(
            status=status, metadata={**row["metadata"], "parse_status": "dead" if dead else "retrying", "error_code": code},
          ))
        if job["resource_type"] == "analysis":
          await db.execute(update(t.case_analyses).where(t.case_analyses.c.id == job["resource_id"]).values(
            status="failed" if dead else "pending", error_message=code,
          ))
          case_id = (await db.execute(select(t.case_analyses.c.case_id).where(t.case_analyses.c.id == job["resource_id"]))).scalar_one()
          await refresh_case_status(db, t, case_id)
    logger.warning("document_job_failed job_id=%s code=%s", job["id"], code)
  return True


async def main():
  settings = get_settings()
  database, ai, storage = Database(settings), AI(settings), Storage(settings)
  await database.connect()
  stopped = asyncio.Event()
  loop = asyncio.get_running_loop()
  for sig in (signal.SIGINT, signal.SIGTERM):
    loop.add_signal_handler(sig, stopped.set)
  try:
    while not stopped.is_set():
      if not await run_once(database, ai, storage, settings):
        try:
          await asyncio.wait_for(stopped.wait(), timeout=2)
        except TimeoutError:
          pass
  finally:
    await ai.close()
    await database.close()


if __name__ == "__main__":
  logging.basicConfig(level=logging.INFO)
  asyncio.run(main())
