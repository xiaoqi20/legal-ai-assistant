"""Enrich >=300 clean MSJudge private-lending cases via local PII scrubbing and DeepSeek LLM calls.

Outputs remain strictly outside Git under ``--data-root`` with 700/600 permissions.
Prediction inputs never expose post-judgment fields (fact_description, fact_labels, outcome_label).
"""

import argparse
import asyncio
import hashlib
import heapq
import io
import json
import math
import os
import re
import sys
import zipfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
  sys.path.insert(0, str(BACKEND_ROOT))

from app.config import Settings  # noqa: E402
from app.services.ai import AI  # noqa: E402
from app.services.win_rate import (  # noqa: E402
  CalibrationParams,
  WinRateExtraction,
  compute_win_rate,
)
from scripts.prepare_msjudge import (  # noqa: E402
  ARCHIVE_BYTES,
  ARCHIVE_SHA256,
  COMMIT,
  JUDICIAL_MARKERS,
  LABELS,
  MEMBER,
  ObjectStream,
  compact,
  prepare_candidate,
  redact,
  write_json,
)

ABSENCE_OR_PUB_RE = re.compile(r"缺席|未到庭|公告送达")
EXCLUSION_STAGE_RE = re.compile(r"上诉|再审|原审法院|一审判决|调解|撤诉")
DEMOGRAPHIC_LINE_RE = re.compile(r"出生|公民身份号码|身份证号|住\[已遮蔽地址\]|住所地|户籍|羁押")
ADDRESS_RE = re.compile(
  r"(?<![\u4e00-\u9fa5])(?:现住|户籍所在地|户籍地|住所地|居住地|住址|住)(?:[:：]|(?=LOC|[\u4e00-\u9fa5]{1,18}(?:省|市|区|县|镇|乡|村|路|街|巷|弄|幢|栋|单元|室|组|\d+号)))(?:LOC|[\u4e00-\u9fa5A-Za-z0-9\-－]){1,45}"
)
CASE_NO_RE = re.compile(r"[（(](?:19|20)\d{2}[）)][\u4e00-\u9fa5A-Za-z0-9]{1,18}?号")
DOB_RE = re.compile(r"(?:19|20)\d{2}年\d{1,2}月\d{1,2}日(?=出生)")
DETENTION_RE = re.compile(r"[\u4e00-\u9fa5A-Za-z]{0,16}看守所")
LOC_TOKEN_RE = re.compile(r"(?:LOC)+[\u4e00-\u9fa5A-Za-z0-9\-－]{0,18}")
PARTIAL_SURNAME_MASK_RE = re.compile(r"[\u4e00-\u9fa5]{1,2}某某|PER[甲乙丙丁\d]?")
ROLE_INLINE_NAME_RE = re.compile(
  r"((?:委托代理人|法定代表人|担保人|保证人|见证人|借款人|出借人|收款人|付款人)[:：])[\u4e00-\u9fa5]{2,4}(?=[,，。；、\s]|$)"
)
CLEAN_BOILERPLATE = {
  "没有", "无", "听清", "听清了", "清楚", "知道了", "不申请", "收到", "是", "略",
  "宣读起诉状", "宣读起诉状(略)", "详见诉状", "略(详见诉状)", "同前", "被告签名",
  "原告签名", "被代", "被告", "原告",
}
RMB_ARABIC_RE = re.compile(r"(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s*(万)?\s*元")
CHINESE_NUMS = {"零": 0, "〇": 0, "一": 1, "壹": 1, "二": 2, "两": 2, "贰": 2, "三": 3, "叁": 3, "四": 4, "肆": 4, "五": 5, "伍": 5, "六": 6, "陆": 6, "七": 7, "柒": 7, "八": 8, "捌": 8, "九": 9, "玖": 9}
CHINESE_UNITS = {"十": 10, "拾": 10, "百": 100, "佰": 100, "千": 1000, "仟": 1000, "万": 10000, "亿": 100000000}
CN_RMB_RE = re.compile(r"([零〇一壹二两贰三叁四肆五伍六陆七柒八捌九玖十拾百佰千仟万亿]+)\s*元")


