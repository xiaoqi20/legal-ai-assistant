"""Opt-in real MinIO test, while keeping all business rows in the disposable test DB."""
import asyncio
import hashlib
import os

import httpx
import pytest
from sqlalchemy import select

from app.config import Settings
from app.services.storage import Storage
from app.worker import run_once
from tests.conftest import login, seed_case


@pytest.mark.skipif(os.getenv("LAW_TEST_S3") != "1", reason="设置 LAW_TEST_S3=1 验证本地真实 S3")
async def test_real_private_upload_version_pin_and_download(app, client):
  storage = Storage(Settings())
  app.state.storage = storage
  headers, owner = await login(client)
  case_id = await seed_case(app, owner)
  data = "【合成材料】甲乙约定合同价款100万元，已付80万元。".encode()
  uploaded = await client.post("/api/v1/files/uploads", headers=headers, json={
    "case_id": case_id, "filename": "合成合同.txt", "size_bytes": len(data),
    "mime_type": "text/plain", "sha256": hashlib.sha256(data).hexdigest(),
  })
  assert uploaded.status_code == 201, uploaded.text
  file_id, upload = uploaded.json()["file_id"], uploaded.json()["upload"]
  async with httpx.AsyncClient() as http:
    result = await http.post(upload["url"], data=upload["fields"], files={"file": ("合成合同.txt", data, "text/plain")})
    assert result.status_code == 204, result.text
    assert (await client.post(f"/api/v1/files/{file_id}/complete", headers=headers)).status_code == 200
    async with app.state.db.sessions() as db:
      row = dict((await db.execute(select(app.state.db.t.files).where(app.state.db.t.files.c.id == file_id))).mappings().one())
    assert row["metadata"]["version_id"]
    # Same key is overwritten after completion: download and indexing must still use pinned original.
    await asyncio.to_thread(storage.client.put_object, Bucket=row["bucket"], Key=row["object_key"], Body=b"overwritten", ContentType="text/plain")
    assert await run_once(app.state.db, app.state.ai, storage, app.state.settings)
    state = (await client.get(f"/api/v1/files/{file_id}", headers=headers)).json()
    assert state["status"] == "available", state
    url = (await client.get(f"/api/v1/files/{file_id}/download", headers=headers)).json()["url"]
    assert (await http.get(url)).content == data
    unsigned = f"{storage.settings.s3_endpoint_url}/{row['bucket']}/{row['object_key']}"
    assert (await http.get(unsigned)).status_code == 403
    cors = await http.options(unsigned, headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
    assert cors.headers["access-control-allow-origin"] == "http://localhost:5173"
    # Remove both synthetic versions; only this test's random key is touched.
    versions = await asyncio.to_thread(storage.client.list_object_versions, Bucket=row["bucket"], Prefix=row["object_key"])
    for version in versions.get("Versions", []):
      await asyncio.to_thread(storage.client.delete_object, Bucket=row["bucket"], Key=version["Key"], VersionId=version["VersionId"])
