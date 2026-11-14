import type { CaseDraftFile } from "@/types/case";

export interface PickedDocumentResult {
  files: CaseDraftFile[];
  rejectedMessages: string[];
}

const MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024;
const ALLOWED_EXT_RE = /\.(pdf|docx|txt)$/i;

function formatFileSize(bytes?: number): string {
  if (!bytes || bytes <= 0) return "128 KB";
  if (bytes < 1024 * 1024) {
    return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function validatePickedList(
  items: { name: string; size?: number }[],
  remainingSlots: number,
): PickedDocumentResult {
  const files: CaseDraftFile[] = [];
  const rejectedMessages: string[] = [];

  for (const item of items) {
    if (files.length >= remainingSlots) {
      rejectedMessages.push("首批材料最多上传 5 个文件");
      break;
    }
    if (!ALLOWED_EXT_RE.test(item.name)) {
      rejectedMessages.push(`${item.name} 仅支持 PDF / DOCX / TXT`);
      continue;
    }
    if (item.size && item.size > MAX_FILE_SIZE_BYTES) {
      rejectedMessages.push(`${item.name} 超过 20MB 限制`);
      continue;
    }
    files.push({
      name: item.name,
      sizeText: formatFileSize(item.size),
      status: "ready",
    });
  }

  return { files, rejectedMessages };
}

/** 统一 H5 与微信小程序端的案件文档选择 */
export function chooseCaseDocuments(
  remainingSlots: number,
): Promise<PickedDocumentResult> {
  if (remainingSlots <= 0) {
    return Promise.resolve({
      files: [],
      rejectedMessages: ["首批材料最多上传 5 个文件"],
    });
  }

  // #ifdef H5
  return new Promise((resolve) => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".pdf,.docx,.txt";
    input.multiple = true;
    let settled = false;

    const finish = (result: PickedDocumentResult) => {
      if (settled) return;
      settled = true;
      resolve(result);
    };

    input.onchange = () => {
      const selected = Array.from(input.files || []).map((file) => ({
        name: file.name,
        size: file.size,
      }));
      finish(validatePickedList(selected, remainingSlots));
    };

    input.click();
  });
  // #endif

  // #ifndef H5
  return new Promise((resolve) => {
    uni.chooseMessageFile({
      count: Math.min(5, remainingSlots),
      type: "file",
      extension: ["pdf", "docx", "txt"],
      success: (res) => {
        const selected = (res.tempFiles || []).map((picked) => ({
          name: picked.name || "案件材料.pdf",
          size: picked.size,
        }));
        resolve(validatePickedList(selected, remainingSlots));
      },
      fail: () => {
        resolve({ files: [], rejectedMessages: [] });
      },
    });
  });
  // #endif
}
