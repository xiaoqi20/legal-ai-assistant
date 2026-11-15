<script setup lang="ts">
import { onHide, onLoad, onShow, onUnload } from "@dcloudio/uni-app";
import { computed, ref } from "vue";
import ComposerBar from "@/components/ComposerBar.vue";
import PageNav from "@/components/PageNav.vue";
import WinRateDonut from "@/components/WinRateDonut.vue";
import {
  ANALYSIS_STATUS_META,
  EVIDENCE_STATUS_META,
  PROCEDURE_LABELS,
} from "@/constants/case";
import {
  fetchCase,
  fetchWinRateDetail,
  triggerCaseAnalysis,
} from "@/services/caseContent";
import { USE_MOCK } from "@/services/request";
import { useCaseCreateStore } from "@/stores/caseCreate";
import type { CaseSummary, WinRateBreakdown, WinRateStatus } from "@/types/case";

const caseCreate = useCaseCreateStore();
const caseId = ref(1);
const detail = ref<CaseSummary | null>(null);
const winRateDetail = ref<WinRateBreakdown | null>(null);
const loading = ref(true);
const evaluatingWinRate = ref(false);
const showWinRateModal = ref(false);
const draft = ref("");
let pollTimer: ReturnType<typeof setInterval> | null = null;
let pollAttempts = 0;

const status = computed(() =>
  detail.value ? ANALYSIS_STATUS_META[detail.value.analysis_status] : null,
);
const evidence = computed(() => {
  if (!detail.value) return null;
  const base = EVIDENCE_STATUS_META[detail.value.evidence_upload_status];
  if (detail.value.evidence_label) {
    return { ...base, label: detail.value.evidence_label };
  }
  return base;
});
const procedure = computed(() =>
  detail.value
    ? detail.value.procedure_label ||
      PROCEDURE_LABELS[detail.value.procedure] ||
      "其他"
    : "",
);
const effectiveWinRateStatus = computed<WinRateStatus>(() => {
  if (!detail.value) return "not_analyzed";
  return detail.value.win_rate_status ?? detail.value.analysis_status;
});
const formattedWinRateTime = computed(() => {
  const raw = detail.value?.win_rate_updated_at;
  if (!raw) return "";
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
});
const activeDefeaters = computed(() =>
  (winRateDetail.value?.defeaters ?? []).filter((d) => d.presence !== "absent"),
);
const canShowBreakdown = computed(
  () =>
    effectiveWinRateStatus.value === "analyzed" ||
    effectiveWinRateStatus.value === "not_applicable" ||
    detail.value?.win_rate_analysis_id != null ||
    winRateDetail.value != null,
);
const winRateActionLabel = computed(() => {
  const s = effectiveWinRateStatus.value;
  if (evaluatingWinRate.value || s === "analyzing") return "测算中…";
  if (s === "analyzed" || s === "not_applicable") return "重新评估";
  return "AI 评估胜诉率";
});
const winRateHint = computed(() => {
  const s = effectiveWinRateStatus.value;
  if (s === "analyzed") {
    const label = winRateDetail.value?.metric_label || "AI 要件支撑度预估（未经判例校准）";
    return formattedWinRateTime.value ? `${label} · ${formattedWinRateTime.value}` : label;
  }
  if (s === "not_applicable") {
    return winRateDetail.value?.reason_message || "当前案件暂不适用胜诉率测算";
  }
  if (s === "analyzing") return "正在基于材料与法定要件进行结构化测算…";
  if (s === "failed") return "上次测算失败，可检查材料后重新评估";
  return "基于诉讼请求与已解析证据进行法定要件支撑度测算";
});

