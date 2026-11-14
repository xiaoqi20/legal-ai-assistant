import {
  CASE_PROCEDURE_CODE_MAP,
  CASE_TYPE_CODE_MAP,
  CREATE_STAGE_OPTIONS,
} from "@/constants/case";
import type {
  CaseCreatePayload,
  CaseDraftForm,
  DraftCaseType,
  DraftPendingFields,
} from "@/types/case";

interface CaseExtractionRule {
  pattern: RegExp;
  caseType: Exclude<DraftCaseType, "不确定">;
  title: string;
}

const CASE_EXTRACTION_RULES: CaseExtractionRule[] = [
  {
    pattern: /(借条|欠条|借款|借给|拖欠.*本金|本金.*利息|民间借贷|还钱|还款)/,
    caseType: "民事",
    title: "民间借贷纠纷案",
  },
  {
    pattern: /(物业|漏水|渗水|车库|维修义务|业主|物业费)/,
    caseType: "民事",
    title: "物业服务合同纠纷案",
  },
  {
    pattern: /(拆迁|补偿|征收)/,
    caseType: "民事",
    title: "房屋拆迁补偿纠纷案",
  },
  {
    pattern: /(装饰|装修|工程|施工|尾款|承揽)/,
    caseType: "民事",
    title: "建设/装修工程合同纠纷案",
  },
  {
    pattern: /(劳动|欠薪|工资|拖欠薪资|解除劳动|加班费|社保)/,
    caseType: "民事",
    title: "劳动争议纠纷案",
  },
  {
    pattern: /(买卖|货款|供货|购销)/,
    caseType: "民事",
    title: "买卖合同纠纷案",
  },
  {
    pattern: /(租房|租赁|房东|押金|退租|房租)/,
    caseType: "民事",
    title: "房屋租赁合同纠纷案",
  },
  {
    pattern: /(离婚|抚养|继承|赡养)/,
    caseType: "民事",
    title: "婚姻家庭纠纷案",
  },
  {
    pattern: /(商标|版权|著作权|专利|侵权)/,
    caseType: "民事",
    title: "知识产权侵权纠纷案",
  },
  {
    pattern: /(交通事故|撞车|车祸|理赔)/,
    caseType: "民事",
    title: "机动车交通事故纠纷案",
  },
  {
    pattern: /(起诉状|合同|违约|赔款|赔偿)/,
    caseType: "民事",
    title: "",
  },
  {
    pattern: /(刑拘|取保|侦查|检察院|诈骗|盗窃|刑事|故意伤害)/,
    caseType: "刑事",
    title: "刑事案件法律事务",
  },
  {
    pattern: /(行政处罚|行政复议|政府信息公开|工商|城管|税务)/,
    caseType: "行政",
    title: "行政争议案件",
  },
];

export function createEmptyDraftForm(): CaseDraftForm {
  return {
    step: "input",
    title: "",
    caseType: "",
    stage: "",
    summary: "",
    rawSummary: "",
    claim: "",
    handlingIdentity: "",
    partyRole: "",
    ourParties: [""],
    opponentParties: [""],
    files: [],
    aiOrganized: false,
    pendingFields: {},
  };
}

export function hasDraftContent(form: CaseDraftForm): boolean {
  return Boolean(
    form.title.trim() ||
      form.caseType ||
      form.stage ||
      form.summary.trim() ||
      form.claim.trim() ||
      form.handlingIdentity ||
      form.partyRole ||
      form.files.length ||
      form.ourParties.some((item) => item.trim()) ||
      form.opponentParties.some((item) => item.trim()),
  );
}

