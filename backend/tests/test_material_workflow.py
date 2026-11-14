import json
import uuid
from io import BytesIO
from types import SimpleNamespace

from docx import Document
from sqlalchemy import insert, select, update

from app.worker import run_once
from tests.conftest import login, seed_case


async def seed_file(app, case_id, owner):
  t = app.state.db.t
  async with app.state.db.sessions.begin() as db:
    file_id = (await db.execute(insert(t.files).values(case_id=case_id, uploaded_by=owner,
      bucket="test", object_key=uuid.uuid4().hex, original_name="合成借款协议.txt", mime_type="text/plain",
      size_bytes=10, status="available", metadata={"parse_status": "succeeded"}).returning(t.files.c.id))).scalar_one()
    await db.execute(insert(t.doc_chunks).values(case_id=case_id, file_id=file_id, chunk_index=0,
      content="合成甲借给合成乙一万元。", page_no=1, embedding=[1.0] + [0.0] * 1535,
      embedding_model=app.state.settings.embedding_model))
  return file_id


async def test_material_revision_review_audit_and_case_isolation(app, client):
  headers, owner = await login(client)
  lawyer_headers, lawyer = await login(client)
  outsider, _ = await login(client)
  case_id = await seed_case(app, owner)
  foreign_case = await seed_case(app, lawyer)
  file_id = await seed_file(app, case_id, owner)
  foreign_file = await seed_file(app, foreign_case, lawyer)
  t = app.state.db.t
  async with app.state.db.sessions.begin() as db:
    org = (await db.execute(insert(t.organizations).values(name="合成律所", owner_user_id=owner).returning(t.organizations.c.id))).scalar_one()
    await db.execute(insert(t.organization_members), [
      {"org_id": org, "user_id": owner, "role": "owner", "status": "active"},
      {"org_id": org, "user_id": lawyer, "role": "member", "status": "active"},
    ])
    await db.execute(update(t.cases).where(t.cases.c.id == case_id).values(org_id=org))
    await db.execute(insert(t.user_profiles).values(user_id=lawyer, role_type="legal", real_name="合成律师",
      organization_name="合成律所", legal_role="律师"))
  base = f"/api/v1/cases/{case_id}/materials"
  payload = {"title": "合成借款协议", "category": "written", "purpose": "证明借贷关系", "file_ids": [file_id]}
  assert (await client.post(base, headers=headers, json=payload | {"file_ids": [foreign_file]})).status_code == 422
  response = await client.post(base, headers=headers, json=payload)
  assert response.status_code == 201, response.text
  item = response.json()
  path = f"{base}/{item['id']}"
  assert (await client.get(path, headers=outsider)).status_code == 404
  assert (await client.post(path + "/actions", headers=headers, json={"revision": 1, "action": "approve"})).status_code == 403
  async with app.state.db.sessions.begin() as db:
    await db.execute(update(t.files).where(t.files.c.id == file_id).values(metadata={"parse_status": "review_required"}))
  assert (await client.post(path + "/actions", headers=headers, json={"revision": 1, "action": "submit"})).status_code == 409
  async with app.state.db.sessions.begin() as db:
    await db.execute(update(t.files).where(t.files.c.id == file_id).values(metadata={"parse_status": "succeeded"}))
  submitted = await client.post(path + "/actions", headers=headers, json={"revision": 1, "action": "submit"})
  assert submitted.json()["status"] == "lawyer_pending", submitted.text
  assert (await client.put(path, headers=headers, json=payload | {"revision": 1})).status_code == 409
  assert (await client.put(path, headers=headers, json=payload | {"revision": 2})).status_code == 409
  assert (await client.post(path + "/actions", headers=lawyer_headers, json={"revision": 2, "action": "reject"})).status_code == 422
  rejected = await client.post(path + "/actions", headers=lawyer_headers,
    json={"revision": 2, "action": "reject", "comment": "请补充签字页"})
  assert rejected.json()["status"] == "lawyer_rejected", rejected.text
  edited = await client.put(path, headers=headers, json=payload | {"revision": 3, "description": "补充签字页"})
  assert edited.json()["status"] == "draft" and edited.json()["revision"] == 4
  assert (await client.post(path + "/actions", headers=headers, json={"revision": 4, "action": "submit"})).status_code == 200
  approved = await client.post(path + "/actions", headers=lawyer_headers, json={"revision": 5, "action": "approve", "comment": "已核验"})
  assert approved.json()["status"] == "lawyer_approved", approved.text
  detail = (await client.get(f"/api/v1/cases/{case_id}", headers=headers)).json()
  assert detail["evidence_upload_status"] == "completed" and detail["win_rate"] is None
  async with app.state.db.sessions.begin() as db:
    document_id = (await db.execute(insert(t.case_documents).values(case_id=case_id,
      file_id=file_id, title="合成借款协议", category="other", uploaded_by=owner).returning(t.case_documents.c.id))).scalar_one()
  deleted = await client.delete(f"/api/v1/cases/{case_id}/documents/{document_id}", headers=headers)
  assert deleted.status_code == 204
  assert (await client.get(f"/api/v1/cases/{case_id}", headers=headers)).json()["evidence_upload_status"] == "partial"
  assert (await client.post(path + "/actions", headers=headers, json={"revision": 6, "action": "withdraw"})).status_code == 200
  history = (await client.get(path + "/events", headers=headers)).json()
  assert [event["action"] for event in history] == ["withdraw", "approve", "submit", "edited", "reject", "submit", "created"]
  assert history[0]["snapshot"]["file_ids"] == [file_id]
  async with app.state.db.sessions.begin() as db:
    await db.execute(update(t.organization_members).where(t.organization_members.c.user_id == lawyer).values(status="removed"))
  assert (await client.get(path, headers=lawyer_headers)).status_code == 404


