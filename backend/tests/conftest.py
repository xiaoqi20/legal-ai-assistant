import uuid
from types import SimpleNamespace

import httpx
import pytest_asyncio
from pydantic import SecretStr
from sqlalchemy.engine import make_url

from app.config import Settings
from app.main import create_app


class FakeAI:
  """Only injected by tests. Production never imports this adapter."""
  mode = "ok"

  def check(self, **kwargs):
    pass

  def check_rerank(self):
    pass

  async def rerank(self, query, documents, *, top_n=None):
    limit = min(len(documents), top_n or len(documents))
    return [(i, max(0.0, 1.0 - i * 0.05)) for i in range(limit)]

  async def close(self):
    pass

  async def complete_json(self, messages, **_kwargs):
    self.last_messages = messages
    content = {"parties": [{"label": "原告", "value": "合成甲"}],
      "facts": ["合成合同事实 [1]"], "requests": [], "limitations": "仅依据召回片段，待人工核验"}
    return SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop",
      message=SimpleNamespace(content=__import__("json").dumps(content, ensure_ascii=False)))],
      usage=SimpleNamespace(prompt_tokens=120, completion_tokens=40))

  async def embed(self, texts):
    return [[1.0] + [0.0] * 1535 for _ in texts]

  async def stream(self, messages):
    self.last_messages = messages
    if self.mode == "error":
      raise RuntimeError("sensitive-upstream-error-must-not-leak")
    if self.mode == "slow":
      import asyncio
      await asyncio.sleep(10)
    for text in ("根据现有信息，", "合同约定价款为100万元。" + ("[1]" if any('"citation"' in m["content"] for m in messages) else "")):
      yield SimpleNamespace(usage=None, choices=[SimpleNamespace(
        delta=SimpleNamespace(content=text), finish_reason=None)])
    yield SimpleNamespace(usage=SimpleNamespace(prompt_tokens=100, completion_tokens=30),
      choices=[SimpleNamespace(delta=SimpleNamespace(content=None), finish_reason="length" if self.mode == "length" else "stop")])


class FakeStorage:
  data = b"Synthetic contract price CNY 1000000."

  async def upload_url(self, row):
    return {"url": "http://storage.invalid", "fields": {"key": row["object_key"]}}

  async def head(self, row):
    return {"ContentLength": row["size_bytes"], "ContentType": row["mime_type"], "VersionId": "test-version", "Metadata": {"sha256": row["sha256"]}}

  async def read(self, row):
    return self.data

  async def download_url(self, row):
    return "http://storage.invalid/signed"


@pytest_asyncio.fixture
async def app():
  # Never run integration tests against law_dev or any non-test database.
  configured = Settings(_env_file=".env.test")
  if not make_url(configured.database_url.get_secret_value()).database.endswith("_test"):
    raise RuntimeError("请配置专用 *_test 数据库后运行测试")
  # This explicitly configured disposable test database is reset for every scenario.
  from unittest.mock import patch

  import psycopg
  from alembic import command
  from alembic.config import Config
  url = configured.database_url.get_secret_value()
  with psycopg.connect(make_url(url).set(drivername="postgresql").render_as_string(hide_password=False), autocommit=True) as conn:
    conn.execute("DROP SCHEMA IF EXISTS law CASCADE")
    conn.execute("DROP TABLE IF EXISTS public.alembic_version")
  with patch("app.config.get_settings", return_value=configured):
    command.upgrade(Config("alembic.ini"), "head")
  settings = Settings(_env_file=None, env="test", database_url=configured.database_url,
    allow_dev_login=True, deepseek_api_key=SecretStr("test"), embedding_api_key=SecretStr("test"),
    tool_calling_enabled=False,
    input_usd_per_million="1", output_usd_per_million="2")
  application = create_app(settings)
  async with application.router.lifespan_context(application):
    await application.state.ai.close()
    application.state.ai = FakeAI()
    application.state.storage = FakeStorage()
    yield application
    # lifespan closes adapter using same interface


@pytest_asyncio.fixture
async def client(app):
  async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
    yield c


async def login(client):
  response = await client.post("/api/v1/auth/dev-login", json={"identity": uuid.uuid4().hex, "agreed": True})
  assert response.status_code == 200, response.text
  payload = response.json()
  return {"Authorization": "Bearer " + payload["access_token"]}, payload["user_id"]


async def seed_case(app, owner):
  from sqlalchemy import insert
  t = app.state.db.t
  async with app.state.db.sessions.begin() as db:
    return (await db.execute(insert(t.cases).values(owner_user_id=owner, title="合成案件").returning(t.cases.c.id))).scalar_one()
