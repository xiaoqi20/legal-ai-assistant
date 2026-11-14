from datetime import UTC, datetime

from sqlalchemy import select, update


async def refresh_case_status(db, t, case_id):
  statuses = set((await db.execute(select(t.case_analyses.c.status).where(t.case_analyses.c.case_id == case_id,
    t.case_analyses.c.analysis_type.not_in(["win_rate", "material_review", "complaint_draft", "evidence_catalog"])))).scalars())
  status = "analyzing" if statuses & {"pending", "running"} else "analyzed" if "succeeded" in statuses else "failed" if "failed" in statuses else "not_analyzed"
  await db.execute(update(t.cases).where(t.cases.c.id == case_id).values(analysis_status=status))


async def refresh_win_rate_status(db, t, case_id: int) -> None:
  rows = (await db.execute(
    select(t.case_analyses.c.id, t.case_analyses.c.status, t.case_analyses.c.content)
    .where(t.case_analyses.c.case_id == case_id, t.case_analyses.c.analysis_type == "win_rate")
    .order_by(t.case_analyses.c.id.desc())
  )).mappings().all()
  if any(r["status"] in {"pending", "running"} for r in rows):
    await db.execute(update(t.cases).where(t.cases.c.id == case_id).values(win_rate_status="analyzing"))
    return

  latest = rows[0] if rows else None
  if latest and latest["status"] == "failed":
    await db.execute(update(t.cases).where(t.cases.c.id == case_id).values(win_rate_status="failed"))
    return

  current_id = (await db.execute(
    select(t.cases.c.win_rate_analysis_id).where(t.cases.c.id == case_id)
  )).scalar_one_or_none()
  if current_id is not None:
    linked = next((r for r in rows if r["id"] == current_id and r["status"] == "succeeded"), None)
    if linked:
      applicable = bool((linked.get("content") or {}).get("applicable", True))
      await db.execute(update(t.cases).where(t.cases.c.id == case_id).values(
        win_rate_status="analyzed" if applicable else "not_applicable",
      ))
      return

  await db.execute(update(t.cases).where(t.cases.c.id == case_id).values(win_rate_status="not_analyzed"))


async def refresh_analysis_status(db, t, case_id: int, analysis_type: str) -> None:
  if analysis_type == "win_rate":
    await refresh_win_rate_status(db, t, case_id)
  else:
    await refresh_case_status(db, t, case_id)


async def invalidate_win_rate(db, t, case_id: int) -> None:
  now = datetime.now(UTC)
  pending_ids = list((await db.execute(
    select(t.case_analyses.c.id)
    .where(t.case_analyses.c.case_id == case_id, t.case_analyses.c.analysis_type == "win_rate",
      t.case_analyses.c.status == "pending")
  )).scalars())
  if pending_ids:
    await db.execute(update(t.async_jobs).where(
      t.async_jobs.c.resource_type == "analysis",
      t.async_jobs.c.resource_id.in_(pending_ids),
      t.async_jobs.c.status == "queued",
    ).values(status="cancelled", finished_at=now))
    await db.execute(update(t.case_analyses).where(
      t.case_analyses.c.id.in_(pending_ids),
      t.case_analyses.c.status == "pending",
    ).values(status="cancelled", completed_at=now))

  await db.execute(update(t.cases).where(t.cases.c.id == case_id).values(
    win_rate=None,
    win_rate_updated_at=None,
    win_rate_status="not_analyzed",
    win_rate_analysis_id=None,
  ))
