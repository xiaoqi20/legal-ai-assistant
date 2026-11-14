import json

import httpx
from openai import AsyncOpenAI
from pydantic import SecretStr

from app.config import Settings
from app.services.ai import AI


async def test_structured_generation_has_separate_budget_without_reasoning():
  received = []
  def handle(request):
    received.append(json.loads(request.content))
    return httpx.Response(200, json={"id": "test", "object": "chat.completion", "created": 0,
      "model": "deepseek-flash", "choices": [{"index": 0, "finish_reason": "stop",
      "message": {"role": "assistant", "content": '{"title":"合成草稿"}'}}]})
  settings = Settings(_env_file=None, deepseek_api_key=SecretStr("test"), max_output_tokens=128,
    structured_output_tokens=8192)
  ai = AI(settings)
  await ai.chat.close()
  ai.chat = AsyncOpenAI(api_key="test", http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle)))
  try:
    response = await ai.complete_json([{"role": "user", "content": "生成 JSON 合成草稿"}])
    assert response.choices[0].finish_reason == "stop"
    assert received[0]["max_tokens"] == 8192
    assert received[0]["thinking"] == {"type": "disabled"}
    assert received[0]["response_format"] == {"type": "json_object"}
    assert settings.max_output_tokens == 128
  finally:
    await ai.close()
