<script setup lang="ts">
import { onLoad, onShow } from "@dcloudio/uni-app";
import { computed, ref } from "vue";
import FileBadge from "@/components/FileBadge.vue";
import FilePreviewModal from "./components/FilePreviewModal.vue";
import FloatingReturn from "./components/FloatingReturn.vue";
import MaterialWorkflow from "./components/MaterialWorkflow.vue";
import PageNav from "@/components/PageNav.vue";
import { MATERIAL_STATUS_META } from "@/constants/case";
import { fetchMaterial } from "@/services/caseContent";
import { openRemoteFile } from "@/services/files";
import { USE_MOCK } from "@/services/request";
import type { CaseMaterial, MaterialFile } from "@/types/case";

const caseId = ref(1);
const materialId = ref(0);
const material = ref<CaseMaterial | null>(null);
const loading = ref(true);
const previewFile = ref<MaterialFile | null>(null);

const status = computed(() =>
  material.value ? MATERIAL_STATUS_META[material.value.status] : null,
);

async function load(id: number) {
  loading.value = true;
  try {
    material.value = await fetchMaterial(id, caseId.value);
    caseId.value = material.value.case_id;
  } catch (error) {
    const msg = error instanceof Error ? error.message : "加载材料详情失败";
    uni.showToast({ title: msg, icon: "none" });
  } finally {
    loading.value = false;
  }
}

onLoad((options) => {
  caseId.value = Number(options?.id || 1);
  materialId.value = Number(options?.mid || 1);
});
onShow(() => { if (materialId.value) void load(materialId.value); });

async function preview(file: MaterialFile) {
  if (!USE_MOCK && file.id) {
    try {
      await openRemoteFile(file.id, file.mime_type);
    } catch (error) {
      const msg = error instanceof Error ? error.message : "打开附件失败";
      uni.showToast({ title: msg, icon: "none" });
    }
    return;
  }
  previewFile.value = file;
}
</script>

<template>
  <view class="page-shell">
    <PageNav title="材料证据详情" />
    <scroll-view scroll-y class="page-scroll">
      <view v-if="loading" class="state">加载中…</view>

      <view v-else-if="material" class="content">
        <view class="detail surface-card">
          <view class="heado">
            <view class="heado-main">
              <text class="kind">{{ material.category }}</text>
              <text class="name">{{ material.name }}</text>
            </view>
            <text v-if="status" class="status" :class="`status--${status.tone}`">
              {{ status.label }}
            </text>
          </view>

          <view v-if="status?.tone === 'red'" class="seal">
            <text>{{ status.label }}</text>
          </view>

          <view class="fields">
            <view class="field">
              <text class="label">证据类型</text>
              <text class="value">{{ material.category }}</text>
            </view>
            <view class="field">
              <text class="label">发生日期</text>
              <text class="value">{{ material.occurred_at }}</text>
            </view>
            <view class="field">
              <text class="label">证据来源</text>
              <text class="value">{{ material.source }}</text>
            </view>
            <view class="field">
              <text class="label">上传人</text>
              <text class="value">{{ material.uploader }}</text>
            </view>
            <view class="field">
              <text class="label">联系方式</text>
              <text class="value">{{ material.contact }}</text>
            </view>
            <view class="field field--block">
              <text class="label">证据描述</text>
              <text class="value value--paragraph">{{ material.description }}</text>
            </view>
          </view>

          <view class="attachments">
            <text class="section">相关附件</text>
            <view
              v-for="(file, index) in material.files"
              :key="index"
              class="file"
              @click="preview(file)"
            >
              <FileBadge :type="file.type" />
              <text class="file-name">{{ file.name }}</text>
              <text class="preview">预览</text>
            </view>
          </view>
        </view>

        <MaterialWorkflow v-if="!USE_MOCK" :material="material" @changed="load(materialId)" />
        <view
          v-if="
            (material.status === 'ai_failed' ||
              material.status === 'lawyer_rejected') &&
            material.status_reason
          "
          class="failure surface-card"
        >
          <text class="failure-title">审核失败原因</text>
          <text class="failure-text">{{ material.status_reason }}</text>
        </view>
      </view>
      <view class="tail" />
    </scroll-view>
    <FloatingReturn :case-id="caseId" />
    <FilePreviewModal
      :visible="!!previewFile"
      :file-name="previewFile?.name || ''"
      :file-type="previewFile?.type"
      @close="previewFile = null"
    />
  </view>
</template>

<style lang="scss" scoped>
.content {
  padding: 10rpx 24rpx 0;
}

.detail {
  position: relative;
  padding: 32rpx;
  overflow: hidden;
}

.heado {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding-bottom: 24rpx;
  border-bottom: 1rpx solid $line;
}

.heado-main {
  flex: 1;
  min-width: 0;
  padding-right: 20rpx;
}

.kind {
  font-size: 24rpx;
  color: $muted;
}

.name {
  display: block;
  margin-top: 8rpx;
  font-size: 34rpx;
  font-weight: 700;
  color: #333;
}

.status {
  flex: none;
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

.seal {
  position: absolute;
  top: 150rpx;
  right: 34rpx;
  width: 190rpx;
  height: 190rpx;
  border: 8rpx double rgba(230, 80, 80, 0.28);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(230, 80, 80, 0.4);
  font-size: 34rpx;
  font-weight: 700;
  transform: rotate(-18deg);
  pointer-events: none;
}

.fields {
  padding-top: 10rpx;
}

.field {
  display: flex;
  align-items: baseline;
  padding: 16rpx 0;
  border-bottom: 1rpx solid #f5f6f8;
}

.field--block {
  flex-direction: column;
}

.label {
  flex: none;
  width: 140rpx;
  font-size: 24rpx;
  color: $muted;
}

.value {
  flex: 1;
  font-size: 26rpx;
  color: #333;
}

.value--paragraph {
  margin-top: 8rpx;
  line-height: 1.65;
  color: $text-secondary;
}

.attachments {
  padding-top: 22rpx;
}

.section {
  display: block;
  margin-bottom: 14rpx;
  font-size: 26rpx;
  font-weight: 600;
  color: #333;
}

.file {
  display: flex;
  align-items: center;
  padding: 12rpx 0;
}

.file-name {
  flex: 1;
  margin-left: 12rpx;
  font-size: 24rpx;
  color: #555;
}

.preview {
  font-size: 22rpx;
  color: $brand;
}

.failure {
  margin-top: 20rpx;
  padding: 28rpx;
  border-left: 6rpx solid #e15a5a;
}

.failure-title {
  display: block;
  font-size: 28rpx;
  font-weight: 700;
  color: #e15a5a;
}

.failure-text {
  display: block;
  margin-top: 10rpx;
  font-size: 24rpx;
  line-height: 1.6;
  color: $text-secondary;
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
