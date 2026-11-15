import pytest

from app.services.win_rate import (
  CalibrationParams,
  ClaimItem,
  DefeaterExtraction,
  ElementExtraction,
  WinRateExtraction,
  check_win_rate_eligibility,
  compute_file_trust_map,
  compute_input_fingerprint,
  compute_win_rate,
  determine_stance,
)


def _sources(count=4, file_ids=None):
  fids = file_ids or [10, 11, 12, 13]
  return [{"rank": i + 1, "file_id": fids[i % len(fids)], "chunk_id": 100 + i, "relevance": 0.9} for i in range(count)]


def _lending_elements(fund_grade="proven", fund_ranks=None):
  return [
    ElementExtraction(key="lending_intent", label="借贷合意", grade="proven", citation_ranks=[1], summary="借条载明合意"),
    ElementExtraction(key="fund_delivery", label="款项实际交付", grade=fund_grade,
      citation_ranks=[2] if fund_ranks is None and fund_grade != "missing" else (fund_ranks or []), summary="银行流水"),
    ElementExtraction(key="maturity_breach", label="借期届满及逾期未还", grade="proven", citation_ranks=[3], summary="催收记录"),
    ElementExtraction(key="interest_agreement", label="利息与违约金约定", grade="proven", citation_ranks=[1], summary="利息条款"),
  ]


def test_plaintiff_full_proven_and_bottleneck_cap():
  trust = {10: 1.0, 11: 1.0, 12: 1.0, 13: 1.0}
  full_ext = WinRateExtraction(cause_code="private_lending", claims=[ClaimItem(index=0, title="归还本金", amount_yuan=100000)],
    elements=_lending_elements("proven"))
  full_res = compute_win_rate(full_ext, _sources(), trust, "plaintiff_side")
  assert full_res["metric_kind"] == "uncalibrated_rubric"
  assert full_res["win_rate"] >= 88.0

  missing_ext = WinRateExtraction(cause_code="private_lending", claims=[ClaimItem(index=0, title="归还本金", amount_yuan=100000)],
    elements=_lending_elements("missing", fund_ranks=[]))
  missing_res = compute_win_rate(missing_ext, _sources(), trust, "plaintiff_side")
  # Hard bottleneck cap <= 0.25 + 0.5 * 0.08 = 0.29 (29%)
  assert missing_res["win_rate"] <= 30.0

  # Optional element missing (e.g. principal-only loan without interest clause) must not penalize strong required core
  no_interest_elements = _lending_elements("proven")[:-1] + [
    ElementExtraction(key="interest_agreement", label="利息与违约金约定", grade="missing", citation_ranks=[], summary="未主张利息"),
  ]
  no_int_res = compute_win_rate(
    WinRateExtraction(cause_code="private_lending", elements=no_interest_elements),
    _sources(), trust, "plaintiff_side",
  )
  assert no_int_res["win_rate"] >= 88.0


def test_defendant_noisy_or_duality_and_defeaters():
  trust = {10: 1.0, 11: 1.0, 12: 1.0, 13: 1.0}
  strong_pl = WinRateExtraction(cause_code="private_lending", elements=_lending_elements("proven"))
  def_weak = compute_win_rate(strong_pl, _sources(), trust, "defendant_side")
  assert def_weak["win_rate"] <= 15.0

  gap_pl = WinRateExtraction(cause_code="private_lending", elements=_lending_elements("missing", fund_ranks=[]))
  def_strong = compute_win_rate(gap_pl, _sources(), trust, "defendant_side")
  assert def_strong["win_rate"] >= 65.0

  with_defeater = WinRateExtraction(
    cause_code="private_lending",
    elements=_lending_elements("proven"),
    defeaters=[DefeaterExtraction(
      key="limitation_expired", label="已过三年诉讼时效", presence="confirmed",
      lethality=0.90, citation_ranks=[4], summary="聊天与催收中断无证据",
    )],
  )
  pl_defeated = compute_win_rate(with_defeater, _sources(), trust, "plaintiff_side")
  def_wins = compute_win_rate(with_defeater, _sources(), trust, "defendant_side")
  assert pl_defeated["win_rate"] <= 15.0
  assert def_wins["win_rate"] >= 85.0