PRE_JUDGMENT_PROMPT = """你是中国民间借贷案件的结构化法务信息抽取与要件标注器。
只能依据我提供的“原告诉讼请求”和带 [编号] 的“庭审双方发言摘要”，严禁编造正文未出现的法院名称、省份、案号年份或日期。

请输出严格合法的 JSON（禁止 Markdown 代码块，禁止额外字段），结构如下：
{
  "win_rate_extraction": {
    "cause_code": "private_lending",
    "claims": [{"index": 0, "title": "简短诉求名称", "amount_yuan": 10000.0, "priority_weight": 1.0}],
    "elements": [
      {
        "key": "lending_intent | fund_delivery | maturity_breach | interest_agreement",
        "label": "要件中文名称",
        "scope_claim_index": null,
        "grade": "proven | corroborated | weak | missing | rebutted",
        "citation_ranks": [1],
        "summary": "一句话客观说明支撑事实与证据"
      }
    ],
    "defeaters": [
      {
        "key": "limitation_expired | repayment_offset | contract_invalidity | prior_breach_defense | procedural_defect | statutory_cap | other_defense",
        "label": "抗辩中文名称",
        "scope_claim_index": null,
        "presence": "confirmed | suspected | absent",
        "lethality": 0.5,
        "citation_ranks": [1],
        "summary": "一句话说明抗辩或风险依据"
      }
    ],
    "positive_factors": ["最多5条简短有利事实"],
    "negative_factors": ["最多5条简短不利点或争议点"],
    "missing_evidence": ["最多5条需补强证据"],
    "limitations": "一句话说明当前庭审记录片段局限"
  },
  "metadata": {
    "claimed_principal_yuan": 10000.0,
    "claimed_total_yuan": null,
    "claimed_interest_requested": true,
    "procedure": "first_instance | second_instance | retrial | unknown",
    "procedure_detail": "simplified | ordinary | small_claims | unspecified",
    "is_absent_defendant": false,
    "borrowing_date": "YYYY-MM-DD 或 YYYY-MM 或 null",
    "maturity_date": "YYYY-MM-DD 或 YYYY-MM 或 null",
    "text_mentioned_case_year": null,
    "text_mentioned_court": null,
    "text_mentioned_province": null
  }
}

严格规则：
1. win_rate_extraction 必须涵盖借贷核心四要件：lending_intent（借贷合意）、fund_delivery（款项交付）、maturity_breach（借期届满及未还）、interest_agreement（利息约定）。
2. grade 为 non-missing 或 defeater 为 non-absent 时，citation_ranks 必须引用至少 1 个真实整数 [编号]；若正文全无体现则 grade="missing" 且 citation_ranks=[]。
3. metadata 中正文明示请求判令归还借款本金的视为 first_instance；除非正文明确提到“未到庭/缺席”，否则双方均到庭质证辩论的 is_absent_defendant=false。
4. text_mentioned_court / text_mentioned_province / text_mentioned_case_year 只有正文明确写明时才能填入，否则必须为 null。"""


GROUND_TRUTH_PROMPT = """你是离线法律研究数据的结果真值校核器。
只能根据提供的“诉讼请求”、“MSJudge 诉求标签(outcome_label)”、“MSJudge 客观事实标签(fact_labels)”和“审理查明事实(fact_description)”提取整案口径与裁判查明元数据，严禁编造文本没有的日期、法院或省份。

输出严格合法 JSON（禁止额外字段）：
{
  "case_win": true,
  "principal_support_tier": "full | partial_major_ge80 | partial_minor_lt80 | rejected | unclear",
  "supported_principal_yuan": 10000.0,
  "disposal_type": "judgment | mediation | withdrawal | unclear",
  "partial_reason": "仅当部分支持或驳回时简述核心原因，否则 null",
  "filing_date": "YYYY-MM-DD 或 null（仅当正文明确写明起诉日期时填写）",
  "judgment_date": "YYYY-MM-DD 或 null（严禁将借款日期或起诉日期填入此处，无明确落款裁判日期必须 null）",
  "court_level": "basic | intermediate | high | supreme | null（仅正文明示法院名称时填写）",
  "province": "省级行政区简称或全称或 null（仅正文明示地域时填写）"
}

整案胜诉(case_win)与结案方式认定规范：
- disposal_type：MSJudge 来自已作实体裁判的民间借贷案件集；只要事实中未明确说明系调解或撤诉结案，应填 "judgment"。
- outcome_label == "fully_supported" 时，case_win 必须为 true，principal_support_tier="full"。
- outcome_label == "dismissed" 时，case_win 必须为 false，principal_support_tier="rejected"，supported_principal_yuan=0.0。
- outcome_label == "partially_supported" 时：按“核心本金诉求是否获实质支持（>=80%）”判定。若借贷关系成立(Loan Established=1)且仅因利息超限/逾期起算日或微小已还抵扣导致部分支持，case_win=true, principal_support_tier="partial_major_ge80"；若大额本金被驳回、借贷关系未成立或共同债务核心请求被否定导致支持不足80%，case_win=false, principal_support_tier="partial_minor_lt80"。"""


