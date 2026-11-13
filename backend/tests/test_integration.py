import asyncio
import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import insert, select, update

from app.schemas import MessageCreate
from app.services.chat import events, prepare
from app.worker import claim, run_once
from tests.conftest import login, seed_case


def parse_events(response):
  return [(block.splitlines()[0][7:], json.loads(block.splitlines()[1][6:]))
          for block in response.text.strip().split("\n\n") if block.startswith("event:")]


async def test_auth_profile_and_isolation(app, client):
  assert (await client.get("/api/v1/cases")).status_code == 401
  headers, owner = await login(client)
  other_headers, _ = await login(client)
  case_id = await seed_case(app, owner)
  assert (await client.get(f"/api/v1/cases/{case_id}", headers=other_headers)).status_code == 404
  assert (await client.get(f"/api/v1/cases/{case_id}", headers=headers)).status_code == 200
  bad = await client.put("/api/v1/profile", headers=headers, json={"role_type": "enterprise", "real_name": "合成姓名"})
  assert bad.status_code == 422
  good = await client.put("/api/v1/profile", headers=headers, json={"role_type": "individual", "real_name": "合成姓名"})
  assert good.status_code == 200
  assert (await client.post("/api/v1/auth/logout", headers=headers)).status_code == 204
  assert (await client.get("/api/v1/profile", headers=headers)).status_code == 401


async def test_document_job_retrieval_stream_and_soft_delete(app, client):
  headers, owner = await login(client)
  other_headers, other = await login(client)
  case_id = await seed_case(app, owner)
  other_case = await seed_case(app, other)
  data = app.state.storage.data
  payload = {"case_id": case_id, "filename": "synthetic.txt", "size_bytes": len(data),
    "mime_type": "text/plain", "sha256": hashlib.sha256(data).hexdigest()}
  response = await client.post("/api/v1/files/uploads", headers=headers, json=payload)
  assert response.status_code == 201, response.text
  file_id = response.json()["file_id"]
  complete = await client.post(f"/api/v1/files/{file_id}/complete", headers=headers)
  assert complete.status_code == 200
  assert (await client.post(f"/api/v1/files/{file_id}/complete", headers=headers)).json() == complete.json()
  assert (await client.get(f"/api/v1/files/{file_id}", headers=other_headers)).status_code == 404
  assert await run_once(app.state.db, app.state.ai, app.state.storage, app.state.settings)
  assert (await client.get(f"/api/v1/files/{file_id}", headers=headers)).json()["status"] == "available"
  t = app.state.db.t
  # Adversarial same-vector material in another case must never enter recall.
  async with app.state.db.sessions.begin() as db:
    other_file = (await db.execute(insert(t.files).values(case_id=other_case, uploaded_by=other,
      bucket="test", object_key=uuid.uuid4().hex, original_name="SECRET.txt", mime_type="text/plain",
      size_bytes=1, status="available").returning(t.files.c.id))).scalar_one()
    await db.execute(insert(t.doc_chunks).values(file_id=other_file, case_id=other_case, chunk_index=0,
      content="DO_NOT_LEAK", embedding=[1.0] + [0.0] * 1535, embedding_model=app.state.settings.embedding_model))
  recall = await client.post(f"/api/v1/cases/{case_id}/retrieval", headers=headers, json={"query": "合同价款"})
  assert recall.status_code == 200, recall.text
  assert {s["file_id"] for s in recall.json()["sources"]} == {file_id}
  conv = (await client.post("/api/v1/conversations", headers=headers, json={"case_id": case_id})).json()
  sent = {"content": "合同价款是多少？", "client_message_id": uuid.uuid4().hex}
  response = await client.post(f"/api/v1/conversations/{conv['id']}/messages/stream", headers=headers, json=sent)
  assert response.status_code == 200, response.text
  parsed = parse_events(response)
  assert [name for name, _ in parsed] == ["meta", "citations", "delta", "delta", "done"]
  assert parsed[-1][1]["status"] == "completed"
  assert "DO_NOT_LEAK" not in json.dumps(app.state.ai.last_messages)
  history = (await client.get(f"/api/v1/conversations/{conv['id']}/messages", headers=headers)).json()
  assistant = history["items"][-1]
  assert assistant["status"] == "completed" and assistant["input_tokens"] == 100
  assert len(assistant["citations"]) == 1 and float(assistant["cost_usd"]) > 0
  duplicate = await client.post(f"/api/v1/conversations/{conv['id']}/messages/stream", headers=headers, json=sent)
  assert duplicate.status_code == 409
  assert (await client.get(f"/api/v1/conversations/{conv['id']}/messages", headers=other_headers)).status_code == 404
  result = await client.post("/api/v1/conversations/delete", headers=headers, json={"ids": [conv["id"]]})
  assert result.status_code == 204
  assert (await client.get(f"/api/v1/conversations/{conv['id']}/messages", headers=headers)).status_code == 404
  async with app.state.db.sessions() as db:
    assert (await db.execute(select(t.audit_logs.c.id).where(t.audit_logs.c.resource_id == conv["id"], t.audit_logs.c.action == "conversation.soft_deleted"))).first()


