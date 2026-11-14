import assert from "node:assert/strict";
import { test } from "node:test";
import { loadService } from "./service-harness.mjs";

test("document and material upload timestamps use the device timezone including date rollover", async (t) => {
  const previousTimezone = process.env.TZ;
  t.after(() => {
    if (previousTimezone === undefined) delete process.env.TZ;
    else process.env.TZ = previousTimezone;
  });
  const { service } = loadService("caseContent", {
    modules: {
      "@/constants/case": { DOCUMENT_CATEGORY_LABELS: { other: "其他" }, EVIDENCE_CATEGORY_LABELS: {} },
      "./mock/cases": {},
    },
    request: async () => [{
      id: 1, case_id: 10, file_id: 8, title: "虚构测试文档", category: "other",
      created_at: "2026-11-14T05:03:57.932276+00:00", uploaded_by: 1,
    }],
  });
  process.env.TZ = "Asia/Shanghai";
  assert.equal((await service.fetchDocuments(10))[0].uploaded_at, "2026-11-14 13:03:57");
  assert.equal((await service.fetchMaterials(10))[0].uploaded_at, "2026-11-14 13:03:57");
  process.env.TZ = "America/Los_Angeles";
  assert.equal((await service.fetchDocuments(10))[0].uploaded_at, "2026-11-13 21:03:57");
});
