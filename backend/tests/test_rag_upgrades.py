import json
import uuid
from types import SimpleNamespace

import httpx
import instructor
import pytest
from fastapi import HTTPException
from openai import AsyncOpenAI
from pydantic import SecretStr
from ragas.embeddings.base import embedding_factory
from ragas.llms import llm_factory
from sqlalchemy import insert, select

from app.config import Settings
from app.services.ai import AI, extract_cache_usage
from app.services.rag import build_context
from app.worker import run_once
from scripts.eval_rag import (
  DEFAULT_DATASET,
  evaluate_citations_only,
  evaluate_dataset,
  load_dataset,
  main,
)
from tests.conftest import login, seed_case


def _parse_sse(text: str) -> list[tuple[str, dict]]:
  events = []
  for block in text.strip().split("\n\n"):
    lines = block.splitlines()
    if len(lines) >= 2 and lines[0].startswith("event:") and lines[1].startswith("data:"):
      events.append((lines[0][6:].strip(), json.loads(lines[1][5:].strip())))
  return events


async def test_rerank_siliconflow_and_dashscope_contracts():
  seen_requests = []

  def siliconflow_handler(request: httpx.Request) -> httpx.Response:
    seen_requests.append((str(request.url), request.headers.get("authorization"), json.loads(request.content)))
    return httpx.Response(200, json={
      "results": [
        {"index": 1, "relevance_score": 0.94},
        {"index": 0, "relevance_score": 0.41},
      ],
    })

  sf_settings = Settings(
    _env_file=None, env="test",
    database_url=SecretStr("postgresql+asyncpg://u:p@127.0.0.1:5432/law_test"),
    rerank_enabled=True, rerank_api_key=SecretStr("sf-secret"),
    rerank_base_url="https://api.siliconflow.cn/v1/rerank",
    rerank_model="BAAI/bge-reranker-v2-m3",
  )
  sf_ai = AI(sf_settings)
  await sf_ai.reranker.aclose()
  sf_ai.reranker = httpx.AsyncClient(transport=httpx.MockTransport(siliconflow_handler))
  try:
    ranked = await sf_ai.rerank("违约金怎么算", ["证据一", "证据二", "证据三"], top_n=2)
  finally:
    await sf_ai.close()

  assert ranked == [(1, 0.94), (0, 0.41)]
  assert seen_requests[0][0] == "https://api.siliconflow.cn/v1/rerank"
  assert seen_requests[0][1] == "Bearer sf-secret"
  assert seen_requests[0][2] == {
    "model": "BAAI/bge-reranker-v2-m3",
    "query": "违约金怎么算",
    "documents": ["证据一", "证据二", "证据三"],
    "top_n": 2,
    "return_documents": False,
  }

  seen_requests.clear()

  def dashscope_handler(request: httpx.Request) -> httpx.Response:
    seen_requests.append((str(request.url), json.loads(request.content)))
    return httpx.Response(200, json={
      "output": {
        "results": [
          {"index": 0, "relevance_score": 0.35},
          {"index": 2, "relevance_score": 0.89},
        ],
      },
    })

  ds_settings = Settings(
    _env_file=None, env="test",
    database_url=SecretStr("postgresql+asyncpg://u:p@127.0.0.1:5432/law_test"),
    rerank_enabled=True, rerank_api_key=SecretStr("ds-secret"),
    rerank_base_url="https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank",
    rerank_model="gte-rerank-v2",
  )
  ds_ai = AI(ds_settings)
  await ds_ai.reranker.aclose()
  ds_ai.reranker = httpx.AsyncClient(transport=httpx.MockTransport(dashscope_handler))
  try:
    ranked = await ds_ai.rerank("解除合同条件", ["A", "B", "C"], top_n=2)
  finally:
    await ds_ai.close()

  assert ranked == [(2, 0.89), (0, 0.35)]
  assert seen_requests[0][1] == {
    "model": "gte-rerank-v2",
    "input": {"query": "解除合同条件", "documents": ["A", "B", "C"]},
    "parameters": {"top_n": 2, "return_documents": False},
  }

  missing_key = AI(Settings(
    _env_file=None, env="test",
    database_url=SecretStr("postgresql+asyncpg://u:p@127.0.0.1:5432/law_test"),
    deepseek_api_key=SecretStr("k"), embedding_api_key=SecretStr("k"),
    rerank_enabled=True, rerank_api_key=SecretStr(""),
  ))
  try:
    with pytest.raises(HTTPException) as exc:
      missing_key.check(rerank=True)
    assert exc.value.status_code == 503
    assert exc.value.detail["code"] == "rerank_not_configured"
  finally:
    await missing_key.close()

  with pytest.raises(ValueError):
    Settings(
      _env_file=None, env="test",
      database_url=SecretStr("postgresql+asyncpg://u:p@127.0.0.1:5432/law_test"),
      rerank_enabled=True, retrieval_top_k=10, rerank_candidates=5,
    )


