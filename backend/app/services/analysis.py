import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import insert, select, update

from app.access import require_case
from app.services.case_status import refresh_case_status
from app.services.rag import build_context, retrieve


class Output(BaseModel):
  model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Party(Output):
  label: str = Field(max_length=100)
  value: str = Field(max_length=1000)


class Summary(Output):
  parties: list[Party] = Field(max_length=30)
  facts: list[str] = Field(max_length=30)
  requests: list[str] = Field(max_length=30)
  limitations: str = Field(max_length=3000)


class TimelineItem(Output):
  date: str = Field(max_length=100)
  title: str = Field(max_length=200)
  detail: str = Field(max_length=2000)


class Timeline(Output):
  items: list[TimelineItem] = Field(max_length=50)
  limitations: str = Field(max_length=3000)


class ReasoningItem(Output):
  title: str = Field(max_length=200)
  premise: str = Field(max_length=3000)
  conclusion: str = Field(max_length=3000)


class Reasoning(Output):
  items: list[ReasoningItem] = Field(max_length=20)
  limitations: str = Field(max_length=3000)


class Dispute(Output):
  party: str = Field(max_length=200)
  points: list[str] = Field(max_length=30)


class Law(Output):
  name: str = Field(max_length=200)
  content: str = Field(max_length=3000)


class Disputes(Output):
  disputes: list[Dispute] = Field(max_length=20)
  laws: list[Law] = Field(max_length=20)
  limitations: str = Field(max_length=3000)


class Evidence(Output):
  name: str = Field(max_length=200)
  purpose: str = Field(max_length=2000)


class EvidenceReport(Output):
  plaintiff: list[Evidence] = Field(max_length=30)
  defendant: list[Evidence] = Field(max_length=30)
  analysis: str = Field(max_length=8000)
  limitations: str = Field(max_length=3000)


SCHEMAS = {"case_summary": Summary, "timeline": Timeline, "judicial_reasoning": Reasoning,
           "dispute_focus": Disputes, "evidence_chain": EvidenceReport, "evidence_list": EvidenceReport}
QUERIES = {"case_summary": "当事人身份、案件事实、合同履行、诉讼请求",
           "timeline": "按日期梳理签订合同、付款、履约、发生争议、诉讼的时间轴",
           "judicial_reasoning": "依据案件事实与法律关系分析司法推理，区分事实、规则与结论",
           "dispute_focus": "原告与被告的争议焦点、各方主张、待核验法律依据",
           "evidence_chain": "原告被告证据链、证明目的、证据缺口与矛盾",
           "evidence_list": "原告被告提供的证据清单、证明目的及综合分析"}


async def process_analysis(database, ai, settings, job):
  t = database.t
  async with database.sessions.begin() as db:
    analysis = (await db.execute(select(t.case_analyses).where(t.case_analyses.c.id == job["resource_id"]))).mappings().one()
    case_id, user_id = analysis["case_id"], analysis["created_by"]
    await require_case(db, t, user_id, case_id)
    active = (await db.execute(select(t.users.c.status).where(t.users.c.id == user_id))).scalar_one()
    if active != "active":
      raise ValueError("resource_unavailable")
    prompt = (await db.execute(select(t.prompt_versions).where(t.prompt_versions.c.prompt_key == "structured_analysis",
      t.prompt_versions.c.status == "active"))).mappings().one()
    await db.execute(update(t.case_analyses).where(t.case_analyses.c.id == analysis["id"]).values(
      status="running", started_at=datetime.now(UTC), prompt_version_id=prompt["id"], model=settings.deepseek_model,
    ))
    sources = await retrieve(db, t, ai, settings, user_id, case_id, QUERIES[analysis["analysis_type"]])
  if not sources:
    raise ValueError("no_case_material")
  schema = SCHEMAS[analysis["analysis_type"]]
  instruction = QUERIES[analysis["analysis_type"]] + "。仅输出符合以下 schema 的 JSON 对象：" + json.dumps(schema.model_json_schema(), ensure_ascii=False)
  messages = build_context(prompt["content"], [], instruction, sources, settings.max_context_chars)
  response = await ai.complete_json(messages)
  if response.choices[0].finish_reason != "stop":
    raise ValueError("analysis_output_incomplete")
  content = response.choices[0].message.content or ""
  if len(content) > settings.max_output_chars:
    raise ValueError("analysis_output_limit")
  import re
  if any(int(rank) not in {source["rank"] for source in sources} for rank in re.findall(r"\[(\d+)\]", content)):
    raise ValueError("invalid_citation")
  report = schema.model_validate_json(content).model_dump()
  usage = response.usage
  cost = None
  if usage and settings.input_usd_per_million is not None and settings.output_usd_per_million is not None:
    cost = (Decimal(usage.prompt_tokens) * settings.input_usd_per_million
            + Decimal(usage.completion_tokens) * settings.output_usd_per_million) / 1000000
  fingerprint = hashlib.sha256(json.dumps(sources, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
  async with database.sessions.begin() as db:
    owned = (await db.execute(select(t.async_jobs.c.id).where(
      t.async_jobs.c.id == job["id"], t.async_jobs.c.lease_token == job["lease_token"],
      t.async_jobs.c.status == "running", t.async_jobs.c.lease_expires_at > datetime.now(UTC),
    ).with_for_update())).scalar_one_or_none()
    if owned is None:
      return
    await require_case(db, t, user_id, case_id)
    await db.execute(update(t.case_analyses).where(t.case_analyses.c.id == analysis["id"]).values(
      status="succeeded", content=report, schema_version="1.0", source_fingerprint=fingerprint,
      input_tokens=usage.prompt_tokens if usage else None, output_tokens=usage.completion_tokens if usage else None,
      cost_usd=cost, error_message=None, completed_at=datetime.now(UTC),
    ))
    for source in sources:
      await db.execute(insert(t.analysis_sources).values(analysis_id=analysis["id"], case_id=case_id,
        file_id=source["file_id"], chunk_id=source["chunk_id"], weight=source["relevance"]))
    await refresh_case_status(db, t, case_id)
    await db.execute(update(t.async_jobs).where(t.async_jobs.c.id == job["id"]).values(
      status="succeeded", finished_at=datetime.now(UTC), lease_token=None, lease_expires_at=None, last_error=None,
    ))
    await db.execute(insert(t.audit_logs).values(user_id=user_id, action="analysis.succeeded", resource_type="analysis", resource_id=analysis["id"]))
