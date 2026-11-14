import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";
import ts from "typescript";

function loadCasesService(request) {
  const source = readFileSync(
    new URL("../src/services/cases.ts", import.meta.url),
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
      require: (id) => {
        if (id.endsWith("request")) return { USE_MOCK: false, request };
        if (id.endsWith("mock/cases")) return { fetchMockCases: async () => [] };
        throw new Error(`Unexpected import: ${id}`);
      },
    },
  );
  return exports;
}

test("createCase sends POST /cases with mapped payload", async () => {
  const calls = [];
  const service = loadCasesService(async (path, options) => {
    calls.push({ path, options });
    return {
      id: 12,
      title: options.data.title,
      case_type: options.data.case_type,
      procedure: options.data.procedure,
      analysis_status: "not_analyzed",
      evidence_upload_status: "not_uploaded",
      win_rate: null,
      win_rate_updated_at: null,
      status: "active",
      created_at: "2026-11-14T02:00:00Z",
      updated_at: "2026-11-14T02:00:00Z",
      our_parties: options.data.our_parties,
      opponent_parties: options.data.opponent_parties,
    };
  });

  const payload = {
    title: "测试借款纠纷",
    case_type: "civil",
    procedure: "first_instance",
    summary: "出借十万元逾期未还",
    claim: "返还本金十万元",
    handling_identity: "self",
    party_role_label: "原告",
    our_parties: ["张三"],
    opponent_parties: ["李四"],
  };
  const created = await service.createCase(payload);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].path, "/cases");
  assert.equal(calls[0].options.method, "POST");
  assert.deepEqual(calls[0].options.data, payload);
  assert.equal(created.id, 12);
});

test("deleteCaseDocument sends DELETE /cases/:id/documents/:docId", async () => {
  const source = readFileSync(
    new URL("../src/services/caseContent.ts", import.meta.url),
    "utf8",
  );
  const calls = [];
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
            createClientId: () => "id",
            request: async (path, options) => {
              calls.push({ path, options });
            },
          };
        }
        return {};
      },
    },
  );
  await exports.deleteCaseDocument(4, 29);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].path, "/cases/4/documents/29");
  assert.equal(calls[0].options.method, "DELETE");
});
