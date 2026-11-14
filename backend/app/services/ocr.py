"""Alibaba Cloud OCR adapter. Network calls are synchronous SDK calls wrapped off-loop."""
import asyncio
import io
import json


class AlibabaOcr:
  provider = "alibaba_ocr"

  def __init__(self, settings):
    self.settings = settings
    self.configured = bool(settings.ocr_access_key_id.get_secret_value()
                            and settings.ocr_access_key_secret.get_secret_value())

  async def recognize(self, image: bytes):
    if not self.configured:
      raise ValueError("ocr_not_configured")
    return await asyncio.to_thread(self._recognize, image)

  def _recognize(self, image: bytes):
    from alibabacloud_ocr_api20210707.client import Client
    from alibabacloud_ocr_api20210707.models import RecognizeGeneralRequest
    from alibabacloud_tea_openapi.models import Config

    config = Config(
      access_key_id=self.settings.ocr_access_key_id.get_secret_value(),
      access_key_secret=self.settings.ocr_access_key_secret.get_secret_value(),
      endpoint=f"ocr-api.{self.settings.ocr_region}.aliyuncs.com",
      connect_timeout=5000,
      read_timeout=30000,
    )
    client = Client(config)
    response = client.recognize_general(RecognizeGeneralRequest(body=io.BytesIO(image)))
    if response.status_code != 200 or not response.body or not response.body.data:
      raise ValueError("ocr_provider_error")
    try:
      payload = json.loads(response.body.data)
    except (TypeError, json.JSONDecodeError) as error:
      raise ValueError("ocr_invalid_response") from error
    words = payload.get("prism_wordsInfo") or payload.get("wordsInfo") or payload.get("WordsInfo") or []
    blocks = []
    for item in words:
      text = item.get("word") or item.get("text") or item.get("Word") or ""
      if not text:
        continue
      score = item.get("prob", item.get("confidence", item.get("Probability")))
      try:
        confidence = float(score) if score is not None else None
        if confidence is not None and confidence > 1:
          confidence /= 100
      except (TypeError, ValueError):
        confidence = None
      position = item.get("pos") or item.get("position") or item.get("Pos") or []
      blocks.append({"text": text, "polygon": position, "confidence": confidence})
    text = "\n".join(block["text"] for block in blocks)
    scores = [block["confidence"] for block in blocks if block["confidence"] is not None]
    average = sum(scores) / len(scores) if scores and len(scores) == len(blocks) else None
    return {"text": text, "blocks": blocks, "confidence": average,
            "provider": self.provider, "model": self.settings.ocr_model}
