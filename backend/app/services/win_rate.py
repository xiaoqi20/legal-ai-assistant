import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

FORMULA_VERSION = "1.0"
RUBRIC_VERSION = "1.0"
CALIBRATION_VERSION = "uncalibrated_v1"

Grade = Literal["proven", "corroborated", "weak", "missing", "rebutted"]
DefeaterPresence = Literal["confirmed", "suspected", "absent"]
CauseCode = Literal[
  "private_lending",
  "sales_contract",
  "lease_contract",
  "property_service",
  "labor_dispute",
  "general_civil",
]

GRADE_SCORES: dict[Grade, float] = {
  "proven": 0.92,
  "corroborated": 0.72,
  "weak": 0.38,
  "missing": 0.08,
  "rebutted": 0.05,
}

GRADE_LABELS: dict[Grade, str] = {
  "proven": "充分印证",
  "corroborated": "基本印证（待补强）",
  "weak": "弱支撑",
  "missing": "证据缺失",
  "rebutted": "被反驳",
}

DEFEATER_PRESENCE_WEIGHTS: dict[DefeaterPresence, float] = {
  "confirmed": 1.0,
  "suspected": 0.45,
  "absent": 0.0,
}

MATERIAL_TRUST: dict[str, float] = {
  "lawyer_approved": 1.0,
  "ai_passed": 0.85,
  "lawyer_pending": 0.85,
  "draft": 0.55,
  "ai_analyzing": 0.55,
  "ai_failed": 0.0,
  "lawyer_rejected": 0.0,
  "withdrawn": 0.0,
}
STANDALONE_DOC_TRUST = 0.75

SUPPORTED_PROCEDURES = {"first_instance", "second_instance", "retrial", "arbitration"}
DEFENDANT_MARKERS = ("被申请人", "被上诉人", "原审被告", "被告", "被执行人", "被起诉方")
PLAINTIFF_MARKERS = ("申请再审人", "原审原告", "原告", "申请人", "上诉人", "起诉方")
THIRD_PARTY_MARKERS = ("第三人", "案外人")


@dataclass(frozen=True)
class RubricElement:
  key: str
  label: str
  weight: float
  required: bool = True


CAUSE_LABELS: dict[CauseCode, str] = {
  "private_lending": "民间借贷纠纷",
  "sales_contract": "买卖合同纠纷",
  "lease_contract": "租赁合同纠纷",
  "property_service": "物业服务合同纠纷",
  "labor_dispute": "劳动争议",
  "general_civil": "通用民商事请求权纠纷",
}

CAUSE_RUBRICS: dict[CauseCode, tuple[RubricElement, ...]] = {
  "private_lending": (
    RubricElement("lending_intent", "借贷合意", 0.25, True),
    RubricElement("fund_delivery", "款项实际交付", 0.35, True),
    RubricElement("maturity_breach", "借期届满及逾期未还", 0.25, True),
    RubricElement("interest_agreement", "利息与违约金约定", 0.15, False),
  ),
  "sales_contract": (
    RubricElement("contract_validity", "买卖合同成立与生效", 0.25, True),
    RubricElement("performance_delivery", "标的物交付履行", 0.30, True),
    RubricElement("acceptance_notice", "验收及质量异议情况", 0.20, True),
    RubricElement("payment_default", "货款结算与拖欠事实", 0.25, True),
  ),
  "lease_contract": (
    RubricElement("lease_validity", "租赁合同效力", 0.25, True),
    RubricElement("possession_delivery", "租赁物交付占有", 0.25, True),
    RubricElement("rent_breach", "欠付租金或违约事实", 0.30, True),
    RubricElement("notice_termination", "催告解除与腾退核验", 0.20, False),
  ),
  "property_service": (
    RubricElement("service_contract_scope", "物业服务合同及收费权", 0.25, True),
    RubricElement("actual_service_rendered", "物业服务实际履行", 0.30, True),
    RubricElement("fee_standard_arrears", "收费标准与欠费核算", 0.30, True),
    RubricElement("notice_termination", "催缴通知程序", 0.15, False),
  ),
  "labor_dispute": (
    RubricElement("labor_relationship", "劳动关系成立", 0.30, True),
    RubricElement("attendance_salary_base", "考勤与工资基数", 0.25, True),
    RubricElement("termination_legality", "解除或欠薪违法性", 0.30, True),
    RubricElement("notice_termination", "仲裁时效与通知程序", 0.15, False),
  ),
  "general_civil": (
    RubricElement("statutory_basis", "请求权基础与法律关系", 0.25, True),
    RubricElement("contract_validity", "合同或法律行为效力", 0.25, True),
    RubricElement("performance_delivery", "己方履行与对方违约", 0.30, True),
    RubricElement("causation_loss", "损失数额与因果关系", 0.20, True),
  ),
}


