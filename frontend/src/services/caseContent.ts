import {
  DOCUMENT_CATEGORY_LABELS,
  EVIDENCE_CATEGORY_LABELS,
} from "@/constants/case";
import type {
  AnalysisData,
  CaseAnalysisRecord,
  CaseAnalysisType,
  CaseDocument,
  CaseMaterial,
  CaseSummary,
  DocumentCategoryCode,
  EvidenceRequirement,
  EvidenceSummaryData,
  MaterialFile,
  MaterialStatus,
} from "@/types/case";
import { fetchMockCases } from "./mock/cases";
import { USE_MOCK, createClientId, request } from "./request";

const delay = (ms = 160) =>
  new Promise<void>((resolve) => setTimeout(resolve, ms));

interface BackendMaterialRow {
  id: number;
  case_id: number;
  requirement_id: number;
  category: string;
  title: string;
  status: MaterialStatus;
  status_reason: string | null;
  description?: string | null;
  source?: string | null;
  occurred_on?: string | null;
  contact_name?: string | null;
  contact_phone_masked?: string | null;
  created_at: string;
  files?: { id: number; original_name: string; mime_type: string }[];
}

interface BackendDocumentRow {
  id: number;
  case_id: number;
  file_id: number;
  title: string;
  category: DocumentCategoryCode;
  original_name?: string;
  mime_type?: string;
  parse_status?: string;
  created_at: string;
  uploaded_by: number;
}

function fileExt(name: string, mimeType?: string): string {
  const idx = name.lastIndexOf(".");
  if (idx >= 0 && idx < name.length - 1) {
    return name.slice(idx + 1).toLowerCase();
  }
  if (mimeType === "application/pdf") return "pdf";
  return "docx";
}

function formatTime(iso: string | null | undefined): string {
  if (!iso) return "";
  return iso.replace("T", " ").slice(0, 19);
}

function mapMaterial(row: BackendMaterialRow): CaseMaterial {
  const files: MaterialFile[] = (row.files || []).map((item) => ({
    id: item.id,
    name: item.original_name,
    type: fileExt(item.original_name, item.mime_type),
    mime_type: item.mime_type,
  }));

  return {
    id: row.id,
    case_id: row.case_id,
    requirement_id: row.requirement_id,
    name: row.title,
    category: EVIDENCE_CATEGORY_LABELS[row.category] || row.category,
    status: row.status,
    status_reason: row.status_reason ?? null,
    uploader: row.contact_name || "案件成员",
    uploaded_at: formatTime(row.created_at),
    occurred_at: row.occurred_on ? row.occurred_on.slice(0, 10) : "—",
    source: row.source || "—",
    description: row.description || "暂无材料说明",
    contact: row.contact_phone_masked || "—",
    files,
  };
}

function mapDocument(row: BackendDocumentRow): CaseDocument {
  const name = row.original_name || row.title;
  return {
    id: row.id,
    case_id: row.case_id,
    file_id: row.file_id,
    name: row.title || name,
    type: fileExt(name, row.mime_type),
    mime_type: row.mime_type,
    parse_status: row.parse_status,
    uploader: `成员 #${row.uploaded_by}`,
    uploaded_at: formatTime(row.created_at),
    category: DOCUMENT_CATEGORY_LABELS[row.category] || "其他",
  };
}

export async function fetchCase(id: number): Promise<CaseSummary> {
  if (USE_MOCK) {
    const cases = await fetchMockCases();
    const found = cases.find((item) => item.id === id);
    if (!found) throw new Error("案件不存在");
    return found;
  }
  return request<CaseSummary>(`/cases/${id}`);
}

const requirements: EvidenceRequirement[] = [
  {
    id: 1,
    case_id: 1,
    title: "房屋买卖合同原件",
    purpose: "证明借款事实及其金额",
    collection:
      "获取途径：银行、支付宝、微信支付等金融机构。收集方法：通过银行流水查询、支付宝/微信账单下载。注意事项：确保转账记录完整、清晰，能够显示交易双方、金额及时间。",
  },
  {
    id: 2,
    case_id: 1,
    title: "微信聊天记录",
    purpose: "证明双方就借款事项进行了沟通，并确认了还款安排",
    collection:
      "获取途径：微信聊天记录保存功能。收集方法：通过微信聊天记录导出功能保存聊天记录，确保包含所有与借款和还款安排相关的内容。",
  },
  {
    id: 3,
    case_id: 1,
    title: "银行转账记录",
    purpose: "证明购房款已实际支付及支付金额",
    collection:
      "获取途径：开户银行。收集方法：申请打印加盖银行业务章的流水，补充对应转账凭证。注意事项：保留原始电子回单。",
  },
];

