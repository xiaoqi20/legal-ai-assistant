export type CaseType = "civil" | "criminal" | "administrative" | "other";

export type CaseProcedure =
  | "first_instance"
  | "second_instance"
  | "retrial"
  | "enforcement"
  | "arbitration"
  | "other";

export type CaseAnalysisStatus =
  | "not_analyzed"
  | "analyzing"
  | "analyzed"
  | "failed";

export type EvidenceUploadStatus = "not_uploaded" | "partial" | "completed";

export type CaseStatus = "active" | "archived" | "deleted";

export type DraftCaseType = "民事" | "刑事" | "行政" | "不确定";

export type HandlingIdentity = "" | "本人办理" | "代理他人";

export interface CaseDraftFile {
  name: string;
  sizeText: string;
  status: "ready" | "failed";
}

export type DraftPendingFieldKey =
  | "title"
  | "caseType"
  | "stage"
  | "claim"
  | "parties";

export type DraftPendingFields = Partial<Record<DraftPendingFieldKey, boolean>>;

export interface CaseDraftForm {
  step: "input" | "draft";
  title: string;
  caseType: "" | DraftCaseType;
  stage: string;
  summary: string;
  rawSummary: string;
  claim: string;
  handlingIdentity: HandlingIdentity;
  partyRole: string;
  ourParties: string[];
  opponentParties: string[];
  files: CaseDraftFile[];
  aiOrganized: boolean;
  pendingFields: DraftPendingFields;
}

export interface CaseSummary {
  id: number;
  title: string;
  case_type: CaseType;
  procedure: CaseProcedure;
  procedure_label?: string;
  analysis_status: CaseAnalysisStatus;
  evidence_upload_status: EvidenceUploadStatus;
  evidence_label?: string;
  win_rate: number | null;
  win_rate_updated_at: string | null;
  status: CaseStatus;
  created_at: string;
  updated_at: string;
  case_type_label?: string;
  summary?: string;
  claim?: string;
  handling_identity?: string;
  party_role?: string;
  our_parties?: string[];
  opponent_parties?: string[];
  files?: CaseDraftFile[];
  is_local?: boolean;
}

export type MaterialStatus =
  | "ai_passed"
  | "ai_analyzing"
  | "lawyer_pending"
  | "lawyer_rejected"
  | "ai_failed";

export type DocumentCategoryCode =
  | "case_procedure"
  | "court_record"
  | "communication"
  | "other";

export type DocumentCategoryLabel =
  | "案件程序"
  | "庭审记录"
  | "沟通记录"
  | "其他";

export type CaseAnalysisType =
  | "case_summary"
  | "timeline"
  | "judicial_reasoning"
  | "dispute_focus"
  | "evidence_chain"
  | "evidence_list";

export type AnalysisRecordStatus =
  | "pending"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled";

export interface CaseAnalysisRecord {
  id: number;
  case_id: number;
  analysis_type: CaseAnalysisType;
  status: AnalysisRecordStatus;
  content: Record<string, unknown> | null;
  error_message: string | null;
  created_at: string;
}

export interface EvidenceRequirement {
  id: number;
  case_id: number;
  title: string;
  purpose: string;
  collection: string;
  source?: "ai" | "manual";
}

export interface MaterialFile {
  id?: number;
  name: string;
  type: string;
  mime_type?: string;
  parse_status?: string;
}

export interface CaseMaterial {
  id: number;
  case_id: number;
  requirement_id: number;
  name: string;
  category: string;
  status: MaterialStatus;
  status_reason: string | null;
  uploader: string;
  uploaded_at: string;
  occurred_at: string;
  source: string;
  description: string;
  contact: string;
  files: MaterialFile[];
}

export interface CaseDocument {
  id: number;
  case_id: number;
  file_id?: number;
  name: string;
  type: string;
  mime_type?: string;
  parse_status?: string;
  uploader: string;
  uploaded_at: string;
  category: DocumentCategoryLabel;
}

export interface AnalysisData {
  summary: {
    parties: { label: string; value: string }[];
    facts: string[];
    requests: string[];
  };
  timeline: { date: string; title: string; detail: string }[];
  reasoning: { title: string; premise: string; conclusion: string }[];
  disputes: { party: string; points: string[] }[];
  laws: { name: string; content: string }[];
  limitations?: string;
}

export interface EvidenceSummaryData {
  plaintiff: { name: string; purpose: string }[];
  defendant: { name: string; purpose: string }[];
  analysis: string;
  limitations?: string;
}
