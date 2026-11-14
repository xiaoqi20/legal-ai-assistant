from fastapi.encoders import jsonable_encoder
from sqlalchemy import insert, select, update

from app.errors import fail


async def permissions(db, t, user_id, case_row, material=None):
  legal = (await db.execute(select(t.user_profiles.c.role_type).where(
    t.user_profiles.c.user_id == user_id))).scalar_one_or_none() == "legal"
  return {
    "can_edit": material is None or user_id in {case_row["owner_user_id"], material["uploader_user_id"]},
    # Access to the case is checked before this helper; a public profile alone grants no case access.
    "can_review": legal and (material is None or material["uploader_user_id"] != user_id),
  }


async def require_material(db, t, case_id, material_id, revision=None):
  row = (await db.execute(select(t.evidence_items).where(
    t.evidence_items.c.id == material_id, t.evidence_items.c.case_id == case_id,
  ).with_for_update())).mappings().first()
  if not row:
    fail(404, "material_not_found", "材料不存在")
  if revision is not None and revision != row["revision"]:
    fail(409, "material_revision_conflict", "材料已更新，请刷新后重试")
  return dict(row)


async def validate_links(db, t, case_id, payload):
  if payload.requirement_id:
    found = await db.scalar(select(t.evidence_requirements.c.id).where(
      t.evidence_requirements.c.id == payload.requirement_id,
      t.evidence_requirements.c.case_id == case_id))
    if not found:
      fail(422, "invalid_requirement", "证据目录不属于当前案件")
  if payload.file_ids:
    rows = (await db.execute(select(t.files).where(t.files.c.id.in_(payload.file_ids),
      t.files.c.case_id == case_id, t.files.c.status == "available").with_for_update())).mappings().all()
    if len(rows) != len(payload.file_ids):
      fail(422, "invalid_material_files", "附件须为当前案件已上传且可用的文档")


async def record_event(db, t, row, actor_id, action, comment=""):
  files = list((await db.execute(select(t.evidence_item_files.c.file_id).where(
    t.evidence_item_files.c.evidence_item_id == row["id"]).order_by(t.evidence_item_files.c.sort_order))).scalars())
  await db.execute(insert(t.material_events).values(case_id=row["case_id"], material_id=row["id"],
    actor_id=actor_id, action=action, revision=row["revision"], comment=comment,
    snapshot=jsonable_encoder(dict(row) | {"file_ids": files})))
  await db.execute(insert(t.audit_logs).values(user_id=actor_id, action=f"material.{action}",
    resource_type="evidence_item", resource_id=row["id"],
    metadata={"case_id": row["case_id"], "revision": row["revision"]}))


async def refresh_evidence_status(db, t, case_id):
  materials = (await db.execute(select(t.evidence_items).where(
    t.evidence_items.c.case_id == case_id, t.evidence_items.c.status != "withdrawn"))).mappings().all()
  uploaded = await db.scalar(select(t.case_documents.c.id).join(t.files,
    t.files.c.id == t.case_documents.c.file_id).where(t.case_documents.c.case_id == case_id,
    t.files.c.status == "available").limit(1))
  requirements = list((await db.execute(select(t.evidence_requirements.c.id).where(
    t.evidence_requirements.c.case_id == case_id, t.evidence_requirements.c.status != "waived"))).scalars())
  files = (await db.execute(select(t.evidence_item_files.c.evidence_item_id, t.files.c.status,
    t.files.c.metadata).join(t.files, t.files.c.id == t.evidence_item_files.c.file_id)
    .where(t.evidence_item_files.c.case_id == case_id))).mappings().all()
  readiness = {}
  for file in files:
    ready = file["status"] == "available" and file["metadata"].get("parse_status") == "succeeded"
    readiness[file["evidence_item_id"]] = readiness.get(file["evidence_item_id"], True) and ready
  approved = [m for m in materials if m["status"] == "lawyer_approved" and readiness.get(m["id"], False)]
  complete = bool(materials) and len(approved) == len(materials) and set(requirements) <= {m["requirement_id"] for m in approved}
  status = "completed" if complete else "partial" if materials or uploaded else "not_uploaded"
  await db.execute(update(t.cases).where(t.cases.c.id == case_id).values(evidence_upload_status=status))
  from app.services.case_status import invalidate_win_rate
  await invalidate_win_rate(db, t, case_id)