const tools = [
  { key: "materials", title: "材料与律师复核", desc: "新增材料、提交及查看复核", icon: "/static/images/icons/evidence.png" },
  { key: "drafts", title: "法律文书草稿", desc: "生成、编辑和导出文书", icon: "/static/images/icons/documents.png" },
  {
    key: "chain",
    title: "AI证据链分析",
    desc: "查看证据链分析结果",
    icon: "/static/images/icons/evidence-chain.png",
  },
  {
    key: "analysis",
    title: "AI案情梳理",
    desc: "智能分析案情脉络",
    icon: "/static/images/icons/analysis.png",
  },
  {
    key: "docs",
    title: "案件文档归类",
    desc: "分类管理案件文档",
    icon: "/static/images/icons/documents.png",
  },
  {
    key: "evidence",
    title: "证据分析",
    desc: "分析原被告争议焦点",
    icon: "/static/images/icons/evidence.png",
  },
];

function stopPoll() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
  pollAttempts = 0;
}

function startPoll() {
  if (USE_MOCK || pollTimer) return;
  pollAttempts = 0;
  pollTimer = setInterval(() => {
    pollAttempts += 1;
    if (pollAttempts > 30) {
      stopPoll();
      return;
    }
    void refreshSilent();
  }, 2000);
}

async function loadWinRateBreakdown() {
  if (!detail.value || detail.value.is_local) return;
  const st = detail.value.win_rate_status ?? detail.value.analysis_status;
  if (st !== "analyzed" && st !== "not_applicable" && !detail.value.win_rate_analysis_id) {
    winRateDetail.value = null;
    return;
  }
  try {
    winRateDetail.value = await fetchWinRateDetail(caseId.value, detail.value.win_rate_analysis_id);
  } catch {
    // Breakdown stays optional if detail fetch temporarily fails.
  }
}

async function refreshSilent() {
  try {
    const fresh = await fetchCase(caseId.value);
    detail.value = fresh;
    if (fresh.win_rate_status !== "analyzing") {
      stopPoll();
      await loadWinRateBreakdown();
    }
  } catch {
    // Keep polling quietly until limit.
  }
}

async function load() {
  loading.value = true;
  try {
    const localFound = USE_MOCK
      ? caseCreate.findLocalCase(caseId.value)
      : undefined;
    detail.value = localFound ?? (await fetchCase(caseId.value));
    await loadWinRateBreakdown();
    if (!USE_MOCK && detail.value?.win_rate_status === "analyzing") {
      startPoll();
    } else {
      stopPoll();
    }
  } catch {
    uni.showToast({ title: "案件加载失败", icon: "none" });
  } finally {
    loading.value = false;
  }
}

async function evaluateWinRate() {
  if (!detail.value) return;
  if (detail.value.is_local) {
    uni.showToast({ title: "本地新建案件暂未同步服务端测算", icon: "none" });
    return;
  }
  if (USE_MOCK) {
    await loadWinRateBreakdown();
    if (winRateDetail.value) {
      showWinRateModal.value = true;
    } else {
      uni.showToast({ title: "演示模式下仅案件 #1 含示例依据", icon: "none" });
    }
    return;
  }
  if (evaluatingWinRate.value || effectiveWinRateStatus.value === "analyzing") {
    uni.showToast({ title: "胜诉率正在测算中，请稍候", icon: "none" });
    return;
  }
  evaluatingWinRate.value = true;
  try {
    await triggerCaseAnalysis(caseId.value, "win_rate");
    detail.value = {
      ...detail.value,
      win_rate_status: "analyzing",
    };
    winRateDetail.value = null;
    startPoll();
  } catch (err) {
    const msg = err instanceof Error ? err.message : "发起胜诉率测算失败";
    uni.showToast({ title: msg, icon: "none" });
  } finally {
    evaluatingWinRate.value = false;
  }
}

async function openWinRateModal() {
  if (!winRateDetail.value && detail.value && !detail.value.is_local) {
    await loadWinRateBreakdown();
  }
  if (!winRateDetail.value) {
    uni.showToast({ title: "暂无测算详情，请先点击评估", icon: "none" });
    return;
  }
  showWinRateModal.value = true;
}

onLoad((options) => {
  caseId.value = Number(options?.id || 1);
});
onShow(() => { void load(); });
onHide(() => { stopPoll(); });
onUnload(() => { stopPoll(); });