const materials: CaseMaterial[] = [
  {
    id: 1,
    case_id: 1,
    requirement_id: 1,
    name: "房屋买卖合同",
    category: "书面文件",
    status: "ai_passed",
    status_reason: null,
    uploader: "周舟",
    uploaded_at: "2024-09-29 11:36:33",
    occurred_at: "2020-01-01",
    source: "客户收集",
    description: "原被告签订的房屋买卖合同原件，约定成交价 100 万元。",
    contact: "138****2201",
    files: [{ name: "民事答辩状.docx", type: "docx" }],
  },
  {
    id: 2,
    case_id: 1,
    requirement_id: 1,
    name: "房屋买卖合同补充页",
    category: "书面文件",
    status: "ai_analyzing",
    status_reason: null,
    uploader: "周舟",
    uploaded_at: "2024-09-29 11:36:33",
    occurred_at: "2020-01-01",
    source: "客户收集",
    description: "合同补充条款及双方签字页。",
    contact: "138****2201",
    files: [{ name: "补充协议.docx", type: "docx" }],
  },
  {
    id: 3,
    case_id: 1,
    requirement_id: 1,
    name: "房屋交接材料",
    category: "书面文件",
    status: "lawyer_pending",
    status_reason: null,
    uploader: "周舟",
    uploaded_at: "2024-09-29 11:36:33",
    occurred_at: "2020-05-18",
    source: "客户收集",
    description: "房屋交接单及钥匙交接记录。",
    contact: "138****2201",
    files: [
      { name: "交接单.docx", type: "docx" },
      { name: "交接照片.png", type: "png" },
      { name: "物业证明.pdf", type: "pdf" },
    ],
  },
  {
    id: 4,
    case_id: 1,
    requirement_id: 2,
    name: "微信聊天记录",
    category: "电子文档",
    status: "ai_passed",
    status_reason: null,
    uploader: "周舟",
    uploaded_at: "2024-09-30 09:21:08",
    occurred_at: "2020-05-10",
    source: "客户收集",
    description: "双方就加价、交房及门锁更换的沟通记录。",
    contact: "138****2201",
    files: [
      { name: "聊天记录.pdf", type: "pdf" },
      { name: "聊天截图.png", type: "png" },
    ],
  },
  {
    id: 5,
    case_id: 1,
    requirement_id: 3,
    name: "房产证复印件",
    category: "物证书证",
    status: "ai_failed",
    status_reason: "证据链不足：缺少过户登记回执，无法证明产权已变更。",
    uploader: "宋芝",
    uploaded_at: "2024-10-02 15:02:41",
    occurred_at: "2020-03-20",
    source: "客户收集",
    description: "涉案房屋不动产权证复印件。",
    contact: "139****7788",
    files: [{ name: "房产证复印件.pdf", type: "pdf" }],
  },
];

const documents: CaseDocument[] = [
  {
    id: 1,
    case_id: 1,
    name: "民事答辩状.docx",
    type: "docx",
    uploader: "周舟",
    uploaded_at: "2024-09-29 11:36:33",
    category: "案件程序",
  },
  {
    id: 2,
    case_id: 1,
    name: "民事答辩状.pdf",
    type: "pdf",
    uploader: "周舟",
    uploaded_at: "2024-09-29 11:36:33",
    category: "案件程序",
  },
  {
    id: 3,
    case_id: 1,
    name: "某某打架斗殴docx.docx",
    type: "docx",
    uploader: "周舟",
    uploaded_at: "2024-09-29 11:36:33",
    category: "庭审记录",
  },
  {
    id: 4,
    case_id: 1,
    name: "王家村房屋拆迁补偿纠纷案.docx",
    type: "docx",
    uploader: "周舟",
    uploaded_at: "2024-09-29 11:36:33",
    category: "案件程序",
  },
  {
    id: 5,
    case_id: 1,
    name: "民事答辩状.docx",
    type: "docx",
    uploader: "周舟",
    uploaded_at: "2024-09-29 11:36:33",
    category: "沟通记录",
  },
  {
    id: 6,
    case_id: 1,
    name: "庭审笔录.pdf",
    type: "pdf",
    uploader: "周舟",
    uploaded_at: "2024-09-29 11:36:33",
    category: "庭审记录",
  },
];