@dataclass(frozen=True)
class CalibrationParams:
  prior: float = 0.5
  gamma: float = 1.0
  bias: float = 0.0
  metric_kind: Literal["uncalibrated_rubric", "calibrated_empirical"] = "uncalibrated_rubric"
  calibration_version: str = CALIBRATION_VERSION


class ClaimItem(BaseModel):
  model_config = ConfigDict(extra="forbid")
  index: int = Field(ge=0)
  title: str = Field(min_length=1, max_length=200)
  amount_yuan: float | None = Field(default=None, ge=0)
  priority_weight: float = Field(default=1.0, gt=0)


class ElementExtraction(BaseModel):
  model_config = ConfigDict(extra="forbid")
  key: str = Field(min_length=1, max_length=80)
  label: str = Field(min_length=1, max_length=120)
  scope_claim_index: int | None = Field(default=None, ge=0)
  grade: Grade
  citation_ranks: list[int] = Field(default_factory=list)
  summary: str = Field(min_length=1, max_length=500)


class DefeaterExtraction(BaseModel):
  model_config = ConfigDict(extra="forbid")
  key: str = Field(min_length=1, max_length=80)
  label: str = Field(min_length=1, max_length=120)
  scope_claim_index: int | None = Field(default=None, ge=0)
  presence: DefeaterPresence
  lethality: float = Field(ge=0.0, le=1.0)
  citation_ranks: list[int] = Field(default_factory=list)
  summary: str = Field(min_length=1, max_length=500)


class WinRateExtraction(BaseModel):
  model_config = ConfigDict(extra="forbid")
  cause_code: CauseCode = "general_civil"
  claims: list[ClaimItem] = Field(default_factory=list, max_length=20)
  elements: list[ElementExtraction] = Field(default_factory=list, max_length=40)
  defeaters: list[DefeaterExtraction] = Field(default_factory=list, max_length=20)
  positive_factors: list[str] = Field(default_factory=list, max_length=8)
  negative_factors: list[str] = Field(default_factory=list, max_length=8)
  missing_evidence: list[str] = Field(default_factory=list, max_length=8)
  limitations: str = Field(default="", max_length=600)


@dataclass(frozen=True)
class EligibilityResult:
  eligible: bool
  stance: Literal["plaintiff_side", "defendant_side", "ambiguous"]
  reason_code: str | None = None
  reason_message: str | None = None
  usable_file_ids: tuple[int, ...] = ()


def determine_stance(
  party_role_label: str | None,
  parties: list[dict[str, Any]],
) -> Literal["plaintiff_side", "defendant_side", "third_party", "ambiguous"]:
  """Infer whether our client stands on the attacking (plaintiff) or defending side."""
  label = (party_role_label or "").strip()
  if label:
    if any(m in label for m in THIRD_PARTY_MARKERS):
      return "third_party"
    if any(m in label for m in DEFENDANT_MARKERS):
      return "defendant_side"
    if any(m in label for m in PLAINTIFF_MARKERS):
      return "plaintiff_side"

  our_roles = {p.get("party_role") for p in parties if p.get("side") == "our"}
  if not our_roles:
    return "ambiguous"
  if "third_party" in our_roles:
    return "third_party"
  has_plaintiff = bool(our_roles & {"plaintiff", "applicant"})
  has_defendant = bool(our_roles & {"defendant", "respondent"})
  if has_plaintiff and not has_defendant:
    return "plaintiff_side"
  if has_defendant and not has_plaintiff:
    return "defendant_side"
  return "ambiguous"


