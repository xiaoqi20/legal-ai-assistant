import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import func, insert, select, update

from app.services.assessment import AssessmentService, process_assessment
from app.services.assessment_store import AssessmentStopped, FencedAssessmentSaver
from app.worker import claim, process_job, run_once
from tests.conftest import login, seed_case


def report(ranks=None):
  ranks = ranks or []
  return {"outcome": "assessed" if ranks else "insufficient_material", "summary": "合成案件研判草稿",
    "facts": [{"statement": "合成付款约定", "origin": "material", "citation_ranks": ranks}] if ranks else [],
    "issues": [{"title": "合成付款争点", "assessment": "需要结合履行材料核验", "supporting_ranks": ranks,
      "opposing_ranks": [], "gaps": ["尚缺实际履行材料"]}], "recommendations": ["补充合成履行凭证"],
    "legal_questions_to_verify": ["法律适用及现行效力待核验"], "limitations": ["仅依据当前片段"]}


class AssessmentAI:
  def __init__(self, original):
    self.original = original
    self.calls = []
    self.bad_report = False
    self.always_bad = False
    self.on_call = None
    self.follow_up = []
    self.missing_usage = False

  def check(self, **kwargs):
    pass

  async def close(self):
    pass

  async def embed(self, texts):
    return await self.original.embed(texts)

  async def rerank(self, *args, **kwargs):
    return await self.original.rerank(*args, **kwargs)

  async def complete_json(self, messages, **kwargs):
    instruction = messages[0]["content"]
    self.calls.append(messages)
    if self.on_call:
      await self.on_call()
    if '"title":"AssessmentPlan"' in instruction:
      value = {"issues": [{"title": "合成付款争点", "query": "合成付款约定"}]}
    elif '"title":"EvidenceCoverage"' in instruction:
      value = {"queries": self.follow_up, "gaps": ["待核验实际履行"]}
    else:
      data = json.loads(messages[-1]["content"].split("\n", 1)[1])
      ranks = [source["rank"] for source in data.get("sources", [])]
      value = report([999] if self.bad_report or self.always_bad else ranks)
      self.bad_report = False
    return SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop",
      message=SimpleNamespace(content=json.dumps(value, ensure_ascii=False)))],
      usage=None if self.missing_usage else SimpleNamespace(prompt_tokens=100, completion_tokens=20, prompt_cache_hit_tokens=60))


async def setup(app, client, *, complete=True, with_file=True):
  headers, owner = await login(client)
  case_id = await seed_case(app, owner)
  t = app.state.db.t
  async with app.state.db.sessions.begin() as db:
    if complete:
      await db.execute(update(t.cases).where(t.cases.c.id == case_id)
        .values(claim="合成请求支付价款", party_role_label="原告"))
    if with_file:
      file_id = await db.scalar(insert(t.files).values(case_id=case_id, uploaded_by=owner,
        bucket="test", object_key=uuid.uuid4().hex, original_name="synthetic.txt", mime_type="text/plain",
        size_bytes=64, status="available", metadata={"parse_status": "succeeded"}).returning(t.files.c.id))
      await db.execute(insert(t.doc_chunks).values(file_id=file_id, case_id=case_id,
        chunk_index=0, page_no=1, content="合成合同约定支付价款100万元。",
        embedding=[1.0] + [0.0] * 1535, embedding_model=app.state.settings.embedding_model))
  ai = AssessmentAI(app.state.ai)
  app.state.ai = ai
  return headers, owner, case_id, ai


async def create(client, headers, case_id, request_id=None):
  response = await client.post(f"/api/v1/cases/{case_id}/assessment-runs", headers=headers,
    json={"client_request_id": request_id or uuid.uuid4().hex})
  assert response.status_code == 202, response.text
  return response.json()


async def get(client, headers, case_id, run_id):
  response = await client.get(f"/api/v1/cases/{case_id}/assessment-runs/{run_id}", headers=headers)
  assert response.status_code == 200, response.text
  return response.json()


async def work(app):
  assert await run_once(app.state.db, app.state.ai, app.state.storage, app.state.settings)


