import assert from "node:assert/strict";
import { test } from "node:test";
import { loadService } from "./service-harness.mjs";

test("file polling returns pending instead of claiming parsing completed", async () => {
  const { service } = loadService("files", { request: async () => ({ id: 1, status: "uploading" }) });
  assert.equal((await service.waitForFileReady(1, 1, 0)).status, "uploading");
});

test("last poll detects permanent processing failure", async () => {
  let attempt = 0;
  const { service } = loadService("files", { request: async () => ++attempt === 1
    ? { id: 1, status: "uploading" }
    : { id: 1, status: "failed", jobs: [{ last_error: "扫描件需要OCR" }] } });
  await assert.rejects(service.waitForFileReady(1, 1, 0), /扫描件需要OCR/);
});