async def test_upstream_errors_and_truncation_not_completed(app, client):
  headers, _ = await login(client)
  conv = (await client.post("/api/v1/conversations", headers=headers, json={})).json()
  for mode, error in [("error", "upstream_error"), ("length", "output_limit")]:
    app.state.ai.mode = mode
    response = await client.post(f"/api/v1/conversations/{conv['id']}/messages/stream", headers=headers,
      json={"content": "合成问题", "client_message_id": uuid.uuid4().hex})
    parsed = parse_events(response)
    assert parsed[-1][1]["status"] == "failed"
    assert parsed[-2][1]["code"] == error
    assert "sensitive-upstream" not in response.text
  rows = (await client.get(f"/api/v1/conversations/{conv['id']}/messages", headers=headers)).json()["items"]
  assert [row["status"] for row in rows if row["role"] == "assistant"] == ["failed", "failed"]


async def test_disconnect_cancel_and_stale_lease(app, client):
  headers, owner = await login(client)
  conv = (await client.post("/api/v1/conversations", headers=headers, json={})).json()
  payload = MessageCreate(content="合成问题", client_message_id=uuid.uuid4().hex)
  prepared = await prepare(app.state.db, app.state.settings, owner, conv["id"], payload)
  request = SimpleNamespace(app=app)
  generator = events(request, owner, payload, prepared)
  assert b"meta" in await anext(generator)
  assert b"citations" in await anext(generator)
  assert b"delta" in await anext(generator)
  await generator.aclose()
  async with app.state.db.sessions() as db:
    row = (await db.execute(select(app.state.db.t.ai_messages).where(app.state.db.t.ai_messages.c.id == prepared["message_id"]))).mappings().one()
    assert row["status"] == "cancelled" and row["content"]
  app.state.ai.mode = "slow"
  payload = MessageCreate(content="取消演示", client_message_id=uuid.uuid4().hex)
  prepared = await prepare(app.state.db, app.state.settings, owner, conv["id"], payload)
  generator = events(request, owner, payload, prepared)
  await anext(generator)
  await anext(generator)
  pending = asyncio.create_task(anext(generator))
  await asyncio.sleep(0.05)
  cancel = await client.post(f"/api/v1/conversations/{conv['id']}/messages/{prepared['message_id']}/cancel", headers=headers)
  assert cancel.status_code == 200
  assert b"error" in await pending
  assert b"cancelled" in await anext(generator)
  await generator.aclose()
  payload = MessageCreate(content="过期演示", client_message_id=uuid.uuid4().hex)
  prepared = await prepare(app.state.db, app.state.settings, owner, conv["id"], payload)
  t = app.state.db.t
  async with app.state.db.sessions.begin() as db:
    await db.execute(update(t.ai_messages).where(t.ai_messages.c.id == prepared["message_id"]).values(lease_expires_at=datetime.now(UTC) - timedelta(seconds=1)))
  history = (await client.get(f"/api/v1/conversations/{conv['id']}/messages", headers=headers)).json()
  assert history["items"][-1]["status"] == "failed"