def test_anti_hallucination_invalid_citation_and_rejected_material():
  files = [{"id": 10, "status": "available"}, {"id": 11, "status": "available"}]
  materials = [{"id": 1, "status": "lawyer_approved"}, {"id": 2, "status": "lawyer_rejected"}]
  links = [{"evidence_item_id": 1, "file_id": 10}, {"evidence_item_id": 2, "file_id": 11}]
  trust = compute_file_trust_map(files, materials, links)
  assert trust[10] == 1.0 and trust[11] == 0.0

  ext = WinRateExtraction(
    cause_code="private_lending",
    elements=[
      ElementExtraction(key="lending_intent", label="借贷合意", grade="proven", citation_ranks=[999], summary="幻觉引用"),
      ElementExtraction(key="fund_delivery", label="款项实际交付", grade="proven", citation_ranks=[2], summary="驳回材料引用"),
      ElementExtraction(key="maturity_breach", label="借期届满及逾期未还", grade="proven", citation_ranks=[1], summary="合法引用"),
      ElementExtraction(key="interest_agreement", label="利息与违约金约定", grade="proven", citation_ranks=[1], summary="合法引用"),
    ],
  )
  res = compute_win_rate(ext, _sources(file_ids=[10, 11]), trust, "plaintiff_side")
  by_key = {e["key"]: e for e in res["elements"]}
  assert by_key["lending_intent"]["grade"] == "missing"
  assert by_key["fund_delivery"]["grade"] == "missing"
  assert res["win_rate"] <= 30.0


def test_multi_claim_weights_bounds_and_calibration_shift():
  trust = {10: 1.0}
  ext = WinRateExtraction(
    cause_code="general_civil",
    claims=[
      ClaimItem(index=0, title="主要货款本金", amount_yuan=90000, priority_weight=1.0),
      ClaimItem(index=1, title="违约金", amount_yuan=10000, priority_weight=0.5),
    ],
    elements=[
      ElementExtraction(key="statutory_basis", label="请求权基础", grade="proven", citation_ranks=[1], summary="合同"),
      ElementExtraction(key="contract_validity", label="合同效力", grade="proven", citation_ranks=[1], summary="盖章"),
      ElementExtraction(key="performance_delivery", label="交货履行", grade="proven", citation_ranks=[1], summary="签收"),
      ElementExtraction(key="causation_loss", label="损失核算", scope_claim_index=0, grade="proven", citation_ranks=[1], summary="对账单"),
      ElementExtraction(key="causation_loss", label="损失核算", scope_claim_index=1, grade="missing", citation_ranks=[], summary="未算"),
    ],
  )
  sources = [{"rank": 1, "file_id": 10, "chunk_id": 1, "relevance": 0.9}]
  uncal = compute_win_rate(ext, sources, trust, "plaintiff_side")
  cal = compute_win_rate(
    ext, sources, trust, "plaintiff_side",
    calibration=CalibrationParams(prior=0.72, gamma=1.15, bias=0.1, metric_kind="calibrated_empirical"),
  )
  assert 5.0 <= uncal["win_rate"] <= 95.0
  assert uncal["claims"][0]["weight"] >= 0.85
  assert cal["metric_kind"] == "calibrated_empirical"
  assert cal["win_rate"] > uncal["win_rate"]


@pytest.mark.parametrize(
  ("label", "parties", "expected"),
  [
    ("被上诉人", [], "defendant_side"),
    ("被申请人（一审被告）", [], "defendant_side"),
    ("上诉人", [], "plaintiff_side"),
    ("原审原告", [], "plaintiff_side"),
    ("有独立请求权第三人", [], "third_party"),
    (None, [{"side": "our", "party_role": "defendant"}], "defendant_side"),
    (None, [{"side": "our", "party_role": "applicant"}], "plaintiff_side"),
    (None, [{"side": "our", "party_role": "other"}], "ambiguous"),
  ],
)
def test_determine_stance(label, parties, expected):
  assert determine_stance(label, parties) == expected


def test_stage0_eligibility_and_fingerprint_sensitivity():
  base_case = {
    "case_type": "civil", "procedure": "first_instance", "title": "民间借贷案",
    "summary": "甲向乙出借十万元", "claim": "判令乙归还十万元", "handling_identity": "self", "party_role_label": "原告",
  }
  files = [{"id": 1, "status": "available", "sha256": "a" * 64, "metadata": {"parse_status": "succeeded", "chunk_count": 2}}]
  mats = [{"id": 5, "status": "lawyer_approved", "revision": 1}]
  links = [{"evidence_item_id": 5, "file_id": 1}]

  assert check_win_rate_eligibility(base_case, [], files, mats, links).eligible
  assert check_win_rate_eligibility({**base_case, "case_type": "criminal"}, [], files, mats, links).reason_code == "non_civil_case"
  assert check_win_rate_eligibility({**base_case, "procedure": "enforcement"}, [], files, mats, links).reason_code == "unsupported_procedure"
  assert check_win_rate_eligibility({**base_case, "party_role_label": "第三人"}, [], files, mats, links).reason_code == "unsupported_third_party"
  assert check_win_rate_eligibility({**base_case, "claim": ""}, [], files, mats, links).reason_code == "missing_claim"
  ocr_files = [{"id": 1, "status": "uploading", "metadata": {"parse_status": "review_required"}}]
  assert check_win_rate_eligibility(base_case, [], ocr_files, mats, links).reason_code == "pending_ocr_review"
  rejected = [{"id": 5, "status": "lawyer_rejected", "revision": 1}]
  assert check_win_rate_eligibility(base_case, [], files, rejected, links).reason_code == "all_materials_rejected"

  fp1 = compute_input_fingerprint(base_case, [], files, mats, links)
  fp2 = compute_input_fingerprint(base_case, [], files, [{"id": 5, "status": "lawyer_approved", "revision": 2}], links)
  assert fp1 != fp2


