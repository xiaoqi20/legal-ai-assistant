import type { CaseAnalysisRecord } from "@/types/case";
import { API_BASE_URL, getStoredToken, request, USE_MOCK } from "./request";

export interface DraftRevision { id: number; revision: number; title: string; body: string; created_at: string }
export interface DraftDetail {
  analysis: CaseAnalysisRecord & { model?: string; prompt_version_id?: number; source_fingerprint?: string };
  revisions: DraftRevision[];
  sources: { id: number; original_name: string; page_no?: number; file_status: string }[];
}
function requireRealService() { if (USE_MOCK) throw new Error("请连接真实服务后使用文书草稿"); }
export function fetchDrafts(caseId: number) {
  requireRealService();
  return request<CaseAnalysisRecord[]>(`/cases/${caseId}/drafts`);
}
export function fetchDraft(caseId: number, id: number) {
  requireRealService();
  return request<DraftDetail>(`/cases/${caseId}/drafts/${id}`);
}
export function saveDraft(caseId: number, id: number, revision: number, title: string, body: string) {
  requireRealService();
  return request<DraftRevision>(`/cases/${caseId}/drafts/${id}`, { method: "PUT", data: { expected_revision: revision, title, body } });
}
export async function exportDraft(caseId: number, id: number, revision: number) {
  requireRealService();
  const url = `${API_BASE_URL}/cases/${caseId}/drafts/${id}/export?revision=${revision}`;
  // #ifdef H5
  const response = await fetch(url, { headers: { Authorization: `Bearer ${getStoredToken()}` } });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(error?.error?.message || "导出失败，请稍后重试");
  }
  const objectUrl = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = objectUrl; link.download = `文书草稿-v${revision}.docx`; link.click();
  setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
  // #endif
  // #ifndef H5
  await new Promise<void>((resolve, reject) => {
    uni.downloadFile({ url, header: { Authorization: `Bearer ${getStoredToken()}` },
      success: (result) => {
        if (result.statusCode !== 200) { reject(new Error("导出失败，请检查草稿及来源材料是否可用")); return; }
        uni.openDocument({ filePath: result.tempFilePath, fileType: "docx", showMenu: true,
          success: () => resolve(), fail: () => reject(new Error("文书已下载，但打开失败，请重试")) });
      }, fail: () => reject(new Error("文书下载失败，请检查网络")),
    });
  });
  // #endif
}