async def test_worker_lease_exclusivity_and_hash_failure(app, client):
  headers, owner = await login(client)
  case_id = await seed_case(app, owner)
  payload = {"case_id": case_id, "filename": "bad.txt", "size_bytes": len(app.state.storage.data),
    "mime_type": "text/plain", "sha256": "0" * 64}
  file_id = (await client.post("/api/v1/files/uploads", headers=headers, json=payload)).json()["file_id"]
  job_id = (await client.post(f"/api/v1/files/{file_id}/complete", headers=headers)).json()["job_id"]
  first, second = await asyncio.gather(claim(app.state.db, app.state.settings), claim(app.state.db, app.state.settings))
  assert sum(job is not None and job["id"] == job_id for job in [first, second]) == 1
  t = app.state.db.t
  async with app.state.db.sessions.begin() as db:
    await db.execute(update(t.async_jobs).where(t.async_jobs.c.id == job_id).values(lease_expires_at=datetime.now(UTC) - timedelta(seconds=1)))
  assert await run_once(app.state.db, app.state.ai, app.state.storage, app.state.settings)
  status = (await client.get(f"/api/v1/files/{file_id}", headers=headers)).json()
  assert status["status"] == "quarantined"
  assert (await client.get(f"/api/v1/files/{file_id}/download", headers=headers)).status_code == 409


async def test_structured_analysis_job_is_grounded_and_idempotent(app, client):
  headers, owner = await login(client)
  case_id = await seed_case(app, owner)
  t = app.state.db.t
  async with app.state.db.sessions.begin() as db:
    file_id = (await db.execute(insert(t.files).values(case_id=case_id, uploaded_by=owner,
      bucket="test", object_key=uuid.uuid4().hex, original_name="合成材料.txt", mime_type="text/plain",
      size_bytes=10, status="available").returning(t.files.c.id))).scalar_one()
    await db.execute(insert(t.doc_chunks).values(case_id=case_id, file_id=file_id, chunk_index=0,
      content="合成甲与合成乙签订合同。", embedding=[1.0] + [0.0] * 1535,
      embedding_model=app.state.settings.embedding_model))
  payload = {"analysis_type": "case_summary", "client_request_id": uuid.uuid4().hex}
  response = await client.post(f"/api/v1/cases/{case_id}/analyses", headers=headers, json=payload)
  assert response.status_code == 202, response.text
  assert (await client.post(f"/api/v1/cases/{case_id}/analyses", headers=headers, json=payload)).json() == response.json()
  assert (await client.post(f"/api/v1/cases/{case_id}/analyses", headers=headers,
    json=payload | {"client_request_id": uuid.uuid4().hex})).status_code == 409
  assert await run_once(app.state.db, app.state.ai, app.state.storage, app.state.settings)
  report = (await client.get(f"/api/v1/cases/{case_id}/analyses/{response.json()['analysis_id']}", headers=headers)).json()
  assert report["status"] == "succeeded" and report["content"]["facts"]
  assert report["sources"][0]["file_id"] == file_id
  assert report["source_fingerprint"] and report["prompt_version_id"]
  assert report["input_tokens"] == 120
  detail = (await client.get(f"/api/v1/cases/{case_id}", headers=headers)).json()
  assert detail["win_rate"] is None


async def test_disconnect_immediately_after_meta_is_persisted(app, client):
  headers, owner = await login(client)
  conv = (await client.post("/api/v1/conversations", headers=headers, json={})).json()
  payload = MessageCreate(content="合成问题", client_message_id=uuid.uuid4().hex)
  prepared = await prepare(app.state.db, app.state.settings, owner, conv["id"], payload)
  generator = events(SimpleNamespace(app=app), owner, payload, prepared)
  await anext(generator)
  await generator.aclose()
  history = (await client.get(f"/api/v1/conversations/{conv['id']}/messages", headers=headers)).json()
  assert history["items"][-1]["status"] == "cancelled"


