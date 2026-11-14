import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";
import ts from "typescript";

function loadOrganizer() {
  const constantsSource = readFileSync(
    new URL("../src/constants/case.ts", import.meta.url),
    "utf8",
  );
  const organizerSource = readFileSync(
    new URL("../src/utils/caseDraftOrganizer.ts", import.meta.url),
    "utf8",
  );

  const constantsExports = {};
  vm.runInNewContext(
    ts.transpileModule(constantsSource, {
      compilerOptions: {
        target: ts.ScriptTarget.ES2022,
        module: ts.ModuleKind.CommonJS,
      },
    }).outputText,
    { exports: constantsExports, require: () => ({}) },
  );

  const organizerExports = {};
  vm.runInNewContext(
    ts.transpileModule(organizerSource, {
      compilerOptions: {
        target: ts.ScriptTarget.ES2022,
        module: ts.ModuleKind.CommonJS,
      },
    }).outputText,
    {
      exports: organizerExports,
      require: (id) => {
        if (id === "@/constants/case") return constantsExports;
        return {};
      },
    },
  );

  return organizerExports;
}

test("loan narrative classifies as 民事 without guessing party orientation from bare names", () => {
  const { createEmptyDraftForm, buildOrganizedDraft } = loadOrganizer();
  const form = createEmptyDraftForm();
  form.summary = "我在2024年借给李某五万元，一直没还，有借条，希望追回本金和利息。";

  const pending = buildOrganizedDraft(form);
  assert.equal(form.caseType, "民事");
  assert.equal(form.title, "民间借贷纠纷案");
  assert.equal(Boolean(pending.stage), true);
  assert.equal(Boolean(pending.parties), true);
  assert.deepEqual(Array.from(form.ourParties), [""]);
  assert.deepEqual(Array.from(form.opponentParties), [""]);
  assert.equal(form.summary.includes("原型"), false);
  assert.equal(form.summary.includes("模拟整理"), false);
});

test("explicit party roles and stage populate draft cleanly without prototype copy", () => {
  const { createEmptyDraftForm, buildOrganizedDraft } = loadOrganizer();
  const form = createEmptyDraftForm();
  form.summary =
    "2025年3月起小区地下车库长期漏水导致我方张某车辆受损，多次向安徽某物业服务有限公司书面报修未果，目前尚未起诉，希望物业公司履行维修义务并赔偿损失1.2万元。";
  form.files = [{ name: "报修沟通记录.docx", sizeText: "186 KB", status: "ready" }];

  const pending = buildOrganizedDraft(form);
  assert.equal(form.caseType, "民事");
  assert.equal(form.stage, "尚未起诉/诉前咨询");
  assert.deepEqual(Array.from(form.ourParties), ["张某"]);
  assert.deepEqual(Array.from(form.opponentParties), ["安徽某物业服务有限公司"]);
  assert.equal(Object.keys(pending).length, 0);
  assert.equal(form.summary.includes("原型"), false);
});

test("files-only input marks unknown fields pending without fabricating document contents", () => {
  const { createEmptyDraftForm, buildOrganizedDraft } = loadOrganizer();
  const form = createEmptyDraftForm();
  form.files = [{ name: "民事起诉状.docx", sizeText: "186 KB", status: "ready" }];

  const pending = buildOrganizedDraft(form);
  assert.equal(form.caseType, "");
  assert.equal(Boolean(pending.title), true);
  assert.equal(Boolean(pending.caseType), true);
  assert.equal(Boolean(pending.stage), true);
  assert.equal(Boolean(pending.parties), true);
  assert.equal(form.summary.includes("原型"), false);
  assert.equal(form.summary.includes("民事起诉状.docx"), true);
});