class PreJudgmentMetadata(BaseModel):
  model_config = ConfigDict(extra="forbid")
  claimed_principal_yuan: float | None = Field(default=None, ge=0)
  claimed_total_yuan: float | None = Field(default=None, ge=0)
  claimed_interest_requested: bool = False
  procedure: Literal["first_instance", "second_instance", "retrial", "unknown"] = "first_instance"
  procedure_detail: Literal["simplified", "ordinary", "small_claims", "unspecified"] = "unspecified"
  is_absent_defendant: bool = False
  borrowing_date: str | None = Field(default=None, max_length=40)
  maturity_date: str | None = Field(default=None, max_length=40)
  text_mentioned_case_year: int | None = Field(default=None, ge=1990, le=2026)
  text_mentioned_court: str | None = Field(default=None, max_length=80)
  text_mentioned_province: str | None = Field(default=None, max_length=40)


class PreJudgmentLLMResult(BaseModel):
  model_config = ConfigDict(extra="forbid")
  win_rate_extraction: WinRateExtraction
  metadata: PreJudgmentMetadata


class GroundTruthLLMResult(BaseModel):
  model_config = ConfigDict(extra="forbid")
  case_win: bool
  principal_support_tier: Literal["full", "partial_major_ge80", "partial_minor_lt80", "rejected", "unclear"]
  supported_principal_yuan: float | None = Field(default=None, ge=0)
  disposal_type: Literal["judgment", "mediation", "withdrawal", "unclear"] = "judgment"
  partial_reason: str | None = Field(default=None, max_length=160)
  filing_date: str | None = Field(default=None, max_length=40)
  judgment_date: str | None = Field(default=None, max_length=40)
  court_level: Literal["basic", "intermediate", "high", "supreme"] | None = None
  province: str | None = Field(default=None, max_length=40)


def _cn_to_int(text: str) -> int | None:
  total, section, number = 0, 0, 0
  for ch in text:
    if ch in CHINESE_NUMS:
      number = CHINESE_NUMS[ch]
    elif ch in CHINESE_UNITS:
      unit = CHINESE_UNITS[ch]
      if unit >= 10000:
        section = (section + number) * unit
        total += section
        section = 0
      else:
        section += (number or 1) * unit
      number = 0
    else:
      return None
  value = total + section + number
  return value if value > 0 else None


def parse_rmb_amount(text: str) -> float | None:
  m = RMB_ARABIC_RE.search(text)
  if m:
    num = float(m.group(1).replace(",", ""))
    return round(num * (10000.0 if m.group(2) else 1.0), 2)
  cm = CN_RMB_RE.search(text)
  if cm:
    val = _cn_to_int(cm.group(1))
    return float(val) if val is not None else None
  return None


def scrub_text_for_llm(text: str) -> tuple[str, dict[str, int]]:
  """Mask residual DOBs, addresses, case numbers, and inline names locally before LLM calls."""
  text, base_counts = redact(text)
  counts = Counter(base_counts)
  substitutions = (
    ("dob", DOB_RE, "[已遮蔽出生日期]"),
    ("case_no", CASE_NO_RE, "[已遮蔽案号]"),
    ("detention", DETENTION_RE, "[已遮蔽羁押场所]"),
    ("address", ADDRESS_RE, "住[已遮蔽地址]"),
    ("loc_token", LOC_TOKEN_RE, "[已遮蔽地点]"),
    ("partial_name", PARTIAL_SURNAME_MASK_RE, "[已遮蔽当事人]"),
    ("role_inline_name", ROLE_INLINE_NAME_RE, r"\1[已遮蔽姓名]"),
  )
  for name, pattern, repl in substitutions:
    text, hit = pattern.subn(repl, text)
    if hit:
      counts[name] += hit
  return text, dict(counts)


def clean_utterances(raw_debate: str, extra_counts: Counter) -> list[str]:
  """Convert anonymized party transcript lines into concise substantive numbered utterances."""
  cleaned: list[str] = []
  for raw_line in raw_debate.splitlines():
    prefix, _, body = raw_line.partition("：")
    if prefix not in {"原告方", "被告方"}:
      continue
    scrubbed, counts = scrub_text_for_llm(body)
    extra_counts.update(counts)
    normalized = scrubbed.strip("。；，:： ")
    role_char = "原" if prefix == "原告方" else "被"
    check_body = normalized[1:] if normalized.startswith(role_char) else normalized
    if check_body in CLEAN_BOILERPLATE or len(check_body) <= 2:
      continue
    if DEMOGRAPHIC_LINE_RE.search(normalized) and len(normalized) <= 95:
      cleaned.append(f"{prefix}：[当事人身份及住址信息已脱敏]")
      continue
    cleaned.append(f"{prefix}：{scrubbed}")
  return cleaned


