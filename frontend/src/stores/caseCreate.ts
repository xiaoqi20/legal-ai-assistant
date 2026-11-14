import { defineStore } from "pinia";
import { computed, reactive, ref } from "vue";
import {
  CASE_PROCEDURE_CODE_MAP,
  CASE_TYPE_CODE_MAP,
  CREATE_ROLE_OPTIONS,
  CREATE_STAGE_OPTIONS,
} from "@/constants/case";
import type {
  CaseDraftFile,
  CaseDraftForm,
  CaseSummary,
  DraftCaseType,
  DraftPendingFieldKey,
  HandlingIdentity,
} from "@/types/case";
import {
  buildOrganizedDraft,
  createEmptyDraftForm,
  hasDraftContent,
} from "@/utils/caseDraftOrganizer";

const LOCAL_CASES_STORAGE_KEY = "law_local_created_cases";

function loadStoredLocalCases(): CaseSummary[] {
  try {
    const raw = uni.getStorageSync(LOCAL_CASES_STORAGE_KEY);
    return Array.isArray(raw) ? (raw as CaseSummary[]) : [];
  } catch {
    return [];
  }
}

function saveStoredLocalCases(cases: CaseSummary[]) {
  try {
    uni.setStorageSync(LOCAL_CASES_STORAGE_KEY, cases);
  } catch {
    // 受限环境下忽略本地持久化失败，保留内存态
  }
}

export const useCaseCreateStore = defineStore("caseCreate", () => {
  const form = reactive<CaseDraftForm>(createEmptyDraftForm());
  const localCases = ref<CaseSummary[]>(loadStoredLocalCases());

  const hasDraft = computed(() => hasDraftContent(form));

  function clearDraft() {
    Object.assign(form, createEmptyDraftForm());
  }

  function applyPresetSummary(summary: string) {
    Object.assign(form, createEmptyDraftForm(), { summary });
  }

  function clearPendingField(field: DraftPendingFieldKey) {
    if (form.pendingFields[field]) {
      delete form.pendingFields[field];
    }
  }

  function setCaseType(nextType: DraftCaseType) {
    if (form.caseType !== nextType) {
      form.caseType = nextType;
      const validStages = CREATE_STAGE_OPTIONS[nextType] || [];
      if (!validStages.includes(form.stage)) form.stage = "";
      const validRoles = CREATE_ROLE_OPTIONS[nextType] || [];
      if (!validRoles.includes(form.partyRole)) form.partyRole = "";
    }
    clearPendingField("caseType");
  }

  function setStage(stage: string) {
    form.stage = stage;
    clearPendingField("stage");
  }

  function setHandlingIdentity(identity: HandlingIdentity) {
    form.handlingIdentity = identity;
  }

  function setPartyRole(role: string) {
    form.partyRole = role;
  }

  function appendFiles(files: CaseDraftFile[]) {
    for (const file of files) {
      if (form.files.length >= 5) break;
      form.files.push(file);
    }
  }

  function removeFile(index: number) {
    form.files.splice(index, 1);
  }

  function retryFile(index: number) {
    const target = form.files[index];
    if (target) target.status = "ready";
  }

  function addParty(side: "our" | "opponent") {
    const list = side === "our" ? form.ourParties : form.opponentParties;
    if (list.length < 5) list.push("");
  }

  function removeParty(side: "our" | "opponent", index: number) {
    const list = side === "our" ? form.ourParties : form.opponentParties;
    if (list.length > 1) list.splice(index, 1);
  }

  function updateParty(side: "our" | "opponent", index: number, value: string) {
    const list = side === "our" ? form.ourParties : form.opponentParties;
    list[index] = value;
    if (
      form.pendingFields.parties &&
      form.ourParties.some((x) => x.trim()) &&
      form.opponentParties.some((x) => x.trim())
    ) {
      delete form.pendingFields.parties;
    }
  }

  function restoreRawSummary() {
    if (!form.rawSummary) return false;
    form.summary = form.rawSummary;
    form.rawSummary = "";
    return true;
  }

  function organizeWithAi() {
    return buildOrganizedDraft(form);
  }

  function createLocalCase(): CaseSummary {
    const nowIso = new Date().toISOString();
    const minId = localCases.value.reduce(
      (min, item) => (item.id < min ? item.id : min),
      0,
    );
    const id = minId - 1;
    const readyFiles = form.files.filter((x) => x.status !== "failed");
    const hasText = Boolean(form.summary.trim() || form.claim.trim());
    const willAnalyze = readyFiles.length > 0 || hasText;
    const stageLabel = form.stage || "待确认";

    const created: CaseSummary = {
      id,
      title: form.title.trim() || "未命名案件（待完善）",
      case_type: CASE_TYPE_CODE_MAP[form.caseType] || "other",
      case_type_label: form.caseType || "待确认",
      procedure: CASE_PROCEDURE_CODE_MAP[stageLabel] || "other",
      procedure_label: stageLabel,
      analysis_status: willAnalyze ? "analyzing" : "not_analyzed",
      evidence_upload_status: readyFiles.length > 0 ? "partial" : "not_uploaded",
      evidence_label: readyFiles.length > 0 ? `已选 ${readyFiles.length} 份` : "未上传",
      win_rate: null,
      win_rate_updated_at: null,
      status: "active",
      created_at: nowIso,
      updated_at: nowIso,
      summary: form.summary.trim(),
      claim: form.claim.trim(),
      handling_identity: form.handlingIdentity,
      party_role: form.partyRole,
      our_parties: form.ourParties.map((x) => x.trim()).filter(Boolean),
      opponent_parties: form.opponentParties.map((x) => x.trim()).filter(Boolean),
      files: readyFiles.map((file) => ({ ...file })),
      is_local: true,
    };

    localCases.value.unshift(created);
    saveStoredLocalCases(localCases.value);
    clearDraft();
    return created;
  }

  function findLocalCase(id: number): CaseSummary | undefined {
    return localCases.value.find((item) => item.id === id);
  }

  return {
    form,
    localCases,
    hasDraft,
    clearDraft,
    applyPresetSummary,
    clearPendingField,
    setCaseType,
    setStage,
    setHandlingIdentity,
    setPartyRole,
    appendFiles,
    removeFile,
    retryFile,
    addParty,
    removeParty,
    updateParty,
    restoreRawSummary,
    organizeWithAi,
    createLocalCase,
    findLocalCase,
  };
});
