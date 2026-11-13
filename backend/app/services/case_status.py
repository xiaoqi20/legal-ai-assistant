from sqlalchemy import select, update


async def refresh_case_status(db, t, case_id):
  statuses = set((await db.execute(select(t.case_analyses.c.status).where(t.case_analyses.c.case_id == case_id))).scalars())
  status = "analyzing" if statuses & {"pending", "running"} else "analyzed" if "succeeded" in statuses else "failed" if "failed" in statuses else "not_analyzed"
  await db.execute(update(t.cases).where(t.cases.c.id == case_id).values(analysis_status=status))
