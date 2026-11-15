"""Data preparation checks use only synthetic cases, without network or real case text."""

import io
import json

import pytest

from scripts.prepare_msjudge import ObjectStream, prepare_candidate, redact


def synthetic_case(**overrides):
  return {
    "claims": ["合成原告请求归还本金"],
    "claims_labels": ["Partially Support"],
    "court_debate": "合成法官询问\n合成原告提交转账凭证\n合成被告提出异议",
    "roles": ["审", "原", "被"],
    "fact_description": "本院认定：此为不得进入输入的合成事实",
    "fact_labels": {"Loan Established": 1},
    **overrides,
  }


def test_stream_handles_utf8_boundaries_and_source_object():
  cases = {"0": synthetic_case(), "1": synthetic_case(claims=["另一合成请求"])}
  payload = json.dumps(cases, ensure_ascii=False)
  assert dict(ObjectStream(io.StringIO(payload), chunk_size=7).items()) == cases


@pytest.mark.parametrize("payload", [
  '{"0":{},}', '{"0":{},"0":{}}', '{"0":{', '{"0":[]} ', '{} trailing', '[]',
])
def test_stream_rejects_invalid_or_duplicate_records(payload):
  with pytest.raises(ValueError):
    list(ObjectStream(io.StringIO(payload), chunk_size=3).items())


def test_party_inputs_exclude_judicial_facts_and_unknown_metadata_stays_null():
  candidate, reason = prepare_candidate("0", synthetic_case())
  assert reason is None
  assert "法官" not in candidate["input_pre_judgment_text"]
  assert "本院认定" not in json.dumps([
    candidate["input_claim_text"], candidate["input_pre_judgment_text"],
  ], ensure_ascii=False)
  assert candidate["outcome_label"] == "partially_supported"
  assert candidate["case_win"] is None
  for key in (
    "judgment_date", "procedure", "is_absent_defendant", "disposal_type",
    "claimed_amount_yuan", "supported_amount_yuan",
  ):
    assert candidate[key] is None
  assert candidate["calibration_eligible"] is False
  assert candidate["preparation"]["privacy_review_complete"] is False


def test_case_date_cannot_be_inferred_from_event_dates_or_outcome_words():
  candidate, _ = prepare_candidate("0", synthetic_case(
    court_debate="是否同意调解\n合成原告：2020年1月1日借款\n合成被告：未还款",
  ))
  assert candidate["judgment_date"] is None
  assert candidate["disposal_type"] is None
  assert candidate["is_absent_defendant"] is None


@pytest.mark.parametrize("overrides,reason", [
  ({"court_debate": "原告\n被告", "roles": ["原"]}, "role_alignment_missing"),
  ({"roles": ["审", "原", "原"]}, "both_party_utterances_missing"),
  ({"court_debate": "判 决 如 下\n原告\n被告"}, "judicial_text_marker"),
  ({"claims_labels": ["unknown"]}, "invalid_claims_or_labels"),
  ({"claims_labels": [[]]}, "invalid_claims_or_labels"),
  ({"claims": ["请求1", "请求2"], "claims_labels": ["Support", "Reject"]},
   "multiple_claims_not_aggregated"),
])
def test_ambiguous_or_leaking_records_are_quarantined(overrides, reason):
  assert prepare_candidate("0", synthetic_case(**overrides)) == (None, reason)


def test_identifier_masking_preserves_amount_but_is_not_a_privacy_certification():
  text, counts = redact("合成号码13800000000、合成邮箱fake@example.invalid，金额100000元")
  assert "13800000000" not in text
  assert "fake@example.invalid" not in text
  assert "100000元" in text
  assert counts == {"mobile": 1, "email": 1}


def test_fingerprint_ignores_source_index_and_outcome_for_duplicate_quarantine():
  first, _ = prepare_candidate("0", synthetic_case())
  second, _ = prepare_candidate("9", synthetic_case(claims_labels=["Reject"]))
  assert first["doc_id"] == second["doc_id"]
  assert first["outcome_label"] != second["outcome_label"]