function openTool(key: string) {
  if (detail.value?.is_local) {
    uni.showToast({
      title: "本地新建案件暂未同步服务端分析",
      icon: "none",
    });
    return;
  }
  const id = caseId.value;
  const routes: Record<string, string> = {
    materials: `/pages/case/materials?id=${id}`,
    drafts: `/pages/case/drafts?id=${id}`,
    chain: `/pages/case/evidence?id=${id}`,
    analysis: `/pages/case/analysis?id=${id}`,
    docs: `/pages/case/documents?id=${id}`,
    evidence: `/pages/case/evidence-sort?id=${id}`,
  };
  uni.navigateTo({ url: routes[key] });
}

function send() {
  const question = draft.value.trim();
  if (!question) return;
  draft.value = "";
  uni.navigateTo({
    url: `/pages/chat/index?mode=case&caseId=${caseId.value}&q=${encodeURIComponent(question)}`,
  });
}

function openMic() {
  uni.showToast({ title: "语音待接入", icon: "none" });
}
</script>

<template>
  <view class="page-shell">
    <PageNav title="案件详情" />
    <scroll-view scroll-y class="page-scroll">
      <view v-if="loading" class="state">加载中…</view>

      <view v-else-if="detail" class="content">
        <view class="detail-card surface-card">
          <view v-if="status" class="status-pill" :class="`status-pill--${status.tone}`">
            {{ status.label }}
          </view>
          <text class="case-title">{{ detail.title }}</text>
          <view class="donut-wrap">
            <WinRateDonut
              large
              :status="detail.analysis_status"
              :win-rate-status="detail.win_rate_status"
              :win-rate="detail.win_rate"
            />
          </view>
          <view v-if="!detail.is_local" class="win-rate-actions">
            <view class="wr-btn-row">
              <button
                class="wr-btn"
                :class="{ 'wr-btn--disabled': evaluatingWinRate || effectiveWinRateStatus === 'analyzing' }"
                @click="evaluateWinRate"
              >
                {{ winRateActionLabel }}
              </button>
              <button
                v-if="canShowBreakdown"
                class="wr-btn wr-btn--ghost"
                @click="openWinRateModal"
              >
                查看测算依据
              </button>
            </view>
            <text class="wr-hint">{{ winRateHint }}</text>
          </view>
          <view class="metrics">
            <view class="metric">
              <text class="metric-label">证据上传</text>
              <text
                class="metric-value"
                :class="{ 'metric-value--danger': !evidence?.complete }"
              >
                {{ evidence?.label }}
              </text>
            </view>
            <view class="metric">
              <text class="metric-label">案件程序</text>
              <text class="metric-value">{{ procedure }}</text>
            </view>
            <view class="metric">
              <text class="metric-label">证据分析</text>
              <text
                class="metric-value"
                :class="{
                  'metric-value--green': detail.analysis_status === 'analyzed',
                  'metric-value--danger': detail.analysis_status === 'failed',
                }"
              >
                {{ status?.label }}
              </text>
            </view>
          </view>
        </view>

        <text class="section-title">查看案件分析结果</text>
        <view class="tools">
          <view
            v-for="tool in tools"
            :key="tool.key"
            class="tool surface-card"
            @click="openTool(tool.key)"
          >
            <view class="tool-icon">
              <image :src="tool.icon" class="tool-img" mode="aspectFit" />
            </view>
            <view class="tool-copy">
              <text class="tool-title">{{ tool.title }}</text>
              <text class="tool-desc">{{ tool.desc }}</text>
            </view>
          </view>
        </view>
        <view class="tail" />
      </view>
    </scroll-view>

    <ComposerBar
      v-model="draft"
      placeholder="关于案件，有什么想要咨询的？"
      @send="send"
      @toggle-attach="openMic"
      @mic="openMic"
    />

    <view
      v-if="showWinRateModal && winRateDetail"
      class="wr-overlay"
      @click="showWinRateModal = false"
    >
      <view class="wr-modal" @click.stop>
        <view class="wr-head">
          <text class="wr-head-title">胜诉率测算依据</text>
          <text class="wr-head-close" @click="showWinRateModal = false">✕</text>
        </view>
        <scroll-view scroll-y class="wr-scroll">
          <view class="wr-summary">
            <view class="wr-summary-top">
              <text class="wr-badge">{{ winRateDetail.metric_label }}</text>
              <text v-if="winRateDetail.cause_label" class="wr-meta">
                {{ winRateDetail.cause_label }}
                {{ winRateDetail.stance === 'defendant_side' ? '· 被告/被申请人方' : winRateDetail.stance === 'plaintiff_side' ? '· 原告/申请人方' : '' }}
              </text>
            </view>
            <text v-if="winRateDetail.applicable && winRateDetail.win_rate != null" class="wr-score">
              {{ winRateDetail.win_rate }}%
            </text>
            <text v-else class="wr-unapplicable">
              暂不适用：{{ winRateDetail.reason_message }}
            </text>
          </view>

          <view v-if="winRateDetail.claims.length" class="wr-sec">
            <text class="wr-sec-title">诉求分项</text>
            <view v-for="c in winRateDetail.claims" :key="c.index" class="wr-item">
              <view class="wr-item-head">
                <text class="wr-item-title">{{ c.title }}</text>
                <text class="wr-tag wr-tag--blue">{{ c.support_score }}%（权重 {{ Math.round(c.weight * 100) }}%）</text>
              </view>
            </view>
          </view>

          <view v-if="winRateDetail.elements.length" class="wr-sec">
            <text class="wr-sec-title">法定证明要件核验</text>
            <view v-for="el in winRateDetail.elements" :key="`${el.key}-${el.scope_claim_index ?? 'all'}`" class="wr-item">
              <view class="wr-item-head">
                <text class="wr-item-title">{{ el.label }}</text>
                <text
                  class="wr-tag"
                  :class="{
                    'wr-tag--green': el.grade === 'proven',
                    'wr-tag--blue': el.grade === 'corroborated',
                    'wr-tag--warn': el.grade === 'weak',
                    'wr-tag--danger': el.grade === 'missing' || el.grade === 'rebutted',
                  }"
                >
                  {{ el.grade_label }}
                </text>
              </view>
              <text class="wr-item-desc">{{ el.summary }}</text>
            </view>
          </view>

          <view v-if="activeDefeaters.length" class="wr-sec">
            <text class="wr-sec-title">抗辩与阻却风险</text>
            <view v-for="df in activeDefeaters" :key="df.key" class="wr-item">
              <view class="wr-item-head">
                <text class="wr-item-title">{{ df.label }}</text>
                <text class="wr-tag wr-tag--danger">
                  {{ df.presence === 'confirmed' ? '明确风险' : '疑似风险' }}
                </text>
              </view>
              <text class="wr-item-desc">{{ df.summary }}</text>
            </view>
          </view>

          <view v-if="winRateDetail.positive_factors.length" class="wr-sec">
            <text class="wr-sec-title">有利支撑要素</text>
            <text v-for="(item, idx) in winRateDetail.positive_factors" :key="`p-${idx}`" class="wr-bullet">· {{ item }}</text>
          </view>

          <view v-if="winRateDetail.negative_factors.length" class="wr-sec">
            <text class="wr-sec-title">不利与风险要素</text>
            <text v-for="(item, idx) in winRateDetail.negative_factors" :key="`n-${idx}`" class="wr-bullet">· {{ item }}</text>
          </view>

          <view v-if="winRateDetail.missing_evidence.length" class="wr-sec">
            <text class="wr-sec-title">待补强缺失证据</text>
            <text v-for="(item, idx) in winRateDetail.missing_evidence" :key="`m-${idx}`" class="wr-bullet">· {{ item }}</text>
          </view>

          <view v-if="winRateDetail.precedent_reference" class="wr-sec">
            <text class="wr-sec-title">同类判例结构参照（不影响当前未校准分值）</text>
            <view class="wr-item">
              <view class="wr-item-head">
                <text class="wr-item-title">
                  匹配 Top-{{ winRateDetail.precedent_reference.matched_count }} / {{ winRateDetail.precedent_reference.pool_count }} 案
                </text>
                <text class="wr-tag wr-tag--blue">
                  结构相似度 {{ winRateDetail.precedent_reference.similarity_avg }}%
                </text>
              </view>
              <text class="wr-item-desc">
                相似判例结果分布：全部支持 {{ winRateDetail.precedent_reference.outcome_counts.fully_supported }} 案 · 部分支持 {{ winRateDetail.precedent_reference.outcome_counts.partially_supported }} 案 · 驳回 {{ winRateDetail.precedent_reference.outcome_counts.dismissed }} 案（核心本金获支持率 {{ winRateDetail.precedent_reference.principal_support_rate }}%）
              </text>
              <text v-if="winRateDetail.precedent_reference.common_risk_factors.length" class="wr-item-desc">
                类案高频风险：{{ winRateDetail.precedent_reference.common_risk_factors.map((f) => `${f.label}(${f.count}案)`).join("、") }}
              </text>
              <text class="wr-item-desc">{{ winRateDetail.precedent_reference.perspective_note }}</text>
              <text class="wr-item-desc">{{ winRateDetail.precedent_reference.caveat }}</text>
            </view>
          </view>

          <view class="wr-disclaimer">
            <text v-if="winRateDetail.limitations" class="wr-limit">测算范围：{{ winRateDetail.limitations }}</text>
            <text class="wr-disc-text">{{ winRateDetail.disclaimer }}</text>
          </view>
        </scroll-view>
      </view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.state {
  padding: 120rpx 0;
  text-align: center;
  color: $muted;
  font-size: 26rpx;
}