async def test_assessment_report_sources_usage_history_events_and_idempotency(app, client):
  headers, owner, case_id, ai = await setup(app, client)
  created = await create(client, headers, case_id, "assessment-1")
  again = await create(client, headers, case_id, "assessment-1")
  assert again["id"] == created["id"]
  active = await client.post(f"/api/v1/cases/{case_id}/assessment-runs", headers=headers,
    json={"client_request_id": "other"})
  assert active.status_code == 409
  await work(app)
  result = await get(client, headers, case_id, created["id"])
  assert result["status"] == "succeeded", result
  assert result["report"]["review_status"] == "unreviewed"
  assert result["report"]["facts"][0]["citation_ranks"] == [1]
  assert result["sources"][0]["document_title"] == "synthetic.txt"
  assert result["usage"]["input_tokens"] == 300
  assert result["usage"]["cached_tokens"] == 180
  assert result["cost_usd"] is not None
  assert result["model_calls"] == 3 and result["tool_calls"] == 1
  assert len(ai.calls) == 3
  history = await client.get(f"/api/v1/cases/{case_id}/assessment-runs", headers=headers)
  assert history.json()["items"][0]["id"] == created["id"]
  events = await client.get(f"/api/v1/cases/{case_id}/assessment-runs/{created['id']}/events", headers=headers)
  assert "event: progress" in events.text and '"status":"succeeded"' in events.text
  assert "合成合同" not in events.text
  async with app.state.db.sessions() as db:
    assert await db.scalar(select(func.count()).select_from(app.state.db.t.case_assessment_checkpoints)) > 3
    audit = (await db.execute(select(app.state.db.t.audit_logs.c.action).where(
      app.state.db.t.audit_logs.c.resource_type == "assessment"))).scalars().all()
    assert "assessment.created" in audit and "assessment.succeeded" in audit


async def test_missing_context_interrupt_releases_worker_and_resumes_once(app, client):
  headers, _, case_id, ai = await setup(app, client, complete=False)
  created = await create(client, headers, case_id)
  await work(app)
  paused = await get(client, headers, case_id, created["id"])
  assert paused["status"] == "awaiting_input", paused
  assert len(paused["questions"]) == 2
  assert ai.calls == []
  assert not await run_once(app.state.db, app.state.ai, app.state.storage, app.state.settings)
  response = await client.post(f"/api/v1/cases/{case_id}/assessment-runs/{created['id']}/resume",
    headers=headers, json={"revision": paused["revision"], "answers": "我方为原告，请求支付剩余合同价款。"})
  assert response.status_code == 202, response.text
  duplicate = await client.post(f"/api/v1/cases/{case_id}/assessment-runs/{created['id']}/resume",
    headers=headers, json={"revision": paused["revision"], "answers": "重复补充"})
  assert duplicate.status_code == 409
  await work(app)
  result = await get(client, headers, case_id, created["id"])
  assert result["status"] == "succeeded", result
  data = json.loads(ai.calls[0][-1]["content"].split("\n", 1)[1])
  assert "我方为原告" in data["supplemental"]


async def test_paused_run_rejects_changed_inputs_and_remains_isolated(app, client):
  headers, _, case_id, _ = await setup(app, client, complete=False)
  created = await create(client, headers, case_id)
  await work(app)
  other_headers, _ = await login(client)
  for suffix in ("", "/events"):
    response = await client.get(f"/api/v1/cases/{case_id}/assessment-runs/{created['id']}{suffix}", headers=other_headers)
    assert response.status_code == 404
  async with app.state.db.sessions.begin() as db:
    await db.execute(update(app.state.db.t.cases).where(app.state.db.t.cases.c.id == case_id).values(summary="更新的案情"))
  response = await client.post(f"/api/v1/cases/{case_id}/assessment-runs/{created['id']}/resume", headers=headers,
    json={"revision": 1, "answers": "我方原告，要求支付价款"})
  assert response.status_code == 409 and response.json()["error"]["code"] == "stale_inputs"
  assert (await get(client, headers, case_id, created["id"]))["status"] == "stale"