async def test_generated_draft_revision_export_and_source_revocation(app, client):
  headers, owner = await login(client)
  outsider, _ = await login(client)
  case_id = await seed_case(app, owner)
  file_id = await seed_file(app, case_id, owner)
  async def complete(messages):
    return SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=json.dumps({
      "title": "合成证据目录", "body": "一、合成借款协议 [1]\n证明目的：证明借贷关系。", "limitations": "仅依据当前召回材料。",
    }, ensure_ascii=False)))], usage=None)
  app.state.ai.complete_json = complete
  response = await client.post(f"/api/v1/cases/{case_id}/analyses", headers=headers,
    json={"analysis_type": "evidence_catalog", "client_request_id": uuid.uuid4().hex})
  assert response.status_code == 202, response.text
  assert await run_once(app.state.db, app.state.ai, app.state.storage, app.state.settings)
  path = f"/api/v1/cases/{case_id}/drafts/{response.json()['analysis_id']}"
  detail = (await client.get(path, headers=headers)).json()
  assert detail["analysis"]["status"] == "succeeded", detail
  assert detail["revisions"][0]["revision"] == 1
  assert (await client.get(path, headers=outsider)).status_code == 404
  body = "经编辑的证据目录 [1]\n证明目的：证明借贷关系及本金交付。"
  saved = await client.put(path, headers=headers, json={"expected_revision": 1, "title": "编辑后的合成证据目录", "body": body})
  assert saved.json()["revision"] == 2, saved.text
  assert (await client.put(path, headers=headers, json={"expected_revision": 1, "title": "旧版本", "body": body})).status_code == 409
  exported = await client.get(path + "/export?revision=2", headers=headers)
  assert exported.status_code == 200, exported.text if exported.status_code != 200 else ""
  document = Document(BytesIO(exported.content))
  text = "\n".join(p.text for p in document.paragraphs)
  assert "编辑后的合成证据目录" in text and body.splitlines()[0] in text
  assert "AI 辅助草稿" in text and "合成借款协议.txt" in text and "材料指纹" in text
  original = await client.get(path + "/export?revision=1", headers=headers)
  assert "编辑后的合成证据目录" not in "\n".join(p.text for p in Document(BytesIO(original.content)).paragraphs)
  async with app.state.db.sessions.begin() as db:
    await db.execute(update(app.state.db.t.files).where(app.state.db.t.files.c.id == file_id).values(status="deleted"))
  assert (await client.get(path + "/export?revision=2", headers=headers)).status_code == 409


async def test_material_advice_only_uses_linked_files_and_preserves_human_status(app, client):
  headers, owner = await login(client)
  case_id = await seed_case(app, owner)
  file_id = await seed_file(app, case_id, owner)
  unrelated = await seed_file(app, case_id, owner)
  base = f"/api/v1/cases/{case_id}"
  item = (await client.post(base + "/materials", headers=headers, json={"title": "合成协议", "purpose": "证明借贷关系", "category": "written", "file_ids": [file_id]})).json()
  async def complete(messages):
    return SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=json.dumps({
      "summary": "借款协议说明借贷关系 [1]", "strengths": ["书面约定 [1]"], "issues": [], "suggestions": ["核验原件"], "limitations": "不替代律师复核",
    }, ensure_ascii=False)))], usage=None)
  app.state.ai.complete_json = complete
  created = await client.post(base + "/analyses", headers=headers, json={"analysis_type": "material_review", "material_id": item["id"], "client_request_id": uuid.uuid4().hex})
  assert created.status_code == 202, created.text
  await run_once(app.state.db, app.state.ai, app.state.storage, app.state.settings)
  report = (await client.get(base + f"/analyses/{created.json()['analysis_id']}", headers=headers)).json()
  assert report["status"] == "succeeded", report
  assert {source["file_id"] for source in report["sources"]} == {file_id}
  assert unrelated not in {source["file_id"] for source in report["sources"]}
  material = (await client.get(base + f"/materials/{item['id']}", headers=headers)).json()
  assert material["status"] == "draft" and material["reviewed_by"] is None
  stale = await client.post(base + "/analyses", headers=headers, json={"analysis_type": "material_review", "material_id": item["id"], "client_request_id": uuid.uuid4().hex})
  assert stale.status_code == 202
  changed = await client.put(base + f"/materials/{item['id']}", headers=headers,
    json={"title": "修改后的协议", "purpose": "证明修改后的事实", "category": "written", "file_ids": [file_id], "revision": 1})
  assert changed.status_code == 200
  await run_once(app.state.db, app.state.ai, app.state.storage, app.state.settings)
  stale_report = (await client.get(base + f"/analyses/{stale.json()['analysis_id']}", headers=headers)).json()
  assert stale_report["status"] == "failed" and stale_report["error_message"] == "material_changed"
  latest = (await client.get(base + f"/materials/{item['id']}", headers=headers)).json()
  assert latest["ai_analysis_id"] is None and latest["revision"] == 2
  async with app.state.db.sessions() as db:
    assert (await db.execute(select(app.state.db.t.cases.c.win_rate).where(app.state.db.t.cases.c.id == case_id))).scalar_one() is None