.content {
  padding: 8rpx 36rpx 0;
}

.detail-card {
  position: relative;
  padding: 40rpx 36rpx 32rpx;
  overflow: hidden;
}

.status-pill {
  position: absolute;
  top: 0;
  right: 0;
  height: 44rpx;
  padding: 0 24rpx;
  border-radius: 24rpx 0 0 24rpx;
  display: flex;
  align-items: center;
  color: #fff;
  font-size: 24rpx;
}

.status-pill--green {
  background: $success;
}

.status-pill--pink {
  background: $pink;
}

.status-pill--lavender {
  background: $lavender;
}

.status-pill--red {
  background: #f08a8a;
}

.case-title {
  display: block;
  padding-right: 100rpx;
  font-size: 34rpx;
  font-weight: 700;
  line-height: 1.45;
  color: #333;
}

.donut-wrap {
  display: flex;
  justify-content: center;
  padding: 38rpx 0 30rpx;
}

.metrics {
  display: flex;
  justify-content: space-around;
  border-top: 1rpx solid $line;
  padding-top: 26rpx;
}

.metric {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.metric-label {
  font-size: 22rpx;
  color: $muted;
}

.metric-value {
  margin-top: 8rpx;
  font-size: 26rpx;
  color: $brand;
}

.metric-value--danger {
  color: #f05b5b;
}

.metric-value--green {
  color: #57c777;
}

.section-title {
  display: block;
  margin: 34rpx 0 20rpx;
  font-size: 30rpx;
  font-weight: 700;
  color: #333;
}

.tools {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
}

.tool {
  width: 48.5%;
  margin-bottom: 16rpx;
  padding: 28rpx 24rpx;
  display: flex;
  flex-direction: column;
}

.tool-icon {
  width: 72rpx;
  height: 72rpx;
  border-radius: 20rpx;
  background: $brand-soft;
  display: flex;
  align-items: center;
  justify-content: center;
}

.tool-img {
  width: 42rpx;
  height: 42rpx;
}

.tool-title {
  display: block;
  margin-top: 18rpx;
  font-size: 28rpx;
  font-weight: 700;
  color: #333;
}

.tool-desc {
  display: block;
  margin-top: 6rpx;
  font-size: 22rpx;
  line-height: 1.4;
  color: $muted;
}

.tail {
  height: 40rpx;
}

.win-rate-actions {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-bottom: 24rpx;
}

.wr-btn-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16rpx;
}

