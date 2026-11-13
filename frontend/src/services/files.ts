import type { DocumentCategoryCode } from "@/types/case";
import { request } from "./request";

export type SupportedUploadMime =
  | "application/pdf"
  | "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
  | "text/plain";

interface UploadCreateResponse {
  file_id: number;
  upload: {
    url: string;
    fields: Record<string, string>;
  };
  expires_in: number;
}

export interface FileStatusResponse {
  id: number;
  case_id: number | null;
  original_name: string;
  mime_type?: string;
  size_bytes?: number;
  status: "uploading" | "available" | "failed" | "quarantined" | "deleted";
  metadata?: {
    parse_status?: string;
    [key: string]: unknown;
  };
  jobs?: {
    id: number;
    status: string;
    attempts: number;
    last_error: string | null;
  }[];
}

const SHA256_K = new Uint32Array([
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1,
  0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
  0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786,
  0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147,
  0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
  0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
  0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a,
  0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
  0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
]);

function rotr(value: number, bits: number): number {
  return (value >>> bits) | (value << (32 - bits));
}

function sha256Pure(bytes: Uint8Array): string {
  const len = bytes.length;
  const paddedLen = Math.ceil((len + 9) / 64) * 64;
  const padded = new Uint8Array(paddedLen);
  padded.set(bytes);
  padded[len] = 0x80;
  const bitLen = len * 8;
  const view = new DataView(padded.buffer);
  view.setUint32(paddedLen - 8, Math.floor(bitLen / 0x100000000), false);
  view.setUint32(paddedLen - 4, bitLen >>> 0, false);

  const h = new Uint32Array([
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
    0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
  ]);
  const w = new Uint32Array(64);

  for (let offset = 0; offset < paddedLen; offset += 64) {
    for (let i = 0; i < 16; i++) {
      w[i] = view.getUint32(offset + i * 4, false);
    }
    for (let i = 16; i < 64; i++) {
      const s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >>> 3);
      const s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >>> 10);
      w[i] = (w[i - 16] + s0 + w[i - 7] + s1) >>> 0;
    }

    let [a, b, c, d, e, f, g, hh] = h;
    for (let i = 0; i < 64; i++) {
      const S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
      const ch = (e & f) ^ (~e & g);
      const temp1 = (hh + S1 + ch + SHA256_K[i] + w[i]) >>> 0;
      const S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
      const maj = (a & b) ^ (a & c) ^ (b & c);
      const temp2 = (S0 + maj) >>> 0;

      hh = g;
      g = f;
      f = e;
      e = (d + temp1) >>> 0;
      d = c;
      c = b;
      b = a;
      a = (temp1 + temp2) >>> 0;
    }

    h[0] = (h[0] + a) >>> 0;
    h[1] = (h[1] + b) >>> 0;
    h[2] = (h[2] + c) >>> 0;
    h[3] = (h[3] + d) >>> 0;
    h[4] = (h[4] + e) >>> 0;
    h[5] = (h[5] + f) >>> 0;
    h[6] = (h[6] + g) >>> 0;
    h[7] = (h[7] + hh) >>> 0;
  }

  return Array.from(h, (word) => word.toString(16).padStart(8, "0")).join("");
}

export async function sha256Hex(buffer: ArrayBuffer): Promise<string> {
  if (typeof crypto !== "undefined" && crypto.subtle) {
    const digest = await crypto.subtle.digest("SHA-256", buffer);
    return Array.from(new Uint8Array(digest), (b) =>
      b.toString(16).padStart(2, "0"),
    ).join("");
  }
  return sha256Pure(new Uint8Array(buffer));
}

export function resolveUploadMimeType(filename: string): SupportedUploadMime {
  const lower = filename.trim().toLowerCase();
  if (lower.endsWith(".pdf")) return "application/pdf";
  if (lower.endsWith(".docx")) {
    return "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
  }
  if (lower.endsWith(".txt")) return "text/plain";
  throw new Error("目前仅支持上传 .pdf、.docx、.txt 文件");
}

function sanitizeFilename(name: string): string {
  const base = name.split(/[/\\]/).pop() || "document.pdf";
  return base.replace(/[\x00-\x1f]/g, "_").slice(0, 255);
}

