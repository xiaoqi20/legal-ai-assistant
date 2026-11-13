<script setup lang="ts">
import { onLoad, onUnload } from "@dcloudio/uni-app";
import { computed, ref } from "vue";
import FloatingReturn from "./components/FloatingReturn.vue";
import PageNav from "@/components/PageNav.vue";
import SearchInput from "@/components/SearchInput.vue";
import {
  cancelCaseAnalysis,
  fetchAnalysisBundle,
  fetchCaseAnalysisRecord,
  triggerCaseAnalysis,
  type AnalysisPanelType,
} from "@/services/caseContent";
import { USE_MOCK } from "@/services/request";
import type { AnalysisData, CaseAnalysisRecord } from "@/types/case";

const caseId = ref(1);
const data = ref<AnalysisData | null>(null);
const records = ref<Record<AnalysisPanelType, CaseAnalysisRecord | null>>({
  case_summary: null,
  timeline: null,
  judicial_reasoning: null,
  dispute_focus: null,
});
const loading = ref(true);
const triggering = ref(false);
const keyword = ref("");
let pollTimer: ReturnType<typeof setTimeout> | null = null;
let disposed = false;

const mainTabs = ["事实分析", "法律分析", "定争分析"];
const subTabs = ["案情摘要", "案情时间轴", "司法推理", "争议焦点"];
const mainTab = ref(mainTabs[0]);
const subTab = ref(subTabs[0]);

const mode = computed(() => {
  if (mainTab.value === "定争分析") return "disputes";
  if (mainTab.value === "法律分析") return "laws";
  if (subTab.value === "案情时间轴") return "timeline";
  if (subTab.value === "司法推理") return "reasoning";
  if (subTab.value === "争议焦点") return "disputes";
  return "summary";
});

const activePanelType = computed<AnalysisPanelType>(() => {
  if (mode.value === "timeline") return "timeline";
  if (mode.value === "reasoning") return "judicial_reasoning";
  if (mode.value === "disputes" || mode.value === "laws") {
    return "dispute_focus";
  }
  return "case_summary";
});

const activeRecord = computed(() => records.value[activePanelType.value]);

const needsGeneration = computed(() => {
  if (USE_MOCK) return false;
  const rec = activeRecord.value;
  return !rec || rec.status !== "succeeded";
});

const isRunning = computed(() => {
  const status = activeRecord.value?.status;
  return status === "pending" || status === "running";
});

const sectionTitle = computed(() => {
  const titles: Record<string, string> = {
    summary: "案情摘要",
    timeline: "案情时间轴",
    reasoning: "司法推理",
    laws: "法律分析",
    disputes: "争议焦点",
  };
  return titles[mode.value] ?? "案情摘要";
});

const factLabels = ["事实一", "事实二", "事实三", "事实四", "事实五"];

function clearPoll() {
  if (pollTimer) {
    clearTimeout(pollTimer);
    pollTimer = null;
  }
}

onUnload(() => {
  disposed = true;
  clearPoll();
});

onLoad((options) => {
  caseId.value = Number(options?.id || 1);
  void load();
});

function schedulePollIfRunning() {
  clearPoll();
  if (disposed || USE_MOCK) return;
  const runningItem = Object.values(records.value).find(
    (item) => item && (item.status === "pending" || item.status === "running"),
  );
  if (!runningItem) return;

  pollTimer = setTimeout(async () => {
    try {
      const updated = await fetchCaseAnalysisRecord(
        caseId.value,
        runningItem.id,
      );
      if (updated.status === "succeeded") {
        await load();
        return;
      }
      records.value = {
        ...records.value,
        [updated.analysis_type as AnalysisPanelType]: updated,
      };
      if (updated.status === "pending" || updated.status === "running") {
        schedulePollIfRunning();
      }
    } catch {
      // stop polling silently on transient disconnect
    }
  }, 1500);
}

async function load() {
  loading.value = true;
  try {
    const bundle = await fetchAnalysisBundle(caseId.value);
    data.value = bundle.data;
    records.value = bundle.records;
    schedulePollIfRunning();
  } catch (error) {
    const msg = error instanceof Error ? error.message : "加载案情梳理失败";
    uni.showToast({ title: msg, icon: "none" });
  } finally {
    loading.value = false;
  }
}