def test_precedent_reference_matching_anonymized_and_optional(tmp_path):
  import json

  from app.services.precedent_reference import match_precedent_reference

  trust = {10: 1.0, 11: 1.0, 12: 1.0, 13: 1.0}
  strong_report = compute_win_rate(
    WinRateExtraction(cause_code="private_lending", claims=[ClaimItem(index=0, title="归还本金", amount_yuan=100000)],
      elements=_lending_elements("proven")),
    _sources(), trust, "plaintiff_side",
  )
  weak_report = compute_win_rate(
    WinRateExtraction(
      cause_code="private_lending",
      claims=[ClaimItem(index=0, title="归还本金", amount_yuan=100000)],
      elements=[
        ElementExtraction(key="lending_intent", label="借贷合意", grade="weak", citation_ranks=[1], summary="口头"),
        ElementExtraction(key="fund_delivery", label="款项实际交付", grade="weak", citation_ranks=[2], summary="存疑"),
        ElementExtraction(key="maturity_breach", label="借期届满及逾期未还", grade="missing", citation_ranks=[], summary="未见"),
        ElementExtraction(key="interest_agreement", label="利息与违约金约定", grade="missing", citation_ranks=[], summary="未见"),
      ],
      defeaters=[DefeaterExtraction(
        key="contract_invalidity", label="效力争议", presence="confirmed", lethality=0.8, citation_ranks=[3], summary="争议",
      )],
    ),
    _sources(), trust, "plaintiff_side",
  )

  # Missing or unset path cleanly disables precedent reference
  assert match_precedent_reference(strong_report, None) is None
  assert match_precedent_reference(strong_report, str(tmp_path / "missing.jsonl")) is None

  ref_file = tmp_path / "synthetic_refs.jsonl"
  rows = [
    {
      "doc_id": f"SYN-STRONG-{i}",
      "cause_code": "private_lending",
      "claimed_amount_yuan": 100000.0,
      "outcome_label": "fully_supported",
      "case_win": True,
      "win_rate_prediction": {
        "raw_support_score": 88.0,
        "elements": [{"key": "lending_intent", "grade": "proven"}, {"key": "fund_delivery", "grade": "proven"},
                     {"key": "maturity_breach", "grade": "proven"}, {"key": "interest_agreement", "grade": "proven"}],
        "defeaters": [],
      },
    }
    for i in range(4)
  ] + [
    {
      "doc_id": f"SYN-WEAK-{i}",
      "cause_code": "private_lending",
      "claimed_amount_yuan": 100000.0,
      "outcome_label": "dismissed",
      "case_win": False,
      "win_rate_prediction": {
        "raw_support_score": 15.0,
        "elements": [{"key": "lending_intent", "grade": "weak"}, {"key": "fund_delivery", "grade": "weak"},
                     {"key": "maturity_breach", "grade": "missing"}, {"key": "interest_agreement", "grade": "missing"}],
        "defeaters": [{"key": "contract_invalidity", "presence": "confirmed"}],
      },
    }
    for i in range(4)
  ]
  ref_file.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")

  strong_ref = match_precedent_reference(strong_report, str(ref_file), top_k=3)
  weak_ref = match_precedent_reference(weak_report, str(ref_file), top_k=3)
  assert strong_ref is not None and weak_ref is not None
  assert strong_ref["pool_count"] == 8 and strong_ref["matched_count"] == 3
  assert strong_ref["outcome_counts"] == {"fully_supported": 3, "partially_supported": 0, "dismissed": 0}
  assert weak_ref["outcome_counts"] == {"fully_supported": 0, "partially_supported": 0, "dismissed": 3}
  assert weak_ref["common_risk_factors"][0]["key"] == "contract_invalidity"
  assert "SYN-" not in json.dumps(strong_ref, ensure_ascii=False)

  other_cause = {**strong_report, "cause_code": "general_civil"}
  assert match_precedent_reference(other_cause, str(ref_file), top_k=3) is None
