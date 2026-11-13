<script setup lang="ts">
import { onLoad } from "@dcloudio/uni-app";
import { computed, ref } from "vue";
import FileBadge from "@/components/FileBadge.vue";
import FloatingReturn from "./components/FloatingReturn.vue";
import PageNav from "@/components/PageNav.vue";
import { MATERIAL_STATUS_META } from "@/constants/case";
import {
  fetchCase,
  fetchEvidenceRequirements,
  fetchMaterials,
} from "@/services/caseContent";
import type { CaseMaterial, EvidenceRequirement } from "@/types/case";

const caseId = ref(1);
const evidenceId = ref(1);
const caseTitle = ref("");
const requirement = ref<EvidenceRequirement | null>(null);
const materials = ref<CaseMaterial[]>([]);
const tabs = ["书面文件", "电子文档", "照片和视频", "音频记录", "物证书证"];
const activeTab = ref(tabs[0]);
const expandedInfo = ref(false);
const expandedFiles = ref<Record<number, boolean>>({});
const loading = ref(true);

const filtered = computed(() =>
  materials.value.filter(
    (item) => item.requirement_id === evidenceId.value && item.category === activeTab.value,
  ),
);

async function load() {
  loading.value = true;
  try {
    const [detail, requirements, list] = await Promise.all([
      fetchCase(caseId.value),
      fetchEvidenceRequirements(caseId.value),
      fetchMaterials(caseId.value),
    ]);
    caseTitle.value = detail.title;
    requirement.value =
      requirements.find((item) => item.id === evidenceId.value) ?? requirements[0] ?? null;
    materials.value = list;
  } finally {
    loading.value = false;
  }
}

onLoad((options) => {
  caseId.value = Number(options?.id || 1);
  evidenceId.value = Number(options?.eid || 1);
  load();
});

function statusMeta(item: CaseMaterial) {
  return MATERIAL_STATUS_META[item.status];
}

function toggleFiles(id: number) {
  expandedFiles.value[id] = !expandedFiles.value[id];
}

function openMaterial(item: CaseMaterial) {
  uni.navigateTo({
    url: `/pages/case/material-detail?id=${caseId.value}&mid=${item.id}`,
  });
}
</script>

<template>
  <view class="page-shell">
    <PageNav title="材料证据" />
    <scroll-view scroll-y class="page-scroll">
      <view class="head">
        <text class="case-name">{{ caseTitle }}</text>
        <text class="evidence-name">{{ requirement?.title }}</text>
      </view>

      <view v-if="requirement" class="info surface-card">
        <view class="info-head" @click="expandedInfo = !expandedInfo">
          <text class="info-title">证据目的与收集要求</text>
          <text class="info-toggle">{{ expandedInfo ? "收起 ∧" : "展开 ∨" }}</text>
        </view>
        <view v-if="expandedInfo" class="info-body">
          <text class="info-line">证据目的：{{ requirement.purpose }}</text>
          <text class="info-line">收集要求：{{ requirement.collection }}</text>
        </view>
      </view>

      <scroll-view scroll-x class="tabs" :show-scrollbar="false">
        <view class="tabs-inner">
          <view
            v-for="tab in tabs"
            :key="tab"
            class="tab"
            :class="{ 'tab--active': activeTab === tab }"
            @click="activeTab = tab"
          >
            {{ tab }}
          </view>
        </view>
      </scroll-view>

      <view v-if="loading" class="state">加载中…</view>
      <view v-else-if="!filtered.length" class="state">该分类下暂无材料</view>
      <view v-else class="list">
        <view
          v-for="item in filtered"
          :key="item.id"
          class="material surface-card"
          @click="openMaterial(item)"
        >
          <view class="material-head">
            <text class="category">{{ item.category }}</text>
            <text
              class="status"
              :class="`status--${statusMeta(item).tone}`"
            >
              {{ statusMeta(item).label }}
            </text>
          </view>
          <text class="material-name">{{ item.name }}</text>
          <text class="meta">{{ item.uploader }} | {{ item.uploaded_at }}</text>

          <view class="files">
            <view
              v-for="(file, index) in item.files.slice(
                0,
                expandedFiles[item.id] ? item.files.length : 1,
              )"
              :key="`${item.id}-${index}`"
              class="file"
            >
              <FileBadge :type="file.type" />
              <text class="file-name">{{ file.name }}</text>
            </view>
            <view
              v-if="item.files.length > 1"
              class="file-toggle"
              @click.stop="toggleFiles(item.id)"
            >
              {{ expandedFiles[item.id] ? "收起 ∧" : `展开 ∨（${item.files.length}）` }}
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
.head {
  padding: 10rpx 36rpx 20rpx;
}

.case-name {
  display: block;
  font-size: 24rpx;
  color: $muted;
}

.evidence-name {
  display: block;
  margin-top: 8rpx;
  font-size: 40rpx;
  font-weight: 700;
  color: #333;
}

.info {
  margin: 0 24rpx 20rpx;
  padding: 24rpx;
}

.info-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.info-title {
  font-size: 28rpx;
  font-weight: 600;
  color: #333;
}

.info-toggle {
  font-size: 22rpx;
  color: $brand;
}

.info-body {
  margin-top: 16rpx;
  padding-top: 16rpx;
  border-top: 1rpx solid $line;
}

.info-line {
  display: block;
  font-size: 24rpx;
  line-height: 1.6;
  color: $text-secondary;

  & + & {
    margin-top: 10rpx;
  }
}

.tabs {
  width: 100%;
  white-space: nowrap;
  padding: 4rpx 0 18rpx;
}

.tabs-inner {
  display: inline-flex;
  padding: 0 24rpx;
}

.tab {
  flex: none;
  height: 64rpx;
  margin-right: 14rpx;
  padding: 0 28rpx;
  border-radius: 32rpx;
  background: #fff;
  border: 1rpx solid #e4e7ee;
  font-size: 24rpx;
  color: #777;
  display: flex;
  align-items: center;
}

.tab--active {
  background: $brand-soft;
  border-color: transparent;
  color: $brand;
  font-weight: 600;
}

.list {
  padding: 0 24rpx;
}

.material {
  margin-bottom: 20rpx;
  padding: 26rpx;
}

.material-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.category {
  font-size: 24rpx;
  color: $text-secondary;
}

.status {
  height: 40rpx;
  padding: 0 18rpx;
  border-radius: 20rpx;
  display: flex;
  align-items: center;
  font-size: 20rpx;
}

.status--blue {
  background: $brand-soft;
  color: $brand;
}

.status--green {
  background: #e9f9e5;
  color: #45a834;
}

.status--red {
  background: #fdeaea;
  color: #e15a5a;
}

.material-name {
  display: block;
  margin-top: 16rpx;
  font-size: 30rpx;
  font-weight: 600;
  color: #333;
}

.meta {
  display: block;
  margin-top: 8rpx;
  font-size: 22rpx;
  color: $muted;
}

.files {
  margin-top: 18rpx;
  padding-top: 16rpx;
  border-top: 1rpx solid $line;
}

.file {
  display: flex;
  align-items: center;
}

.file + .file {
  margin-top: 12rpx;
}

.file-name {
  margin-left: 12rpx;
  font-size: 24rpx;
  color: #555;
}

.file-toggle {
  margin-top: 12rpx;
  font-size: 22rpx;
  color: $brand;
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