def compute_file_trust_map(
  files: list[dict[str, Any]],
  materials: list[dict[str, Any]],
  links: list[dict[str, Any]],
) -> dict[int, float]:
  """Map each ready file_id to its credibility coefficient tau based on linked evidence items."""
  mat_by_id = {m["id"]: m for m in materials}
  bound_statuses: dict[int, list[str]] = {}
  for link in links:
    mat = mat_by_id.get(link["evidence_item_id"])
    if not mat or mat["status"] == "withdrawn":
      continue
    bound_statuses.setdefault(link["file_id"], []).append(mat["status"])

  trust_map: dict[int, float] = {}
  for f in files:
    if f.get("status") != "available":
      continue
    statuses = bound_statuses.get(f["id"])
    if not statuses:
      trust_map[f["id"]] = STANDALONE_DOC_TRUST
    else:
      trust_map[f["id"]] = max(MATERIAL_TRUST.get(s, 0.55) for s in statuses)
  return trust_map


def check_win_rate_eligibility(
  case_row: dict[str, Any],
  parties: list[dict[str, Any]],
  files: list[dict[str, Any]],
  materials: list[dict[str, Any]],
  links: list[dict[str, Any]],
) -> EligibilityResult:
  """Stage 0 hard eligibility and abstention gate."""
  if case_row.get("case_type") != "civil":
    return EligibilityResult(False, "ambiguous", "non_civil_case",
      "当前测算模型仅适用于民商事诉讼与仲裁案件，刑事、行政或未定类型案件暂不适用。")

  if case_row.get("procedure") not in SUPPORTED_PROCEDURES:
    return EligibilityResult(False, "ambiguous", "unsupported_procedure",
      "当前案件程序（如执行程序或尚未确定程序）暂不适用实体胜诉率测算。")

  stance = determine_stance(case_row.get("party_role_label"), parties)
  if stance == "third_party":
    return EligibilityResult(False, "ambiguous", "unsupported_third_party",
      "第三人或案外人诉讼地位暂不适用双方胜诉率测算。")
  if stance == "ambiguous":
    return EligibilityResult(False, "ambiguous", "missing_stance",
      "尚未明确我方诉讼地位（如原告/被告、申请人/被申请人），请补充当事人地位后再测算。")

  if not (case_row.get("claim") or "").strip():
    return EligibilityResult(False, stance, "missing_claim",
      "尚未填写明确的诉讼或仲裁请求，无法界定证明目标与胜诉率。")

  active_files = [f for f in files if f.get("status") != "deleted"]
  if any((f.get("metadata") or {}).get("parse_status") == "review_required" for f in active_files):
    return EligibilityResult(False, stance, "pending_ocr_review",
      "存在待人工复核的 OCR 识别文档，请先确认识别文本或移除该文件后再测算。")

  ready_files = [
    f for f in active_files
    if f.get("status") == "available" and (f.get("metadata") or {}).get("parse_status") == "succeeded"
  ]
  if not ready_files:
    processing = any(
      f.get("status") == "uploading"
      or (f.get("metadata") or {}).get("parse_status") in {"queued", "index_queued", "retrying"}
      for f in active_files
    )
    if processing:
      return EligibilityResult(False, stance, "processing_documents",
        "案件文档仍在上传或解析中，请等待解析完成后再评估。")
    return EligibilityResult(False, stance, "insufficient_evidence",
      "当前案件尚无已完成解析的有效文档或证据材料，暂无法进行要件支撑度测算。")

  trust_map = compute_file_trust_map(ready_files, materials, links)
  usable = tuple(f["id"] for f in ready_files if trust_map.get(f["id"], 0.0) > 0.0)
  if not usable:
    return EligibilityResult(False, stance, "all_materials_rejected",
      "已上传材料均处于未采信或已驳回状态，暂无可采信证据支撑胜诉率测算。")

  return EligibilityResult(True, stance, usable_file_ids=usable)