async function startGeneration() {
  if (USE_MOCK || triggering.value || isRunning.value) return;
  triggering.value = true;
  const panelType = activePanelType.value;
  try {
    const res = await triggerCaseAnalysis(caseId.value, panelType);
    const rec = await fetchCaseAnalysisRecord(caseId.value, res.analysis_id);
    records.value = {
      ...records.value,
      [panelType]: rec,
    };
    if (rec.status === "succeeded") {
      await load();
    } else {
      schedulePollIfRunning();
    }
  } catch (error) {
    const msg = error instanceof Error ? error.message : "发起分析失败";
    uni.showToast({ title: msg, icon: "none" });
  } finally {
    triggering.value = false;
  }
}

async function cancelGeneration() {
  const rec = activeRecord.value;
  if (!rec) return;
  try {
    await cancelCaseAnalysis(caseId.value, rec.id);
    clearPoll();
    await load();
  } catch (error) {
    const msg = error instanceof Error ? error.message : "取消失败";
    uni.showToast({ title: msg, icon: "none" });
  }
}

function searchAnalysis() {
  const q = keyword.value.trim();
  if (!q) return;

  if (q.includes("时间")) {
    mainTab.value = "事实分析";
    subTab.value = "案情时间轴";
  } else if (q.includes("摘要") || q.includes("事实")) {
    mainTab.value = "事实分析";
    subTab.value = "案情摘要";
  } else if (q.includes("推理")) {
    mainTab.value = "事实分析";
    subTab.value = "司法推理";
  } else if (q.includes("争议")) {
    mainTab.value = "事实分析";
    subTab.value = "争议焦点";
  } else if (q.includes("法律") || q.includes("法条")) {
    mainTab.value = "法律分析";
  } else {
    uni.showToast({ title: "未找到相关内容", icon: "none" });
  }
}
</script>

