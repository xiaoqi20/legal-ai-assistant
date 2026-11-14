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


async def test_create_case_persists_intake_and_scopes_access(app, client):
  headers, owner = await login(client)
  other_headers, _ = await login(client)
  payload = {
    "title": "合成借款纠纷案",
    "case_type": "civil",
    "procedure": "first_instance",
    "summary": "双方签订借款协议，借款到期后尚未归还。",
    "claim": "请求归还本金及利息",
    "handling_identity": "agent",
    "party_role_label": "原告",
    "our_parties": ["合成甲"],
    "opponent_parties": ["合成乙", "合成丙"],
  }
  response = await client.post("/api/v1/cases", headers=headers, json=payload)
  assert response.status_code == 201, response.text
  created = response.json()
  case_id = created["id"]
  assert created["owner_user_id"] == owner
  assert created["handling_identity"] == "agent"
  assert created["party_role_label"] == "原告"
  assert created["analysis_status"] == "not_analyzed"
  assert created["summary"] == payload["summary"]
  assert created["claim"] == payload["claim"]
  assert created["our_parties"] == payload["our_parties"]
  assert created["opponent_parties"] == payload["opponent_parties"]
  assert [party["party_role"] for party in created["parties"]] == [
    "plaintiff", "defendant", "defendant",
  ]

  listed = await client.get("/api/v1/cases", headers=headers)
  assert listed.status_code == 200
  assert any(row["id"] == case_id for row in listed.json())
  detail = await client.get(f"/api/v1/cases/{case_id}", headers=headers)
  assert detail.status_code == 200
  assert detail.json()["our_parties"] == payload["our_parties"]
  assert detail.json()["opponent_parties"] == payload["opponent_parties"]
  assert (await client.get(f"/api/v1/cases/{case_id}", headers=other_headers)).status_code == 404

  data = app.state.storage.data
  upload = await client.post("/api/v1/files/uploads", headers=headers, json={
    "case_id": case_id, "filename": "synthetic.txt", "size_bytes": len(data),
    "mime_type": "text/plain", "sha256": hashlib.sha256(data).hexdigest(),
  })
  assert upload.status_code == 201, upload.text
  t = app.state.db.t
  async with app.state.db.sessions() as db:
    audit = (await db.execute(select(t.audit_logs).where(
      t.audit_logs.c.action == "case.created", t.audit_logs.c.resource_id == case_id,
    ))).mappings().one()
    assert audit["user_id"] == owner
    party_count = await db.scalar(select(t.case_parties.c.id).where(t.case_parties.c.case_id == case_id))
    assert party_count is not None


async def test_create_case_validation_and_empty_defaults(app, client):
  headers, _ = await login(client)
  response = await client.post("/api/v1/cases", headers=headers, json={})
  assert response.status_code == 201, response.text
  created = response.json()
  assert created["title"] == "未命名案件（待完善）"
  assert created["case_type"] == "other"
  assert created["procedure"] == "other"
  assert created["analysis_status"] == "not_analyzed"
  assert created["our_parties"] == []
  assert created["opponent_parties"] == []

  blank_title = await client.post("/api/v1/cases", headers=headers, json={"title": "  "})
  assert blank_title.status_code == 201, blank_title.text
  assert blank_title.json()["title"] == "未命名案件（待完善）"

  invalid = await client.post("/api/v1/cases", headers=headers, json={
    "title": "非法类型", "case_type": "unknown",
  })
  assert invalid.status_code == 422
  blank_party = await client.post("/api/v1/cases", headers=headers, json={
    "our_parties": ["  "],
  })
  assert blank_party.status_code == 422


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
  assert await run_once(app.state.db, app.state.ai, app.state.storage, app.state.settings)
  assert (await client.get(f"/api/v1/files/{file_id}", headers=headers)).json()["status"] == "available"
  t = app.state.db.t
  async with app.state.db.sessions.begin() as db:
    material_id = (await db.execute(insert(t.evidence_items).values(
      case_id=case_id, category="written", title="合成材料附件验收", status="ai_passed",
    ).returning(t.evidence_items.c.id))).scalar_one()
    await db.execute(insert(t.evidence_item_files).values(
      evidence_item_id=material_id, file_id=file_id, case_id=case_id, sort_order=0,
    ))
  materials = await client.get(f"/api/v1/cases/{case_id}/materials", headers=headers)
  assert materials.status_code == 200
  assert materials.json()[0]["files"] == [{
    "id": file_id, "original_name": "synthetic.txt", "mime_type": "text/plain",
  }]
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