/** 从案情描述整理可编辑建案草稿；未显式提及的主体与阶段不臆测，标为待确认 */
export function buildOrganizedDraft(form: CaseDraftForm): DraftPendingFields {
  const readyFiles = form.files.filter((file) => file.status !== "failed");
  const rawText = [form.summary.trim(), form.claim.trim()]
    .filter(Boolean)
    .join("；");
  const corpus = rawText;
  const pending: DraftPendingFields = {};

  let nextType = form.caseType;
  let matchedTitle = "";
  if (corpus) {
    for (const rule of CASE_EXTRACTION_RULES) {
      if (rule.pattern.test(corpus)) {
        if (!nextType) nextType = rule.caseType;
        if (!matchedTitle && rule.title) matchedTitle = rule.title;
        if (nextType && matchedTitle) break;
      }
    }
  }
  if (!nextType) pending.caseType = true;

  let nextStage = form.stage;
  if (!nextStage && corpus) {
    let guessedStage = "";
    if (/(尚未起诉|还没起诉|没起诉|诉前|准备起诉|打算起诉|还没去法院)/.test(corpus)) {
      guessedStage = "尚未起诉/诉前咨询";
    } else if (/行政复议|复议中/.test(corpus)) {
      guessedStage = "行政复议";
    } else if (/复议前|刚收到处罚/.test(corpus)) {
      guessedStage = "尚未起诉/复议前";
    } else if (/侦查|刑拘|刑事立案|派出所/.test(corpus)) {
      guessedStage = "侦查阶段";
    } else if (/审查起诉|移送检察/.test(corpus)) {
      guessedStage = "审查起诉";
    } else if (/二审|上诉/.test(corpus)) {
      guessedStage = "二审";
    } else if (/再审|申诉/.test(corpus)) {
      guessedStage = "再审";
    } else if (/仲裁/.test(corpus)) {
      guessedStage = "仲裁";
    } else if (/强制执行|执行阶段/.test(corpus)) {
      guessedStage = "执行";
    } else if (/(一审|已经起诉|收到传票|已立案)/.test(corpus)) {
      guessedStage = "一审";
    }

    if (
      guessedStage &&
      nextType &&
      (CREATE_STAGE_OPTIONS[nextType] || []).includes(guessedStage)
    ) {
      nextStage = guessedStage;
    }
  }
  if (!nextStage) pending.stage = true;

  const nextTitle = form.title.trim() || matchedTitle;
  if (!nextTitle) pending.title = true;

  let nextClaim = form.claim.trim();
  if (!nextClaim && corpus) {
    const claimMatch = rawText.match(
      /(?:希望|要求|诉求|想看看怎么|想要|请求)([^。；;\n]+)/,
    );
    if (claimMatch?.[1]) {
      nextClaim = claimMatch[1].replace(/^(能|可以)?/, "").trim();
    } else if (/赔偿|维修|退还|支付|要回欠款|本金|利息|归还|追回/.test(corpus)) {
      const actionMatch = corpus.match(
        /(履行维修[^。；，,]*|赔偿[^。；，,]*|要回[^。；，,]*|退还[^。；，,]*|支付[^。；，,]*|归还[^。；，,]*|追回[^。；，,]*)/,
      );
      if (actionMatch) nextClaim = actionMatch[1].trim();
    }
  }
  if (!nextClaim) pending.claim = true;

  let ourList = form.ourParties.map((x) => x.trim()).filter(Boolean);
  let oppList = form.opponentParties.map((x) => x.trim()).filter(Boolean);

  if (!ourList.length && rawText) {
    const ourMatch = rawText.match(
      /(?:我方|委托人|己方)(?:是|为|：|:)?([\u4e00-\u9fa5A-Za-z0-9]{2,18}(?:有限公司|公司|厂)|[\u4e00-\u9fa5]某)/,
    );
    if (ourMatch?.[1] && !/^[与和跟同因向借给]/.test(ourMatch[1])) {
      ourList = [ourMatch[1]];
    }
  }
  if (!oppList.length && rawText) {
    const oppLabelMatch = rawText.match(
      /(?:对方|被告|被申请人)(?:是|为|：|:)([\u4e00-\u9fa5A-Za-z0-9]{2,18}(?:有限公司|公司|厂)|[\u4e00-\u9fa5]某)/,
    );
    const oppOrgMatch = rawText.match(
      /(?:向|对|被)([\u4e00-\u9fa5A-Za-z0-9]{2,18}(?:物业服务有限公司|装饰工程有限公司|科技有限公司|有限公司|管理局|派出所))/,
    );
    const pickedOpp = oppLabelMatch?.[1] || oppOrgMatch?.[1] || "";
    if (
      pickedOpp &&
      !oppList.includes(pickedOpp) &&
      !ourList.includes(pickedOpp)
    ) {
      oppList = [pickedOpp];
    }
  }
  if (!ourList.length || !oppList.length) pending.parties = true;

  const baseRaw = form.rawSummary || rawText;
  const metaLines = [
    `• 案件类型：${nextType || "待确认"} ｜ 办理阶段：${nextStage || "待确认"}`,
    `• 核心诉求：${nextClaim || "待确认"}`,
  ];
  const metaSuffix = metaLines.join("\n");
  const maxBodyLen = Math.max(0, 2000 - metaSuffix.length - 1);
  let bodyLine = "";
  if (rawText) {
    const cleanRaw = rawText.replace(/^【案情摘要】/, "").split("\n")[0];
    bodyLine = `【案情摘要】${cleanRaw}`.slice(0, maxBodyLen);
  } else if (readyFiles.length) {
    const fileNames = readyFiles.map((x) => x.name).join("、");
    bodyLine = `已附首批材料 ${readyFiles.length} 份（${fileNames}），可补充案情文字描述或直接完善下方字段。`.slice(
      0,
      maxBodyLen,
    );
  }
  const summaryText = [bodyLine, ...metaLines]
    .filter(Boolean)
    .join("\n")
    .slice(0, 2000);

  form.rawSummary = baseRaw;
  form.summary = summaryText;
  form.title = nextTitle.slice(0, 200);
  form.caseType = nextType;
  form.stage = nextStage;
  form.claim = nextClaim.slice(0, 2000);
  form.ourParties = ourList.length ? ourList : [""];
  form.opponentParties = oppList.length ? oppList : [""];
  form.aiOrganized = true;
  form.step = "draft";
  form.pendingFields = pending;

  return pending;
}

/** 将前端建档草稿映射为后端 POST /cases 请求体 */
export function buildCaseCreatePayload(form: CaseDraftForm): CaseCreatePayload {
  const title = form.title.trim().slice(0, 200) || "未命名案件（待完善）";
  const case_type = CASE_TYPE_CODE_MAP[form.caseType] || "other";
  const procedure = CASE_PROCEDURE_CODE_MAP[form.stage] || "other";
  const summary = form.summary.trim().slice(0, 2000) || null;
  const claim = form.claim.trim().slice(0, 2000) || null;
  const handling_identity =
    form.handlingIdentity === "本人办理"
      ? "self"
      : form.handlingIdentity === "代理他人"
        ? "agent"
        : null;
  const party_role_label = form.partyRole.trim().slice(0, 80) || null;
  const our_parties = form.ourParties
    .map((x) => x.trim().slice(0, 200))
    .filter(Boolean)
    .slice(0, 5);
  const opponent_parties = form.opponentParties
    .map((x) => x.trim().slice(0, 200))
    .filter(Boolean)
    .slice(0, 5);

  return {
    title,
    case_type,
    procedure,
    summary,
    claim,
    handling_identity,
    party_role_label,
    our_parties,
    opponent_parties,
  };
}