const analysis: AnalysisData = {
  summary: {
    parties: [
      { label: "原告", value: "张某（委托人）" },
      { label: "被告", value: "李某" },
    ],
    facts: [
      "2020 年 1 月，双方签订房屋买卖合同，约定成交价 100 万元。",
      "原告支付全部购房款并完成过户，取得房屋产权。",
      "2020 年 5 月，被告要求额外支付 20 万元，遭拒后强行换锁。",
    ],
    requests: [
      "判令被告停止侵权、恢复房屋原状。",
      "判令被告赔偿经济损失 20,000 元。",
      "本案诉讼费用由被告承担。",
    ],
  },
  timeline: [
    {
      date: "2020 年 1 月",
      title: "签订房屋买卖合同",
      detail: "约定房屋成交价 100 万元，原告依约付款。",
    },
    {
      date: "2020 年 3 月",
      title: "完成过户登记",
      detail: "房屋产权变更至原告名下，原告取得不动产权证。",
    },
    {
      date: "2020 年 5 月",
      title: "被告要求加价",
      detail: "被告以价格过低为由要求追加 20 万元，原告拒绝。",
    },
    {
      date: "2020 年 5 月",
      title: "强行换锁",
      detail: "被告进入房屋并更换门锁，导致原告无法正常使用。",
    },
  ],
  reasoning: [
    {
      title: "大前提：合同应全面履行",
      premise:
        "依法成立的合同对当事人具有法律约束力，双方应按约定全面履行义务。",
      conclusion: "被告无权在合同履行完毕后单方要求加价。",
    },
    {
      title: "小前提：原告已取得物权",
      premise: "原告已支付全部价款并完成过户登记，依法享有房屋所有权。",
      conclusion: "被告强行进入并换锁，妨碍原告行使物权。",
    },
    {
      title: "结论：构成侵权",
      premise: "未经权利人同意进入并妨碍其正常使用房屋，属于侵权行为。",
      conclusion: "被告应承担停止侵害、恢复原状及赔偿损失的责任。",
    },
  ],
  disputes: [
    {
      party: "原告主张",
      points: [
        "合同合法有效且已履行完毕，被告无权加价。",
        "被告换锁行为侵害原告物权，应赔偿损失。",
      ],
    },
    {
      party: "被告抗辩",
      points: [
        "主张合同价款明显低于市场价，合同条款理解存在分歧。",
        "主张部分款项到账时间与约定不符。",
      ],
    },
  ],
  laws: [
    {
      name: "《民法典》第 465 条",
      content: "依法成立的合同，受法律保护，仅对当事人具有法律约束力。",
    },
    {
      name: "《民法典》第 509 条",
      content: "当事人应当按照约定全面履行自己的义务。",
    },
    {
      name: "《民法典》第 1165 条",
      content: "行为人因过错侵害他人民事权益造成损害的，应当承担侵权责任。",
    },
  ],
};

const evidenceSummary: EvidenceSummaryData = {
  plaintiff: [
    { name: "房屋买卖合同原件", purpose: "证明合同有效及履行情况。" },
    { name: "银行转账记录", purpose: "证明已支付全部购房款。" },
    { name: "房产证复印件", purpose: "证明已完成过户登记。" },
    { name: "物业证明", purpose: "证明被告强行换锁的侵权事实。" },
  ],
  defendant: [
    { name: "房屋买卖合同原件", purpose: "证明合同条款理解存在分歧。" },
    { name: "银行转账记录", purpose: "核实款项到账时间。" },
  ],
  analysis:
    "原告证据能够形成完整证据链，被告证据不足以反驳原告主张。建议补充物业出具的侵权事实证明及门锁更换记录。",
};

