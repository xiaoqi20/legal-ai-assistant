<script setup lang="ts">
import { onHide, onLoad, onShow, onUnload } from "@dcloudio/uni-app";
import { computed, ref } from "vue";
import ConfirmDialog from "@/components/ConfirmDialog.vue";
import FileBadge from "@/components/FileBadge.vue";
import FilePreviewModal from "./components/FilePreviewModal.vue";
import FloatingReturn from "./components/FloatingReturn.vue";
import PageNav from "@/components/PageNav.vue";
import SearchInput from "@/components/SearchInput.vue";
import {
  deleteCaseDocument,
  fetchCase,
  fetchDocuments,
} from "@/services/caseContent";
import { fetchFileStatus, getFileProcessingError, openRemoteFile, uploadCaseDocument } from "@/services/files";
import { USE_MOCK } from "@/services/request";
import type { CaseDocument, DocumentCategoryCode } from "@/types/case";

const caseId = ref(1);
const caseTitle = ref("");
const keyword = ref("");
const activeCategory = ref("全部");
const categories = ["全部", "案件程序", "庭审记录", "沟通记录", "其他"];
const documents = ref<CaseDocument[]>([]);
const loading = ref(true);
const uploading = ref(false);
const deleting = ref(false);
const previewDoc = ref<CaseDocument | null>(null);
const deleteTarget = ref<CaseDocument | null>(null);
const deleteDialogTitle = computed(() =>
  deleteTarget.value
    ? `删除「${deleteTarget.value.name}」？删除后将不再展示且不再参与 AI 问答与分析`
    : "",
);
const pendingFiles = new Set<number>();
let pollTimer: ReturnType<typeof setTimeout> | null = null;
let pageVisible = false;
let loadVersion = 0;

function stopPolling() {
  if (pollTimer !== null) clearTimeout(pollTimer);
  pollTimer = null;
}

function scheduleRefresh() {
  stopPolling();
  if (!pageVisible || USE_MOCK || !pendingFiles.size) return;
  pollTimer = setTimeout(() => void load(true), 2000);
}

function pauseRefresh() {
  pageVisible = false;
  loadVersion++;
  stopPolling();
}

const CATEGORY_TO_CODE: Record<string, DocumentCategoryCode> = {
  案件程序: "case_procedure",
  庭审记录: "court_record",
  沟通记录: "communication",
  其他: "other",
};

const filtered = computed(() => {
  const query = keyword.value.trim();
  return documents.value.filter((item) => {
    const categoryOk =
      activeCategory.value === "全部" || item.category === activeCategory.value;
    const queryOk = !query || item.name.includes(query);
    return categoryOk && queryOk;
  });
});

async function load(silent = false) {
  if (!pageVisible) return;
  const version = ++loadVersion;
  stopPolling();
  if (!silent) loading.value = true;
  try {
    const [detail, list, statuses] = await Promise.all([
      silent ? null : fetchCase(caseId.value),
      fetchDocuments(caseId.value),
      Promise.all([...pendingFiles].map(fetchFileStatus)),
    ]);
    if (!pageVisible || version !== loadVersion) return;
    if (detail) caseTitle.value = detail.title;
    documents.value = list;
    for (const status of statuses) {
      if (status.status === "uploading" || (status.status === "available"
        && ["queued", "retrying", "index_queued"].includes(status.metadata?.parse_status || ""))) continue;
      pendingFiles.delete(status.id);
      if (status.status === "failed" || status.status === "quarantined") {
        uni.showToast({ title: getFileProcessingError(status), icon: "none" });
      }
    }
    // A status response can finish before the list response; refresh that stale row once more.
    for (const doc of list) {
      if (doc.file_id && ["queued", "retrying", "index_queued"].includes(doc.parse_status || "")) {
        pendingFiles.add(doc.file_id);
      }
    }
  } catch (error) {
    if (pageVisible && version === loadVersion && !silent) {
      const msg = error instanceof Error ? error.message : "加载文档失败";
      uni.showToast({ title: msg, icon: "none" });
    }
  } finally {
    if (pageVisible && version === loadVersion) {
      loading.value = false;
      scheduleRefresh();
    }
  }
}

onLoad((options) => {
  caseId.value = Number(options?.id || 1);
});
onShow(() => {
  pageVisible = true;
  void load();
});
onHide(pauseRefresh);
onUnload(pauseRefresh);