def is_clean_contested_case(claim: str, utterances: list[str], fact_desc: str) -> tuple[bool, str | None]:
  """Ensure single-claim first-instance contested civil private-lending eligibility."""
  if parse_rmb_amount(claim) is None:
    return False, "missing_claim_amount"
  combined = claim + "\n" + "\n".join(utterances) + "\n" + fact_desc
  if ABSENCE_OR_PUB_RE.search(combined):
    return False, "absence_or_publication_cue"
  if EXCLUSION_STAGE_RE.search(combined):
    return False, "appeal_mediation_or_withdrawal_cue"
  substantive_def = [
    u for u in utterances
    if u.startswith("被告方：") and "[当事人身份及住址信息已脱敏]" not in u
    and len(u.removeprefix("被告方：").strip("。；，:： ")) >= 4
  ]
  if not substantive_def:
    return False, "no_substantive_defendant_utterance"
  return True, None


def select_clean_candidates(data_root: Path, sample_size: int) -> tuple[list[dict[str, Any]], dict[str, int]]:
  """Stream raw MSJudge archive and deterministically pick clean contested first-instance cases."""
  archive_path = data_root / "raw/msjudge/judgment_prediction_dataset.zip"
  manifest = json.loads((archive_path.parent / "source-manifest.json").read_text())
  with archive_path.open("rb") as source:
    digest = hashlib.file_digest(source, "sha256").hexdigest()
  if (
    archive_path.stat().st_size != ARCHIVE_BYTES or digest != ARCHIVE_SHA256
    or manifest.get("commit") != COMMIT or manifest.get("sha256") != digest
  ):
    raise ValueError("Source archive/version does not match pinned MSJudge release")

  stats = Counter()
  seen_fingerprints: dict[str, str] = {}
  conflicting: set[str] = set()
  heap: list[tuple[int, str, dict[str, Any]]] = []

  with zipfile.ZipFile(archive_path) as archive:
    if archive.testzip() is not None:
      raise ValueError("ZIP CRC check failed")
    with archive.open(MEMBER) as raw, io.TextIOWrapper(raw, encoding="utf-8") as stream:
      for key, row in ObjectStream(stream).items():
        stats["scanned_cases"] += 1
        candidate, reason = prepare_candidate(key, row)
        if reason:
          stats[f"base_excluded_{reason}"] += 1
          continue
        fp = candidate["doc_id"]
        if fp in seen_fingerprints:
          if seen_fingerprints[fp] != candidate["outcome_label"]:
            conflicting.add(fp)
          stats["duplicate_pool_skipped"] += 1
          continue
        seen_fingerprints[fp] = candidate["outcome_label"]
        stats["base_unique_pool"] += 1

        fact_raw = compact(str(row.get("fact_description", "")))
        scrub_counts = Counter()
        clean_claim, claim_counts = scrub_text_for_llm(candidate["input_claim_text"])
        scrub_counts.update(claim_counts)
        utterances = clean_utterances(candidate["input_pre_judgment_text"], scrub_counts)
        fact_scrubbed, fact_counts = scrub_text_for_llm(fact_raw)
        scrub_counts.update(fact_counts)

        ok, clean_reason = is_clean_contested_case(clean_claim, utterances, fact_scrubbed)
        if not ok:
          stats[f"clean_excluded_{clean_reason}"] += 1
          continue
        stats["clean_contested_pool"] += 1

        # Re-verify zero judicial markers after utterance cleaning
        if any(m in clean_claim + "\n".join(utterances) for m in JUDICIAL_MARKERS):
          stats["clean_excluded_judicial_marker_post"] += 1
          continue

        record = {
          "doc_id": fp,
          "record_key": key,
          "cause_code": "private_lending",
          "outcome_label": LABELS[row["claims_labels"][0]],
          "raw_claim_amount_rule": parse_rmb_amount(clean_claim),
          "input_claim_text": clean_claim,
          "utterances": utterances,
          "fact_description_scrubbed": fact_scrubbed,
          "fact_labels": row.get("fact_labels", {}),
          "redaction_counts": dict(scrub_counts),
        }
        rank = -int(fp.removeprefix("msjudge_"), 16)
        entry = (rank, fp, record)
        if len(heap) < sample_size * 2:
          heapq.heappush(heap, entry)
        elif entry[:2] > heap[0][:2]:
          heapq.heapreplace(heap, entry)

  selected = sorted(
    (item[2] for item in heap if item[1] not in conflicting),
    key=lambda x: x["doc_id"],
  )[:sample_size]
  stats["selected_count"] = len(selected)
  return selected, dict(stats)


class InsufficientBalanceError(RuntimeError):
  pass