<template>
  <view class="page-shell analysis-page">
    <PageNav title="案情梳理" />

    <SearchInput
      v-model="keyword"
      placeholder="请输入搜索内容"
      tone="gray"
      @search="searchAnalysis"
    />

    <view class="analysis-tabs">
      <view
        v-for="tab in mainTabs"
        :key="tab"
        class="analysis-tab"
        :class="{ 'analysis-tab--active': mainTab === tab }"
        @click="mainTab = tab"
      >
        <text>{{ tab }}</text>
        <view v-if="mainTab === tab" class="analysis-tab-bar" />
      </view>
    </view>

    <scroll-view
      scroll-y
      class="page-scroll analysis-body"
      :show-scrollbar="false"
    >
      <scroll-view
        v-if="mainTab === '事实分析'"
        scroll-x
        class="chips"
        :show-scrollbar="false"
      >
        <view class="chips-inner">
          <view
            v-for="tab in subTabs"
            :key="tab"
            class="chip"
            :class="{ 'chip--active': subTab === tab }"
            @click="subTab = tab"
          >
            {{ tab }}
          </view>
        </view>
      </scroll-view>

      <view v-if="loading" class="state">加载中…</view>

      <view v-else-if="needsGeneration" class="analysis-section">
        <view class="analysis-section-title">
          <view class="title-bar" />
          <text>{{ sectionTitle }}</text>
        </view>
        <view class="sum-card action-card">
          <text class="action-hint">
            {{
              isRunning
                ? "AI 正在结合案件文档生成本项分析，请稍候…"
                : activeRecord?.status === "failed"
                  ? `上次分析未完成（${activeRecord.error_message || "请重试"}）`
                  : "当前维度尚未生成 AI 分析，请确保已上传并解析案件文档。"
            }}
          </text>
          <view
            v-if="isRunning"
            class="action-btn action-btn--ghost"
            @click="cancelGeneration"
          >
            取消分析
          </view>
          <view v-else class="action-btn" @click="startGeneration">
            {{ triggering ? "提交中..." : "生成 AI 分析" }}
          </view>
        </view>
      </view>

      <view v-else-if="data" class="analysis-section">
        <view class="analysis-section-title">
          <view class="title-bar" />
          <text>{{ sectionTitle }}</text>
        </view>

        <template v-if="mode === 'summary'">
          <view class="sum-card">
            <view class="sum-pill">当事人</view>
            <view
              v-for="party in data.summary.parties"
              :key="party.label"
              class="sum-row"
            >
              <text class="sum-label">{{ party.label }}：</text>
              <text>{{ party.value }}</text>
            </view>
          </view>

          <view class="sum-card">
            <view class="sum-pill">事实详情</view>
            <view
              v-for="(fact, index) in data.summary.facts"
              :key="index"
              class="bullet-line"
            >
              <view class="dot" />
              <text class="bullet-text">
                <text class="bullet-bold">{{ factLabels[index] || `事实${index + 1}` }}：</text>{{ fact }}
              </text>
            </view>
          </view>

          <view class="sum-card">
            <view class="sum-pill">当事人请求</view>
            <view
              v-for="(request, index) in data.summary.requests"
              :key="index"
              class="bullet-line"
            >
              <view class="dot" />
              <text class="bullet-text">{{ request }}</text>
            </view>
          </view>
        </template>

        <template v-else-if="mode === 'timeline'">
          <view
            v-for="(event, index) in data.timeline"
            :key="index"
            class="timeline-card"
          >
            <view class="timeline-head">
              <view class="timeline-num">{{ String(index + 1).padStart(2, "0") }}</view>
              <text class="timeline-date">{{ event.date }}</text>
            </view>
            <view class="timeline-body">
              <view class="bullet-line bullet-line--tight">
                <view class="dot" />
                <text class="bullet-text">{{ event.title }}</text>
              </view>
              <view class="bullet-line bullet-line--tight">
                <view class="dot" />
                <text class="bullet-text">{{ event.detail }}</text>
              </view>
            </view>
          </view>
        </template>

        <template v-else-if="mode === 'reasoning'">
          <view
            v-for="(item, index) in data.reasoning"
            :key="index"
            class="reason-box"
          >
            <text class="reason-title">{{ item.title }}</text>
            <text class="reason-text">{{ item.premise }}{{ item.conclusion }}</text>
          </view>
        </template>

        <template v-else-if="mode === 'laws'">
          <view
            v-for="law in data.laws"
            :key="law.name"
            class="reason-box"
          >
            <text class="reason-title">{{ law.name }}</text>
            <text class="reason-text">{{ law.content }}</text>
          </view>
        </template>

        <template v-else>
          <view
            v-for="group in data.disputes"
            :key="group.party"
            class="dispute-item"
          >
            <text class="dispute-party">{{ group.party }}：</text>
            <view
              v-for="(point, index) in group.points"
              :key="index"
              class="bullet-line bullet-line--tight"
            >
              <view class="dot" />
              <text class="bullet-text">{{ point }}</text>
            </view>
          </view>
        </template>
      </view>

      <view class="tail" />
    </scroll-view>

    <FloatingReturn :case-id="caseId" />
  </view>
</template>

<style lang="scss" scoped>
.analysis-page {
  background: #fff;
}

.action-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 20rpx;
}

.action-hint {
  font-size: 26rpx;
  line-height: 1.7;
  color: $text-secondary;
}

.action-btn {
  height: 68rpx;
  padding: 0 32rpx;
  border-radius: 34rpx;
  background: $brand;
  color: #fff;
  font-size: 26rpx;
  font-weight: 500;
  display: flex;
  align-items: center;
  justify-content: center;
}

.action-btn--ghost {
  background: #f1f4fb;
  color: $brand;
}

.analysis-tabs {
  flex: none;
  display: flex;
  margin-top: 8rpx;
  background: #fff;
  border-bottom: 2rpx solid #f1f2f5;
}

.analysis-tab {
  position: relative;
  flex: 1;
  padding: 26rpx 0 24rpx;
  text-align: center;
  font-size: 30rpx;
  color: #333;
}

.analysis-tab--active {
  color: $brand;
  font-weight: 600;
}

.analysis-tab-bar {
  position: absolute;
  left: 50%;
  bottom: 0;
  width: 76rpx;
  height: 6rpx;
  border-radius: 4rpx;
  background: $brand;
  transform: translateX(-50%);
}

.analysis-body {
  padding-top: 4rpx;
}

.chips {
  width: 100%;
  white-space: nowrap;
  padding: 16rpx 0;
}

.chips-inner {
  display: inline-flex;
  padding: 0 36rpx;
}

