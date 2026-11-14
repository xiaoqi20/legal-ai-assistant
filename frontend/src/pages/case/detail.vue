<script setup lang="ts">
import { onLoad } from "@dcloudio/uni-app";
import { computed, ref } from "vue";
import ComposerBar from "@/components/ComposerBar.vue";
import PageNav from "@/components/PageNav.vue";
import WinRateDonut from "@/components/WinRateDonut.vue";
import {
  ANALYSIS_STATUS_META,
  EVIDENCE_STATUS_META,
  PROCEDURE_LABELS,
} from "@/constants/case";
import { fetchCase } from "@/services/caseContent";
import { useCaseCreateStore } from "@/stores/caseCreate";
import type { CaseSummary } from "@/types/case";

const caseCreate = useCaseCreateStore();
const caseId = ref(1);
const detail = ref<CaseSummary | null>(null);
const loading = ref(true);
const draft = ref("");

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

const tools = [
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

async function load() {
  loading.value = true;
  try {
    const localFound = caseCreate.findLocalCase(caseId.value);
    detail.value = localFound ?? (await fetchCase(caseId.value));
  } catch {
    uni.showToast({ title: "案件加载失败", icon: "none" });
  } finally {
    loading.value = false;
  }
}

onLoad((options) => {
  caseId.value = Number(options?.id || 1);
  load();
});

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
              :win-rate="detail.win_rate"
            />
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
</style>