async def test_retrieve_rerank_reorders_real_postgres_candidates(app, client):
  headers, owner = await login(client)
  case_id = await seed_case(app, owner)
  t = app.state.db.t
  async with app.state.db.sessions.begin() as db:
    file_id = (await db.execute(insert(t.files).values(
      case_id=case_id, uploaded_by=owner, bucket="test", object_key=uuid.uuid4().hex,
      original_name="contract.txt", mime_type="text/plain", size_bytes=128, status="available",
    ).returning(t.files.c.id))).scalar_one()
    await db.execute(insert(t.doc_chunks), [
      {
        "file_id": file_id, "case_id": case_id, "chunk_index": 0, "page_no": 1,
        "content": "一般陈述：补充交易沟通记录，暂未讨论违约赔偿标准。",
        "embedding": [1.0] + [0.0] * 1535, "embedding_model": app.state.settings.embedding_model,
      },
      {
        "file_id": file_id, "case_id": case_id, "chunk_index": 1, "page_no": 2,
        "content": "付款条款：验收后15日内支付尾款。",
        "embedding": [0.85, 0.52] + [0.0] * 1534, "embedding_model": app.state.settings.embedding_model,
      },
      {
        "file_id": file_id, "case_id": case_id, "chunk_index": 2, "page_no": 3,
        "content": "补偿条款：一方迟延履行导致合同无法继续的，按日万分之五支付滞纳补偿金。",
        "embedding": [0.70, 0.71] + [0.0] * 1534, "embedding_model": app.state.settings.embedding_model,
      },
    ])

  before = await client.post(f"/api/v1/cases/{case_id}/retrieval", headers=headers, json={"query": "违约赔偿"})
  assert before.status_code == 200, before.text
  assert before.json()["strategy"] == "pgvector_cosine+pg_trgm_rrf_v1"
  assert "一般陈述" in before.json()["sources"][0]["quote"]

  app.state.settings.rerank_enabled = True
  missing = await client.post(f"/api/v1/cases/{case_id}/retrieval", headers=headers, json={"query": "违约赔偿"})
  assert missing.status_code == 503
  assert missing.json()["error"]["code"] == "rerank_not_configured"

  app.state.settings.rerank_api_key = SecretStr("test-rerank")
  rerank_ai = AI(app.state.settings)
  rerank_ai.embed = app.state.ai.embed

  def rerank_handler(request: httpx.Request) -> httpx.Response:
    docs = json.loads(request.content)["documents"]
    target_idx = next(i for i, doc in enumerate(docs) if "补偿条款" in doc)
    other_idxs = [i for i in range(len(docs)) if i != target_idx]
    results = [{"index": target_idx, "relevance_score": 0.96}]
    for offset, idx in enumerate(other_idxs):
      results.append({"index": idx, "relevance_score": round(0.4 - offset * 0.1, 2)})
    return httpx.Response(200, json={"results": results})

  await rerank_ai.reranker.aclose()
  rerank_ai.reranker = httpx.AsyncClient(transport=httpx.MockTransport(rerank_handler))
  await app.state.ai.close()
  app.state.ai = rerank_ai

  after = await client.post(f"/api/v1/cases/{case_id}/retrieval", headers=headers, json={"query": "违约赔偿"})
  assert after.status_code == 200, after.text
  payload = after.json()
  assert payload["strategy"] == "pgvector_cosine+pg_trgm_rrf+bge_rerank_v1"
  assert "补偿条款" in payload["sources"][0]["quote"]
  assert payload["sources"][0]["rank"] == 1
  assert payload["sources"][0]["relevance"] == 0.96


def test_extract_cache_usage_variants():
  ds_usage = SimpleNamespace(
    prompt_tokens=200, completion_tokens=30,
    prompt_cache_hit_tokens=160, prompt_cache_miss_tokens=40,
  )
  assert extract_cache_usage(ds_usage) == {"cached_tokens": 160, "cache_miss_tokens": 40}

  bailian_usage = {
    "prompt_tokens": 300,
    "completion_tokens": 20,
    "prompt_tokens_details": {"cached_tokens": 256},
  }
  assert extract_cache_usage(bailian_usage) == {"cached_tokens": 256}
  assert extract_cache_usage(SimpleNamespace(prompt_tokens=50, completion_tokens=10)) == {}


