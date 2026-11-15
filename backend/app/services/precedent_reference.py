"""Optional anonymized precedent structural matcher for win-rate reports."""
from __future__ import annotations

import json
import math
import threading
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_GRADE_SCORE: dict[str, float] = {
  "proven": 1.0,
  "corroborated": 0.72,
  "weak": 0.35,
  "missing": 0.0,
  "rebutted": 0.0,
}

# Exclude generic "other_defense" because court opinions trigger it in ~88% of cases.
_SPECIFIC_DEFEATER_LABELS: dict[str, str] = {
  "repayment_offset": "已偿还或抵扣抗辩",
  "statutory_cap": "法定利率上限与利息扣减",
  "limitation_expired": "诉讼时效抗辩",
  "contract_invalidity": "借贷关系成立/效力争议",
  "procedural_defect": "主体适格或程序抗辩",
  "prior_breach_defense": "违约或对待给付抗辩",
}

_CACHE_LOCK = threading.Lock()
_CACHE: dict[str, tuple[int, dict[str, tuple[_PrecedentRecord, ...]]]] = {}


@dataclass(frozen=True, slots=True)
class _PrecedentRecord:
  cause_code: str
  outcome_label: str
  case_win: bool
  element_scores: dict[str, float]
  defeater_scores: dict[str, float]
  raw_support_score: float
  claimed_amount_yuan: float | None


def _extract_feature_vector(
  elements: list[dict[str, Any]],
  defeaters: list[dict[str, Any]],
  raw_support_score: Any,
  claimed_amount_yuan: Any,
) -> tuple[dict[str, float], dict[str, float], float, float | None]:
  element_scores: dict[str, float] = {}
  for el in elements:
    key = el.get("key")
    if not isinstance(key, str) or not key:
      continue
    score = _GRADE_SCORE.get(str(el.get("grade") or ""), 0.0)
    element_scores[key] = min(element_scores[key], score) if key in element_scores else score

  defeater_scores: dict[str, float] = {}
  for df in defeaters:
    key = df.get("key")
    presence = df.get("presence")
    if key in _SPECIFIC_DEFEATER_LABELS and presence in {"confirmed", "suspected"}:
      val = 1.0 if presence == "confirmed" else 0.5
      defeater_scores[key] = max(defeater_scores.get(key, 0.0), val)

  raw_score = float(raw_support_score) if isinstance(raw_support_score, (int, float)) else 50.0
  amount = float(claimed_amount_yuan) if isinstance(claimed_amount_yuan, (int, float)) and claimed_amount_yuan > 0 else None
  return element_scores, defeater_scores, raw_score, amount


def _load_grouped_records(path_str: str | None) -> dict[str, tuple[_PrecedentRecord, ...]]:
  if not path_str:
    return {}
  path = Path(path_str).expanduser()
  try:
    stat = path.stat()
  except OSError:
    return {}
  if not path.is_file():
    return {}

  cache_key = str(path.resolve())
  with _CACHE_LOCK:
    cached = _CACHE.get(cache_key)
    if cached and cached[0] == stat.st_mtime_ns:
      return cached[1]

  grouped: dict[str, list[_PrecedentRecord]] = {}
  with path.open(encoding="utf-8") as fh:
    for line in fh:
      raw = line.strip()
      if not raw:
        continue
      try:
        item = json.loads(raw)
      except json.JSONDecodeError:
        continue
      pred = item.get("win_rate_prediction")
      cause_code = item.get("cause_code") or (pred or {}).get("cause_code")
      outcome_label = item.get("outcome_label")
      if not isinstance(pred, dict) or not isinstance(cause_code, str) or outcome_label not in {
        "fully_supported", "partially_supported", "dismissed",
      }:
        continue
      el_scores, df_scores, raw_score, amount = _extract_feature_vector(
        pred.get("elements") or [],
        pred.get("defeaters") or [],
        pred.get("raw_support_score"),
        item.get("claimed_amount_yuan"),
      )
      grouped.setdefault(cause_code, []).append(_PrecedentRecord(
        cause_code=cause_code,
        outcome_label=outcome_label,
        case_win=bool(item.get("case_win")),
        element_scores=el_scores,
        defeater_scores=df_scores,
        raw_support_score=raw_score,
        claimed_amount_yuan=amount,
      ))

  frozen = {k: tuple(v) for k, v in grouped.items()}
  with _CACHE_LOCK:
    _CACHE[cache_key] = (stat.st_mtime_ns, frozen)
  return frozen


