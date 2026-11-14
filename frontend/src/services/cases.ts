import type { CaseCreatePayload, CaseSummary } from "@/types/case";
import { fetchMockCases } from "./mock/cases";
import { request, USE_MOCK } from "./request";

export function fetchCases(keyword = ""): Promise<CaseSummary[]> {
  if (USE_MOCK) return fetchMockCases(keyword);
  return request<CaseSummary[]>("/cases", { query: { keyword } });
}

export function createCase(payload: CaseCreatePayload): Promise<CaseSummary> {
  return request<CaseSummary>("/cases", {
    method: "POST",
    data: payload,
  });
}