def compute_input_fingerprint(
  case_row: dict[str, Any],
  parties: list[dict[str, Any]],
  files: list[dict[str, Any]],
  materials: list[dict[str, Any]],
  links: list[dict[str, Any]],
) -> str:
  """Compute deterministic SHA-256 over all case inputs affecting win_rate."""
  active_files = sorted(
    [
      {
        "id": f["id"],
        "status": f.get("status"),
        "sha256": f.get("sha256"),
        "parse_status": (f.get("metadata") or {}).get("parse_status"),
        "chunk_count": (f.get("metadata") or {}).get("chunk_count"),
      }
      for f in files
      if f.get("status") != "deleted"
    ],
    key=lambda x: x["id"],
  )
  active_materials = sorted(
    [
      {
        "id": m["id"],
        "status": m.get("status"),
        "revision": m.get("revision"),
      }
      for m in materials
      if m.get("status") != "withdrawn"
    ],
    key=lambda x: x["id"],
  )
  active_mat_ids = {m["id"] for m in active_materials}
  active_links = sorted(
    [(link["evidence_item_id"], link["file_id"]) for link in links if link["evidence_item_id"] in active_mat_ids]
  )
  sorted_parties = sorted(
    [(p.get("side") or "", p.get("party_role") or "", p.get("name") or "") for p in parties]
  )
  payload = {
    "formula_version": FORMULA_VERSION,
    "rubric_version": RUBRIC_VERSION,
    "case": {
      "case_type": case_row.get("case_type"),
      "procedure": case_row.get("procedure"),
      "title": case_row.get("title"),
      "summary": case_row.get("summary"),
      "claim": case_row.get("claim"),
      "handling_identity": case_row.get("handling_identity"),
      "party_role_label": case_row.get("party_role_label"),
    },
    "parties": sorted_parties,
    "files": active_files,
    "materials": active_materials,
    "links": active_links,
  }
  encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
  return hashlib.sha256(encoded).hexdigest()


def _verify_citations(
  ranks: list[int],
  sources: list[dict[str, Any]],
  file_trust_map: dict[int, float],
) -> tuple[list[int], float]:
  valid: list[int] = []
  max_trust = 0.0
  for r in ranks:
    if isinstance(r, int) and 1 <= r <= len(sources):
      file_id = sources[r - 1].get("file_id")
      trust = file_trust_map.get(file_id, STANDALONE_DOC_TRUST)
      if trust > 0.0:
        valid.append(r)
        if trust > max_trust:
          max_trust = trust
  return valid, max_trust


def _logit(p: float) -> float:
  clamped = max(1e-4, min(1.0 - 1e-4, p))
  return math.log(clamped / (1.0 - clamped))


def _sigmoid(z: float) -> float:
  if z >= 0:
    return 1.0 / (1.0 + math.exp(-z))
  ez = math.exp(z)
  return ez / (1.0 + ez)


def _normalize_claim_weights(claims: list[ClaimItem]) -> list[float]:
  n = len(claims)
  if n == 1:
    return [1.0]
  if all(c.amount_yuan is not None and c.amount_yuan > 0 for c in claims):
    raw = [float(c.amount_yuan) for c in claims]
  else:
    raw = [float(c.priority_weight) for c in claims]
  total = sum(raw) or float(n)
  weights = [x / total for x in raw]
  # Primary claim floor >= 0.50 when there are multiple claims
  if weights[0] < 0.50:
    rest = sum(weights[1:])
    weights[0] = 0.50
    if rest > 0:
      scale = 0.50 / rest
      for i in range(1, n):
        weights[i] *= scale
    else:
      for i in range(1, n):
        weights[i] = 0.50 / (n - 1)
  return weights


