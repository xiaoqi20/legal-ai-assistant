<script setup lang="ts">
import { onMounted, ref, shallowRef } from "vue";
import { fetchDocuments } from "@/services/caseContent";
import { chooseAndUploadDocument } from "@/platform/wechat/uploadDocument";
import type { CaseDocument } from "@/types/case";

const props = defineProps<{ caseId: number }>();
const selected = defineModel<number[]>({ required: true });
const documents = ref<CaseDocument[]>([]);
const busy = shallowRef(false);
const error = shallowRef("");
async function reload() {
  try { documents.value = await fetchDocuments(props.caseId); }
  catch (cause) { error.value = cause instanceof Error ? cause.message : "附件加载失败"; }
}
function toggle(id?: number) {
  if (!id) return;
  selected.value = selected.value.includes(id) ? selected.value.filter((value) => value !== id) : [...selected.value, id];
}
async function upload() {
  if (busy.value) return;
  busy.value = true;
  error.value = "";
  try {
    const id = await chooseAndUploadDocument(props.caseId);
    await reload();
    if (id && documents.value.some((doc) => doc.file_id === id) && !selected.value.includes(id)) {
      selected.value = [...selected.value, id];
    } else if (id) error.value = "文件仍在后台处理，请稍后刷新附件列表后选择";
  } catch (cause) { error.value = cause instanceof Error ? cause.message : "附件上传失败"; }
  finally { busy.value = false; }
}
onMounted(reload);
</script>

<template>
  <view class="attachments-field">
    <text class="field-title">关联附件（{{ selected.length }}）</text>
    <text class="hint">可选择案件已有文档，或上传新附件。提交复核前须完成识别和校对。</text>
    <view class="buttons"><button size="mini" :disabled="busy" @click="upload">{{ busy ? "上传处理中…" : "上传附件" }}</button><button size="mini" :disabled="busy" @click="reload">刷新附件</button></view>
    <text v-if="error" class="error">{{ error }}</text>
    <view v-for="doc in documents" :key="doc.id" class="choice" @click="toggle(doc.file_id)">
      <text>{{ doc.file_id && selected.includes(doc.file_id) ? "☑" : "□" }} {{ doc.name }}</text>
      <text v-if="doc.parse_status !== 'succeeded'" class="hint">{{ doc.parse_status === 'review_required' ? "待 OCR 校对" : "处理中" }}</text>
    </view>
    <text v-if="!documents.length" class="hint">暂无可关联文档</text>
  </view>
</template>

<style scoped lang="scss">
.field-title { display: block; font-weight: 600; font-size: 28rpx; }
.hint { display: block; color: $muted; font-size: 24rpx; margin: 12rpx 0; }
.buttons { display: flex; gap: 16rpx; margin: 20rpx 0; button { margin: 0; } }
.choice { padding: 20rpx 0; border-bottom: 1rpx solid $line; font-size: 26rpx; overflow-wrap: anywhere; }
.error { color: #d64b52; font-size: 24rpx; }
</style>