async def test_low_confidence_image_requires_review_before_rag(app, client):
  from sqlalchemy import insert, select

  class FakeOcr:
    async def recognize(self, image):
      assert image.startswith(b"\x89PNG")
      return {"text": "合成价款100万元", "blocks": [{"text": "合成价款100万元", "polygon": [1, 2, 3, 4], "confidence": 0.51}],
        "confidence": 0.51, "provider": "fake_ocr", "model": "fixture"}

  headers, owner = await login(client)
  case_id = await seed_case(app, owner)
  image = b"\x89PNG\r\n\x1a\nsynthetic"
  app.state.storage.data = image
  t = app.state.db.t
  async with app.state.db.sessions.begin() as db:
    file_id = (await db.execute(insert(t.files).values(case_id=case_id, uploaded_by=owner,
      bucket="test", object_key=uuid.uuid4().hex, original_name="scan.png", mime_type="image/png",
      size_bytes=len(image), sha256=hashlib.sha256(image).hexdigest(), status="uploading",
      metadata={"category": "other", "version_id": "test"}).returning(t.files.c.id))).scalar_one()
    await db.execute(insert(t.async_jobs).values(job_type="document_parse", resource_type="file",
      resource_id=file_id, payload={"requested_by": owner}, idempotency_key=f"parse:{file_id}:v1"))
  assert await run_once(app.state.db, app.state.ai, app.state.storage, app.state.settings, FakeOcr())
  pages = (await client.get(f"/api/v1/files/{file_id}/ocr", headers=headers)).json()
  assert pages[0]["page_no"] == 1 and pages[0]["provider"] == "fake_ocr"
  assert pages[0]["blocks"][0]["polygon"] == [1, 2, 3, 4]
  assert pages[0]["review_status"] == "pending"
  async with app.state.db.sessions() as db:
    assert (await db.execute(select(t.doc_chunks.c.id).where(t.doc_chunks.c.file_id == file_id))).first() is None
  reviewed = await client.put(f"/api/v1/files/{file_id}/ocr/1", headers=headers,
    json={"corrected_text": "已核实：价款为100万元"})
  assert reviewed.status_code == 200, reviewed.text
  assert reviewed.json()["index_job_id"]
  assert (await client.put(f"/api/v1/files/{file_id}/ocr/1", headers=headers,
    json={"corrected_text": "篡改已确认内容"})).status_code == 409
  assert await run_once(app.state.db, app.state.ai, app.state.storage, app.state.settings, FakeOcr())
  async with app.state.db.sessions() as db:
    chunk = (await db.execute(select(t.doc_chunks).where(t.doc_chunks.c.file_id == file_id))).mappings().one()
    assert chunk["page_no"] == 1 and "已核实" in chunk["content"]


async def test_scanned_pdf_ocr_checkpoints_completed_pages(app, client):
  import io

  from pypdf import PdfWriter
  from sqlalchemy import insert, select, update

  class FirstAttemptOcr:
    calls = 0

    async def recognize(self, image):
      assert image.startswith(b"\x89PNG")
      self.calls += 1
      if self.calls == 2:
        raise RuntimeError("temporary provider failure")
      return {"text": "合成扫描页", "blocks": [{"text": "合成扫描页", "polygon": [{"x": 1, "y": 2}], "confidence": 0.99}],
        "confidence": 0.99, "provider": "fake_ocr", "model": "fixture"}

  class RecoveryOcr:
    calls = 0

    async def recognize(self, image):
      assert image.startswith(b"\x89PNG")
      self.calls += 1
      return {"text": "第二页内容", "blocks": [], "confidence": 0.99,
        "provider": "fake_ocr", "model": "fixture"}

  headers, owner = await login(client)
  case_id = await seed_case(app, owner)
  writer = PdfWriter()
  writer.add_blank_page(width=200, height=200)
  writer.add_blank_page(width=200, height=200)
  stream = io.BytesIO()
  writer.write(stream)
  pdf = stream.getvalue()
  app.state.storage.data = pdf
  t = app.state.db.t
  async with app.state.db.sessions.begin() as db:
    file_id = (await db.execute(insert(t.files).values(case_id=case_id, uploaded_by=owner,
      bucket="test", object_key=uuid.uuid4().hex, original_name="scan.pdf", mime_type="application/pdf",
      size_bytes=len(pdf), sha256=hashlib.sha256(pdf).hexdigest(), status="uploading",
      metadata={"category": "other", "version_id": "test"}).returning(t.files.c.id))).scalar_one()
    job_id = (await db.execute(insert(t.async_jobs).values(job_type="document_parse", resource_type="file",
      resource_id=file_id, payload={"requested_by": owner}, idempotency_key=f"parse:{file_id}:v1")
      .returning(t.async_jobs.c.id))).scalar_one()
  first_attempt = FirstAttemptOcr()
  assert await run_once(app.state.db, app.state.ai, app.state.storage, app.state.settings, first_attempt)
  assert first_attempt.calls == 2
  async with app.state.db.sessions.begin() as db:
    saved = (await db.execute(select(t.document_ocr_pages).where(
      t.document_ocr_pages.c.file_id == file_id))).mappings().all()
    assert [page["page_no"] for page in saved] == [1]
    await db.execute(update(t.async_jobs).where(t.async_jobs.c.id == job_id).values(scheduled_at=datetime.now(UTC)))
  recovery = RecoveryOcr()
  assert await run_once(app.state.db, app.state.ai, app.state.storage, app.state.settings, recovery)
  assert recovery.calls == 1
  pages = (await client.get(f"/api/v1/files/{file_id}/ocr", headers=headers)).json()
  assert [page["page_no"] for page in pages] == [1, 2]
  assert pages[0]["blocks"][0]["polygon"] == [{"x": 1, "y": 2}]


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