async def test_cancel_queued_and_running_assessment_prevents_late_writes(app, client):
  headers, _, case_id, ai = await setup(app, client)
  created = await create(client, headers, case_id)
  response = await client.post(f"/api/v1/cases/{case_id}/assessment-runs/{created['id']}/cancel", headers=headers)
  assert response.json()["status"] == "cancelled"
  assert not await run_once(app.state.db, app.state.ai, app.state.storage, app.state.settings)
  created = await create(client, headers, case_id)
  entered, closed = asyncio.Event(), asyncio.Event()

  async def slow():
    entered.set()
    try:
      await asyncio.sleep(10)
    finally:
      closed.set()

  ai.on_call = slow
  processing = asyncio.create_task(work(app))
  await asyncio.wait_for(entered.wait(), timeout=5)
  await client.post(f"/api/v1/cases/{case_id}/assessment-runs/{created['id']}/cancel", headers=headers)
  await asyncio.wait_for(processing, timeout=5)
  assert closed.is_set()
  result = await get(client, headers, case_id, created["id"])
  assert result["status"] == "cancelled" and result["report"] is None
  assert result["usage"] is None


@pytest.mark.parametrize("bad_report,always_bad,expected", [(True, False, "succeeded"), (False, True, "failed")])
async def test_report_invalid_citations_get_one_repair(app, client, bad_report, always_bad, expected):
  headers, _, case_id, ai = await setup(app, client)
  ai.bad_report, ai.always_bad = bad_report, always_bad
  created = await create(client, headers, case_id)
  await work(app)
  result = await get(client, headers, case_id, created["id"])
  assert result["status"] == expected, result
  assert len(ai.calls) == 4
  if expected == "failed":
    assert result["error_code"] == "invalid_assessment_report"
    assert result["report"] is None


async def test_empty_sources_and_missing_usage_are_explicit(app, client):
  headers, _, case_id, ai = await setup(app, client, with_file=False)
  ai.missing_usage = True
  created = await create(client, headers, case_id)
  await work(app)
  result = await get(client, headers, case_id, created["id"])
  assert result["status"] == "succeeded", result
  assert result["report"]["outcome"] == "insufficient_material"
  assert result["sources"] == [] and result["usage"] is None and result["cost_usd"] is None


async def test_repeated_queries_stop_without_spending_another_tool_call(app, client):
  headers, _, case_id, ai = await setup(app, client)
  ai.follow_up = ["合成付款约定"]
  created = await create(client, headers, case_id)
  await work(app)
  result = await get(client, headers, case_id, created["id"])
  assert result["status"] == "succeeded", result
  assert result["tool_calls"] == 1


async def test_completed_model_step_is_reused_and_unknown_call_is_not_replayed(app, client):
  headers, _, case_id, ai = await setup(app, client)
  created = await create(client, headers, case_id)
  job = await claim(app.state.db, app.state.settings)
  service = AssessmentService(app.state.db, ai, app.state.settings, job)
  await service.reserve("plan", "model")
  with pytest.raises(AssessmentStopped, match="model_outcome_unknown"):
    await service.reserve("plan", "model")
  await service.save_step("plan", {"content": '{"issues":[]}', "finish_reason": "stop"})
  saved = await service.reserve("plan", "model")
  assert saved["result"]["content"] == '{"issues":[]}'
  assert ai.calls == []
  # A new fencing token prevents the expired worker from writing even a checkpoint.
  async with app.state.db.sessions.begin() as db:
    await db.execute(update(app.state.db.t.async_jobs).where(app.state.db.t.async_jobs.c.id == job["id"])
      .values(lease_token=uuid.uuid4()))
  saver = FencedAssessmentSaver(app.state.db, job)
  with pytest.raises(AssessmentStopped, match="lease_lost"):
    await saver.aput(saver.config(), {"id": "checkpoint-test"}, {}, {})
  with pytest.raises(AssessmentStopped, match="checkpoint_scope_invalid"):
    await saver.aget_tuple({"configurable": {"thread_id": str(created["id"] + 100)}})


async def test_stale_mid_generation_never_saves_report(app, client):
  headers, _, case_id, ai = await setup(app, client)
  created = await create(client, headers, case_id)

  async def change_input():
    async with app.state.db.sessions.begin() as db:
      await db.execute(update(app.state.db.t.doc_chunks).where(app.state.db.t.doc_chunks.c.case_id == case_id)
        .values(content="合成资料修订"))

  ai.on_call = change_input
  await work(app)
  result = await get(client, headers, case_id, created["id"])
  assert result["status"] == "stale", result
  assert result["report"] is None


