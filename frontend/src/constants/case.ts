import type {
  CaseAnalysisStatus,
  CaseAnalysisType,
  CaseProcedure,
  DocumentCategoryCode,
  DocumentCategoryLabel,
  EvidenceUploadStatus,
  MaterialStatus,
} from "@/types/case";

type StatusTone = "green" | "pink" | "lavender" | "red";

export const ANALYSIS_STATUS_META: Record<
  CaseAnalysisStatus,
  { label: string; tone: StatusTone }
> = {
  analyzed: { label: "已分析", tone: "green" },
  not_analyzed: { label: "未分析", tone: "pink" },
  analyzing: { label: "分析中", tone: "lavender" },
  failed: { label: "分析失败", tone: "red" },
};

export const EVIDENCE_STATUS_META: Record<
  EvidenceUploadStatus,
  { label: string; complete: boolean }
> = {
  completed: { label: "已完成", complete: true },
  partial: { label: "部分上传", complete: false },
  not_uploaded: { label: "未上传", complete: false },
};

export const PROCEDURE_LABELS: Record<CaseProcedure, string> = {
  first_instance: "一审",
  second_instance: "二审",
  retrial: "再审",
  enforcement: "执行",
  arbitration: "仲裁",
  other: "其他",
};

export const MATERIAL_STATUS_META: Record<
  MaterialStatus,
  { label: string; tone: "blue" | "green" | "red" }
> = {
  ai_passed: { label: "AI分析通过", tone: "blue" },
  ai_analyzing: { label: "AI分析中", tone: "green" },
  lawyer_pending: { label: "律师待审核", tone: "blue" },
  lawyer_rejected: { label: "律师已驳回", tone: "red" },
  ai_failed: { label: "AI审核失败", tone: "red" },
};

export const EVIDENCE_CATEGORY_LABELS: Record<string, string> = {
  written: "书面文件",
  electronic: "电子文档",
  photo_video: "照片和视频",
  audio: "音频记录",
  physical: "物证书证",
};

export const DOCUMENT_CATEGORY_LABELS: Record<
  DocumentCategoryCode,
  DocumentCategoryLabel
> = {
  case_procedure: "案件程序",
  court_record: "庭审记录",
  communication: "沟通记录",
  other: "其他",
};

export const ANALYSIS_TYPE_LABELS: Record<CaseAnalysisType, string> = {
  case_summary: "案情摘要",
  timeline: "案情时间轴",
  judicial_reasoning: "司法推理",
  dispute_focus: "争议焦点与法律分析",
  evidence_chain: "证据链分析",
  evidence_list: "证据清单梳理",
};
