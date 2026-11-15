"""Offline RAG evaluation runner combining Ragas metrics, citation audits, and cache telemetry."""

import argparse
import asyncio
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
  sys.path.insert(0, str(BACKEND_ROOT))

DEFAULT_DATASET = BACKEND_ROOT / "evals" / "synthetic_rag_eval.jsonl"


def audit_citations(
  response: str, num_contexts: int, expected_citations: list[int] | None = None,
) -> dict[str, Any]:
  """Verify every `[rank]` marker stays within retrieved context bounds and check expected recall."""
  cited = [int(match) for match in re.findall(r"\[(\d+)\]", response)]
  out_of_range = [rank for rank in cited if rank < 1 or rank > num_contexts]
  citation_valid = not out_of_range
  if expected_citations:
    expected_set = {rank for rank in expected_citations if 1 <= rank <= num_contexts}
    hit_rate = round(len(set(cited) & expected_set) / len(expected_set), 4) if expected_set else 1.0
  else:
    hit_rate = 1.0 if cited and citation_valid else 0.0
  return {
    "cited": cited,
    "out_of_range": out_of_range,
    "citation_valid": citation_valid,
    "citation_hit_rate": hit_rate,
  }


def load_dataset(path: Path, *, require_response: bool = True) -> list[dict[str, Any]]:
  samples: list[dict[str, Any]] = []
  with path.open(encoding="utf-8") as handle:
    for line_no, raw in enumerate(handle, 1):
      line = raw.strip()
      if not line:
        continue
      item = json.loads(line)
      required = ("id", "user_input", "reference") if not require_response else (
        "id", "user_input", "retrieved_contexts", "response", "reference"
      )
      missing = [key for key in required if key not in item]
      if missing:
        raise ValueError(f"{path}:{line_no} 缺少字段: {missing}")
      samples.append(item)
  if not samples:
    raise ValueError(f"{path} 数据集为空")
  return samples


def _safe_score(value: float) -> float | None:
  val = float(value)
  return round(val, 4) if math.isfinite(val) else None


def _mean(values: list[float | None]) -> float | None:
  present = [value for value in values if value is not None and math.isfinite(value)]
  return round(sum(present) / len(present), 4) if present else None


def evaluate_citations_only(samples: list[dict[str, Any]]) -> dict[str, Any]:
  rows = []
  for item in samples:
    audit = audit_citations(
      item["response"], len(item.get("retrieved_contexts") or []), item.get("expected_citations"),
    )
    rows.append({"id": item["id"], **audit})
  return {
    "mode": "citations_only",
    "sample_count": len(rows),
    "summary": {
      "citation_valid_rate": _mean([1.0 if r["citation_valid"] else 0.0 for r in rows]),
      "citation_hit_rate": _mean([r["citation_hit_rate"] for r in rows]),
    },
    "samples": rows,
  }


async def populate_live_responses(
  samples: list[dict[str, Any]], settings: Any, *, case_id: int, user_id: int,
) -> list[dict[str, Any]]:
  """Generate contexts and answers from PostgreSQL + configured reranker/LLM."""
  from sqlalchemy import select

  from app.db import create_db
  from app.services.ai import AI, extract_cache_usage
  from app.services.rag import build_context, retrieve

  ai = AI(settings)
  ai.check(embeddings=True, rerank=True)
  database = create_db(settings.database_url)
  t = database.t
  enriched: list[dict[str, Any]] = []
  try:
    async with database.sessions() as db:
      prompt = (await db.execute(select(t.prompt_versions).where(
        t.prompt_versions.c.prompt_key == "grounded_qa",
        t.prompt_versions.c.status == "active",
      ))).mappings().first()
      if not prompt:
        raise RuntimeError("未找到激活状态的 grounded_qa 提示词模板")
      for item in samples:
        sources = await retrieve(db, t, ai, settings, user_id, case_id, item["user_input"])
        contexts = [f"《{s['document_title']}》（第{s['page_no']}页）：{s['quote']}" for s in sources]
        messages = build_context(
          prompt["content"], [], item["user_input"], sources, settings.max_context_chars,
        )
        completion = await ai.chat.chat.completions.create(
          model=settings.deepseek_model, messages=messages, max_tokens=settings.max_output_tokens,
        )
        answer = completion.choices[0].message.content or ""
        usage = completion.usage
        prompt_tokens = getattr(usage, "prompt_tokens", None) if usage else None
        cache_usage = extract_cache_usage(usage)
        row = dict(item)
        row["retrieved_contexts"] = contexts
        row["response"] = answer
        if prompt_tokens and "cached_tokens" in cache_usage:
          row["prompt_cache"] = {
            **cache_usage, "prompt_tokens": prompt_tokens,
            "cache_hit_ratio": round(cache_usage["cached_tokens"] / prompt_tokens, 4),
          }
        enriched.append(row)
  finally:
    await ai.close()
    await database.engine.dispose()
  return enriched


def build_ragas_clients(settings: Any, *, judge_model: str | None = None):
  """Create pure AsyncOpenAI Ragas LLM and embedding wrappers without LangChain."""
  try:
    import instructor
    from ragas.embeddings.base import embedding_factory
    from ragas.llms import llm_factory
  except ImportError as exc:
    raise RuntimeError("请先在 backend 目录执行 `uv sync --group eval` 安装 RAGAS 评测依赖") from exc

  from openai import AsyncOpenAI

  chat_key = settings.deepseek_api_key.get_secret_value()
  emb_key = settings.embedding_api_key.get_secret_value()
  if not chat_key:
    raise RuntimeError("缺少 LAW_DEEPSEEK_API_KEY，无法初始化 Ragas 评测裁判模型（严禁静默回退）")
  if not emb_key:
    raise RuntimeError("缺少 LAW_EMBEDDING_API_KEY，无法计算 AnswerRelevancy（严禁静默回退）")

  chat_client = AsyncOpenAI(
    api_key=chat_key, base_url=settings.deepseek_base_url,
    timeout=settings.upstream_read_timeout_seconds, max_retries=1,
  )
  emb_client = AsyncOpenAI(
    api_key=emb_key, base_url=settings.embedding_base_url,
    timeout=settings.upstream_read_timeout_seconds, max_retries=1,
  )
  llm = llm_factory(
    judge_model or settings.deepseek_model, client=chat_client, mode=instructor.Mode.JSON,
  )
  embeddings = embedding_factory("openai", model=settings.embedding_model, client=emb_client)
  return llm, embeddings, chat_client, emb_client


