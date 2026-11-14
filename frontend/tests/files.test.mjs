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

test("empty browser files and buffers are rejected before creating an upload", async () => {
  let requests = 0;
  const { service } = loadService("files", { request: async () => { requests++; } });
  const params = { caseId: 10, filename: "空文件.txt", sizeBytes: 100 };
  await assert.rejects(service.uploadCaseDocument({ ...params, file: new File([], params.filename) }), /文件为空，请重新选择/);
  await assert.rejects(service.uploadCaseDocument({ ...params, buffer: new ArrayBuffer(0) }), /文件为空，请重新选择/);
  assert.equal(requests, 0);
});

test("empty mini-program files are rejected after reading even when declared size is nonzero", async () => {
  let requests = 0;
  const { service } = loadService("files", {
    platform: "MP-WEIXIN",
    request: async () => { requests++; },
    globals: { uni: { getFileSystemManager: () => ({ readFileSync: () => new ArrayBuffer(0) }) } },
  });
  await assert.rejects(service.uploadCaseDocument({
    caseId: 10, filename: "空文件.txt", sizeBytes: 100, filePath: "/tmp/empty.txt",
  }), /文件为空，请重新选择/);
  assert.equal(requests, 0);
});

test("processing failures provide Chinese guidance without exposing internal error codes", async () => {
  const { service } = loadService("files", {
    request: async () => ({ id: 1, status: "failed", metadata: { error_code: "invalid_pdf" } }),
  });
  await assert.rejects(service.waitForFileReady(1, 1, 0), /PDF 文件损坏或格式无效，请重新导出后上传/);
  assert.equal(service.getFileProcessingError({ status: "quarantined" }), "文件完整性校验失败，请重新上传");
  assert.equal(service.getFileProcessingError({ status: "failed", jobs: [{ last_error: "RuntimeError" }] }),
    "文件处理失败，请检查文件后重新上传或稍后重试");
});

test("valid uploads remain usable while indexing continues", async () => {
  let uploaded = false;
  const { service } = loadService("files", {
    request: async (path) => {
      if (path === "/files/uploads") return { file_id: 5, upload: { url: "http://storage.invalid", fields: {} } };
      if (path.endsWith("/complete")) return {};
      return { id: 5, status: "available", metadata: { parse_status: "index_queued" } };
    },
    globals: { fetch: async () => { uploaded = true; return { ok: true }; } },
  });
  const status = await service.uploadCaseDocument({
    caseId: 10, filename: "有效样本.txt", sizeBytes: 4, buffer: new Uint8Array([116, 101, 115, 116]).buffer,
  });
  assert.equal(uploaded, true);
  assert.equal(status.metadata.parse_status, "index_queued");
});
