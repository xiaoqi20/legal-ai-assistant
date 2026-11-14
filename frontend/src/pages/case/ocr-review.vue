<script setup lang="ts">
import { onLoad } from "@dcloudio/uni-app";
import { computed, ref } from "vue";
import PageNav from "@/components/PageNav.vue";
import { fetchOcrPages, reviewOcrPage, type OcrPage } from "@/services/files";

const fileId = ref(0);
const pages = ref<OcrPage[]>([]);
const loading = ref(true);
const savingPage = ref(0);
const pendingCount = computed(() => pages.value.filter((page) => page.review_status === "pending").length);

function positionLabel(polygon: OcrPage["blocks"][number]["polygon"]): string {
  if (!polygon.length) return "";
  if (typeof polygon[0] === "number") return (polygon as number[]).join(", ");
  return (polygon as { x: number; y: number }[]).map((point) => `${point.x}, ${point.y}`).join(" · ");
}

async function load() {
  loading.value = true;
  try {
    pages.value = await fetchOcrPages(fileId.value);
  } catch (error) {
    uni.showToast({ title: error instanceof Error ? error.message : "加载识别页失败", icon: "none" });
  } finally {
    loading.value = false;
  }
}

onLoad((options) => {
  fileId.value = Number(options?.fileId || 0);
  if (fileId.value) void load();
});

async function approve(page: OcrPage) {
  if (savingPage.value || page.review_status === "approved") return;
  savingPage.value = page.page_no;
  try {
    const result = await reviewOcrPage(fileId.value, page.page_no, page.corrected_text);
    page.review_status = "approved";
    page.revision += 1;
    uni.showToast({
      title: result.index_job_id ? "全部页面已确认，正在建立检索索引" : "本页校对已保存",
      icon: "none",
    });
  } catch (error) {
    uni.showToast({ title: error instanceof Error ? error.message : "保存校对失败", icon: "none" });
  } finally {
    savingPage.value = 0;
  }
}
</script>

<template>
  <view class="page-shell">
    <PageNav title="OCR 文字校对" />
    <scroll-view scroll-y class="page-scroll">
      <view class="summary">
        <text class="summary-title">识别页面</text>
        <text class="summary-meta">{{ pendingCount }} 页待确认</text>
      </view>
      <view v-if="loading" class="state">加载中…</view>
      <view v-else-if="!pages.length" class="state">暂无 OCR 页面</view>
      <view v-else class="page-list">
        <view v-for="page in pages" :key="page.id" class="ocr-page">
          <view class="page-heading">
            <text class="page-number">第 {{ page.page_no }} 页</text>
            <text class="confidence" :class="{ 'confidence--low': page.review_status === 'pending' }">
              {{ page.average_confidence === null ? "无置信度" : `${Math.round(page.average_confidence * 100)}%` }}
            </text>
          </view>
          <text class="source">{{ page.provider }} · {{ page.model }} · {{ page.review_status === "approved" ? "已确认" : "待确认" }}</text>
          <view v-if="page.blocks.length" class="blocks">
            <text v-for="(block, index) in page.blocks" :key="index" class="block-line">
              {{ block.text }}<text v-if="block.confidence !== null" class="block-confidence"> {{ Math.round(block.confidence * 100) }}%</text>
              <text v-if="positionLabel(block.polygon)" class="block-position"> {{ positionLabel(block.polygon) }}</text>
            </text>
          </view>
          <textarea
            v-model="page.corrected_text"
            class="editor"
            :disabled="page.review_status === 'approved'"
            maxlength="500000"
            auto-height
            placeholder="识别文本"
          />
          <button
            class="approve-btn"
            :disabled="page.review_status === 'approved' || savingPage === page.page_no"
            @click="approve(page)"
          >{{ page.review_status === "approved" ? "已确认" : savingPage === page.page_no ? "保存中…" : "确认本页" }}</button>
        </view>
      </view>
      <view class="tail" />
    </scroll-view>
  </view>
</template>

<style lang="scss" scoped>
.summary { display: flex; align-items: baseline; justify-content: space-between; padding: 30rpx 36rpx 18rpx; }
.summary-title { font-size: 34rpx; font-weight: 650; color: #292d32; }
.summary-meta, .source { font-size: 23rpx; color: #737a83; }
.page-list { padding: 0 24rpx; }
.ocr-page { padding: 26rpx 24rpx; margin-bottom: 18rpx; border: 1px solid #e5e8eb; border-radius: 8rpx; background: #fff; }
.page-heading { display: flex; justify-content: space-between; align-items: center; }
.page-number { font-size: 29rpx; color: #292d32; font-weight: 600; }
.confidence { color: #27734a; font-size: 24rpx; }
.confidence--low { color: #b54732; }
.source { display: block; margin-top: 8rpx; }
.blocks { display: flex; flex-direction: column; gap: 8rpx; margin-top: 22rpx; padding: 16rpx; background: #f5f7f8; }
.block-line { font-size: 23rpx; color: #444b53; line-height: 1.5; }
.block-confidence { color: #8a5a1c; }
.block-position { color: #737a83; font-size: 20rpx; }
.editor { width: 100%; min-height: 260rpx; box-sizing: border-box; padding: 18rpx; margin-top: 18rpx; border: 1px solid #d9dee3; border-radius: 6rpx; color: #30363d; font-size: 27rpx; line-height: 1.65; }
.approve-btn { margin-top: 18rpx; background: #246c55; color: #fff; border-radius: 6rpx; font-size: 26rpx; }
.approve-btn[disabled] { background: #e9edef; color: #68717a; }
.state { padding: 100rpx 30rpx; text-align: center; color: #777; }
.tail { height: 48rpx; }
</style>