.chip {
  flex: none;
  height: 68rpx;
  margin-right: 20rpx;
  padding: 0 36rpx;
  border: 2rpx solid #dadde4;
  border-radius: 36rpx;
  background: #fff;
  color: #8a8f99;
  font-size: 26rpx;
  display: flex;
  align-items: center;
}

.chip--active {
  border-color: transparent;
  background: $brand-soft;
  color: $brand;
  font-weight: 500;
}

.analysis-section {
  margin: 28rpx 24rpx 48rpx;
  padding: 28rpx 20rpx 36rpx;
  border-radius: 24rpx;
  background: #f1f6ff;
}

.analysis-section-title {
  display: flex;
  align-items: center;
  margin: 4rpx 12rpx 24rpx;
  font-size: 30rpx;
  font-weight: 600;
  color: #333;
}

.title-bar {
  width: 8rpx;
  height: 32rpx;
  margin-right: 16rpx;
  border-radius: 4rpx;
  background: $brand;
}

.sum-card {
  margin-bottom: 24rpx;
  padding: 32rpx 28rpx;
  border-radius: 20rpx;
  background: #fff;
  box-shadow: 0 4rpx 16rpx rgba(60, 90, 150, 0.03);

  &:last-child {
    margin-bottom: 0;
  }
}

.sum-pill {
  width: max-content;
  margin: 0 auto 28rpx;
  padding: 8rpx 36rpx;
  border-radius: 20rpx;
  background: linear-gradient(90deg, #b9cdff, #8fa8ff);
  color: #fff;
  font-size: 28rpx;
  font-weight: 600;
  letter-spacing: 2rpx;
}

.sum-row {
  display: flex;
  justify-content: center;
  margin: 20rpx 0;
  font-size: 28rpx;
  line-height: 1.5;
  color: #555;
}

.sum-label {
  font-weight: 600;
  color: #444;
}

.bullet-line {
  display: flex;
  align-items: flex-start;
  margin: 24rpx 0;
}

.bullet-line--tight {
  margin: 8rpx 0;
}

.dot {
  flex: none;
  width: 8rpx;
  height: 8rpx;
  margin: 15rpx 16rpx 0 0;
  border-radius: 50%;
  background: $brand;
}

.bullet-text {
  flex: 1;
  font-size: 28rpx;
  line-height: 1.65;
  color: #444;
}

.bullet-bold {
  font-weight: 600;
}

.timeline-card {
  margin-bottom: 24rpx;
  padding: 28rpx 28rpx 24rpx;
  border-left: 8rpx solid #6e9bff;
  border-radius: 20rpx;
  background: #fff;
  box-shadow: 0 4rpx 16rpx rgba(60, 90, 150, 0.03);

  &:last-child {
    margin-bottom: 0;
  }
}

.timeline-head {
  display: flex;
  align-items: center;
  margin-bottom: 20rpx;
}

.timeline-num {
  flex: none;
  width: 52rpx;
  height: 52rpx;
  margin-right: 20rpx;
  border-radius: 50%;
  background: #2f6bff;
  color: #fff;
  font-size: 26rpx;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}

.timeline-date {
  font-size: 34rpx;
  font-weight: 700;
  color: #2f2f2f;
}

.timeline-body {
  padding-left: 8rpx;
}

.reason-box {
  margin-bottom: 24rpx;
  padding: 32rpx;
  border-radius: 20rpx;
  background: #fff;

  &:last-child {
    margin-bottom: 0;
  }
}

.reason-title {
  display: block;
  margin-bottom: 16rpx;
  font-size: 30rpx;
  font-weight: 700;
  color: #333;
}

.reason-text {
  display: block;
  font-size: 28rpx;
  line-height: 1.8;
  color: #444;
}

.dispute-item {
  margin-bottom: 20rpx;
  padding: 28rpx 32rpx;
  border-radius: 20rpx;
  background: #fff;

  &:last-child {
    margin-bottom: 0;
  }
}

.dispute-party {
  display: block;
  margin-bottom: 10rpx;
  font-size: 28rpx;
  font-weight: 700;
  color: #2f6bff;
}

.state {
  padding: 120rpx 0;
  text-align: center;
  color: $muted;
  font-size: 26rpx;
}

.tail {
  height: 160rpx;
}
</style>
