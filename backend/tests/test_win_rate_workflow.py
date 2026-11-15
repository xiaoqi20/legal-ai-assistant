import hashlib
import json
import uuid
from types import SimpleNamespace

from sqlalchemy import insert, select

from app.worker import run_once
from tests.conftest import login


async def _seed_ready_file(app, case_id: int, owner: int, text: str = "借款协议与转账凭证确认已交付十万元。"):
  t = app.state.db.t
  async with app.state.db.sessions.begin() as db:
    file_id = (await db.execute(insert(t.files).values(
      case_id=case_id,
      uploaded_by=owner,
      bucket=app.state.settings.s3_bucket,
      object_key=f"test/{uuid.uuid4().hex}.txt",
      original_name="证据材料.txt",
      mime_type="text/plain",
      size_bytes=len(text.encode()),
      sha256=hashlib.sha256(text.encode()).hexdigest(),
      status="available",
      metadata={"parse_status": "succeeded", "chunk_count": 1, "category": "other"},
    ).returning(t.files.c.id))).scalar_one()
    doc_id = (await db.execute(insert(t.case_documents).values(
      case_id=case_id, file_id=file_id, title="证据材料.txt", uploaded_by=owner, category="other",
    ).returning(t.case_documents.c.id))).scalar_one()
    await db.execute(insert(t.doc_chunks).values(
      case_id=case_id, file_id=file_id, chunk_index=0, content=text,
      token_count=20, embedding=[1.0] + [0.0] * 1535, embedding_model=app.state.settings.embedding_model,
    ))
    return file_id, doc_id


def _win_rate_payload(fund_grade="proven", fund_ranks=None):
  return {
    "cause_code": "private_lending",
    "claims": [{"index": 0, "title": "偿还借款本金10万元", "amount_yuan": 100000.0, "priority_weight": 1.0}],
    "elements": [
      {"key": "lending_intent", "label": "借贷合意", "grade": "proven", "citation_ranks": [1], "summary": "书面协议 [1]"},
      {"key": "fund_delivery", "label": "款项实际交付", "grade": fund_grade,
       "citation_ranks": fund_ranks if fund_ranks is not None else [1], "summary": "凭证 [1]"},
      {"key": "maturity_breach", "label": "借期届满及逾期未还", "grade": "proven", "citation_ranks": [1], "summary": "到期未付 [1]"},
      {"key": "interest_agreement", "label": "利息与违约金约定", "grade": "proven", "citation_ranks": [1], "summary": "利率条款 [1]"},
    ],
    "defeaters": [],
    "positive_factors": ["书面协议与交付凭证相互印证"],
    "negative_factors": [],
    "missing_evidence": [],
    "limitations": "仅依据当前已提交材料",
  }


