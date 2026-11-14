<script setup lang="ts">
import { onLoad } from "@dcloudio/uni-app";
import { computed, ref } from "vue";
import FloatingReturn from "./components/FloatingReturn.vue";
import PageNav from "@/components/PageNav.vue";
import SearchInput from "@/components/SearchInput.vue";
import { fetchCase, fetchEvidenceRequirements } from "@/services/caseContent";
import type { EvidenceRequirement } from "@/types/case";

const caseId = ref(1);
const caseTitle = ref("");
const keyword = ref("");
const requirements = ref<EvidenceRequirement[]>([]);
const loading = ref(true);

const introCopy = computed(() => {
  const sources = new Set(requirements.value.map((item) => item.source).filter(Boolean));
  if (sources.size > 1) return "清单包含 AI 生成和人工维护内容，请按收集要求准备材料。";
  if (sources.has("manual")) return "以下证据目录由人工维护，请按收集要求准备材料。";
  if (sources.has("ai")) return "以下证据目录由 AI 根据案情生成，请按收集要求准备材料。";
  return "请按下方收集要求准备材料。";
});

const filtered = computed(() => {
  const query = keyword.value.trim();
  if (!query) return requirements.value;
  return requirements.value.filter(
    (item) =>
      item.title.includes(query) ||
      item.purpose.includes(query) ||
      item.collection.includes(query),
  );
});

async function load() {
  loading.value = true;
  try {
    const [detail, list] = await Promise.all([
      fetchCase(caseId.value),
      fetchEvidenceRequirements(caseId.value),
    ]);
    caseTitle.value = detail.title;
    requirements.value = list;
  } finally {
    loading.value = false;
  }
}

onLoad((options) => {
  caseId.value = Number(options?.id || 1);
  load();
});

function open(item: EvidenceRequirement) {
  uni.navigateTo({
    url: `/pages/case/materials?id=${caseId.value}&eid=${item.id}`,
  });
}
</script>

<template>
  <view class="page-shell">
    <PageNav title="证据资料清单" />
    <scroll-view scroll-y class="page-scroll">
      <view class="intro">
        <text class="intro-case">{{ caseTitle }}</text>
        <text class="intro-title">证据资料清单</text>
        <text class="intro-sub">{{ introCopy }}</text>
      </view>

      <SearchInput v-model="keyword" placeholder="搜索证据名称或收集要求" />

      <view v-if="loading" class="state">加载中…</view>
      <view v-else-if="!filtered.length" class="state">没有找到相关证据</view>
      <view v-else class="list">
        <view
          v-for="item in filtered"
          :key="item.id"
          class="evidence-card surface-card"
          @click="open(item)"
        >
          <view class="card-head">
            <text class="dot">•</text>
            <text class="card-title">{{ item.title }}</text>
            <text class="chevron">›</text>
          </view>
          <view class="card-body">
            <view class="field">
              <text class="label">证据目的</text>
              <text class="text">{{ item.purpose }}</text>
            </view>
            <view class="field">
              <text class="label">收集要求</text>
              <text class="text">{{ item.collection }}</text>
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
.intro {
  padding: 10rpx 36rpx 20rpx;
}

.intro-case {
  display: block;
  font-size: 24rpx;
  color: $muted;
}

.intro-title {
  display: block;
  margin-top: 10rpx;
  font-size: 40rpx;
  font-weight: 700;
  color: #333;
}

.intro-sub {
  display: block;
  margin-top: 12rpx;
  font-size: 24rpx;
  line-height: 1.55;
  color: $text-secondary;
}

.list {
  padding: 8rpx 24rpx 0;
}

.evidence-card {
  overflow: hidden;
  margin-bottom: 20rpx;
}

.card-head {
  height: 76rpx;
  padding: 0 24rpx;
  background: linear-gradient(90deg, #6f8dff 0%, #9bb6ff 100%);
  display: flex;
  align-items: center;
  color: #fff;
}

.dot {
  margin-right: 10rpx;
  font-size: 30rpx;
}

.card-title {
  flex: 1;
  font-size: 28rpx;
  font-weight: 600;
}

.chevron {
  font-size: 34rpx;
}

.card-body {
  padding: 24rpx;
}

.field + .field {
  margin-top: 18rpx;
}

.label {
  display: block;
  font-size: 24rpx;
  font-weight: 600;
  color: $brand;
}

.text {
  display: block;
  margin-top: 6rpx;
  font-size: 24rpx;
  line-height: 1.6;
  color: $text-secondary;
}

.state {
  padding: 100rpx 0;
  text-align: center;
  color: $muted;
  font-size: 26rpx;
}

.tail {
  height: 140rpx;
}
</style>
