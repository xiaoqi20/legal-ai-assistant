import type {
  CaseAnalysisStatus,
  CaseAnalysisType,
  CaseProcedure,
  CaseType,
  DocumentCategoryCode,
  DocumentCategoryLabel,
  DraftCaseType,
  EvidenceUploadStatus,
  MaterialStatus,
  WinRateStatus,
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

export const WIN_RATE_STATUS_META: Record<
  WinRateStatus,
  { label: string; tone: StatusTone }
> = {
  analyzed: { label: "已评估", tone: "green" },
  not_analyzed: { label: "未评估", tone: "pink" },
  analyzing: { label: "测算中", tone: "lavender" },
  failed: { label: "测算失败", tone: "red" },
  not_applicable: { label: "暂不适用", tone: "pink" },
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
  draft: { label: "草稿", tone: "blue" },
  withdrawn: { label: "已撤回", tone: "blue" },
  lawyer_approved: { label: "律师已通过", tone: "green" },
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
  win_rate: "胜诉率测算",
  material_review: "材料辅助分析",
  complaint_draft: "民事起诉状草稿",
  evidence_catalog: "证据目录草稿",
  case_summary: "案情摘要",
  timeline: "案情时间轴",
  judicial_reasoning: "司法推理",
  dispute_focus: "争议焦点与法律分析",
  evidence_chain: "证据链分析",
  evidence_list: "证据清单梳理",
};

export const CREATE_CASE_TYPES: DraftCaseType[] = [
  "民事",
  "刑事",
  "行政",
  "不确定",
];

export const CREATE_STAGE_OPTIONS: Record<DraftCaseType, string[]> = {
  民事: ["尚未起诉/诉前咨询", "一审", "二审", "再审", "执行", "仲裁", "不确定"],
  刑事: ["尚未立案/咨询", "侦查阶段", "审查起诉", "一审", "二审", "不确定"],
  行政: ["尚未起诉/复议前", "行政复议", "一审", "二审", "再审", "不确定"],
  不确定: ["尚未起诉/诉前咨询", "已进入诉讼/仲裁", "不确定"],
};

export const CREATE_ROLE_OPTIONS: Record<DraftCaseType, string[]> = {
  民事: ["原告", "被告", "申请人", "被申请人", "第三人", "不确定"],
  刑事: ["被害人/报案人", "犯罪嫌疑人/被告人", "近亲属/委托人", "不确定"],
  行政: ["行政相对人/原告", "利害关系人", "不确定"],
  不确定: ["主张权利方", "被追责/被诉方", "不确定"],
};

export const CASE_TYPE_CODE_MAP: Record<DraftCaseType | "", CaseType> = {
  民事: "civil",
  刑事: "criminal",
  行政: "administrative",
  不确定: "other",
  "": "other",
};

export const CASE_PROCEDURE_CODE_MAP: Record<string, CaseProcedure> = {
  一审: "first_instance",
  二审: "second_instance",
  再审: "retrial",
  执行: "enforcement",
  仲裁: "arbitration",
};

export interface CasePromptPreset {
  key: string;
  label: string;
  summary: string;
}

export const CASE_PROMPT_PRESETS: CasePromptPreset[] = [
  {
    key: "loan",
    label: "借条欠款未还",
    summary:
      "我在2024年借给李某五万元，一直没还，有借条，希望追回本金和利息。",
  },
  {
    key: "property",
    label: "物业漏水索赔",
    summary:
      "2025年3月起小区地下车库长期漏水导致我方张某车辆受损，多次向安徽某物业服务有限公司书面报修未果，目前尚未起诉，希望物业公司履行维修义务并赔偿损失1.2万元。",
  },
  {
    key: "labor",
    label: "劳动欠薪维权",
    summary:
      "2024年8月入职某科技有限公司，公司拖欠近3个月工资共计3.6万元并单方解除劳动关系，准备申请劳动仲裁，希望追回欠薪及经济补偿。",
  },
];
