import math

import httpx
from openai import AsyncOpenAI

from app.errors import fail


class AI:
  def __init__(self, settings):
    self.settings = settings
    timeout = httpx.Timeout(settings.upstream_read_timeout_seconds, connect=10)
    self.chat = AsyncOpenAI(
      api_key=settings.deepseek_api_key.get_secret_value() or "not-configured",
      base_url=settings.deepseek_base_url, timeout=timeout, max_retries=0,
    )
    self.embeddings = AsyncOpenAI(
      api_key=settings.embedding_api_key.get_secret_value() or "not-configured",
      base_url=settings.embedding_base_url, timeout=timeout, max_retries=1,
    )

  def check(self, *, embeddings=True):
    if not self.settings.deepseek_api_key.get_secret_value():
      fail(503, "deepseek_not_configured", "DeepSeek 服务尚未配置")
    if embeddings and not self.settings.embedding_api_key.get_secret_value():
      fail(503, "embedding_not_configured", "向量化服务尚未配置")

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

  async def stream(self, messages):
    stream = await self.chat.chat.completions.create(
      model=self.settings.deepseek_model, messages=messages, stream=True,
      stream_options={"include_usage": True}, max_tokens=self.settings.max_output_tokens,
    )
    async with stream:
      async for chunk in stream:
        # Only final answer content leaves this adapter; reasoning_content is never exposed.
        yield chunk

  async def complete_json(self, messages):
    return await self.chat.chat.completions.create(
      model=self.settings.deepseek_model, messages=messages,
      response_format={"type": "json_object"}, max_tokens=self.settings.max_output_tokens,
    )

  async def close(self):
    await self.chat.close()
    await self.embeddings.close()