async function preview(doc: CaseDocument) {
  if (!USE_MOCK && doc.file_id) {
    try {
      await openRemoteFile(doc.file_id, doc.mime_type);
    } catch (error) {
      const msg = error instanceof Error ? error.message : "打开文档失败";
      uni.showToast({ title: msg, icon: "none" });
    }
    return;
  }
  previewDoc.value = doc;
}

async function runUpload(params: {
  filename: string;
  sizeBytes: number;
  file?: File;
  filePath?: string;
}) {
  uploading.value = true;
  try {
    const categoryCode = CATEGORY_TO_CODE[activeCategory.value] || "other";
    const status = await uploadCaseDocument({
      caseId: caseId.value,
      filename: params.filename,
      sizeBytes: params.sizeBytes,
      category: categoryCode,
      file: params.file,
      filePath: params.filePath,
    });
    if (status.status === "uploading" || status.metadata?.parse_status === "index_queued") {
      pendingFiles.add(status.id);
    }
    if (!pageVisible) return;
    const parseStatus = status.metadata?.parse_status;
    uni.showToast({
      title: parseStatus === "review_required"
        ? "识别完成，请校对低置信度页面"
        : parseStatus === "index_queued" ? "上传成功，正在建立索引"
          : status.status === "available" ? "上传并解析完成" : "上传成功，正在后台解析",
      icon: parseStatus === "succeeded" ? "success" : "none",
    });
    await load(true);
  } catch (error) {
    const msg = error instanceof Error ? error.message : "文档上传失败";
    if (pageVisible) uni.showToast({ title: msg, icon: "none" });
  } finally {
    uploading.value = false;
  }
}

function reviewDocument(doc: CaseDocument) {
  if (!doc.file_id) return;
  uni.navigateTo({ url: `/pages/case/ocr-review?fileId=${doc.file_id}&caseId=${caseId.value}` });
}

function askDelete(doc: CaseDocument) {
  if (deleting.value) return;
  deleteTarget.value = doc;
}

async function confirmDelete() {
  const target = deleteTarget.value;
  if (!target || deleting.value) return;
  deleting.value = true;
  try {
    await deleteCaseDocument(caseId.value, target.id);
    deleteTarget.value = null;
    if (previewDoc.value?.id === target.id) previewDoc.value = null;
    if (target.file_id) pendingFiles.delete(target.file_id);
    documents.value = documents.value.filter((item) => item.id !== target.id);
    uni.showToast({ title: "已删除文档", icon: "none" });
    if (!USE_MOCK) await load(true);
  } catch (error) {
    const msg = error instanceof Error ? error.message : "删除文档失败";
    uni.showToast({ title: msg, icon: "none" });
  } finally {
    deleting.value = false;
  }
}

function handleUpload() {
  if (USE_MOCK) {
    uni.showToast({ title: "当前为 Mock 演示模式", icon: "none" });
    return;
  }
  if (uploading.value) return;

  // #ifdef H5
  const input = document.createElement("input");
  input.type = "file";
  input.accept = ".pdf,.jpg,.jpeg,.png,.docx,.txt";
  input.onchange = () => {
    const selected = input.files?.[0];
    if (!selected) return;
    void runUpload({
      filename: selected.name,
      sizeBytes: selected.size,
      file: selected,
    });
  };
  input.click();
  // #endif

  // #ifndef H5
  uni.chooseMessageFile({
    count: 1,
    type: "file",
    extension: ["pdf", "jpg", "jpeg", "png", "docx", "txt"],
    success: (res) => {
      const picked = res.tempFiles?.[0];
      if (!picked) return;
      void runUpload({
        filename: picked.name || "document.pdf",
        sizeBytes: picked.size || 0,
        filePath: picked.path,
      });
    },
  });
  // #endif
}
</script>