def _similarity(
  q_el: dict[str, float],
  q_df: dict[str, float],
  q_raw: float,
  q_amt: float | None,
  rec: _PrecedentRecord,
) -> float:
  el_keys = set(q_el) | set(rec.element_scores)
  if el_keys:
    el_diff = sum(abs(q_el.get(k, 0.5) - rec.element_scores.get(k, 0.5)) for k in el_keys) / len(el_keys)
    esim = 1.0 - el_diff
  else:
    esim = 0.5

  df_keys = set(q_df) | set(rec.defeater_scores)
  if not df_keys:
    dsim = 1.0
  else:
    num = sum(min(q_df.get(k, 0.0), rec.defeater_scores.get(k, 0.0)) for k in df_keys)
    den = sum(max(q_df.get(k, 0.0), rec.defeater_scores.get(k, 0.0)) for k in df_keys)
    dsim = num / den if den else 1.0

  ssim = max(0.0, 1.0 - abs(q_raw - rec.raw_support_score) / 100.0)
  if q_amt and rec.claimed_amount_yuan and q_amt > 0 and rec.claimed_amount_yuan > 0:
    asim = max(0.0, 1.0 - abs(math.log10(q_amt) - math.log10(rec.claimed_amount_yuan)) / 3.0)
  else:
    asim = 0.5

  return 0.45 * esim + 0.25 * dsim + 0.25 * ssim + 0.05 * asim


def match_precedent_reference(
  report: dict[str, Any],
  reference_path: str | None,
  *,
  top_k: int = 15,
) -> dict[str, Any] | None:
  """Return aggregated structural precedent outcome stats without PII or calibration overwrite."""
  if not report.get("applicable") or not reference_path:
    return None
  cause_code = report.get("cause_code")
  if not isinstance(cause_code, str) or not cause_code:
    return None
  pool = _load_grouped_records(reference_path).get(cause_code)
  if not pool:
    return None

  claim_amounts = [
    float(c["amount_yuan"])
    for c in (report.get("claims") or [])
    if isinstance(c, dict) and isinstance(c.get("amount_yuan"), (int, float)) and c["amount_yuan"] > 0
  ]
  query_amount = sum(claim_amounts) if claim_amounts else None
  q_el, q_df, q_raw, q_amt = _extract_feature_vector(
    report.get("elements") or [],
    report.get("defeaters") or [],
    report.get("raw_support_score"),
    query_amount,
  )

  scored = [(_similarity(q_el, q_df, q_raw, q_amt, rec), idx, rec) for idx, rec in enumerate(pool)]
  scored.sort(key=lambda item: (-item[0], item[1]))
  matched = scored[: max(1, min(top_k, len(scored)))]

  outcome_counts = Counter(item[2].outcome_label for item in matched)
  win_count = sum(1 for item in matched if item[2].case_win)
  sim_avg = round(sum(item[0] for item in matched) * 100.0 / len(matched), 1)
  risk_counts = Counter(
    key
    for item in matched
    for key in item[2].defeater_scores
  )
  common_risks = [
    {"key": key, "label": _SPECIFIC_DEFEATER_LABELS[key], "count": count}
    for key, count in risk_counts.most_common(3)
    if key in _SPECIFIC_DEFEATER_LABELS
  ]

  return {
    "dataset_label": "MSJudge 清洁裁判特征库（离线脱敏参照）",
    "cause_code": cause_code,
    "pool_count": len(pool),
    "matched_count": len(matched),
    "similarity_avg": sim_avg,
    "outcome_counts": {
      "fully_supported": outcome_counts.get("fully_supported", 0),
      "partially_supported": outcome_counts.get("partially_supported", 0),
      "dismissed": outcome_counts.get("dismissed", 0),
    },
    "principal_support_rate": round(win_count * 100.0 / len(matched), 1),
    "perspective_note": "统计口径为相似结构判例中原告核心诉求获法院实质支持的比例；若我方为被告，请结合抗辩空间反向评估。",
    "common_risk_factors": common_risks,
    "caveat": "该离线样本源自公开生效判决（缺裁判日期、法院层级且存在法院样本偏态），仅作同结构判例结果分布参考，不改变当前未经判例校准的要件支撑度数值。",
  }