async def test_worker_reclaims_crashed_assessment_without_resetting_budgets(app, client):
  headers, _, case_id, ai = await setup(app, client)
  created = await create(client, headers, case_id)
  job = await claim(app.state.db, app.state.settings)
  service = AssessmentService(app.state.db, ai, app.state.settings, job)
  await service.reserve("plan", "model")
  async with app.state.db.sessions.begin() as db:
    await db.execute(update(app.state.db.t.async_jobs).where(app.state.db.t.async_jobs.c.id == job["id"])
      .values(lease_expires_at=datetime.now(UTC) - timedelta(seconds=1)))
  recovered = await claim(app.state.db, app.state.settings)
  assert recovered["id"] == job["id"] and recovered["lease_token"] != job["lease_token"]
  await process_job(app.state.db, ai, app.state.storage, app.state.settings, recovered, None)
  result = await get(client, headers, case_id, created["id"])
  assert result["status"] == "failed" and result["error_code"] == "model_outcome_unknown", result
  assert result["model_calls"] == 1
  assert ai.calls == []


async def test_disable_and_idempotency_conflict(app, client):
  headers, _, case_id, _ = await setup(app, client)
  await create(client, headers, case_id, "key-1")
  response = await client.post(f"/api/v1/cases/{case_id}/assessment-runs", headers=headers,
    json={"client_request_id": "key-1", "question": "不同的问题"})
  assert response.status_code == 409
  app.state.settings.assessment_enabled = False
  response = await client.post(f"/api/v1/cases/{case_id}/assessment-runs", headers=headers,
    json={"client_request_id": "key-2"})
  assert response.status_code == 503


@pytest.mark.parametrize("paused", [False, True])
async def test_crash_after_completed_nodes_resumes_checkpoint_without_duplicate_model_calls(app, client, monkeypatch, paused):
  headers, _, case_id, ai = await setup(app, client, complete=not paused)
  created = await create(client, headers, case_id)
  if paused:
    await work(app)
    response = await client.post(f"/api/v1/cases/{case_id}/assessment-runs/{created['id']}/resume", headers=headers,
      json={"revision": 1, "answers": "我方原告，请求支付合同价款"})
    assert response.status_code == 202
  job = await claim(app.state.db, app.state.settings)
  original_progress = AssessmentService.progress
  entered = asyncio.Event()

  async def crash_before_coverage(self, stage):
    if stage == "checking_coverage":
      entered.set()
      await asyncio.Event().wait()
    await original_progress(self, stage)

  monkeypatch.setattr(AssessmentService, "progress", crash_before_coverage)
  processing = asyncio.create_task(process_assessment(app.state.db, ai, app.state.settings, job))
  await asyncio.wait_for(entered.wait(), timeout=5)
  processing.cancel()
  with pytest.raises(asyncio.CancelledError):
    await processing
  assert len(ai.calls) == 1
  async with app.state.db.sessions.begin() as db:
    await db.execute(update(app.state.db.t.async_jobs).where(app.state.db.t.async_jobs.c.id == job["id"])
      .values(lease_expires_at=datetime.now(UTC) - timedelta(seconds=1)))
  monkeypatch.setattr(AssessmentService, "progress", original_progress)
  await work(app)
  result = await get(client, headers, case_id, created["id"])
  assert result["status"] == "succeeded", result
  assert len(ai.calls) == 3
  assert result["model_calls"] == 3 and result["tool_calls"] == 1
  assert result["error_code"] is None


async def test_checkpointer_round_trip_parent_pending_writes_history_and_scope(app, client):
  from langgraph.checkpoint.base import empty_checkpoint

  headers, _, case_id, _ = await setup(app, client)
  await create(client, headers, case_id)
  job = await claim(app.state.db, app.state.settings)
  saver = FencedAssessmentSaver(app.state.db, job)
  cp1 = empty_checkpoint()
  cp1["channel_values"] = {"case": {"title": "合成测试"}}
  config1 = await saver.aput(saver.config(), cp1, {"source": "input", "step": -1, "custom": "preserved"}, {})
  await saver.aput_writes(config1, [("result", {"ok": True}), ("__error__", "first")], "task1")
  await saver.aput_writes(config1, [("result", {"ok": False}), ("__error__", "second")], "task1")
  restored = await saver.aget_tuple(config1)
  assert restored.checkpoint["channel_values"] == cp1["channel_values"]
  assert restored.metadata["custom"] == "preserved"
  assert ("task1", "result", {"ok": True}) in restored.pending_writes
  assert ("task1", "__error__", "second") in restored.pending_writes
  cp2 = empty_checkpoint()
  await saver.aput(config1, cp2, {"source": "loop", "step": 0}, {})
  latest = await saver.aget_tuple(saver.config())
  assert latest.parent_config == config1
  history = [item async for item in saver.alist(saver.config(), limit=1)]
  assert len(history) == 1 and history[0].checkpoint["id"] == cp2["id"]
  filtered = [item async for item in saver.alist(saver.config(), filter={"source": "input"})]
  assert len(filtered) == 1 and filtered[0].checkpoint["id"] == cp1["id"]
  await saver.adelete_thread(str(job["resource_id"]))
  assert await saver.aget_tuple(saver.config()) is None