<template>
  <view class="page-shell">
    <PageNav title="案件文档" />
    <scroll-view scroll-y class="page-scroll">
      <view class="head head--row">
        <view class="head-copy">
          <text class="case-name">{{ caseTitle }}</text>
          <text class="head-title">案件文档管理</text>
        </view>
        <view v-if="!USE_MOCK" class="upload-btn" @click="handleUpload">
          {{ uploading ? "上传中..." : "上传文档" }}
        </view>
      </view>

      <SearchInput v-model="keyword" placeholder="搜索案件文档" />

      <scroll-view scroll-x class="chips" :show-scrollbar="false">
        <view class="chips-inner">
          <view
            v-for="category in categories"
            :key="category"
            class="chip"
            :class="{ 'chip--active': activeCategory === category }"
            @click="activeCategory = category"
          >
            {{ category }}
          </view>
        </view>
      </scroll-view>

      <view v-if="loading" class="state">加载中…</view>
      <view v-else-if="!filtered.length" class="state">没有找到相关文档</view>
      <view v-else class="list">
        <view
          v-for="doc in filtered"
          :key="doc.id"
          class="doc surface-card"
          @click="preview(doc)"
        >
          <FileBadge :type="doc.type" />
          <view class="doc-copy">
            <text class="doc-name">{{ doc.name }}</text>
            <text class="doc-meta">{{ doc.uploader }} | {{ doc.uploaded_at }}</text>
          </view>
          <view class="doc-side">
            <view class="doc-actions">
              <text class="category">{{ doc.category }}</text>
              <text class="delete-link" @click.stop="askDelete(doc)">删除</text>
            </view>
            <text
              v-if="doc.parse_status === 'review_required'"
              class="review-link"
              @click.stop="reviewDocument(doc)"
            >
              校对
            </text>
            <text v-else-if="doc.parse_status === 'index_queued'" class="index-status">
              建立索引中
            </text>
          </view>
        </view>
      </view>
      <view class="tail" />
    </scroll-view>
    <FloatingReturn :case-id="caseId" />
    <FilePreviewModal
      :visible="!!previewDoc"
      :file-name="previewDoc?.name || ''"
      :file-type="previewDoc?.type"
      @close="previewDoc = null"
    />
    <ConfirmDialog
      :visible="!!deleteTarget"
      :title="deleteDialogTitle"
      :confirm-text="deleting ? '删除中...' : '删除'"
      @cancel="if (!deleting) deleteTarget = null;"
      @confirm="confirmDelete"
    />
  </view>
</template>

<style lang="scss" scoped>
.head {
  padding: 10rpx 36rpx 16rpx;
}

.head--row {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20rpx;
}

.head-copy {
  flex: 1;
  min-width: 0;
}

.upload-btn {
  flex: none;
  height: 60rpx;
  padding: 0 24rpx;
  border-radius: 30rpx;
  background: $brand;
  color: #fff;
  font-size: 24rpx;
  font-weight: 500;
  display: flex;
  align-items: center;
  justify-content: center;
}

.case-name {
  display: block;
  font-size: 24rpx;
  color: $muted;
}

.head-title {
  display: block;
  margin-top: 8rpx;
  font-size: 40rpx;
  font-weight: 700;
  color: #333;
}

.chips {
  width: 100%;
  white-space: nowrap;
  padding-bottom: 16rpx;
}

.chips-inner {
  display: inline-flex;
  padding: 0 24rpx;
}

.chip {
  flex: none;
  height: 58rpx;
  margin-right: 12rpx;
  padding: 0 26rpx;
  border-radius: 29rpx;
  border: 1rpx solid #e4e7ee;
  background: #fff;
  color: #777;
  font-size: 24rpx;
  display: flex;
  align-items: center;
}

.chip--active {
  background: $brand-soft;
  border-color: transparent;
  color: $brand;
  font-weight: 600;
}

.list {
  padding: 0 24rpx;
}

.doc {
  display: flex;
  align-items: center;
  margin-bottom: 16rpx;
  padding: 24rpx;
}

.doc-copy {
  flex: 1;
  min-width: 0;
  margin-left: 16rpx;
}

.doc-name {
  display: block;
  font-size: 28rpx;
  font-weight: 500;
  color: #333;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-meta {
  display: block;
  margin-top: 6rpx;
  font-size: 22rpx;
  color: $muted;
}

.doc-side {
  flex: none;
  margin-left: 16rpx;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8rpx;
}

.doc-actions {
  display: flex;
  align-items: center;
  gap: 16rpx;
}

.category {
  flex: none;
  font-size: 20rpx;
  color: $muted;
}

.delete-link {
  flex: none;
  padding: 6rpx 12rpx;
  border-radius: 10rpx;
  color: #d9534f;
  font-size: 22rpx;
}

.review-link {
  flex: none;
  padding: 6rpx 14rpx;
  color: $brand;
  font-size: 24rpx;
}

.index-status {
  flex: none;
  color: #8a5a1c;
  font-size: 22rpx;
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