async function uploadToPresignedPost(
  upload: UploadCreateResponse["upload"],
  filename: string,
  mimeType: SupportedUploadMime,
  params: { file?: File; filePath?: string; buffer?: ArrayBuffer },
) {
  // #ifdef H5
  const blob =
    params.file ||
    new Blob([params.buffer || new ArrayBuffer(0)], { type: mimeType });
  const formData = new FormData();
  Object.entries(upload.fields).forEach(([key, value]) => {
    formData.append(key, value);
  });
  // S3 presigned POST requires `file` to appear after policy form fields.
  formData.append("file", blob, filename);

  const response = await fetch(upload.url, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    throw new Error(`文件上传存储失败（${response.status}）`);
  }
  // #endif

  // #ifndef H5
  await new Promise<void>((resolve, reject) => {
    uni.uploadFile({
      url: upload.url,
      filePath: params.filePath || "",
      name: "file",
      formData: upload.fields,
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve();
        } else {
          reject(new Error(`文件上传存储失败（${res.statusCode}）`));
        }
      },
      fail: () => reject(new Error("文件上传网络失败")),
    });
  });
  // #endif
}

export function fetchFileStatus(fileId: number): Promise<FileStatusResponse> {
  return request<FileStatusResponse>(`/files/${fileId}`);
}

export async function waitForFileReady(
  fileId: number,
  maxAttempts = 20,
  intervalMs = 1000,
): Promise<FileStatusResponse> {
  for (let i = 0; i < maxAttempts; i++) {
    const status = await fetchFileStatus(fileId);
    if (status.status === "available") return status;
    if (status.status === "failed" || status.status === "quarantined") {
      const reason = status.jobs?.[0]?.last_error || "文件解析失败";
      throw new Error(reason);
    }
    await new Promise<void>((resolve) => setTimeout(resolve, intervalMs));
  }
  return fetchFileStatus(fileId);
}

export async function uploadCaseDocument(params: {
  caseId: number;
  filename: string;
  sizeBytes: number;
  category?: DocumentCategoryCode;
  file?: File;
  filePath?: string;
  buffer?: ArrayBuffer;
}): Promise<FileStatusResponse> {
  const filename = sanitizeFilename(params.filename);
  const mimeType = resolveUploadMimeType(filename);

  let arrayBuffer = params.buffer;
  if (!arrayBuffer && params.file) {
    arrayBuffer = await params.file.arrayBuffer();
  }
  if (!arrayBuffer && params.filePath) {
    const fs = uni.getFileSystemManager();
    arrayBuffer = fs.readFileSync(params.filePath) as ArrayBuffer;
  }
  if (!arrayBuffer) {
    throw new Error("无法读取文件内容");
  }

  const sha256 = await sha256Hex(arrayBuffer);
  const created = await request<UploadCreateResponse>("/files/uploads", {
    method: "POST",
    data: {
      case_id: params.caseId,
      filename,
      size_bytes: params.sizeBytes || arrayBuffer.byteLength,
      mime_type: mimeType,
      sha256,
      category: params.category || "other",
    },
  });

  await uploadToPresignedPost(created.upload, filename, mimeType, {
    file: params.file,
    filePath: params.filePath,
    buffer: arrayBuffer,
  });

  await request(`/files/${created.file_id}/complete`, { method: "POST" });
  return waitForFileReady(created.file_id);
}

export function getFileDownloadUrl(
  fileId: number,
): Promise<{ url: string; expires_in: number }> {
  return request<{ url: string; expires_in: number }>(
    `/files/${fileId}/download`,
  );
}

export async function openRemoteFile(
  fileId: number,
  mimeType?: string,
): Promise<void> {
  const { url } = await getFileDownloadUrl(fileId);

  // #ifdef H5
  window.open(url, "_blank", "noopener,noreferrer");
  // #endif

  // #ifndef H5
  if (mimeType?.startsWith("image/")) {
    uni.previewImage({ urls: [url] });
    return;
  }
  await new Promise<void>((resolve, reject) => {
    uni.downloadFile({
      url,
      success: (res) => {
        if (res.statusCode !== 200 || !res.tempFilePath) {
          reject(new Error("文件下载失败"));
          return;
        }
        uni.openDocument({
          filePath: res.tempFilePath,
          showMenu: true,
          success: () => resolve(),
          fail: () => reject(new Error("暂不支持直接打开此格式文件")),
        });
      },
      fail: () => reject(new Error("文件下载失败")),
    });
  });
  // #endif
}