async def test_concurrent_sends_and_limits_are_database_enforced(app, client):
  headers, owner = await login(client)
  conv = (await client.post("/api/v1/conversations", headers=headers, json={})).json()
  async def attempt():
    from fastapi import HTTPException
    try:
      return await prepare(app.state.db, app.state.settings, owner, conv["id"],
        MessageCreate(content="合成并发", client_message_id=uuid.uuid4().hex))
    except HTTPException as error:
      return error.status_code
  results = await asyncio.gather(attempt(), attempt())
  assert sum(isinstance(result, dict) for result in results) == 1
  assert 409 in results
  app.state.settings.max_concurrent_streams = 1
  another = (await client.post("/api/v1/conversations", headers=headers, json={})).json()
  assert (await client.post(f"/api/v1/conversations/{another['id']}/messages/stream", headers=headers,
    json={"content": "合成限流", "client_message_id": uuid.uuid4().hex})).status_code == 429


async def test_organization_access_revocation_applies_to_history_and_retrieval(app, client):
  headers, owner = await login(client)
  member_headers, member = await login(client)
  t = app.state.db.t
  async with app.state.db.sessions.begin() as db:
    org_id = (await db.execute(insert(t.organizations).values(name="合成组织", owner_user_id=owner).returning(t.organizations.c.id))).scalar_one()
    await db.execute(insert(t.organization_members), [
      {"org_id": org_id, "user_id": owner, "role": "owner", "status": "active"},
      {"org_id": org_id, "user_id": member, "role": "member", "status": "active"},
    ])
    case_id = (await db.execute(insert(t.cases).values(title="合成组织案件", owner_user_id=owner, org_id=org_id).returning(t.cases.c.id))).scalar_one()
  conv = (await client.post("/api/v1/conversations", headers=member_headers, json={"case_id": case_id})).json()
  assert (await client.get(f"/api/v1/cases/{case_id}", headers=member_headers)).status_code == 200
  async with app.state.db.sessions.begin() as db:
    await db.execute(update(t.organization_members).where(t.organization_members.c.org_id == org_id,
      t.organization_members.c.user_id == member).values(status="removed"))
  assert (await client.get(f"/api/v1/cases/{case_id}", headers=member_headers)).status_code == 404
  assert (await client.get(f"/api/v1/conversations/{conv['id']}/messages", headers=member_headers)).status_code == 404
  assert (await client.post(f"/api/v1/cases/{case_id}/retrieval", headers=member_headers, json={"query": "合成资料"})).status_code == 404
  assert (await client.get("/api/v1/conversations", headers=member_headers)).json()["items"] == []
  assert (await client.get(f"/api/v1/cases/{case_id}", headers=headers)).status_code == 200


async def test_empty_analysis_fails_and_queued_analysis_can_cancel(app, client):
  headers, owner = await login(client)
  case_id = await seed_case(app, owner)
  payload = {"analysis_type": "case_summary", "client_request_id": uuid.uuid4().hex}
  queued = (await client.post(f"/api/v1/cases/{case_id}/analyses", headers=headers, json=payload)).json()
  assert await run_once(app.state.db, app.state.ai, app.state.storage, app.state.settings)
  report = (await client.get(f"/api/v1/cases/{case_id}/analyses/{queued['analysis_id']}", headers=headers)).json()
  assert report["status"] == "failed" and report["error_message"] == "no_case_material"
  assert (await client.get(f"/api/v1/cases/{case_id}", headers=headers)).json()["analysis_status"] == "failed"
  queued = (await client.post(f"/api/v1/cases/{case_id}/analyses", headers=headers,
    json=payload | {"client_request_id": uuid.uuid4().hex})).json()
  cancelled = await client.post(f"/api/v1/cases/{case_id}/analyses/{queued['analysis_id']}/cancel", headers=headers)
  assert cancelled.json()["status"] == "cancelled"
  assert not await run_once(app.state.db, app.state.ai, app.state.storage, app.state.settings)
