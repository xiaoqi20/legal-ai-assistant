import json

import httpx
import pytest
from pydantic import SecretStr

from app.config import Settings
from app.services.ai import AI


async def test_real_sdk_stream_protocol_and_embedding_dimensions():
  seen = []
  def upstream(request):
    payload = json.loads(request.content)
    seen.append(payload)
    if request.url.path.endswith("embeddings"):
      assert payload["dimensions"] == 1536
      return httpx.Response(200, json={"object": "list", "data": [
        {"object": "embedding", "index": 0, "embedding": [1.0] + [0.0] * 1535}
      ], "model": "text-embedding-v4", "usage": {"prompt_tokens": 3, "total_tokens": 3}})
    return httpx.Response(200, headers={"Content-Type": "text/event-stream"}, content=(
      'data: {"id":"test","object":"chat.completion.chunk","created":1,"model":"test",'
      '"choices":[{"index":0,"delta":{"reasoning_content":"hidden","content":"中文回答"},"finish_reason":null}]}\n\n'
      'data: {"id":"test","object":"chat.completion.chunk","created":1,"model":"test",'
      '"choices":[{"index":0,"delta":{},"finish_reason":"stop"}],'
      '"usage":{"prompt_tokens":10,"completion_tokens":3,"total_tokens":13}}\n\n'
      'data: [DONE]\n\n'
    ).encode())
  ai = AI(Settings(_env_file=None, deepseek_api_key=SecretStr("test"), embedding_api_key=SecretStr("test")))
  await ai.chat._client.aclose()
  await ai.embeddings._client.aclose()
  ai.chat._client = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
  ai.embeddings._client = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
  try:
    vectors = await ai.embed(["合成材料"])
    chunks = [chunk async for chunk in ai.stream([{"role": "user", "content": "合成问题"}])]
    assert len(vectors[0]) == 1536
    assert chunks[0].choices[0].delta.content == "中文回答"
    assert chunks[-1].usage.prompt_tokens == 10
    assert seen[-1]["stream_options"]["include_usage"] is True
  finally:
    await ai.close()


async def test_sdk_rejects_bad_embedding_dimension():
  ai = AI(Settings(_env_file=None, embedding_api_key=SecretStr("test")))
  def upstream(request):
    return httpx.Response(200, json={"object": "list", "data": [
      {"object": "embedding", "index": 0, "embedding": [1.0, 2.0]}
    ], "model": "test", "usage": {"prompt_tokens": 1, "total_tokens": 1}})
  await ai.embeddings._client.aclose()
  ai.embeddings._client = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
  try:
    with pytest.raises(RuntimeError, match="embedding_invalid_vector"):
      await ai.embed(["合成材料"])
  finally:
    await ai.close()


def test_example_settings_and_production_dev_login_guard():
  from pydantic import ValidationError
  settings = Settings(_env_file=".env.example")
  assert settings.embedding_dimensions == 1536
  assert settings.input_usd_per_million is None
  with pytest.raises(ValidationError, match="生产环境禁止"):
    Settings(_env_file=None, env="production", allow_dev_login=True)
