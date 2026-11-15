import math
from urllib.parse import urlsplit

import httpx
from openai import AsyncOpenAI

from app.errors import fail


def _int_or_none(value):
  return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def extract_cache_usage(usage) -> dict[str, int]:
  """Extract prompt cache hit/miss token counts across DeepSeek and Bailian/OpenAI responses."""
  if usage is None:
    return {}
  extra = getattr(usage, "model_extra", None) or {}
  def read(key):
    return usage.get(key) if isinstance(usage, dict) else getattr(usage, key, extra.get(key))
  hit = _int_or_none(read("prompt_cache_hit_tokens"))
  miss = _int_or_none(read("prompt_cache_miss_tokens"))
  details = read("prompt_tokens_details")
  if hit is None and details is not None:
    details_extra = getattr(details, "model_extra", None) or {}
    cached = details.get("cached_tokens") if isinstance(details, dict) else getattr(details, "cached_tokens", details_extra.get("cached_tokens"))
    hit = _int_or_none(cached)
  if hit is None:
    hit = _int_or_none(read("cached_tokens"))
  result = {}
  if hit is not None:
    result["cached_tokens"] = hit
  if miss is not None:
    result["cache_miss_tokens"] = miss
  return result


class AI:
  def __init__(self, settings):
    self.settings = settings
    host = urlsplit(settings.deepseek_base_url).hostname or ""
    self._uses_bailian = host in {
      "dashscope.aliyuncs.com", "dashscope-intl.aliyuncs.com", "dashscope-us.aliyuncs.com",
    } or host.endswith(".maas.aliyuncs.com")
    timeout = httpx.Timeout(settings.upstream_read_timeout_seconds, connect=10)
    self.chat = AsyncOpenAI(
      api_key=settings.deepseek_api_key.get_secret_value() or "not-configured",
      base_url=settings.deepseek_base_url, timeout=timeout, max_retries=0,
    )
    self.embeddings = AsyncOpenAI(
      api_key=settings.embedding_api_key.get_secret_value() or "not-configured",
      base_url=settings.embedding_base_url, timeout=timeout, max_retries=1,
    )
    self.reranker = httpx.AsyncClient(timeout=timeout)

  def check_rerank(self):
    if self.settings.rerank_enabled and not self.settings.rerank_api_key.get_secret_value():
      fail(503, "rerank_not_configured", "重排服务尚未配置")

  def check(self, *, embeddings=True, rerank=False):
    if not self.settings.deepseek_api_key.get_secret_value():
      fail(503, "deepseek_not_configured", "DeepSeek 服务尚未配置")
    if embeddings and not self.settings.embedding_api_key.get_secret_value():
      fail(503, "embedding_not_configured", "向量化服务尚未配置")
    if rerank:
      self.check_rerank()

  async def embed(self, texts: list[str]):
    if not self.settings.embedding_api_key.get_secret_value():
      raise RuntimeError("embedding_not_configured")
    response = await self.embeddings.embeddings.create(
      model=self.settings.embedding_model, input=texts,
      dimensions=self.settings.embedding_dimensions, encoding_format="float",
    )
    ordered = sorted(response.data, key=lambda item: item.index)
    if [item.index for item in ordered] != list(range(len(texts))):
      raise RuntimeError("embedding_count_mismatch")
    vectors = [item.embedding for item in ordered]
    for vector in vectors:
      if (len(vector) != self.settings.embedding_dimensions
          or not all(math.isfinite(v) for v in vector) or not any(vector)):
        raise RuntimeError("embedding_invalid_vector")
    return vectors

  async def stream(self, messages, *, tools=None, tool_choice=None):
    kwargs = {}
    if tools is not None:
      kwargs.update(tools=tools, tool_choice=tool_choice or "auto")
    stream = await self.chat.chat.completions.create(
      model=self.settings.deepseek_model, messages=messages, stream=True,
      stream_options={"include_usage": True}, max_tokens=self.settings.max_output_tokens,
      extra_body={"enable_thinking": False} if self._uses_bailian else None,
      **kwargs,
    )
    async with stream:
      async for chunk in stream:
        # Only final answer content leaves this adapter; reasoning_content is never exposed.
        yield chunk

  async def complete_tools(self, messages, tools):
    # Local validation is mandatory even when a provider supports strict schemas.
    return await self.chat.chat.completions.create(
      model=self.settings.deepseek_model, messages=messages, tools=tools,
      tool_choice="auto", max_tokens=self.settings.max_output_tokens,
      extra_body={"enable_thinking": False} if self._uses_bailian else {"thinking": {"type": "disabled"}},
    )

  async def complete_json(self, messages, temperature: float | None = None):
    kwargs = {} if temperature is None else {"temperature": temperature}
    return await self.chat.chat.completions.create(
      model=self.settings.deepseek_model, messages=messages,
      response_format={"type": "json_object"}, max_tokens=self.settings.structured_output_tokens,
      extra_body={"enable_thinking": False} if self._uses_bailian else {"thinking": {"type": "disabled"}},
      **kwargs,
    )

  async def rerank(self, query: str, documents: list[str], *, top_n: int | None = None) -> list[tuple[int, float]]:
    """Score candidate documents with a Cross-Encoder reranker and return ordered (index, score) pairs."""
    if not documents:
      return []
    api_key = self.settings.rerank_api_key.get_secret_value()
    if not api_key:
      fail(503, "rerank_not_configured", "重排服务尚未配置")
    limit = min(len(documents), top_n or self.settings.retrieval_top_k)
    url = self.settings.rerank_base_url.rstrip("/")
    is_dashscope = "services/rerank/text-rerank" in url
    payload = (
      {"model": self.settings.rerank_model, "input": {"query": query, "documents": documents},
       "parameters": {"top_n": limit, "return_documents": False}}
      if is_dashscope else
      {"model": self.settings.rerank_model, "query": query, "documents": documents,
       "top_n": limit, "return_documents": False}
    )
    response = await self.reranker.post(url, json=payload, headers={"Authorization": f"Bearer {api_key}"})
    response.raise_for_status()
    data = response.json()
    items = data["output"].get("results") if is_dashscope and isinstance(data.get("output"), dict) else data.get("results")
    if not isinstance(items, list) or not items:
      raise RuntimeError("rerank_invalid_response")
    ranked: list[tuple[int, float]] = []
    seen: set[int] = set()
    for item in items:
      if not isinstance(item, dict):
        raise RuntimeError("rerank_invalid_response")
      idx = item.get("index")
      score = item.get("relevance_score")
      if (not isinstance(idx, int) or isinstance(idx, bool) or not (0 <= idx < len(documents))
          or isinstance(score, bool) or not isinstance(score, int | float) or not math.isfinite(score)):
        raise RuntimeError("rerank_invalid_response")
      if idx not in seen:
        seen.add(idx)
        ranked.append((idx, float(score)))
    ranked.sort(key=lambda pair: (-pair[1], pair[0]))
    return ranked[:limit]

  async def close(self):
    await self.chat.close()
    await self.embeddings.close()
    await self.reranker.aclose()
