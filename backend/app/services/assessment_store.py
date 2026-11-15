"""Case snapshots and a PostgreSQL checkpointer fenced by the durable job lease."""

import hashlib
import json
from datetime import UTC, datetime

from fastapi import HTTPException
from langgraph.checkpoint.base import (
  WRITES_IDX_MAP,
  BaseCheckpointSaver,
  CheckpointTuple,
  writes_sort_key,
)
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.access import require_case


class AssessmentStopped(Exception):
  def __init__(self, code):
    self.code = code
    super().__init__(code)


async def snapshot(db, t, user_id, case_id):
  case = await require_case(db, t, user_id, case_id)
  keys = ("title", "case_type", "procedure", "summary", "claim", "party_role_label", "handling_identity")
  context = {key: case.get(key) for key in keys}
  inputs = {"case": context}
  for name, columns in [
    ("case_parties", ["id", "name", "side", "party_role"]),
    ("files", ["id", "sha256", "status", "metadata", "original_name"]),
    ("evidence_items", ["id", "revision", "status", "title", "purpose"]),
    ("evidence_item_files", ["evidence_item_id", "file_id"]),
  ]:
    table = getattr(t, name)
    inputs[name] = [dict(row) for row in (await db.execute(select(
      *(table.c[key] for key in columns)).where(table.c.case_id == case_id)
      .order_by(*(table.c[key] for key in (columns if name == "evidence_item_files" else columns[:1]))))).mappings()]
  context = {**context, "parties": inputs["case_parties"], "materials": [
    {**item, "purpose": (item["purpose"] or "")[:200]} for item in inputs["evidence_items"][:50]
  ], "material_count": len(inputs["evidence_items"])}
  inputs["chunks"] = [list(row) for row in (await db.execute(select(
    t.doc_chunks.c.id, t.doc_chunks.c.file_id, t.doc_chunks.c.embedding_model,
    func.md5(t.doc_chunks.c.content),
  ).where(t.doc_chunks.c.case_id == case_id).order_by(t.doc_chunks.c.id)))]
  inputs["ocr"] = [list(row) for row in (await db.execute(select(
    t.document_ocr_pages.c.id, t.document_ocr_pages.c.review_status,
    func.md5(t.document_ocr_pages.c.corrected_text),
  ).where(t.document_ocr_pages.c.case_id == case_id).order_by(t.document_ocr_pages.c.id)))]
  fingerprint = hashlib.sha256(json.dumps(inputs, sort_keys=True, ensure_ascii=False,
    default=str).encode()).hexdigest()
  return context, fingerprint


async def guard(db, database, job, *, check_inputs=False):
  t = database.t
  owned = await db.scalar(select(t.async_jobs.c.id).where(
    t.async_jobs.c.id == job["id"], t.async_jobs.c.resource_id == job["resource_id"],
    t.async_jobs.c.resource_type == "assessment", t.async_jobs.c.lease_token == job["lease_token"],
    t.async_jobs.c.status == "running", t.async_jobs.c.lease_expires_at > datetime.now(UTC),
  ).with_for_update())
  if owned is None:
    raise AssessmentStopped("lease_lost")
  run = (await db.execute(select(t.case_assessment_runs).where(
    t.case_assessment_runs.c.id == job["resource_id"]).with_for_update())).mappings().one()
  if run["status"] not in {"pending", "running"}:
    raise AssessmentStopped("run_inactive")
  active = await db.scalar(select(t.users.c.id).where(t.users.c.id == run["created_by"],
    t.users.c.status == "active", t.users.c.deleted_at.is_(None)))
  if active is None:
    raise AssessmentStopped("access_revoked")
  try:
    await require_case(db, t, run["created_by"], run["case_id"])
    if check_inputs:
      _, fingerprint = await snapshot(db, t, run["created_by"], run["case_id"])
      if fingerprint != run["input_fingerprint"]:
        raise AssessmentStopped("stale_inputs")
  except HTTPException:
    raise AssessmentStopped("access_revoked") from None
  if run["deadline_at"] and run["deadline_at"] <= datetime.now(UTC):
    raise AssessmentStopped("assessment_timeout")
  return dict(run)


