from datetime import UTC, datetime

from fastapi import APIRouter, Request
from sqlalchemy import delete, insert, select, update

from app.access import DB, User, require_case
from app.errors import fail
from app.schemas import MaterialAction, MaterialInput, MaterialUpdate
from app.services.materials import (
  permissions,
  record_event,
  refresh_evidence_status,
  require_material,
  validate_links,
)

router = APIRouter()


async def replace_files(db, t, case_id, material_id, file_ids):
  await db.execute(delete(t.evidence_item_files).where(t.evidence_item_files.c.evidence_item_id == material_id))
  if file_ids:
    await db.execute(insert(t.evidence_item_files), [{"evidence_item_id": material_id,
      "case_id": case_id, "file_id": file_id, "sort_order": index} for index, file_id in enumerate(file_ids)])


@router.get("/cases/{case_id}/material-permissions")
async def capabilities(case_id: int, request: Request, db: DB, user: User):
  t = request.app.state.db.t
  case_row = await require_case(db, t, user["id"], case_id)
  return await permissions(db, t, user["id"], case_row)


@router.post("/cases/{case_id}/materials", status_code=201)
async def create(case_id: int, payload: MaterialInput, request: Request, db: DB, user: User):
  t = request.app.state.db.t
  await require_case(db, t, user["id"], case_id)
  await validate_links(db, t, case_id, payload)
  row = (await db.execute(insert(t.evidence_items).values(
    **payload.model_dump(exclude={"file_ids"}), case_id=case_id,
    uploader_user_id=user["id"], status="draft",
  ).returning(t.evidence_items))).mappings().one()
  await replace_files(db, t, case_id, row["id"], payload.file_ids)
  await record_event(db, t, row, user["id"], "created")
  await refresh_evidence_status(db, t, case_id)
  await db.commit()
  return dict(row)


@router.put("/cases/{case_id}/materials/{material_id}")
async def edit(case_id: int, material_id: int, payload: MaterialUpdate, request: Request, db: DB, user: User):
  t = request.app.state.db.t
  case_row = await require_case(db, t, user["id"], case_id)
  row = await require_material(db, t, case_id, material_id, payload.revision)
  access = await permissions(db, t, user["id"], case_row, row)
  if not access["can_edit"]:
    fail(403, "material_edit_forbidden", "只有提交人或案件负责人可以修改材料")
  if row["status"] not in {"draft", "withdrawn", "lawyer_rejected", "ai_failed", "ai_passed"}:
    fail(409, "material_not_editable", "请先撤回材料再修改")
  await validate_links(db, t, case_id, payload)
  row = (await db.execute(update(t.evidence_items).where(t.evidence_items.c.id == material_id).values(
    **payload.model_dump(exclude={"file_ids", "revision"}), status="draft", revision=row["revision"] + 1,
    status_reason=None, reviewed_by=None, reviewed_at=None, ai_analysis_id=None,
  ).returning(t.evidence_items))).mappings().one()
  await replace_files(db, t, case_id, material_id, payload.file_ids)
  await record_event(db, t, row, user["id"], "edited")
  await refresh_evidence_status(db, t, case_id)
  await db.commit()
  return dict(row)


@router.post("/cases/{case_id}/materials/{material_id}/actions")
async def action(case_id: int, material_id: int, payload: MaterialAction, request: Request, db: DB, user: User):
  t = request.app.state.db.t
  case_row = await require_case(db, t, user["id"], case_id)
  row = await require_material(db, t, case_id, material_id, payload.revision)
  access = await permissions(db, t, user["id"], case_row, row)
  reviewing = payload.action in {"approve", "reject"}
  if not access["can_review" if reviewing else "can_edit"]:
    fail(403, "material_action_forbidden", "没有此操作权限，复核须由案件内其他法务成员完成")
  if reviewing:
    if row["status"] != "lawyer_pending":
      fail(409, "material_not_pending", "材料尚未提交复核或已处理")
    target = "lawyer_approved" if payload.action == "approve" else "lawyer_rejected"
  elif payload.action == "submit":
    if row["status"] not in {"draft", "withdrawn", "lawyer_rejected", "ai_passed", "ai_failed"}:
      fail(409, "material_already_submitted", "当前状态不能提交复核")
    files = (await db.execute(select(t.files).join(t.evidence_item_files,
      t.evidence_item_files.c.file_id == t.files.c.id).where(
      t.evidence_item_files.c.evidence_item_id == material_id).with_for_update())).mappings().all()
    if not files or any(f["status"] != "available" or f["metadata"].get("parse_status") != "succeeded" for f in files):
      fail(409, "material_files_not_ready", "请关联已完成识别、校对和索引的附件后提交")
    target = "lawyer_pending"
  else:
    if row["status"] not in {"lawyer_pending", "lawyer_approved"}:
      fail(409, "material_cannot_withdraw", "当前状态不能撤回")
    target = "withdrawn"
  values = {"status": target, "revision": row["revision"] + 1,
    "status_reason": payload.comment or None,
    "reviewed_by": user["id"] if reviewing else None,
    "reviewed_at": datetime.now(UTC) if reviewing else None}
  row = (await db.execute(update(t.evidence_items).where(t.evidence_items.c.id == material_id)
    .values(**values).returning(t.evidence_items))).mappings().one()
  await record_event(db, t, row, user["id"], payload.action, payload.comment)
  await refresh_evidence_status(db, t, case_id)
  await db.commit()
  return dict(row)


@router.get("/cases/{case_id}/materials/{material_id}/events")
async def history(case_id: int, material_id: int, request: Request, db: DB, user: User):
  t = request.app.state.db.t
  await require_case(db, t, user["id"], case_id)
  await require_material(db, t, case_id, material_id)
  rows = (await db.execute(select(t.material_events).where(t.material_events.c.case_id == case_id,
    t.material_events.c.material_id == material_id).order_by(t.material_events.c.id.desc()).limit(100))).mappings().all()
  return [dict(row) for row in rows]
