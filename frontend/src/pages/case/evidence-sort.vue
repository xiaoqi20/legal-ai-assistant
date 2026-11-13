<script setup lang="ts">
import { onLoad, onUnload } from "@dcloudio/uni-app";
import { computed, ref } from "vue";
import FloatingReturn from "./components/FloatingReturn.vue";
import PageNav from "@/components/PageNav.vue";
import {
  cancelCaseAnalysis,
  fetchCaseAnalysisRecord,
  fetchEvidenceSummaryBundle,
  triggerCaseAnalysis,
} from "@/services/caseContent";
import { USE_MOCK } from "@/services/request";
import type { CaseAnalysisRecord, EvidenceSummaryData } from "@/types/case";

const caseId = ref(1);
const data = ref<EvidenceSummaryData | null>(null);
const record = ref<CaseAnalysisRecord | null>(null);
const loading = ref(true);
const triggering = ref(false);
let pollTimer: ReturnType<typeof setTimeout> | null = null;
let disposed = false;

const isRunning = computed(() => {
  const status = record.value?.status;
  return status === "pending" || status === "running";
});

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
  if (disposed || USE_MOCK || !record.value || !isRunning.value) return;
  const analysisId = record.value.id;
  pollTimer = setTimeout(async () => {
    try {
      const updated = await fetchCaseAnalysisRecord(caseId.value, analysisId);
      record.value = updated;
      if (updated.status === "succeeded") {
        await load();
        return;
      }
      if (updated.status === "pending" || updated.status === "running") {
        schedulePollIfRunning();
      }
    } catch {
      // ignore transient polling failure
    }
  }, 1500);
}

async function load() {
  loading.value = true;
  try {
    const bundle = await fetchEvidenceSummaryBundle(caseId.value);
    data.value = bundle.data;
    record.value = bundle.record;
    schedulePollIfRunning();
  } catch (error) {
    const msg = error instanceof Error ? error.message : "加载证据梳理失败";
    uni.showToast({ title: msg, icon: "none" });
  } finally {
    loading.value = false;
  }
}

async function startGeneration() {
  if (USE_MOCK || triggering.value || isRunning.value) return;
  triggering.value = true;
  try {
    const res = await triggerCaseAnalysis(caseId.value, "evidence_list");
    record.value = await fetchCaseAnalysisRecord(caseId.value, res.analysis_id);
    if (record.value.status === "succeeded") {
      await load();
    } else {
      schedulePollIfRunning();
    }
  } catch (error) {
    const msg = error instanceof Error ? error.message : "发起梳理失败";
    uni.showToast({ title: msg, icon: "none" });
  } finally {
    triggering.value = false;
  }
}

async function cancelGeneration() {
  if (!record.value) return;
  try {
    await cancelCaseAnalysis(caseId.value, record.value.id);
    clearPoll();
    await load();
  } catch (error) {
    const msg = error instanceof Error ? error.message : "取消失败";
    uni.showToast({ title: msg, icon: "none" });
  }
}
</script>

<template>
  <view class="page-shell">
    <PageNav title="证据清单梳理" />
    <scroll-view scroll-y class="page-scroll">
      <view v-if="loading" class="state">AI 正在梳理证据清单…</view>

      <view v-else-if="data" class="content">
        <view class="answer surface-card">
          <text class="answer-title">证据清单梳理</text>
          <text class="answer-intro">根据案件材料，证据清单梳理如下：</text>

          <text class="party-title party-title--blue">原告提供的证据</text>
          <view
            v-for="(item, index) in data.plaintiff"
            :key="`p-${index}`"
            class="evidence-item"
          >
            <text class="num">{{ index + 1 }}.</text>
            <view class="item-copy">
              <text class="item-name">{{ item.name }}</text>
              <text class="item-purpose">证明目的：{{ item.purpose }}</text>
            </view>
          </view>

          <text class="party-title party-title--blue">被告提供的证据</text>
          <view
            v-for="(item, index) in data.defendant"
            :key="`d-${index}`"
            class="evidence-item"
          >
            <text class="num">{{ index + 1 }}.</text>
            <view class="item-copy">
              <text class="item-name">{{ item.name }}</text>
              <text class="item-purpose">证明目的：{{ item.purpose }}</text>
            </view>
          </view>

          <text class="party-title party-title--blue">综合证据分析</text>
          <text class="analysis">{{ data.analysis }}</text>
          <text class="disclaimer">以上分析由 AI 生成，仅供参考。</text>
        </view>
      </view>

      <view v-else class="content">
        <view class="answer surface-card">
          <text class="answer-title">证据清单梳理</text>
          <text class="answer-intro">
            {{
              isRunning
                ? "AI 正在梳理案件证据与举证目录，请稍候…"
                : record?.status === "failed"
                  ? `上次梳理失败（${record.error_message || "请重试"}）`
                  : "当前案件尚未生成证据清单梳理，可点击下方按钮发起 AI 梳理。"
            }}
          </text>
          <view class="sort-actions">
            <view
              v-if="isRunning"
              class="sort-btn sort-btn--ghost"
              @click="cancelGeneration"
            >
              取消梳理
            </view>
            <view v-else class="sort-btn" @click="startGeneration">
              {{ triggering ? "提交中..." : "生成证据清单梳理" }}
            </view>
          </view>
        </view>
      </view>
      <view class="tail" />
    </scroll-view>
    <FloatingReturn :case-id="caseId" />
  </view>
</template>

<style lang="scss" scoped>
.content {
  padding: 10rpx 24rpx 0;
}

.answer {
  padding: 32rpx;
}

.answer-title {
  display: block;
  font-size: 34rpx;
  font-weight: 700;
  color: #333;
}

.answer-intro {
  display: block;
  margin-top: 14rpx;
  font-size: 26rpx;
  line-height: 1.7;
  color: $text-secondary;
}

.party-title {
  display: block;
  margin-top: 28rpx;
  font-size: 28rpx;
  font-weight: 700;
}

.party-title--blue {
  color: $brand;
}

.evidence-item {
  display: flex;
  align-items: flex-start;
  padding: 14rpx 0;
  border-bottom: 1rpx solid $line;
}

.num {
  flex: none;
  width: 34rpx;
  color: $brand;
  font-size: 26rpx;
  font-weight: 600;
}

.item-copy {
  flex: 1;
}

.item-name {
  display: block;
  font-size: 26rpx;
  font-weight: 500;
  color: #333;
}

.item-purpose {
  display: block;
  margin-top: 6rpx;
  font-size: 24rpx;
  line-height: 1.6;
  color: $text-secondary;
}

.analysis {
  display: block;
  margin-top: 12rpx;
  font-size: 26rpx;
  line-height: 1.7;
  color: $text-secondary;
}

.disclaimer {
  display: block;
  margin-top: 24rpx;
  font-size: 22rpx;
  color: $muted;
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

.sort-actions {
  margin-top: 28rpx;
  display: flex;
}

.sort-btn {
  height: 70rpx;
  padding: 0 34rpx;
  border-radius: 35rpx;
  background: $brand;
  color: #fff;
  font-size: 26rpx;
  font-weight: 500;
  display: flex;
  align-items: center;
  justify-content: center;
}

.sort-btn--ghost {
  background: #f1f4fb;
  color: $brand;
}
</style>