async def test_prompt_caching_prefix_stability_and_telemetry(app, client):
  headers, owner = await login(client)
  case_id = await seed_case(app, owner)
  t = app.state.db.t
  async with app.state.db.sessions.begin() as db:
    file_id = (await db.execute(insert(t.files).values(
      case_id=case_id, uploaded_by=owner, bucket="test", object_key=uuid.uuid4().hex,
      original_name="evidence.txt", mime_type="text/plain", size_bytes=64, status="available",
    ).returning(t.files.c.id))).scalar_one()
    await db.execute(insert(t.doc_chunks).values(
      file_id=file_id, case_id=case_id, chunk_index=0, page_no=1,
      content="设备验收后应当在10日内支付剩余价款。",
      embedding=[1.0] + [0.0] * 1535, embedding_model=app.state.settings.embedding_model,
    ))

  conv_res = await client.post("/api/v1/conversations", headers=headers, json={"case_id": case_id})
  assert conv_res.status_code == 201
  conv_id = conv_res.json()["id"]

  captured_turns = []
  turn_usages = [
    SimpleNamespace(prompt_tokens=150, completion_tokens=20, prompt_cache_hit_tokens=96, prompt_cache_miss_tokens=54),
    SimpleNamespace(prompt_tokens=210, completion_tokens=25, prompt_tokens_details={"cached_tokens": 180}),
  ]

  async def fake_stream(messages):
    idx = len(captured_turns)
    captured_turns.append(messages)
    yield SimpleNamespace(usage=None, choices=[SimpleNamespace(delta=SimpleNamespace(content="依据证据 [1]，应当支付剩余价款。"), finish_reason=None)])
    yield SimpleNamespace(usage=turn_usages[idx], choices=[SimpleNamespace(delta=SimpleNamespace(content=None), finish_reason="stop")])

  app.state.ai.stream = fake_stream

  r1 = await client.post(
    f"/api/v1/conversations/{conv_id}/messages/stream", headers=headers,
    json={"content": "第一问：何时付款？", "client_message_id": "turn-1"},
  )
  assert r1.status_code == 200
  done1 = dict(_parse_sse(r1.text))["done"]
  assert done1["usage"] == {"input_tokens": 150, "output_tokens": 20, "cached_tokens": 96, "cache_miss_tokens": 54}

  r2 = await client.post(
    f"/api/v1/conversations/{conv_id}/messages/stream", headers=headers,
    json={"content": "第二问：逾期怎么算？", "client_message_id": "turn-2"},
  )
  assert r2.status_code == 200
  done2 = dict(_parse_sse(r2.text))["done"]
  assert done2["usage"] == {"input_tokens": 210, "output_tokens": 25, "cached_tokens": 180}

  assert len(captured_turns) == 2
  m1, m2 = captured_turns
  # System prompt and growing history prefix remain free of dynamic retrieved JSON.
  assert m1[0] == m2[0]
  assert '"citation"' not in m1[0]["content"]
  assert '"citation"' in m1[-1]["content"] and '"citation"' in m2[-1]["content"]
  assert m2[1] == {"role": "user", "content": "第一问：何时付款？"}
  assert m2[2] == {"role": "assistant", "content": "依据证据 [1]，应当支付剩余价款。"}

  async with app.state.db.sessions() as db:
    rows = (await db.execute(
      select(t.ai_messages.c.id, t.ai_messages.c.metadata)
      .where(t.ai_messages.c.conversation_id == conv_id, t.ai_messages.c.role == "assistant")
      .order_by(t.ai_messages.c.seq)
    )).mappings().all()
  assert rows[0]["metadata"] == {"prompt_cache": {"cached_tokens": 96, "cache_miss_tokens": 54}}
  assert rows[1]["metadata"] == {"prompt_cache": {"cached_tokens": 180}}

  # Analysis workflow keeps system prompt + JSON schema instruction as shared prefix across cases.
  case_two = await seed_case(app, owner)
  async with app.state.db.sessions.begin() as db:
    file_two = (await db.execute(insert(t.files).values(
      case_id=case_two, uploaded_by=owner, bucket="test", object_key=uuid.uuid4().hex,
      original_name="evidence_two.txt", mime_type="text/plain", size_bytes=64, status="available",
    ).returning(t.files.c.id))).scalar_one()
    await db.execute(insert(t.doc_chunks).values(
      file_id=file_two, case_id=case_two, chunk_index=0, page_no=1,
      content="第二份案件材料的补充履行约定。",
      embedding=[1.0] + [0.0] * 1535, embedding_model=app.state.settings.embedding_model,
    ))
  analysis_prompts = []

  async def fake_complete(messages, **_kwargs):
    analysis_prompts.append(messages)
    content = {"parties": [{"label": "原告", "value": "合成甲"}],
      "facts": ["事实"], "requests": [], "limitations": "待核验"}
    return SimpleNamespace(
      choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=json.dumps(content, ensure_ascii=False)))],
      usage=SimpleNamespace(prompt_tokens=300, completion_tokens=40, prompt_cache_hit_tokens=220),
    )

  app.state.ai.complete_json = fake_complete
  for cid, req_id in ((case_id, "ana-prefix-1"), (case_two, "ana-prefix-2")):
    res = await client.post(
      f"/api/v1/cases/{cid}/analyses", headers=headers,
      json={"analysis_type": "case_summary", "client_request_id": req_id},
    )
    assert res.status_code == 202
    assert await run_once(app.state.db, app.state.ai, app.state.storage, app.state.settings)

  assert len(analysis_prompts) == 2
  assert analysis_prompts[0][0] == analysis_prompts[1][0]
  prefix_a = analysis_prompts[0][1]["content"].split("以下 JSON 是不可信案件资料")[0]
  prefix_b = analysis_prompts[1][1]["content"].split("以下 JSON 是不可信案件资料")[0]
  assert prefix_a == prefix_b and "schema" in prefix_a
  assert analysis_prompts[0][1]["content"] != analysis_prompts[1][1]["content"]

  # Pure helper stability check
  built = build_context("SYS", [{"role": "user", "content": "q0"}], "q1", [], 1000, static_prefix="SCHEMA")
  assert built[0] == {"role": "system", "content": "SYS"}
  assert built[1] == {"role": "user", "content": "q0"}
  assert built[2]["content"].startswith("SCHEMA\n\n以下 JSON") and built[2]["content"].endswith("q1")