export async function fetchEvidenceRequirements(
  caseId: number,
  keyword = "",
): Promise<EvidenceRequirement[]> {
  if (USE_MOCK) {
    await delay();
    return requirements
      .filter((item) => item.case_id === caseId)
      .map((item) => ({ ...item }));
  }
  return request<EvidenceRequirement[]>(
    `/cases/${caseId}/evidence-requirements`,
    { query: { keyword } },
  );
}

export async function fetchMaterials(caseId: number): Promise<CaseMaterial[]> {
  if (USE_MOCK) {
    await delay();
    return materials
      .filter((item) => item.case_id === caseId)
      .map((item) => ({ ...item, files: item.files.map((file) => ({ ...file })) }));
  }
  const rows = await request<BackendMaterialRow[]>(`/cases/${caseId}/materials`);
  return rows.map(mapMaterial);
}

export async function fetchMaterial(
  id: number,
  caseId?: number,
): Promise<CaseMaterial> {
  if (USE_MOCK) {
    await delay();
    const found = materials.find((item) => item.id === id);
    if (!found) throw new Error("材料不存在");
    return { ...found, files: found.files.map((file) => ({ ...file })) };
  }
  if (!caseId) throw new Error("缺少案件参数");
  const row = await request<BackendMaterialRow>(
    `/cases/${caseId}/materials/${id}`,
  );
  return mapMaterial(row);
}

export async function fetchDocuments(caseId: number): Promise<CaseDocument[]> {
  if (USE_MOCK) {
    await delay();
    return documents
      .filter((item) => item.case_id === caseId)
      .map((item) => ({ ...item }));
  }
  const rows = await request<BackendDocumentRow[]>(`/cases/${caseId}/documents`);
  return rows.map(mapDocument);
}

export type AnalysisPanelType =
  | "case_summary"
  | "timeline"
  | "judicial_reasoning"
  | "dispute_focus";

export interface AnalysisBundle {
  data: AnalysisData;
  records: Record<AnalysisPanelType, CaseAnalysisRecord | null>;
}

export interface EvidenceSummaryBundle {
  data: EvidenceSummaryData | null;
  record: CaseAnalysisRecord | null;
}

function emptyAnalysisData(): AnalysisData {
  return {
    summary: { parties: [], facts: [], requests: [] },
    timeline: [],
    reasoning: [],
    disputes: [],
    laws: [],
  };
}

function latestByType(
  rows: CaseAnalysisRecord[],
  analysisType: CaseAnalysisType,
): CaseAnalysisRecord | null {
  return rows.find((item) => item.analysis_type === analysisType) ?? null;
}

function mapEvidenceReport(
  content: Record<string, unknown>,
): EvidenceSummaryData {
  return {
    plaintiff: Array.isArray(content.plaintiff)
      ? (content.plaintiff as EvidenceSummaryData["plaintiff"])
      : [],
    defendant: Array.isArray(content.defendant)
      ? (content.defendant as EvidenceSummaryData["defendant"])
      : [],
    analysis: typeof content.analysis === "string" ? content.analysis : "",
    limitations:
      typeof content.limitations === "string" ? content.limitations : undefined,
  };
}

export async function fetchCaseAnalyses(
  caseId: number,
): Promise<CaseAnalysisRecord[]> {
  return request<CaseAnalysisRecord[]>(`/cases/${caseId}/analyses`);
}

export function fetchCaseAnalysisRecord(
  caseId: number,
  analysisId: number,
): Promise<CaseAnalysisRecord> {
  return request<CaseAnalysisRecord>(`/cases/${caseId}/analyses/${analysisId}`);
}

export function triggerCaseAnalysis(
  caseId: number,
  analysisType: CaseAnalysisType,
): Promise<{ analysis_id: number; job_id: number; status: string }> {
  return request<{ analysis_id: number; job_id: number; status: string }>(
    `/cases/${caseId}/analyses`,
    {
      method: "POST",
      data: {
        analysis_type: analysisType,
        client_request_id: createClientId("ana"),
      },
    },
  );
}