async def _call_json_validated(ai: AI, prompt: str, user_text: str, schema: type[BaseModel], max_retries: int = 4):
  last_err: Exception | None = None
  for attempt in range(max_retries):
    try:
      resp = await ai.complete_json([
        {"role": "system", "content": prompt},
        {"role": "user", "content": user_text},
      ], temperature=0)
      content = resp.choices[0].message.content or ""
      parsed = schema.model_validate_json(content)
      tokens = resp.usage.total_tokens if resp.usage else 0
      return parsed, tokens
    except Exception as exc:  # pragma: no cover - exercised under live transient faults
      msg = str(exc)
      if "insufficient_balance" in msg or "402" in msg:
        raise InsufficientBalanceError(msg) from exc
      last_err = exc
      if attempt + 1 < max_retries:
        await asyncio.sleep(2.0 * (attempt + 1))
  raise RuntimeError(f"LLM call failed after {max_retries} attempts: {last_err}") from last_err


def _truncate_utterances(utterances: list[str], max_chars: int = 9000) -> list[str]:
  kept: list[str] = []
  total = 0
  for item in utterances:
    if total + len(item) > max_chars and len(kept) >= 4:
      break
    kept.append(item)
    total += len(item) + 1
  return kept


def _enforce_ground_truth(
  outcome_label: str,
  claimed_principal: float | None,
  gt: GroundTruthLLMResult,
) -> GroundTruthLLMResult:
  if outcome_label == "fully_supported":
    supported = gt.supported_principal_yuan if gt.supported_principal_yuan is not None else claimed_principal
    return gt.model_copy(update={
      "case_win": True,
      "principal_support_tier": "full",
      "supported_principal_yuan": supported,
    })
  if outcome_label == "dismissed":
    return gt.model_copy(update={
      "case_win": False,
      "principal_support_tier": "rejected",
      "supported_principal_yuan": 0.0,
    })
  return gt


async def enrich_single_case(ai: AI, item: dict[str, Any]) -> dict[str, Any]:
  """Run isolated pre-judgment & ground-truth DeepSeek calls plus deterministic engine scoring."""
  kept_utterances = _truncate_utterances(item["utterances"])
  numbered_lines = "\n".join(f"[{idx}] {line}" for idx, line in enumerate(kept_utterances, start=1))
  sources = [
    {"rank": idx, "file_id": 1, "chunk_id": idx, "document_title": "庭审双方陈述", "snippet": line}
    for idx, line in enumerate(kept_utterances, start=1)
  ]
  pre_user = f"原告诉讼请求：{item['input_claim_text']}\n\n双方陈述摘要：\n{numbered_lines}"
  pre_res, pre_tokens = await _call_json_validated(ai, PRE_JUDGMENT_PROMPT, pre_user, PreJudgmentLLMResult)

  claim_amt = pre_res.metadata.claimed_principal_yuan or item["raw_claim_amount_rule"]
  if claim_amt is not None:
    pre_res.metadata.claimed_principal_yuan = round(float(claim_amt), 2)

  report = compute_win_rate(
    pre_res.win_rate_extraction,
    sources,
    {1: 0.85},
    "plaintiff_side",
    item["input_claim_text"],
    CalibrationParams(),
  )

  gt_user = (
    f"诉讼请求：{item['input_claim_text']}\n"
    f"MSJudge诉求结果标签(outcome_label)：{item['outcome_label']}\n"
    f"MSJudge客观事实标签(fact_labels)：{json.dumps(item['fact_labels'], ensure_ascii=False)}\n"
    f"审理查明事实(fact_description)：{item['fact_description_scrubbed'][:5000]}"
  )
  gt_raw, gt_tokens = await _call_json_validated(ai, GROUND_TRUTH_PROMPT, gt_user, GroundTruthLLMResult)
  gt = _enforce_ground_truth(item["outcome_label"], pre_res.metadata.claimed_principal_yuan, gt_raw)

  final_court = gt.court_level
  final_province = gt.province or pre_res.metadata.text_mentioned_province
  return {
    "doc_id": item["doc_id"],
    "cause_code": "private_lending",
    "judgment_date": gt.judgment_date,
    "filing_date": gt.filing_date,
    "borrowing_date": pre_res.metadata.borrowing_date,
    "maturity_date": pre_res.metadata.maturity_date,
    "text_mentioned_case_year": pre_res.metadata.text_mentioned_case_year,
    "procedure": pre_res.metadata.procedure,
    "procedure_detail": pre_res.metadata.procedure_detail,
    "court_level": final_court,
    "court_name_text": pre_res.metadata.text_mentioned_court,
    "province": final_province,
    "is_absent_defendant": pre_res.metadata.is_absent_defendant,
    "disposal_type": gt.disposal_type,
    "claimed_amount_yuan": pre_res.metadata.claimed_principal_yuan,
    "claimed_total_yuan": pre_res.metadata.claimed_total_yuan,
    "supported_amount_yuan": gt.supported_principal_yuan,
    "stance_target": "plaintiff_side",
    "input_claim_text": item["input_claim_text"],
    "input_pre_judgment_text": "\n".join(kept_utterances),
    "outcome_label": item["outcome_label"],
    "case_win": gt.case_win,
    "principal_support_tier": gt.principal_support_tier,
    "partial_reason": gt.partial_reason,
    "claim_outcomes": [{"claim_index": 1, "outcome_label": item["outcome_label"]}],
    "win_rate_prediction": {
      "win_rate_percent": report["win_rate"],
      "raw_support_score": report["raw_support_score"],
      "metric_kind": report["metric_kind"],
      "formula_version": report["formula_version"],
      "elements": report["elements"],
      "defeaters": report["defeaters"],
      "positive_factors": report["positive_factors"],
      "negative_factors": report["negative_factors"],
      "missing_evidence": report["missing_evidence"],
    },
    "calibration_eligible_chronological": False,
    "source": {"dataset": "MSJudge", "commit": COMMIT, "record_key": item["record_key"]},
    "preparation": {
      "version": "msjudge_llm_enriched_v1",
      "llm_model": None,
      "tokens_used": pre_tokens + gt_tokens,
      "redaction_counts": item["redaction_counts"],
      "privacy_review_complete": False,
      "field_provenance": {
        "claimed_amount_yuan": "llm_and_rule_extracted",
        "supported_amount_yuan": "ground_truth_llm_or_claim_derived" if gt.supported_principal_yuan is not None else "unquantified_in_fact",
        "case_win": "msjudge_label_plus_ground_truth_llm_principal_check",
        "procedure": "pre_judgment_llm_and_corpus",
        "is_absent_defendant": "rule_filtered_plus_llm_verified",
        "disposal_type": "ground_truth_llm_verified",
        "judgment_date": "text_extracted" if gt.judgment_date else "absent_in_msjudge_source",
        "court_level": "text_extracted" if final_court else "absent_in_msjudge_source",
        "province": "text_extracted" if final_province else "absent_in_msjudge_source",
      },
    },
  }