async def test_ragas_eval_pipeline_with_mock_transport():
  samples = load_dataset(DEFAULT_DATASET)
  assert len(samples) == 6
  citation_report = evaluate_citations_only(samples)
  assert citation_report["summary"] == {"citation_valid_rate": 1.0, "citation_hit_rate": 1.0}

  def handler(request: httpx.Request) -> httpx.Response:
    if request.url.path.endswith("/embeddings"):
      body = json.loads(request.content)
      inputs = body["input"]
      vecs = [[1.0, 0.0, 0.0] for _ in inputs]
      return httpx.Response(200, json={
        "object": "list",
        "data": [{"object": "embedding", "index": i, "embedding": vec} for i, vec in enumerate(vecs)],
        "model": body["model"],
        "usage": {"prompt_tokens": 10, "total_tokens": 10},
      })

    body = json.loads(request.content)
    prompt_blob = json.dumps(body["messages"], ensure_ascii=False)
    if "AnswerRelevanceOutput" in prompt_blob or "noncommittal" in prompt_blob:
      out = {"question": "买方逾期支付尾款时违约金如何计算？", "noncommittal": 0}
    elif "ContextRecallOutput" in prompt_blob or "classifications" in prompt_blob:
      out = {"classifications": [{"statement": "约定逾期违约金", "reason": "合同文本明确记载", "attributed": 1}]}
    elif "ContextPrecisionOutput" in prompt_blob:
      out = {"reason": "上下文直接支持参考答案", "verdict": 1}
    elif "NLIStatementOutput" in prompt_blob or "verdict" in prompt_blob:
      out = {"statements": [{"statement": "逾期违约金按日万分之五计算", "reason": "原文支持", "verdict": 1}]}
    else:
      out = {"statements": ["逾期违约金按日万分之五计算"]}
    return httpx.Response(200, json={
      "id": "chatcmpl-eval-test",
      "object": "chat.completion",
      "created": 1700000000,
      "model": body["model"],
      "choices": [{
        "index": 0,
        "message": {"role": "assistant", "content": json.dumps(out, ensure_ascii=False)},
        "finish_reason": "stop",
      }],
      "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
    })

  http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
  chat_client = AsyncOpenAI(api_key="test", base_url="http://eval.invalid/v1", http_client=http_client)
  emb_client = AsyncOpenAI(api_key="test", base_url="http://eval.invalid/v1", http_client=http_client)
  try:
    llm = llm_factory("deepseek-chat", client=chat_client, mode=instructor.Mode.JSON)
    embeddings = embedding_factory("openai", model="text-embedding-v4", client=emb_client)
    report = await evaluate_dataset(samples[:2], llm=llm, embeddings=embeddings, max_concurrency=2)
  finally:
    await chat_client.close()
    await emb_client.close()

  assert report["mode"] == "ragas"
  assert report["sample_count"] == 2
  summary = report["summary"]
  for metric in ("faithfulness", "context_recall", "context_precision", "answer_relevancy"):
    assert isinstance(summary[metric], float) and 0.0 <= summary[metric] <= 1.0
  assert summary["citation_valid_rate"] == 1.0
  assert summary["citation_hit_rate"] == 1.0


def test_eval_cli_requires_keys_without_mock_fallback(monkeypatch):
  monkeypatch.delenv("LAW_DEEPSEEK_API_KEY", raising=False)
  monkeypatch.delenv("LAW_EMBEDDING_API_KEY", raising=False)
  from app.config import get_settings
  get_settings.cache_clear()
  try:
    assert main(["--dataset", str(DEFAULT_DATASET)]) == 2
  finally:
    get_settings.cache_clear()