async def test_win_rate_full_flow_decoupling_and_invalidation(app, client):
  headers, owner = await login(client)
  other_headers, _ = await login(client)
  created_case = await client.post("/api/v1/cases", headers=headers, json={
    "title": "民间借贷测试案",
    "case_type": "civil",
    "procedure": "first_instance",
    "summary": "出借人已交付十万元借款，到期未还",
    "claim": "判令被告归还借款本金10万元",
    "handling_identity": "self",
    "party_role_label": "原告",
    "our_parties": ["张三"],
    "opponent_parties": ["李四"],
  })
  assert created_case.status_code == 201, created_case.text
  case_id = created_case.json()["id"]
  _, doc_id = await _seed_ready_file(app, case_id, owner)

  async def complete(messages):
    return SimpleNamespace(
      choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=json.dumps(_win_rate_payload(), ensure_ascii=False)))],
      usage=SimpleNamespace(prompt_tokens=150, completion_tokens=80),
    )

  app.state.ai.complete_json = complete

  # Cross-user access blocked with 404
  forbidden = await client.post(f"/api/v1/cases/{case_id}/analyses", headers=other_headers,
    json={"analysis_type": "win_rate", "client_request_id": uuid.uuid4().hex})
  assert forbidden.status_code == 404

  queued = await client.post(f"/api/v1/cases/{case_id}/analyses", headers=headers,
    json={"analysis_type": "win_rate", "client_request_id": uuid.uuid4().hex})
  assert queued.status_code == 202, queued.text
  analysis_id = queued.json()["analysis_id"]

  # analysis_status stays independent of win_rate_status
  during = (await client.get(f"/api/v1/cases/{case_id}", headers=headers)).json()
  assert during["win_rate_status"] == "analyzing"
  assert during["analysis_status"] == "not_analyzed"

  await run_once(app.state.db, app.state.ai, app.state.storage, app.state.settings)

  after = (await client.get(f"/api/v1/cases/{case_id}", headers=headers)).json()
  assert after["win_rate_status"] == "analyzed"
  assert after["win_rate_analysis_id"] == analysis_id
  assert after["win_rate"] is not None and 5.0 <= float(after["win_rate"]) <= 95.0
  assert after["analysis_status"] == "not_analyzed"

  detail = (await client.get(f"/api/v1/cases/{case_id}/analyses/{analysis_id}", headers=headers)).json()
  assert detail["status"] == "succeeded"
  assert detail["content"]["applicable"] is True
  assert detail["content"]["metric_kind"] == "uncalibrated_rubric"
  assert len(detail["sources"]) == 1

  # Optional precedent reference enrichment attaches cleanly without changing metric_kind
  import pathlib
  ref_path = pathlib.Path("/tmp") / f"law_ref_{uuid.uuid4().hex}.jsonl"
  try:
    ref_path.write_text(json.dumps({
      "doc_id": "SYN-1",
      "cause_code": "private_lending",
      "claimed_amount_yuan": 100000.0,
      "outcome_label": "fully_supported",
      "case_win": True,
      "win_rate_prediction": {
        "raw_support_score": 88.0,
        "elements": _win_rate_payload()["elements"],
        "defeaters": [],
      },
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    app.state.settings.precedent_reference_path = str(ref_path)
    queued2 = await client.post(f"/api/v1/cases/{case_id}/analyses", headers=headers,
      json={"analysis_type": "win_rate", "client_request_id": uuid.uuid4().hex})
    assert queued2.status_code == 202
    await run_once(app.state.db, app.state.ai, app.state.storage, app.state.settings)
    detail2 = (await client.get(f"/api/v1/cases/{case_id}/analyses/{queued2.json()['analysis_id']}", headers=headers)).json()
    assert detail2["content"]["metric_kind"] == "uncalibrated_rubric"
    assert detail2["content"]["precedent_reference"]["pool_count"] == 1
    assert detail2["content"]["precedent_reference"]["outcome_counts"]["fully_supported"] == 1
  finally:
    app.state.settings.precedent_reference_path = None
    ref_path.unlink(missing_ok=True)

  # Deleting document atomically invalidates win_rate
  deleted = await client.delete(f"/api/v1/cases/{case_id}/documents/{doc_id}", headers=headers)
  assert deleted.status_code == 204
  reset = (await client.get(f"/api/v1/cases/{case_id}", headers=headers)).json()
  assert reset["win_rate"] is None
  assert reset["win_rate_status"] == "not_analyzed"
  assert reset["win_rate_analysis_id"] is None


async def test_win_rate_abstains_on_non_civil_and_excludes_rejected_material(app, client):
  headers, owner = await login(client)
  non_civil = await client.post("/api/v1/cases", headers=headers, json={
    "title": "刑事测试", "case_type": "criminal", "procedure": "first_instance", "party_role_label": "辩护人", "claim": "无罪辩护",
  })
  nc_id = non_civil.json()["id"]
  await _seed_ready_file(app, nc_id, owner)
  req = await client.post(f"/api/v1/cases/{nc_id}/analyses", headers=headers,
    json={"analysis_type": "win_rate", "client_request_id": uuid.uuid4().hex})
  assert req.status_code == 202
  await run_once(app.state.db, app.state.ai, app.state.storage, app.state.settings)
  nc_detail = (await client.get(f"/api/v1/cases/{nc_id}", headers=headers)).json()
  assert nc_detail["win_rate"] is None and nc_detail["win_rate_status"] == "not_applicable"
  report = (await client.get(f"/api/v1/cases/{nc_id}/analyses/{req.json()['analysis_id']}", headers=headers)).json()
  assert report["content"]["applicable"] is False and report["content"]["reason_code"] == "non_civil_case"

  # Rejected evidence item leaves no usable file if only linked file is rejected -> not_applicable
  civil = await client.post("/api/v1/cases", headers=headers, json={
    "title": "退回测试", "case_type": "civil", "procedure": "first_instance", "party_role_label": "原告", "claim": "还款",
  })
  cid = civil.json()["id"]
  fid, _ = await _seed_ready_file(app, cid, owner)
  async with app.state.db.sessions.begin() as db:
    t = app.state.db.t
    mid = (await db.execute(insert(t.evidence_items).values(
      case_id=cid, title="瑕疵凭证", purpose="证明转账", category="written", status="lawyer_rejected", uploader_user_id=owner,
    ).returning(t.evidence_items.c.id))).scalar_one()
    await db.execute(insert(t.evidence_item_files).values(case_id=cid, evidence_item_id=mid, file_id=fid, sort_order=0))
  req2 = await client.post(f"/api/v1/cases/{cid}/analyses", headers=headers,
    json={"analysis_type": "win_rate", "client_request_id": uuid.uuid4().hex})
  await run_once(app.state.db, app.state.ai, app.state.storage, app.state.settings)
  rej_detail = (await client.get(f"/api/v1/cases/{cid}", headers=headers)).json()
  assert rej_detail["win_rate_status"] == "not_applicable"
  rej_rep = (await client.get(f"/api/v1/cases/{cid}/analyses/{req2.json()['analysis_id']}", headers=headers)).json()
  assert rej_rep["content"]["reason_code"] == "all_materials_rejected"


async def test_win_rate_discards_stale_write_when_inputs_mutate_inflight_and_cancel(app, client):
  headers, owner = await login(client)
  case_res = await client.post("/api/v1/cases", headers=headers, json={
    "title": "并发失效测试", "case_type": "civil", "procedure": "first_instance", "party_role_label": "原告", "claim": "归还十万元",
  })
  cid = case_res.json()["id"]
  fid, _ = await _seed_ready_file(app, cid, owner)

  # Cancel restores not_analyzed cleanly
  c_req = await client.post(f"/api/v1/cases/{cid}/analyses", headers=headers,
    json={"analysis_type": "win_rate", "client_request_id": uuid.uuid4().hex})
  assert c_req.status_code == 202
  cancelled = await client.post(f"/api/v1/cases/{cid}/analyses/{c_req.json()['analysis_id']}/cancel", headers=headers)
  assert cancelled.status_code == 200
  assert (await client.get(f"/api/v1/cases/{cid}", headers=headers)).json()["win_rate_status"] == "not_analyzed"

  # Mutate material mid-flight inside complete_json -> fingerprint mismatch discards stale write
  req = await client.post(f"/api/v1/cases/{cid}/analyses", headers=headers,
    json={"analysis_type": "win_rate", "client_request_id": uuid.uuid4().hex})
  aid = req.json()["analysis_id"]

  async def mutate_inflight(messages):
    async with app.state.db.sessions.begin() as db:
      t = app.state.db.t
      await db.execute(insert(t.evidence_items).values(
        case_id=cid, title="新增材料", purpose="补强转账", category="written", status="draft", uploader_user_id=owner,
      ))
    return SimpleNamespace(
      choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=json.dumps(_win_rate_payload(), ensure_ascii=False)))],
      usage=None,
    )

  app.state.ai.complete_json = mutate_inflight
  await run_once(app.state.db, app.state.ai, app.state.storage, app.state.settings)

  case_after = (await client.get(f"/api/v1/cases/{cid}", headers=headers)).json()
  assert case_after["win_rate"] is None
  assert case_after["win_rate_status"] == "not_analyzed"
  async with app.state.db.sessions() as db:
    t = app.state.db.t
    row = (await db.execute(select(t.case_analyses).where(t.case_analyses.c.id == aid))).mappings().one()
    assert row["status"] == "cancelled" and row["error_message"] == "stale_inputs"