async def test_soft_delete_case_document_enforces_permissions_and_excludes_rag(app, client):
  headers, owner = await login(client)
  member_headers, member = await login(client)
  t = app.state.db.t
  async with app.state.db.sessions.begin() as db:
    org_id = (await db.execute(insert(t.organizations).values(name="合成律所", owner_user_id=owner).returning(t.organizations.c.id))).scalar_one()
    await db.execute(insert(t.organization_members), [
      {"org_id": org_id, "user_id": owner, "role": "owner", "status": "active"},
      {"org_id": org_id, "user_id": member, "role": "member", "status": "active"},
    ])
    case_id = (await db.execute(insert(t.cases).values(title="合成文档删除案", owner_user_id=owner, org_id=org_id).returning(t.cases.c.id))).scalar_one()

  data = b"Synthetic lease deposit breach evidence line."
  app.state.storage.data = data
  file_id = (await client.post("/api/v1/files/uploads", headers=headers, json={
    "case_id": case_id, "filename": "synthetic_doc.txt", "size_bytes": len(data),
    "mime_type": "text/plain", "sha256": hashlib.sha256(data).hexdigest(), "category": "other",
  })).json()["file_id"]
  await client.post(f"/api/v1/files/{file_id}/complete", headers=headers)
  assert await run_once(app.state.db, app.state.ai, app.state.storage, app.state.settings)
  assert await run_once(app.state.db, app.state.ai, app.state.storage, app.state.settings)

  docs = (await client.get(f"/api/v1/cases/{case_id}/documents", headers=headers)).json()
  assert len(docs) == 1
  doc_id = docs[0]["id"]
  assert (await client.get(f"/api/v1/cases/{case_id}", headers=headers)).json()["evidence_upload_status"] == "partial"

  # Other org member cannot delete a document uploaded by owner
  assert (await client.delete(f"/api/v1/cases/{case_id}/documents/{doc_id}", headers=member_headers)).status_code == 403

  # Add a queued follow-up job to confirm deletion cancels pending work too
  async with app.state.db.sessions.begin() as db:
    pending_job_id = (await db.execute(insert(t.async_jobs).values(
      job_type="document_index", resource_type="file", resource_id=file_id,
      payload={"requested_by": owner}, idempotency_key=f"index:{file_id}:pending_delete",
    ).returning(t.async_jobs.c.id))).scalar_one()

  deleted = await client.delete(f"/api/v1/cases/{case_id}/documents/{doc_id}", headers=headers)
  assert deleted.status_code == 204
  assert (await client.delete(f"/api/v1/cases/{case_id}/documents/{doc_id}", headers=headers)).status_code == 404
  assert (await client.get(f"/api/v1/cases/{case_id}/documents", headers=headers)).json() == []
  assert (await client.get(f"/api/v1/cases/{case_id}", headers=headers)).json()["evidence_upload_status"] == "not_uploaded"
  assert (await client.get(f"/api/v1/files/{file_id}", headers=headers)).status_code == 404
  assert (await client.get(f"/api/v1/files/{file_id}/download", headers=headers)).status_code == 404
  assert (await client.post(f"/api/v1/cases/{case_id}/retrieval", headers=headers, json={"query": "deposit"})).json()["sources"] == []

  async with app.state.db.sessions() as db:
    job_status = await db.scalar(select(t.async_jobs.c.status).where(t.async_jobs.c.id == pending_job_id))
    assert job_status == "cancelled"
    audit = (await db.execute(select(t.audit_logs).where(
      t.audit_logs.c.action == "file.deleted", t.audit_logs.c.resource_id == file_id,
    ))).mappings().one()
    assert audit["user_id"] == owner and audit["metadata"]["document_id"] == doc_id