def _logit(p: float) -> float:
  p = max(1e-4, min(1.0 - 1e-4, p))
  return math.log(p / (1.0 - p))


def _sigmoid(x: float) -> float:
  if x >= 0:
    return 1.0 / (1.0 + math.exp(-x))
  z = math.exp(x)
  return z / (1.0 + z)


def _fit_platt_1d(xs: list[float], ys: list[int], steps: int = 2000, lr: float = 0.2) -> tuple[float, float]:
  """Lightweight pure-Python logistic calibration (p = sigmoid(gamma * x + bias)) with L2."""
  n = max(1, len(xs))
  gamma, bias = 1.0, _logit(sum(ys) / n)
  reg = 0.01
  for _ in range(steps):
    g_grad, b_grad = 0.0, 0.0
    for x, y in zip(xs, ys, strict=True):
      pred = _sigmoid(gamma * x + bias)
      err = pred - y
      g_grad += err * x
      b_grad += err
    gamma -= lr * (g_grad / n + reg * gamma)
    bias -= lr * (b_grad / n)
  return round(gamma, 4), round(bias, 4)


def _roc_auc(scores: list[float], ys: list[int]) -> float | None:
  pos = [s for s, y in zip(scores, ys, strict=True) if y == 1]
  neg = [s for s, y in zip(scores, ys, strict=True) if y == 0]
  if not pos or not neg:
    return None
  concordant = sum(1.0 if p > n else (0.5 if p == n else 0.0) for p in pos for n in neg)
  return round(concordant / (len(pos) * len(neg)), 4)