export function cancelCaseAnalysis(
  caseId: number,
  analysisId: number,
): Promise<{ status: string }> {
  return request<{ status: string }>(
    `/cases/${caseId}/analyses/${analysisId}/cancel`,
    { method: "POST" },
  );
}

export async function fetchAnalysisBundle(
  caseId: number,
): Promise<AnalysisBundle> {
  if (USE_MOCK) {
    await delay();
    if (caseId <= 0) throw new Error("案件不存在");
    const mockRecord = (type: AnalysisPanelType): CaseAnalysisRecord => ({
      id: 0,
      case_id: caseId,
      analysis_type: type,
      status: "succeeded",
      content: null,
      error_message: null,
      created_at: "",
    });
    return {
      data: JSON.parse(JSON.stringify(analysis)) as AnalysisData,
      records: {
        case_summary: mockRecord("case_summary"),
        timeline: mockRecord("timeline"),
        judicial_reasoning: mockRecord("judicial_reasoning"),
        dispute_focus: mockRecord("dispute_focus"),
      },
    };
  }

  const rows = await fetchCaseAnalyses(caseId);
  const summaryRec = latestByType(rows, "case_summary");
  const timelineRec = latestByType(rows, "timeline");
  const reasoningRec = latestByType(rows, "judicial_reasoning");
  const disputeRec = latestByType(rows, "dispute_focus");

  const data = emptyAnalysisData();
  if (summaryRec?.status === "succeeded" && summaryRec.content) {
    const c = summaryRec.content;
    data.summary = {
      parties: Array.isArray(c.parties)
        ? (c.parties as AnalysisData["summary"]["parties"])
        : [],
      facts: Array.isArray(c.facts) ? (c.facts as string[]) : [],
      requests: Array.isArray(c.requests) ? (c.requests as string[]) : [],
    };
  }
  if (timelineRec?.status === "succeeded" && timelineRec.content) {
    const c = timelineRec.content;
    data.timeline = Array.isArray(c.items)
      ? (c.items as AnalysisData["timeline"])
      : [];
  }
  if (reasoningRec?.status === "succeeded" && reasoningRec.content) {
    const c = reasoningRec.content;
    data.reasoning = Array.isArray(c.items)
      ? (c.items as AnalysisData["reasoning"])
      : [];
  }
  if (disputeRec?.status === "succeeded" && disputeRec.content) {
    const c = disputeRec.content;
    data.disputes = Array.isArray(c.disputes)
      ? (c.disputes as AnalysisData["disputes"])
      : [];
    data.laws = Array.isArray(c.laws) ? (c.laws as AnalysisData["laws"]) : [];
  }

  return {
    data,
    records: {
      case_summary: summaryRec,
      timeline: timelineRec,
      judicial_reasoning: reasoningRec,
      dispute_focus: disputeRec,
    },
  };
}

export async function fetchAnalysis(caseId: number): Promise<AnalysisData> {
  const bundle = await fetchAnalysisBundle(caseId);
  return bundle.data;
}

export async function fetchEvidenceSummaryBundle(
  caseId: number,
): Promise<EvidenceSummaryBundle> {
  if (USE_MOCK) {
    await delay();
    if (caseId <= 0) throw new Error("案件不存在");
    return {
      data: JSON.parse(JSON.stringify(evidenceSummary)) as EvidenceSummaryData,
      record: {
        id: 0,
        case_id: caseId,
        analysis_type: "evidence_list",
        status: "succeeded",
        content: null,
        error_message: null,
        created_at: "",
      },
    };
  }

  const rows = await fetchCaseAnalyses(caseId);
  const record =
    latestByType(rows, "evidence_list") || latestByType(rows, "evidence_chain");
  if (record?.status === "succeeded" && record.content) {
    return {
      data: mapEvidenceReport(record.content),
      record,
    };
  }
  return { data: null, record };
}

export async function fetchEvidenceSummary(
  caseId: number,
): Promise<EvidenceSummaryData> {
  const bundle = await fetchEvidenceSummaryBundle(caseId);
  return bundle.data || { plaintiff: [], defendant: [], analysis: "" };
}
