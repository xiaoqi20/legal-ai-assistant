import json

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import SecretStr

from app.config import Settings
from app.services.ai import AI


@pytest.mark.parametrize("base_url,expected_thinking", [
  ("https://api.deepseek.com", {"thinking": {"type": "disabled"}}),
  ("https://workspace.cn-beijing.maas.aliyuncs.com/compatible-mode/v1", {"enable_thinking": False}),
  ("https://dashscope.aliyuncs.com/compatible-mode/v1", {"enable_thinking": False}),
  ("https://dashscope-intl.aliyuncs.com/compatible-mode/v1", {"enable_thinking": False}),
])
async def test_structured_generation_has_separate_budget_without_reasoning(base_url, expected_thinking):
  received = []
  def handle(request):
    assert str(request.url) == base_url + "/chat/completions"
    assert request.headers["Authorization"] == "Bearer test"
    received.append(json.loads(request.content))
    return httpx.Response(200, json={"id": "test", "object": "chat.completion", "created": 0,
      "model": "deepseek-flash", "choices": [{"index": 0, "finish_reason": "stop",
      "message": {"role": "assistant", "content": '{"title":"合成草稿"}'}}]})
  settings = Settings(_env_file=None, deepseek_api_key=SecretStr("test"), deepseek_base_url=base_url, max_output_tokens=128,
    structured_output_tokens=8192)
  ai = AI(settings)
  await ai.chat.close()
  ai.chat = AsyncOpenAI(api_key="test", base_url=base_url,
    http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle)))
  try:
    response = await ai.complete_json([{"role": "user", "content": "生成 JSON 合成草稿"}], temperature=0)
    assert response.choices[0].finish_reason == "stop"
    assert received[0]["max_tokens"] == 8192
    assert {key: received[0][key] for key in ("thinking", "enable_thinking") if key in received[0]} == expected_thinking
    assert received[0]["response_format"] == {"type": "json_object"}
    assert received[0]["temperature"] == 0
    assert settings.max_output_tokens == 128
  finally:
    await ai.close()