def _active_elements(elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
  # Optional rubric elements (e.g. interest clause on a principal-only claim) should not penalize when missing.
  active = [e for e in elements if e["required"] or e["grade"] != "missing"]
  return active or elements


def _score_plaintiff_claim(
  elements: list[dict[str, Any]],
  defeaters: list[dict[str, Any]],
) -> float:
  scored = _active_elements(elements)
  total_w = sum(e["weight"] for e in scored) or 1.0
  log_sum = sum((e["weight"] / total_w) * math.log(max(e["certainty"], 1e-4)) for e in scored)
  g_mean = math.exp(log_sum)
  req_scores = [e["certainty"] for e in elements if e["required"]] or [e["certainty"] for e in scored]
  c_min = min(req_scores)
  base_score = min(g_mean, 0.25 + 0.50 * c_min) if c_min < 0.50 else g_mean
  attenuation = 1.0
  for d in defeaters:
    attenuation *= 1.0 - d["impact"]
  return max(0.02, min(0.98, base_score * attenuation))


def _score_defendant_claim(
  elements: list[dict[str, Any]],
  defeaters: list[dict[str, Any]],
) -> float:
  scored = _active_elements(elements)
  total_w = sum(e["weight"] for e in scored) or 1.0
  survival = 1.0
  for e in scored:
    alpha_k = e["weight"] / total_w
    u_k = max(0.0, min(0.95, 1.0 - e["certainty"]))
    eta_k = max(alpha_k, 0.75) if (e["required"] and e["certainty"] < 0.50) else alpha_k
    survival *= 1.0 - max(0.0, min(0.95, eta_k * u_k))
  for d in defeaters:
    survival *= 1.0 - d["impact"]
  return max(0.02, min(0.98, 1.0 - survival))


def compute_win_rate(
  extraction: WinRateExtraction,
  sources: list[dict[str, Any]],
  file_trust_map: dict[int, float],
  stance: Literal["plaintiff_side", "defendant_side"],
  claim_text: str | None = None,
  calibration: CalibrationParams = CalibrationParams(),
) -> dict[str, Any]:
  """Pure deterministic scoring & Bayesian-logit mapping over verified legal-element annotations."""
  claims = list(extraction.claims) or [
    ClaimItem(index=0, title=(claim_text or "核心诉求")[:200], amount_yuan=None, priority_weight=1.0)
  ]
  claim_weights = _normalize_claim_weights(claims)

  rubric = CAUSE_RUBRICS[extraction.cause_code]
  rubric_by_key = {item.key: item for item in rubric}

  verified_elements: list[dict[str, Any]] = []
  seen_keys: set[str] = set()
  for el in extraction.elements:
    valid_ranks, trust = _verify_citations(el.citation_ranks, sources, file_trust_map)
    effective_grade: Grade = el.grade
    note = el.summary
    if el.grade != "missing" and not valid_ranks:
      effective_grade = "missing"
      certainty = GRADE_SCORES["missing"]
      note = f"{el.summary}（无有效引用或对应材料未采信，系统已降级为缺失）"
    elif effective_grade == "missing":
      certainty = GRADE_SCORES["missing"]
    else:
      raw = GRADE_SCORES["missing"] + trust * (GRADE_SCORES[effective_grade] - GRADE_SCORES["missing"])
      certainty = round(max(0.03, min(0.96, raw)), 4)

    tmpl = rubric_by_key.get(el.key)
    seen_keys.add(el.key)
    verified_elements.append({
      "key": el.key,
      "label": el.label,
      "scope_claim_index": el.scope_claim_index,
      "grade": effective_grade,
      "grade_label": GRADE_LABELS[effective_grade],
      "certainty": certainty,
      "citation_ranks": valid_ranks,
      "trust": round(trust, 2),
      "weight": tmpl.weight if tmpl else 0.10,
      "required": tmpl.required if tmpl else False,
      "summary": note,
    })

  # Guard against LLM omitting required rubric elements
  for tmpl in rubric:
    if tmpl.key not in seen_keys:
      verified_elements.append({
        "key": tmpl.key,
        "label": tmpl.label,
        "scope_claim_index": None,
        "grade": "missing",
        "grade_label": GRADE_LABELS["missing"],
        "certainty": GRADE_SCORES["missing"],
        "citation_ranks": [],
        "trust": 0.0,
        "weight": tmpl.weight,
        "required": tmpl.required,
        "summary": "现有材料中未充分体现该核心要件，按证据缺失计入评估。",
      })

  verified_defeaters: list[dict[str, Any]] = []
  for df in extraction.defeaters:
    valid_ranks, trust = _verify_citations(df.citation_ranks, sources, file_trust_map)
    eff_presence: DefeaterPresence = df.presence
    if df.presence != "absent" and not valid_ranks:
      eff_presence = "absent"
    strength = DEFEATER_PRESENCE_WEIGHTS[eff_presence] * (trust if eff_presence != "absent" else 0.0)
    impact = round(max(0.0, min(0.95, strength * df.lethality)), 4)
    verified_defeaters.append({
      "key": df.key,
      "label": df.label,
      "scope_claim_index": df.scope_claim_index,
      "presence": eff_presence,
      "lethality": df.lethality,
      "impact": impact,
      "citation_ranks": valid_ranks,
      "summary": df.summary,
    })

  claim_breakdowns: list[dict[str, Any]] = []
  agg_prob = 0.0
  for pos, claim in enumerate(claims):
    scoped_els = [e for e in verified_elements if e["scope_claim_index"] in (None, claim.index)]
    if not scoped_els:
      scoped_els = verified_elements
    scoped_defs = [d for d in verified_defeaters if d["scope_claim_index"] in (None, claim.index)]
    raw_score = (
      _score_plaintiff_claim(scoped_els, scoped_defs)
      if stance == "plaintiff_side"
      else _score_defendant_claim(scoped_els, scoped_defs)
    )
    weight = claim_weights[pos]
    agg_prob += weight * raw_score
    claim_breakdowns.append({
      "index": claim.index,
      "title": claim.title,
      "amount_yuan": claim.amount_yuan,
      "weight": round(weight, 4),
      "support_score": round(raw_score * 100, 2),
    })

  logit_score = _logit(calibration.prior) + calibration.gamma * _logit(agg_prob) + calibration.bias
  calibrated_prob = _sigmoid(logit_score)
  win_rate = round(max(5.0, min(95.0, calibrated_prob * 100.0)), 2)

  return {
    "applicable": True,
    "win_rate": win_rate,
    "metric_kind": calibration.metric_kind,
    "metric_label": (
      "历史判例校准胜诉率"
      if calibration.metric_kind == "calibrated_empirical"
      else "AI 要件支撑度预估（未经判例校准）"
    ),
    "stance": stance,
    "cause_code": extraction.cause_code,
    "cause_label": CAUSE_LABELS[extraction.cause_code],
    "raw_support_score": round(agg_prob * 100.0, 2),
    "formula_version": FORMULA_VERSION,
    "rubric_version": RUBRIC_VERSION,
    "calibration_version": calibration.calibration_version,
    "claims": claim_breakdowns,
    "elements": verified_elements,
    "defeaters": verified_defeaters,
    "positive_factors": extraction.positive_factors,
    "negative_factors": extraction.negative_factors,
    "missing_evidence": extraction.missing_evidence,
    "limitations": extraction.limitations or "本结果基于当前已提交文书与证据原文进行要件映射。",
    "disclaimer": "当前结果为基于案件证据与法定要件的结构化支撑度测算，未经历史判例统计校准，仅供办案风险研判参考，不构成对裁判结果的承诺或法律意见。",
  }