async def evaluate_dataset(
  samples: list[dict[str, Any]], *, llm: Any, embeddings: Any, max_concurrency: int = 4,
) -> dict[str, Any]:
  """Run Ragas 4-metric evaluation + grounded citation audits across evaluation samples."""
  from ragas.metrics.collections import (
    AnswerRelevancy,
    ContextPrecision,
    ContextRecall,
    Faithfulness,
  )

  faithfulness = Faithfulness(llm=llm)
  context_recall = ContextRecall(llm=llm)
  context_precision = ContextPrecision(llm=llm)
  answer_relevancy = AnswerRelevancy(llm=llm, embeddings=embeddings)
  sem = asyncio.Semaphore(max_concurrency)

  async def score_one(item: dict[str, Any]) -> dict[str, Any]:
    async with sem:
      contexts = item.get("retrieved_contexts") or []
      user_input = item["user_input"]
      response = item["response"]
      reference = item["reference"]
      f_res, cr_res, cp_res, ar_res = await asyncio.gather(
        faithfulness.ascore(user_input=user_input, response=response, retrieved_contexts=contexts),
        context_recall.ascore(user_input=user_input, retrieved_contexts=contexts, reference=reference),
        context_precision.ascore(user_input=user_input, reference=reference, retrieved_contexts=contexts),
        answer_relevancy.ascore(user_input=user_input, response=response),
      )
      audit = audit_citations(response, len(contexts), item.get("expected_citations"))
      scores = {
        "faithfulness": _safe_score(f_res.value),
        "context_recall": _safe_score(cr_res.value),
        "context_precision": _safe_score(cp_res.value),
        "answer_relevancy": _safe_score(ar_res.value),
      }
      entry: dict[str, Any] = {"id": item["id"], **scores, **audit}
      if "prompt_cache" in item:
        entry["prompt_cache"] = item["prompt_cache"]
      return entry

  rows = await asyncio.gather(*(score_one(item) for item in samples))
  cache_ratios = [
    r["prompt_cache"]["cache_hit_ratio"] for r in rows
    if isinstance(r.get("prompt_cache"), dict) and "cache_hit_ratio" in r["prompt_cache"]
  ]
  summary = {
    "faithfulness": _mean([r["faithfulness"] for r in rows]),
    "context_recall": _mean([r["context_recall"] for r in rows]),
    "context_precision": _mean([r["context_precision"] for r in rows]),
    "answer_relevancy": _mean([r["answer_relevancy"] for r in rows]),
    "citation_valid_rate": _mean([1.0 if r["citation_valid"] else 0.0 for r in rows]),
    "citation_hit_rate": _mean([r["citation_hit_rate"] for r in rows]),
  }
  if cache_ratios:
    summary["avg_prompt_cache_hit_ratio"] = _mean(cache_ratios)
  return {"mode": "ragas", "sample_count": len(rows), "summary": summary, "samples": rows}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Legal RAG offline evaluation with Ragas")
  parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET, help="JSONL 评测集路径")
  parser.add_argument("--output", type=Path, default=None, help="评测结果 JSON 输出路径")
  parser.add_argument("--citations-only", action="store_true", help="仅运行本地引用与边界校验")
  parser.add_argument("--from-db", action="store_true", help="从真实数据库检索并生成回答后评测")
  parser.add_argument("--case-id", type=int, default=None, help="--from-db 目标案件 ID")
  parser.add_argument("--user-id", type=int, default=None, help="--from-db 案件所属用户 ID")
  parser.add_argument("--judge-model", type=str, default=None, help="覆盖评测 Judge 模型名")
  parser.add_argument("--max-concurrency", type=int, default=4, help="并发评测样本数")
  return parser.parse_args(argv)


async def _run(args: argparse.Namespace) -> dict[str, Any]:
  samples = load_dataset(args.dataset, require_response=not args.from_db)
  if args.citations_only:
    return evaluate_citations_only(samples)

  from app.config import get_settings

  settings = get_settings()
  if args.from_db:
    if args.case_id is None or args.user_id is None:
      raise RuntimeError("使用 --from-db 时必须指定 --case-id 与 --user-id")
    samples = await populate_live_responses(
      samples, settings, case_id=args.case_id, user_id=args.user_id,
    )

  llm, embeddings, chat_client, emb_client = build_ragas_clients(
    settings, judge_model=args.judge_model,
  )
  try:
    return await evaluate_dataset(
      samples, llm=llm, embeddings=embeddings, max_concurrency=args.max_concurrency,
    )
  finally:
    await chat_client.close()
    await emb_client.close()


def main(argv: list[str] | None = None) -> int:
  os.environ.setdefault("PYTHONUTF8", "1")
  args = parse_args(argv)
  try:
    report = asyncio.run(_run(args))
  except Exception as exc:
    print(f"评测失败: {exc}", file=sys.stderr)
    return 2
  rendered = json.dumps(report, ensure_ascii=False, indent=2)
  if args.output:
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered + "\n", encoding="utf-8")
  print(rendered)
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