async def test_snapshot_detects_ocr_revision_and_unindexed_files_are_excluded(app, client):
  headers, _, case_id, _ = await setup(app, client)
  t = app.state.db.t
  async with app.state.db.sessions.begin() as db:
    await db.execute(update(t.files).where(t.files.c.case_id == case_id).values(metadata={"parse_status": "review_required"}))
  created = await create(client, headers, case_id)
  await work(app)
  result = await get(client, headers, case_id, created["id"])
  assert result["status"] == "succeeded" and result["sources"] == [], result


async def test_model_budget_and_upstream_error_do_not_leak_or_retry(app, client):
  headers, _, case_id, ai = await setup(app, client)
  app.state.settings.assessment_max_model_calls = 3
  ai.always_bad = True
  created = await create(client, headers, case_id)
  await work(app)
  result = await get(client, headers, case_id, created["id"])
  assert result["status"] == "failed" and result["error_code"] == "assessment_model_limit", result
  assert len(ai.calls) == 3
  created = await create(client, headers, case_id)

  async def upstream_failed():
    raise RuntimeError("secret-upstream-key-and-case-data")

  ai.on_call = upstream_failed
  await work(app)
  result = await get(client, headers, case_id, created["id"])
  assert result["error_code"] == "assessment_upstream_error", result
  assert result["usage"] is None
  async with app.state.db.sessions() as db:
    writes = (await db.execute(select(app.state.db.t.case_assessment_writes.c.value)
      .where(app.state.db.t.case_assessment_writes.c.run_id == created["id"]))).scalars().all()
  assert not any(b"secret-upstream" in bytes(value) for value in writes)


async def test_waiting_run_requires_owner_and_revoked_member_cannot_execute(app, client):
  headers, owner, case_id, _ = await setup(app, client, complete=False)
  member_headers, member = await login(client)
  t = app.state.db.t
  async with app.state.db.sessions.begin() as db:
    org_id = await db.scalar(insert(t.organizations).values(name="合成组织", owner_user_id=owner).returning(t.organizations.c.id))
    await db.execute(insert(t.organization_members), [
      {"org_id": org_id, "user_id": owner, "role": "owner", "status": "active"},
      {"org_id": org_id, "user_id": member, "role": "member", "status": "active"},
    ])
    await db.execute(update(t.cases).where(t.cases.c.id == case_id).values(org_id=org_id))
  created = await create(client, headers, case_id)
  await work(app)
  response = await client.post(f"/api/v1/cases/{case_id}/assessment-runs/{created['id']}/resume", headers=member_headers,
    json={"revision": 1, "answers": "试图替他人补充"})
  assert response.status_code == 403
  response = await client.post(f"/api/v1/cases/{case_id}/assessment-runs/{created['id']}/cancel", headers=member_headers)
  assert response.status_code == 403
  await client.post(f"/api/v1/cases/{case_id}/assessment-runs/{created['id']}/cancel", headers=headers)
  member_run = await create(client, member_headers, case_id)
  async with app.state.db.sessions.begin() as db:
    await db.execute(update(t.organization_members).where(t.organization_members.c.org_id == org_id,
      t.organization_members.c.user_id == member).values(status="removed"))
  await work(app)
  async with app.state.db.sessions() as db:
    row = (await db.execute(select(t.case_assessment_runs).where(t.case_assessment_runs.c.id == member_run["id"]))).mappings().one()
  assert row["status"] == "cancelled" and row["error_code"] == "access_revoked"