class FencedAssessmentSaver(BaseCheckpointSaver):
  """Full checkpoints avoid blob splitting; every mutation checks the job fencing token."""

  def __init__(self, database, job):
    super().__init__()
    self.database, self.job = database, job

  def config(self, checkpoint_id=None):
    value = {"thread_id": str(self.job["resource_id"]), "checkpoint_ns": ""}
    if checkpoint_id:
      value["checkpoint_id"] = checkpoint_id
    return {"configurable": value}

  def validate(self, config):
    values = config["configurable"]
    if values["thread_id"] != str(self.job["resource_id"]) or values.get("checkpoint_ns", ""):
      raise AssessmentStopped("checkpoint_scope_invalid")

  async def aget_tuple(self, config):
    self.validate(config)
    t = self.database.t
    async with self.database.sessions.begin() as db:
      await guard(db, self.database, self.job)
      query = select(t.case_assessment_checkpoints).where(t.case_assessment_checkpoints.c.run_id == self.job["resource_id"])
      if checkpoint_id := config["configurable"].get("checkpoint_id"):
        query = query.where(t.case_assessment_checkpoints.c.checkpoint_id == checkpoint_id)
      row = (await db.execute(query.order_by(t.case_assessment_checkpoints.c.checkpoint_id.desc()).limit(1))).mappings().first()
      if row is None:
        return None
      writes = (await db.execute(select(t.case_assessment_writes).where(
        t.case_assessment_writes.c.run_id == self.job["resource_id"],
        t.case_assessment_writes.c.checkpoint_id == row["checkpoint_id"],
      ))).mappings().all()
    writes = sorted(writes, key=lambda w: writes_sort_key(w["task_path"], w["task_id"], w["idx"]))
    return CheckpointTuple(
      config=self.config(row["checkpoint_id"]),
      checkpoint=self.serde.loads_typed((row["checkpoint_type"], bytes(row["checkpoint"]))),
      metadata=self.serde.loads_typed((row["metadata_type"], bytes(row["metadata"]))),
      parent_config=self.config(row["parent_id"]) if row["parent_id"] else None,
      pending_writes=[(w["task_id"], w["channel"], self.serde.loads_typed((w["value_type"], bytes(w["value"])))) for w in writes],
    )

  async def aput(self, config, checkpoint, metadata, new_versions):
    self.validate(config)
    cp_type, cp_data = self.serde.dumps_typed(checkpoint)
    meta_type, meta_data = self.serde.dumps_typed(metadata)
    async with self.database.sessions.begin() as db:
      await guard(db, self.database, self.job)
      await db.execute(pg_insert(self.database.t.case_assessment_checkpoints).values(
        run_id=self.job["resource_id"], checkpoint_id=checkpoint["id"],
        parent_id=config["configurable"].get("checkpoint_id"), checkpoint_type=cp_type,
        checkpoint=cp_data, metadata_type=meta_type, metadata=meta_data,
      ).on_conflict_do_nothing())
    return self.config(checkpoint["id"])

  async def aput_writes(self, config, writes, task_id, task_path=""):
    self.validate(config)
    table = self.database.t.case_assessment_writes
    async with self.database.sessions.begin() as db:
      await guard(db, self.database, self.job)
      for index, (channel, value) in enumerate(writes):
        kind, data = self.serde.dumps_typed(value)
        idx = WRITES_IDX_MAP.get(channel, index)
        query = pg_insert(table).values(run_id=self.job["resource_id"],
          checkpoint_id=config["configurable"]["checkpoint_id"], task_id=task_id,
          idx=idx, channel=channel, value_type=kind, value=data, task_path=task_path)
        if idx < 0:
          query = query.on_conflict_do_update(index_elements=[table.c.run_id, table.c.checkpoint_id,
            table.c.task_id, table.c.idx], set_={"value_type": kind, "value": data, "channel": channel})
        else:
          query = query.on_conflict_do_nothing()
        await db.execute(query)

  async def alist(self, config, *, filter=None, before=None, limit=None):
    config = config or self.config()
    self.validate(config)
    if before:
      self.validate(before)
    table = self.database.t.case_assessment_checkpoints
    async with self.database.sessions.begin() as db:
      await guard(db, self.database, self.job)
      query = select(table.c.checkpoint_id).where(table.c.run_id == self.job["resource_id"])
      if before and before["configurable"].get("checkpoint_id"):
        query = query.where(table.c.checkpoint_id < before["configurable"]["checkpoint_id"])
      ids = list((await db.execute(query.order_by(table.c.checkpoint_id.desc()))).scalars())
    count = 0
    for checkpoint_id in ids:
      if limit is not None and count >= limit:
        break
      checkpoint = await self.aget_tuple(self.config(checkpoint_id))
      if checkpoint and all(checkpoint.metadata.get(key) == value for key, value in (filter or {}).items()):
        count += 1
        yield checkpoint

  async def adelete_thread(self, thread_id):
    self.validate({"configurable": {"thread_id": thread_id}})
    async with self.database.sessions.begin() as db:
      await guard(db, self.database, self.job)
      for table in (self.database.t.case_assessment_writes, self.database.t.case_assessment_checkpoints):
        await db.execute(delete(table).where(table.c.run_id == self.job["resource_id"]))
