import { request, USE_MOCK, createClientId } from "./request";

export interface MaterialPayload {
  title: string;
  category: string;
  purpose: string;
  description: string;
  source: string;
  occurred_on: string | null;
  requirement_id: number | null;
  file_ids: number[];
}

function requireRealService() {
  if (USE_MOCK) throw new Error("请连接真实服务后使用材料写入与复核");
}

export function saveMaterial(caseId: number, payload: MaterialPayload, id?: number, revision?: number) {
  requireRealService();
  return request<{ id: number }>(`/cases/${caseId}/materials${id ? `/${id}` : ""}`, {
    method: id ? "PUT" : "POST", data: id ? { ...payload, revision } : { ...payload },
  });
}

export function actOnMaterial(caseId: number, id: number, revision: number, action: string, comment: string) {
  requireRealService();
  return request(`/cases/${caseId}/materials/${id}/actions`, { method: "POST", data: { revision, action, comment } });
}

export interface MaterialEvent {
  id: number;
  actor_id: number;
  action: string;
  revision: number;
  comment: string;
  created_at: string;
}

export function fetchMaterialEvents(caseId: number, id: number) {
  requireRealService();
  return request<MaterialEvent[]>(`/cases/${caseId}/materials/${id}/events`);
}

export function analyzeMaterial(caseId: number, id: number) {
  requireRealService();
  return request<{ analysis_id: number }>(`/cases/${caseId}/analyses`, { method: "POST", data: {
    analysis_type: "material_review", material_id: id, client_request_id: createClientId("mat"),
  } });
}
