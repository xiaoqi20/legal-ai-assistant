import { uploadCaseDocument } from "@/services/files";

/** Returns null when selection is cancelled. The selected binary stays with the upload workflow. */
export async function chooseAndUploadDocument(caseId: number): Promise<number | null> {
  // #ifdef H5
  return uploadBrowserFile(caseId);
  // #endif
  // #ifndef H5
  return uploadWechatFile(caseId);
  // #endif
}

// #ifdef H5
async function uploadBrowserFile(caseId: number) {
  const file = await new Promise<File | null>((resolve) => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".pdf,.docx,.txt,.jpg,.jpeg,.png";
    input.onchange = () => resolve(input.files?.[0] || null);
    input.oncancel = () => resolve(null);
    input.click();
  });
  if (!file) return null;
  return (await uploadCaseDocument({ caseId, filename: file.name, sizeBytes: file.size, file })).id;
}
// #endif

// #ifndef H5
async function uploadWechatFile(caseId: number) {
  const pickedFile = await new Promise<{ path: string; name: string; size: number } | null>((resolve, reject) => {
    uni.chooseMessageFile({ count: 1, type: "file", extension: ["pdf", "docx", "txt", "jpg", "jpeg", "png"],
      success: (result) => resolve(result.tempFiles[0] || null),
      fail: (error) => error.errMsg.includes("cancel") ? resolve(null) : reject(new Error("选择文件失败")),
    });
  });
  if (!pickedFile) return null;
  return (await uploadCaseDocument({ caseId, filename: pickedFile.name, sizeBytes: pickedFile.size, filePath: pickedFile.path })).id;
}
// #endif
