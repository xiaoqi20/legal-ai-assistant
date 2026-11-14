import type { CaseSummary } from "@/types/case";

const cases: CaseSummary[] = [
  {
    id: 1,
    title: "王家村房屋拆迁补偿纠纷案",
    case_type: "civil",
    procedure: "first_instance",
    analysis_status: "analyzed",
    evidence_upload_status: "completed",
    win_rate: 80,
    win_rate_updated_at: "2024-10-12T09:30:00+08:00",
    win_rate_status: "analyzed",
    status: "active",
    created_at: "2024-09-20T10:00:00+08:00",
    updated_at: "2024-10-12T09:30:00+08:00",
  },
  {
    id: 2,
    title: "王家村房屋拆迁补偿纠纷案",
    case_type: "civil",
    procedure: "first_instance",
    analysis_status: "not_analyzed",
    evidence_upload_status: "not_uploaded",
    win_rate: null,
    win_rate_updated_at: null,
    win_rate_status: "not_analyzed",
    status: "active",
    created_at: "2024-09-22T14:12:00+08:00",
    updated_at: "2024-09-22T14:12:00+08:00",
  },
  {
    id: 3,
    title: "王家村房屋拆迁补偿纠纷案",
    case_type: "civil",
    procedure: "first_instance",
    analysis_status: "analyzing",
    evidence_upload_status: "completed",
    win_rate: null,
    win_rate_updated_at: null,
    win_rate_status: "analyzing",
    status: "active",
    created_at: "2024-09-25T09:08:00+08:00",
    updated_at: "2024-10-12T10:20:00+08:00",
  },
  {
    id: 4,
    title: "王家村房屋拆迁补偿纠纷案",
    case_type: "civil",
    procedure: "first_instance",
    analysis_status: "analyzing",
    evidence_upload_status: "completed",
    win_rate: null,
    win_rate_updated_at: null,
    win_rate_status: "analyzing",
    status: "active",
    created_at: "2024-09-28T16:40:00+08:00",
    updated_at: "2024-10-12T11:05:00+08:00",
  },
];

export function fetchMockCases(keyword = ""): Promise<CaseSummary[]> {
  const query = keyword.trim();
  const result = query
    ? cases.filter((item) => item.title.includes(query))
    : cases;

  return new Promise((resolve) => {
    setTimeout(() => {
      resolve(result.map((item) => ({ ...item })));
    }, 240);
  });
}
