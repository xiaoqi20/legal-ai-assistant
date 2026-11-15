"""Audit the pinned MSJudge release and prepare local research candidates, never model parameters.

Only synthetic tests and this script belong in Git. All source and output case data must
remain outside the repository. No downloaded code is imported or executed.
"""

import argparse
import hashlib
import heapq
import io
import json
import os
import re
import zipfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

COMMIT = "87f038e714f3bac4e8bee461983715f8893261db"
ARCHIVE_SHA256 = "c27aa1f2a0ee7c5cb9573b7b83c4915c29a3bff1bc8d3637d8916b9ff1133782"
ARCHIVE_BYTES = 91_167_278
MEMBER = "judgment_prediction_dataset.json"
LABELS = {
  "Support": "fully_supported",
  "Partially Support": "partially_supported",
  "Reject": "dismissed",
}
EXPECTED_FIELDS = {
  "court_debate", "fact_description", "claims", "claims_labels", "roles", "fact_labels",
}
METADATA_FIELDS = (
  "judgment_date", "procedure", "court_level", "province",
  "is_absent_defendant", "disposal_type", "claimed_amount_yuan", "supported_amount_yuan",
)
JUDICIAL_MARKERS = (
  "本院认为", "判决如下", "裁定如下", "经审理查明", "本院查明", "本院认定", "本院确认",
)
PII_PATTERNS = {
  "email": re.compile(r"[A-Za-z0-9_.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
  "long_identifier": re.compile(r"(?<!\d)\d{15,19}[Xx]?(?!\d)"),
  "mobile": re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
  "landline": re.compile(r"(?<!\d)0\d{2,3}[-－]?\d{7,8}(?!\d)"),
}


class ObjectStream:
  """Bound memory by one JSON value while reading a large root object incrementally."""

  def __init__(self, stream, chunk_size=65536, max_value_chars=8_000_000):
    self.stream = stream
    self.chunk_size = chunk_size
    self.max_value_chars = max_value_chars
    self.buffer = ""
    self.pos = 0
    self.eof = False
    self.decoder = json.JSONDecoder()

  def fill(self):
    self.buffer = self.buffer[self.pos:]
    self.pos = 0
    chunk = self.stream.read(self.chunk_size)
    self.buffer += chunk
    self.eof = not chunk
    if len(self.buffer) > self.max_value_chars:
      raise ValueError("JSON value exceeds the configured memory limit")

  def peek(self):
    while True:
      while self.pos < len(self.buffer) and self.buffer[self.pos].isspace():
        self.pos += 1
      if self.pos < len(self.buffer):
        return self.buffer[self.pos]
      if self.eof:
        return ""
      self.fill()

  def expect(self, char):
    if self.peek() != char:
      raise ValueError(f"Expected JSON delimiter {char!r}")
    self.pos += 1

  def value(self):
    self.peek()
    while True:
      try:
        result, end = self.decoder.raw_decode(self.buffer, self.pos)
        self.pos = end
        return result
      except json.JSONDecodeError:
        if self.eof:
          raise ValueError("Invalid or truncated JSON source") from None
        self.fill()

  def items(self):
    self.expect("{")
    seen = set()
    if self.peek() != "}":
      while True:
        key = self.value()
        if not isinstance(key, str) or key in seen:
          raise ValueError("Source record keys must be unique strings")
        seen.add(key)
        self.expect(":")
        value = self.value()
        if not isinstance(value, dict):
          raise ValueError("Each source case must be an object")
        yield key, value
        if self.peek() == "}":
          break
        self.expect(",")
    self.expect("}")
    if self.peek():
      raise ValueError("Unexpected content after the root object")


def compact(text):
  # The release uses tokenized Chinese text. Preserve utterance boundaries separately.
  return re.sub(r"\s+", "", text)


def redact(text):
  counts = Counter()
  for name, pattern in PII_PATTERNS.items():
    text, count = pattern.subn("[已遮蔽标识]", text)
    counts[name] += count
  return text, +counts


def prepare_candidate(key, row):
  """Keep only one unambiguous claim and party utterances; unknown facts remain null."""
  claims, labels = row.get("claims"), row.get("claims_labels")
  if (
    not isinstance(claims, list) or not isinstance(labels, list)
    or len(claims) != len(labels) or not claims
    or any(not isinstance(c, str) or not compact(c) for c in claims)
    or any(not isinstance(label, str) or label not in LABELS for label in labels)
  ):
    return None, "invalid_claims_or_labels"
  if len(claims) != 1:
    return None, "multiple_claims_not_aggregated"
  debate, roles = row.get("court_debate"), row.get("roles")
  if not isinstance(debate, str) or not isinstance(roles, list):
    return None, "invalid_debate_or_roles"
  lines = debate.splitlines()
  if len(lines) != len(roles) or any(not isinstance(r, str) for r in roles):
    return None, "role_alignment_missing"
  if not {"原", "被"}.issubset({r for line, r in zip(lines, roles, strict=True) if compact(line)}):
    return None, "both_party_utterances_missing"
  # Conservative quarantine: even a party quoting an earlier judgment needs manual review.
  if any(marker in compact(debate + claims[0]) for marker in JUDICIAL_MARKERS):
    return None, "judicial_text_marker"
  utterances = [
    f"{'原告方' if role == '原' else '被告方'}：{compact(line)}"
    for line, role in zip(lines, roles, strict=True)
    if role in {"原", "被"} and compact(line)
  ]
  claim, claim_redactions = redact(compact(claims[0]))
  transcript, debate_redactions = redact("\n".join(utterances))
  # Hash before redaction so masking two distinct identifiers cannot merge different cases.
  fingerprint = hashlib.sha256(
    json.dumps([compact(c) for c in claims] + [compact(debate)], ensure_ascii=False).encode()
  ).hexdigest()
  return {
    "doc_id": "msjudge_" + fingerprint,
    "cause_code": "private_lending",
    **dict.fromkeys(METADATA_FIELDS),
    "stance_target": "plaintiff_side",
    "input_claim_text": claim,
    "input_pre_judgment_text": transcript,
    "outcome_label": LABELS[labels[0]],
    "case_win": None,
    "claim_outcomes": [{"claim_index": 1, "outcome_label": LABELS[labels[0]]}],
    "calibration_eligible": False,
    "review_required": [
      "missing_judgment_date_and_court_metadata", "unknown_absence_and_disposal",
      "core_claim_win_definition_not_set", "amounts_not_verified",
      "manual_privacy_and_leakage_review", "courtroom_vs_pretrial_input_shift",
      "dataset_usage_permission_unverified",
    ],
    "source": {"dataset": "MSJudge", "commit": COMMIT, "record_key": key},
    "preparation": {
      "version": "msjudge_candidates_v1",
      "role_filter": ["原", "被"],
      "excluded_fields": ["fact_description", "fact_labels"],
      "removed_non_party_utterances": sum(r not in {"原", "被"} for r in roles),
      "identifier_redactions": dict(claim_redactions + debate_redactions),
      "privacy_review_complete": False,
    },
  }, None


def write_json(path, value):
  path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
  path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
  path.chmod(0o600)


def audit(data_root, sample_size):
  archive_path = data_root / "raw/msjudge/judgment_prediction_dataset.zip"
  manifest = json.loads((archive_path.parent / "source-manifest.json").read_text())
  with archive_path.open("rb") as source:
    digest = hashlib.file_digest(source, "sha256").hexdigest()
  if (
    archive_path.stat().st_size != ARCHIVE_BYTES or digest != ARCHIVE_SHA256
    or manifest.get("commit") != COMMIT or manifest.get("sha256") != digest
  ):
    raise ValueError("Source archive/version does not match the verified release")
  counts = Counter()
  fields, labels, roles, exclusions, markers = (Counter() for _ in range(5))
  metadata_presence, redactions = Counter(), Counter()
  seen_inputs, seen_candidates, conflicting_candidates = set(), {}, set()
  sample = []
  with zipfile.ZipFile(archive_path) as archive:
    if archive.testzip() is not None:
      raise ValueError("ZIP CRC check failed")
    with archive.open(MEMBER) as raw, io.TextIOWrapper(raw, encoding="utf-8") as stream:
      for key, row in ObjectStream(stream).items():
        counts["cases"] += 1
        fields.update(row.keys())
        counts["unexpected_schema_cases"] += set(row) != EXPECTED_FIELDS
        metadata_presence.update(k for k in METADATA_FIELDS if row.get(k) is not None)
        row_claims, row_labels = row.get("claims", []), row.get("claims_labels", [])
        if isinstance(row_claims, list):
          counts["claims"] += len(row_claims)
        if isinstance(row_labels, list):
          labels.update(str(label) for label in row_labels)
        if isinstance(row.get("roles"), list):
          roles.update(str(role) for role in row["roles"])
        source_input = json.dumps(
          [row.get("claims"), row.get("court_debate")], ensure_ascii=False, sort_keys=True,
        )
        input_hash = hashlib.sha256(compact(source_input).encode()).digest()
        if input_hash in seen_inputs:
          counts["duplicate_input_records"] += 1
        seen_inputs.add(input_hash)
        text = compact(str(row.get("court_debate", "")))
        markers.update(marker for marker in JUDICIAL_MARKERS if marker in text)
        for cue in ("缺席", "未到庭", "调解", "撤诉"):
          counts[f"mention_only_{cue}"] += cue in text
        candidate, reason = prepare_candidate(key, row)
        if reason:
          exclusions[reason] += 1
          continue
        fingerprint = candidate["doc_id"]
        if fingerprint in seen_candidates:
          exclusions["duplicate_candidate_input"] += 1
          if seen_candidates[fingerprint] != candidate["outcome_label"]:
            conflicting_candidates.add(fingerprint)
          continue
        seen_candidates[fingerprint] = candidate["outcome_label"]
        counts["unique_research_candidate_pool"] += 1
        redactions.update(candidate["preparation"]["identifier_redactions"])
        rank = -int(fingerprint.removeprefix("msjudge_"), 16)
        entry = (rank, fingerprint, candidate)
        # Small reserve allows later conflicting duplicates to be quarantined.
        if len(sample) < sample_size * 2:
          heapq.heappush(sample, entry)
        elif entry[:2] > sample[0][:2]:
          heapq.heapreplace(sample, entry)
        if counts["cases"] % 10000 == 0:
          print(f"Audited {counts['cases']} source cases", flush=True)
  selected = sorted(
    (item[2] for item in sample if item[1] not in conflicting_candidates),
    key=lambda item: item["doc_id"],
  )[:sample_size]
  counts["conflicting_candidate_inputs_quarantined"] = len(conflicting_candidates)
  candidates_path = data_root / "cleaned/msjudge-research-candidates.jsonl"
  candidates_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
  with candidates_path.open("w", encoding="utf-8") as output:
    for candidate in selected:
      output.write(json.dumps(candidate, ensure_ascii=False) + "\n")
  candidates_path.chmod(0o600)
  report = {
    "generated_at": datetime.now(UTC).isoformat(),
    "dataset": "MSJudge", "commit": COMMIT, "archive_sha256": digest,
    "archive_bytes": ARCHIVE_BYTES, "zip_crc_passed": True,
    "counts": dict(counts), "source_field_coverage": dict(fields),
    "source_claim_labels": dict(labels), "source_roles": dict(roles),
    "metadata_non_null_cases": {key: metadata_presence[key] for key in METADATA_FIELDS},
    "debate_judicial_marker_cases": dict(markers),
    "candidate_exclusions": dict(exclusions),
    "candidate_pool_identifier_redactions": dict(redactions),
    "selected_candidates": len(selected),
    "selected_outcomes": dict(Counter(item["outcome_label"] for item in selected)),
    "selected_with_identifier_redactions": sum(
      bool(item["preparation"]["identifier_redactions"]) for item in selected
    ),
    "selection": "Lowest SHA256 of unique inputs; single claim, aligned original/defendant roles",
    "qualified_calibration_cases": 0,
    "chronological_split_created": False,
    "case_win_labels_created": 0,
    "commercial_use_cleared": False,
    "limitations": [
      "No reliable judgment-date, procedure, location, absence or disposal metadata supplied.",
      "Roles and text cues do not establish actual appearance, judgment or mediation outcomes.",
      "Claim support labels are preserved; no core-claim case-win or amount labels inferred.",
      "fact_description, fact_labels and non-party dialogue are excluded from model inputs.",
      "Marker screening and identifier masking require manual privacy/leakage review.",
      "Single-claim, both-party-role subset differs from the full release and pretrial product inputs.",
      "No temporal evaluation, probability fitting, license clearance or production import performed.",
    ],
  }
  write_json(data_root / "reports/msjudge-quality.json", report)
  write_json(data_root / "splits/manifest.json", {
    "status": "blocked_missing_judgment_dates_and_review",
    "qualified_cases": 0, "fit": None, "test": None,
    "reason": "Do not substitute publication dates or random splits for judgment dates.",
  })
  summary = (
    f"# MSJudge 本地采集与质量报告\n\n"
    f"来源版本：`{COMMIT}`。原始包 SHA256：`{digest}`。ZIP 完整性校验通过。\n\n"
    f"实测 {counts['cases']:,} 案、{counts['claims']:,} 项诉求；"
    f"唯一研究候选池 {counts['unique_research_candidate_pool']:,} 案，"
    f"按输入哈希确定性抽取 {len(selected)} 案。正式校准合格样本 **0 案**。\n\n"
    "候选限定为单项诉求、双方角色均有文本且角色与发言逐行对应的记录。"
    "这不等于证明被告实际到庭；缺席和结案方式均保留 null。"
    "只保留诉求、原被告发言；不使用法官发言、fact_description 或 fact_labels。"
    "出现裁判结论标记的记录隔离；手机号、邮箱和长标识作规则遮蔽，"
    "姓名、地址及残留裁判信息仍须人工复核，不能称为完成脱敏。\n\n"
    "缺少裁判日期、程序、法院、地区、缺席及结案方式，无法按时间切分；"
    "不猜测金额、不把部分支持折算为 0.5、不自动生成整案 case_win。"
    "候选全部 calibration_eligible=false，当前不训练、不导入线上、不修改校准参数。\n\n"
    "下载公开研究集未绕过法院平台访问控制；未发现明确的数据商用授权。"
    "当前资料仅作为本地研究候选保存，商用资格未确认。"
    "后续需补齐日期、授权和人工复核，或换用具备这些条件的数据来源。\n\n"
    "逐字段覆盖率、标签分布、过滤原因见同目录 msjudge-quality.json。"
    "`mention_only_*` 仅是文本提及次数，不是缺席或调撤案件统计。\n"
  )
  (data_root / "reports/msjudge-quality.md").write_text(summary, encoding="utf-8")
  (data_root / "README.md").write_text(
    "# 胜诉率离线数据工作目录\n\n"
    "真实案件数据仅保存在此仓库外目录，不提交 Git。目录权限 700、数据文件权限 600。\n\n"
    "- raw/msjudge/：公开原始包、固定来源清单、作者说明与标签映射代码（只读，不执行）。\n"
    "- cleaned/msjudge-research-candidates.jsonl：研究候选，尚未完成人工脱敏/校准验收。\n"
    "- reports/：归档清单与全量质量报告。\n"
    "- splits/manifest.json：时间划分阻塞原因；未生成训练/测试数据。\n"
    "- params/：预留；当前未拟合或启用参数。\n\n"
    "先阅读 reports/msjudge-quality.md。不要把候选文件直接导入生产或当作校准结果。\n",
    encoding="utf-8",
  )
  print(json.dumps({
    "source_cases": counts["cases"], "source_claims": counts["claims"],
    "selected_candidates": len(selected), "qualified_calibration_cases": 0,
    "report": str(data_root / "reports/msjudge-quality.json"),
  }, ensure_ascii=False))
  return report


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--data-root", type=Path, required=True)
  parser.add_argument("--sample-size", type=int, default=500)
  args = parser.parse_args()
  root = args.data_root.expanduser().resolve()
  repo = Path(__file__).resolve().parents[2]
  if root.is_relative_to(repo):
    parser.error("Real case data must be stored outside the repository")
  if not 1 <= args.sample_size <= 500:
    parser.error("sample-size must be between 1 and 500")
  os.umask(0o077)
  audit(root, args.sample_size)


if __name__ == "__main__":
  main()