.wr-btn {
  margin: 0;
  padding: 0 28rpx;
  height: 60rpx;
  line-height: 60rpx;
  border-radius: 30rpx;
  background: $brand;
  color: #fff;
  font-size: 24rpx;
  font-weight: 600;
  border: none;
}

.wr-btn::after {
  border: none;
}

.wr-btn--ghost {
  background: $brand-soft;
  color: $brand;
}

.wr-btn--disabled {
  background: #d5e0f7;
  color: #fff;
}

.wr-hint {
  margin-top: 12rpx;
  padding: 0 12rpx;
  text-align: center;
  font-size: 21rpx;
  line-height: 1.45;
  color: $muted;
}

.wr-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  z-index: 90;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}

.wr-modal {
  width: 100%;
  max-height: 82vh;
  background: #fff;
  border-radius: 28rpx 28rpx 0 0;
  padding: 28rpx 32rpx 36rpx;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
}

.wr-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 20rpx;
  border-bottom: 1rpx solid $line;
}

.wr-head-title {
  font-size: 32rpx;
  font-weight: 700;
  color: #222;
}

.wr-head-close {
  padding: 6rpx 12rpx;
  font-size: 30rpx;
  color: $muted;
}

.wr-scroll {
  max-height: 68vh;
  padding-top: 20rpx;
}

