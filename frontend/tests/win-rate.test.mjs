import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";
import ts from "typescript";

function loadCaseContent(handler) {
  const source = readFileSync(
    new URL("../src/services/caseContent.ts", import.meta.url),
    "utf8",
  );
  const exports = {};
  vm.runInNewContext(
    ts.transpileModule(source, {
      compilerOptions: {
        target: ts.ScriptTarget.ES2022,
        module: ts.ModuleKind.CommonJS,
      },
    }).outputText,
    {
      exports,
      setTimeout,
      require: (id) => {
        if (id.endsWith("request")) {
          return {
            USE_MOCK: false,
            createClientId: () => "wr_client_1",
            request: handler,
          };
        }
        return {};
      },
    },
  );
  return exports;
}

test("triggerCaseAnalysis posts win_rate and fetchWinRateDetail parses breakdown", async () => {
  const calls = [];
  const mod = loadCaseContent(async (path, options) => {
    calls.push({ path, options });
    if (options?.method === "POST") {
      return { analysis_id: 99, job_id: 12, status: "pending" };
    }
    return {
      id: 99,
      case_id: 4,
      analysis_type: "win_rate",
      status: "succeeded",
      error_message: null,
      created_at: "2026-11-14T12:00:00Z",
      content: {
        applicable: true,
        win_rate: 84.5,
        metric_kind: "uncalibrated_rubric",
        metric_label: "AI 要件支撑度预估（未经判例校准）",
        stance: "plaintiff_side",
        cause_code: "private_lending",
        cause_label: "民间借贷纠纷",
        claims: [{ index: 0, title: "偿还本金", amount_yuan: 100000, weight: 1, support_score: 84.5 }],
        elements: [
          {
            key: "fund_delivery",
            label: "款项实际交付",
            grade: "proven",
            grade_label: "充分印证",
            certainty: 0.92,
            citation_ranks: [1],
            trust: 1,
            summary: "转账流水明确",
          },
        ],
        defeaters: [],
        positive_factors: ["核心凭证完整"],
        negative_factors: [],
        missing_evidence: [],
        precedent_reference: {
          dataset_label: "MSJudge 清洁裁判特征库（离线脱敏参照）",
          cause_code: "private_lending",
          pool_count: 500,
          matched_count: 15,
          similarity_avg: 91.2,
          outcome_counts: { fully_supported: 12, partially_supported: 3, dismissed: 0 },
          principal_support_rate: 100.0,
          perspective_note: "原告核心诉求支持比例参考",
          common_risk_factors: [{ key: "statutory_cap", label: "法定利率上限与利息扣减", count: 4 }],
          caveat: "仅作结构参考",
        },
        limitations: "仅基于已提交材料",
        disclaimer: "仅供办案风险研判参考",
      },
    };
  });

  const triggered = await mod.triggerCaseAnalysis(4, "win_rate");
  assert.equal(triggered.analysis_id, 99);
  assert.equal(calls[0].path, "/cases/4/analyses");
  assert.equal(calls[0].options.method, "POST");
  assert.equal(calls[0].options.data.analysis_type, "win_rate");

  const detail = await mod.fetchWinRateDetail(4, 99);
  assert.equal(calls[1].path, "/cases/4/analyses/99");
  assert.equal(detail.applicable, true);
  assert.equal(detail.win_rate, 84.5);
  assert.equal(detail.elements.length, 1);
  assert.equal(detail.elements[0].grade_label, "充分印证");
  assert.equal(detail.precedent_reference?.matched_count, 15);
  assert.equal(detail.precedent_reference?.common_risk_factors[0]?.count, 4);

  const ignored = mod.parseWinRateDetail({
    id: 5,
    case_id: 4,
    analysis_type: "case_summary",
    status: "succeeded",
    content: { applicable: true },
    error_message: null,
    created_at: "",
  });
  assert.equal(ignored, null);
});
