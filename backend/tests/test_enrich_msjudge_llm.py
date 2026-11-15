"""Synthetic unit tests for MSJudge local scrubbing, field enrichment, and engine scoring."""

import json
from types import SimpleNamespace

import pytest

from scripts.enrich_msjudge_llm import (
  clean_utterances,
  enrich_single_case,
  evaluate_calibration,
  is_clean_contested_case,
  parse_rmb_amount,
  scrub_text_for_llm,
)


def test_parse_rmb_amount_supports_digits_ten_thousand_and_chinese():
  assert parse_rmb_amount("请求归还借款本金48000元及利息") == 48000.0
  assert parse_rmb_amount("借款本金2.5万元") == 25000.0
  assert parse_rmb_amount("借款人民币1,200,500.50元") == 1200500.5
  assert parse_rmb_amount("归还借款五万元") == 50000.0
  assert parse_rmb_amount("确认合同解除") is None


def test_scrub_text_for_llm_masks_pii_while_preserving_legal_facts():
  raw = (
    "原告没有。被告于2012年1月18日向原告借款48000元，"
    "住LOC幸福路12号，1988年1月6日出生，手机号13800000000，"
    "参照(2013)甬奉保字第18号民事裁定书，担保人：张三，用于居住。"
  )
  cleaned, counts = scrub_text_for_llm(raw)
  assert "原告没有。" in cleaned
  assert "2012年1月18日" in cleaned
  assert "48000元" in cleaned
  assert "用于居住" in cleaned
  assert "1988年1月6日" not in cleaned
  assert "13800000000" not in cleaned
  assert "幸福路12号" not in cleaned
  assert "甬奉保字第18号" not in cleaned
  assert "张三" not in cleaned
  assert counts["dob"] == 1
  assert counts["case_no"] == 1
  assert counts["address"] == 1
  assert counts["mobile"] == 1
  assert counts["role_inline_name"] == 1


def test_clean_utterances_and_contested_filter():
  debate = "\n".join([
    "原告方：原PER,Gender,1972年4月24日出生,住LOC某路1号。",
    "原告方：原听清了。",
    "被告方：被对原告借条无异议，但已经归还本金1万元。",
    "被告方：被没有。",
  ])
  from collections import Counter
  utterances = clean_utterances(debate, Counter())
  assert utterances[0] == "原告方：[当事人身份及住址信息已脱敏]"
  assert len(utterances) == 2
  assert "无异议" in utterances[1]
  ok, reason = is_clean_contested_case("请求判令被告归还借款本金5万元", utterances, "事实如下：被告未按期归还。")
  assert ok is True
  assert reason is None

  ok_abs, reason_abs = is_clean_contested_case(
    "请求判令归还5万元", ["原告方：请求归还", "被告方：被PER(未到庭)"], "经合法传唤未到庭",
  )
  assert ok_abs is False
  assert reason_abs == "absence_or_publication_cue"


class FakeAI:
  def __init__(self, pre_payload, gt_payload):
    self.pre_payload = pre_payload
    self.gt_payload = gt_payload
    self.calls = []

  async def complete_json(self, messages, temperature=None):
    user_msg = messages[1]["content"]
    self.calls.append((user_msg, temperature))
    payload = self.pre_payload if "双方陈述摘要" in user_msg else self.gt_payload
    return SimpleNamespace(
      choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload, ensure_ascii=False)))],
      usage=SimpleNamespace(total_tokens=150),
    )


@pytest.mark.asyncio
async def test_enrich_single_case_isolates_inputs_and_evaluates_metrics():
  pre_payload = {
    "win_rate_extraction": {
      "cause_code": "private_lending",
      "claims": [{"index": 0, "title": "归还借款本金", "amount_yuan": 50000.0, "priority_weight": 1.0}],
      "elements": [
        {"key": "lending_intent", "label": "借贷合意", "scope_claim_index": None, "grade": "proven", "citation_ranks": [1], "summary": "有借条"},
        {"key": "fund_delivery", "label": "款项交付", "scope_claim_index": None, "grade": "corroborated", "citation_ranks": [2], "summary": "双方确认"},
        {"key": "maturity_breach", "label": "逾期未还", "scope_claim_index": None, "grade": "proven", "citation_ranks": [2], "summary": "已到期"},
        {"key": "interest_agreement", "label": "利息约定", "scope_claim_index": None, "grade": "weak", "citation_ranks": [1], "summary": "口头提及"},
      ],
      "defeaters": [],
      "positive_factors": ["被告确认借条"],
      "negative_factors": [],
      "missing_evidence": [],
      "limitations": "仅含庭审陈述",
    },
    "metadata": {
      "claimed_principal_yuan": 50000.0,
      "claimed_total_yuan": None,
      "claimed_interest_requested": True,
      "procedure": "first_instance",
      "procedure_detail": "unspecified",
      "is_absent_defendant": False,
      "borrowing_date": "2012-03-10",
      "maturity_date": None,
      "text_mentioned_case_year": None,
      "text_mentioned_court": None,
      "text_mentioned_province": None,
    },
  }
  gt_payload = {
    "case_win": True,
    "principal_support_tier": "partial_major_ge80",
    "supported_principal_yuan": 50000.0,
    "disposal_type": "judgment",
    "partial_reason": "超额利息部分未支持",
    "filing_date": "2013-05-02",
    "judgment_date": None,
    "court_level": None,
    "province": None,
  }
  fake_ai = FakeAI(pre_payload, gt_payload)
  item = {
    "doc_id": "msjudge_0001",
    "record_key": "1",
    "cause_code": "private_lending",
    "outcome_label": "partially_supported",
    "raw_claim_amount_rule": 50000.0,
    "input_claim_text": "请求归还借款5万元及超额利息",
    "utterances": ["原告方：提供借条与转账记录", "被告方：借条真实，利息过高"],
    "fact_description_scrubbed": "事实如下：唯一秘密标记_NOT_IN_PRE_CALL_借贷关系成立，2013年5月2日起诉。",
    "fact_labels": {"Loan Established": 1},
    "redaction_counts": {"mobile": 0},
  }
  res = await enrich_single_case(fake_ai, item)
  assert len(fake_ai.calls) == 2
  assert "唯一秘密标记_NOT_IN_PRE_CALL" not in fake_ai.calls[0][0]
  assert "partially_supported" not in fake_ai.calls[0][0]
  assert fake_ai.calls[0][1] == 0
  assert res["case_win"] is True
  assert res["claimed_amount_yuan"] == 50000.0
  assert res["supported_amount_yuan"] == 50000.0
  assert res["judgment_date"] is None
  assert res["filing_date"] == "2013-05-02"
  assert res["win_rate_prediction"]["win_rate_percent"] > 50.0

  metrics = evaluate_calibration([
    res,
    {**res, "doc_id": "msjudge_0002", "outcome_label": "dismissed", "case_win": False,
     "win_rate_prediction": {**res["win_rate_prediction"], "win_rate_percent": 15.0, "raw_support_score": 15.0}},
  ])
  assert metrics["evaluated_cases"] == 2
  assert metrics["roc_auc"] == 1.0
  assert metrics["offline_diagnostic_full_fit"]["gamma"] > 0
  assert 0.0 <= metrics["uncalibrated_v1_metrics"]["brier"] <= 1.0