.wr-summary {
  padding: 22rpx 24rpx;
  border-radius: 18rpx;
  background: $brand-soft;
  margin-bottom: 20rpx;
}

.wr-summary-top {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12rpx;
}

.wr-badge {
  font-size: 22rpx;
  font-weight: 600;
  color: $brand;
}

.wr-meta {
  font-size: 22rpx;
  color: $text-secondary;
}

.wr-score {
  display: block;
  margin-top: 10rpx;
  font-size: 48rpx;
  font-weight: 700;
  color: $brand;
}

.wr-unapplicable {
  display: block;
  margin-top: 10rpx;
  font-size: 25rpx;
  line-height: 1.5;
  color: #b45309;
}

.wr-sec {
  margin-bottom: 22rpx;
}

.wr-sec-title {
  display: block;
  margin-bottom: 12rpx;
  font-size: 26rpx;
  font-weight: 700;
  color: #222;
}

.wr-item {
  padding: 16rpx 18rpx;
  border-radius: 14rpx;
  background: #f8faff;
  margin-bottom: 12rpx;
}

.wr-item-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12rpx;
}

.wr-item-title {
  font-size: 25rpx;
  font-weight: 600;
  color: #222;
  flex: 1;
}

.wr-item-desc {
  display: block;
  margin-top: 8rpx;
  font-size: 23rpx;
  line-height: 1.5;
  color: $text-secondary;
}

.wr-tag {
  flex: none;
  padding: 4rpx 14rpx;
  border-radius: 20rpx;
  font-size: 20rpx;
  font-weight: 600;
}

.wr-tag--green {
  background: #e6f7ec;
  color: #15803d;
}

.wr-tag--blue {
  background: #e7f0ff;
  color: $brand;
}

.wr-tag--warn {
  background: #fef3c7;
  color: #b45309;
}

.wr-tag--danger {
  background: #fee2e2;
  color: #b91c1c;
}

.wr-bullet {
  display: block;
  margin-bottom: 8rpx;
  font-size: 24rpx;
  line-height: 1.5;
  color: $text-secondary;
}

.wr-disclaimer {
  margin-top: 12rpx;
  padding: 18rpx 20rpx;
  border-radius: 14rpx;
  background: #f5f7fb;
}

.wr-limit {
  display: block;
  margin-bottom: 8rpx;
  font-size: 22rpx;
  line-height: 1.5;
  color: $text-secondary;
}

.wr-disc-text {
  display: block;
  font-size: 21rpx;
  line-height: 1.5;
  color: $muted;
}
</style>