def evaluate_calibration(records: list[dict[str, Any]]) -> dict[str, Any]:
  """Compute Brier, LogLoss, ECE, subgroup means, and 5-fold CV diagnostic over enriched cases."""
  probs = [r["win_rate_prediction"]["win_rate_percent"] / 100.0 for r in records]
  raw_scores = [r["win_rate_prediction"]["raw_support_score"] / 100.0 for r in records]
  ys = [1 if r["case_win"] else 0 for r in records]
  n = len(records)

  def _metrics(ps: list[float], targets: list[int]) -> dict[str, float]:
    cnt = max(1, len(ps))
    brier = sum((p - y) ** 2 for p, y in zip(ps, targets, strict=True)) / cnt
    logloss = -sum(
      y * math.log(max(1e-6, p)) + (1 - y) * math.log(max(1e-6, 1.0 - p))
      for p, y in zip(ps, targets, strict=True)
    ) / cnt
    bins = [[] for _ in range(5)]
    for p, y in zip(ps, targets, strict=True):
      bins[min(4, int(p * 5))].append((p, y))
    ece = sum(
      (len(b) / cnt) * abs(sum(y for _, y in b) / len(b) - sum(p for p, _ in b) / len(b))
      for b in bins if b
    )
    return {"brier": round(brier, 4), "log_loss": round(logloss, 4), "ece_5bin": round(ece, 4)}

  # 5-fold deterministic CV (by doc_id order already SHA256 shuffled) for diagnostic Platt check
  logits = [_logit(s) for s in raw_scores]
  cv_preds = [0.5] * n
  fold_params = []
  for fold in range(5):
    train_x = [logits[i] for i in range(n) if i % 5 != fold]
    train_y = [ys[i] for i in range(n) if i % 5 != fold]
    g, b = _fit_platt_1d(train_x, train_y)
    fold_params.append((g, b))
    for i in range(n):
      if i % 5 == fold:
        cv_preds[i] = _sigmoid(g * logits[i] + b)
  full_gamma, full_bias = _fit_platt_1d(logits, ys)

  by_outcome: dict[str, list[float]] = {}
  for r in records:
    by_outcome.setdefault(r["outcome_label"], []).append(r["win_rate_prediction"]["win_rate_percent"])
  mean_by_outcome = {k: round(sum(v) / len(v), 2) for k, v in by_outcome.items()}

  return {
    "evaluated_cases": n,
    "case_win_rate": round(sum(ys) / max(1, n), 4),
    "roc_auc": _roc_auc(probs, ys),
    "uncalibrated_v1_metrics": _metrics(probs, ys),
    "offline_platt_cv_diagnostic_metrics": _metrics(cv_preds, ys),
    "offline_diagnostic_full_fit": {
      "gamma": full_gamma,
      "bias": full_bias,
      "warning": "MSJudge lack of chronological dates & commercial clearance prevents promoting these parameters to production.",
    },
    "mean_predicted_percent_by_outcome": mean_by_outcome,
  }


async def run_pipeline(data_root: Path, sample_size: int, concurrency: int) -> dict[str, Any]:
  selected, sel_stats = select_clean_candidates(data_root, sample_size)
  if len(selected) < sample_size:
    raise RuntimeError(f"Only {len(selected)} clean candidates found; expected {sample_size}")

  ckpt_path = data_root / "cleaned/msjudge-llm-checkpoint.jsonl"
  out_path = data_root / f"cleaned/msjudge-llm-reference-{sample_size}.jsonl"
  ckpt_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

  done_by_id: dict[str, dict[str, Any]] = {}
  if ckpt_path.exists():
    for line in ckpt_path.read_text(encoding="utf-8").splitlines():
      if not line.strip():
        continue
      row = json.loads(line)
      if row.get("preparation", {}).get("version") == "msjudge_llm_enriched_v1":
        done_by_id[row["doc_id"]] = row

  pending = [item for item in selected if item["doc_id"] not in done_by_id]
  print(json.dumps({
    "selected_target": len(selected),
    "cached_checkpoint": len(done_by_id),
    "pending_llm_calls": len(pending),
    "selection_stats": sel_stats,
  }, ensure_ascii=False), flush=True)

  settings = Settings(_env_file=BACKEND_ROOT / ".env")
  ai = AI(settings)
  ai.check(embeddings=False)
  sem = asyncio.Semaphore(concurrency)
  write_lock = asyncio.Lock()
  stop_event = asyncio.Event()
  failures: list[dict[str, str]] = []
  completed_now = 0

  async def worker(item: dict[str, Any]) -> None:
    nonlocal completed_now
    if stop_event.is_set():
      return
    async with sem:
      if stop_event.is_set():
        return
      try:
        enriched = await enrich_single_case(ai, item)
        enriched["preparation"]["llm_model"] = settings.deepseek_model
        async with write_lock:
          with ckpt_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(enriched, ensure_ascii=False) + "\n")
          ckpt_path.chmod(0o600)
          done_by_id[enriched["doc_id"]] = enriched
          completed_now += 1
          if completed_now % 25 == 0 or completed_now == len(pending):
            print(f"LLM enriched {completed_now}/{len(pending)} new cases (total cached={len(done_by_id)})", flush=True)
      except InsufficientBalanceError as exc:
        stop_event.set()
        async with write_lock:
          failures.append({"doc_id": item["doc_id"], "error": str(exc)})
      except Exception as exc:
        async with write_lock:
          failures.append({"doc_id": item["doc_id"], "error": str(exc)})

  try:
    await asyncio.gather(*(worker(item) for item in pending))
  finally:
    await ai.close()

  ordered = [done_by_id[item["doc_id"]] for item in selected if item["doc_id"] in done_by_id]
  with out_path.open("w", encoding="utf-8") as fh:
    for row in ordered:
      fh.write(json.dumps(row, ensure_ascii=False) + "\n")
  out_path.chmod(0o600)

  filled_fields = [
    "claimed_amount_yuan", "supported_amount_yuan", "case_win", "procedure",
    "is_absent_defendant", "disposal_type", "borrowing_date", "maturity_date",
    "filing_date", "judgment_date", "court_level", "province",
  ]
  coverage = {
    field: sum(1 for row in ordered if row.get(field) is not None)
    for field in filled_fields
  }
  eval_summary = evaluate_calibration(ordered) if ordered else {}
  total_tokens = sum(r["preparation"].get("tokens_used", 0) for r in ordered)

  model_counts = dict(Counter(r["preparation"].get("llm_model") for r in ordered))
  report = {
    "generated_at": datetime.now(UTC).isoformat(),
    "model": settings.deepseek_model,
    "models_used": model_counts,
    "selection_stats": sel_stats,
    "completed_cases": len(ordered),
    "failed_cases": failures,
    "total_tokens_used": total_tokens,
    "field_fill_counts": coverage,
    "outcome_counts": dict(Counter(r["outcome_label"] for r in ordered)),
    "case_win_counts": dict(Counter(str(r["case_win"]) for r in ordered)),
    "disposal_counts": dict(Counter(r["disposal_type"] for r in ordered)),
    "procedure_counts": dict(Counter(r["procedure"] for r in ordered)),
    "calibration_evaluation": eval_summary,
    "output_jsonl": str(out_path),
  }
  write_json(data_root / "reports/msjudge-llm-reference.json", report)

  md = (
    f"# MSJudge 离线脱敏填充与大模型评测报告\n\n"
    f"模型分布：`{json.dumps(model_counts, ensure_ascii=False)}`；实测完成样本：**{len(ordered)} 条**（失败 {len(failures)} 条），"
    f"累计消耗 Token：`{total_tokens:,}`。\n\n"
    f"从 {sel_stats.get('clean_contested_pool', 0):,} 条具备明确诉求金额、非缺席且具实质被告发言的一审民间借贷池中按输入哈希抽取 {sample_size} 条。"
    f"所有记录均在送入 DeepSeek 前先做本地手机号/邮箱/证件号/出生日期/住址/案号脱敏，且预测侧与结果真值侧调用严格隔离。\n\n"
    f"## 字段实测填充率（分母 {len(ordered)} 条）\n\n"
    + "\n".join(f"- `{k}`: {v}/{len(ordered)}" for k, v in coverage.items())
    + "\n\n## 当前生产要件引擎对照实测（`uncalibrated_v1` vs `case_win`）\n\n"
    + f"- 整案核心本金胜诉率 (`case_win=true`): {eval_summary.get('case_win_rate')}\n"
    + f"- 区分度指标 (`roc_auc`): {eval_summary.get('roc_auc')}\n"
    + f"- 未校准引擎指标: `{json.dumps(eval_summary.get('uncalibrated_v1_metrics', {}), ensure_ascii=False)}`\n"
    + f"- 离线 5 折 Platt 诊断指标（不自动升入生产）: `{json.dumps(eval_summary.get('offline_platt_cv_diagnostic_metrics', {}), ensure_ascii=False)}`\n"
    + f"- 离线诊断全量参数: `{json.dumps(eval_summary.get('offline_diagnostic_full_fit', {}), ensure_ascii=False)}`\n"
    + f"- 各结果标签平均预测值: `{json.dumps(eval_summary.get('mean_predicted_percent_by_outcome', {}), ensure_ascii=False)}`\n"
  )
  md_path = data_root / "reports/msjudge-llm-reference.md"
  md_path.write_text(md, encoding="utf-8")
  md_path.chmod(0o600)
  print(json.dumps({
    "completed_cases": len(ordered),
    "failed_cases": len(failures),
    "total_tokens": total_tokens,
    "field_fill_counts": coverage,
    "calibration_evaluation": eval_summary,
  }, ensure_ascii=False, indent=2))
  return report


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--data-root", type=Path, required=True)
  parser.add_argument("--sample-size", type=int, default=500)
  parser.add_argument("--concurrency", type=int, default=4)
  parser.add_argument("--allow-small", action="store_true")
  args = parser.parse_args()
  root = args.data_root.expanduser().resolve()
  repo = Path(__file__).resolve().parents[2]
  if root.is_relative_to(repo):
    parser.error("Real case data must be stored outside the repository")
  if not args.allow_small and args.sample_size < 300:
    parser.error("Reference dataset must contain at least 300 cases unless --allow-small is set")
  if not 1 <= args.concurrency <= 32:
    parser.error("concurrency must be between 1 and 32")
  os.umask(0o077)
  asyncio.run(run_pipeline(root, args.sample_size, args.concurrency))


if __name__ == "__main__":
  main()
