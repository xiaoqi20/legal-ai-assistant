<script setup lang="ts">
import { computed, ref, shallowRef, watch } from "vue";
import { exportDraft, fetchDraft, saveDraft, type DraftDetail } from "@/services/drafts";
const props = defineProps<{ caseId: number; draftId: number }>();
const emit = defineEmits<{ close: [] }>();
const detail = ref<DraftDetail | null>(null);
const title = shallowRef("");
const body = shallowRef("");
const revision = shallowRef(0);
const busy = shallowRef(false);
const error = shallowRef("");
const message = shallowRef("");
const baseline = shallowRef({ title: "", body: "" });
const dirty = computed(() => title.value !== baseline.value.title || body.value !== baseline.value.body);
function select(index: number) {
  const item = detail.value?.revisions[index];
  if (!item) return;
  title.value = item.title; body.value = item.body; revision.value = item.revision;
  baseline.value = { title: item.title, body: item.body };
}
let version = 0;
watch(() => props.draftId, async () => {
  const current = ++version;
  error.value = ""; message.value = ""; detail.value = null;
  try { const value = await fetchDraft(props.caseId, props.draftId); if (current !== version) return; detail.value = value; select(0); }
  catch (cause) { if (current === version) error.value = cause instanceof Error ? cause.message : "草稿加载失败"; }
}, { immediate: true });
async function save() {
  if (busy.value || !detail.value) return;
  busy.value = true; error.value = ""; message.value = "";
  try {
    const item = await saveDraft(props.caseId, props.draftId, detail.value.revisions[0]?.revision || 0, title.value, body.value);
    detail.value.revisions.unshift(item); select(0); message.value = "新版本已保存";
  } catch (cause) { error.value = cause instanceof Error ? cause.message : "保存失败"; }
  finally { busy.value = false; }
}
async function download() {
  if (busy.value || dirty.value) return;
  busy.value = true; error.value = "";
  try { await exportDraft(props.caseId, props.draftId, revision.value); }
  catch (cause) { error.value = cause instanceof Error ? cause.message : "导出失败"; }
  finally { busy.value = false; }
}
function close() {
  if (busy.value) return;
  if (!dirty.value) { emit("close"); return; }
  uni.showModal({ title: "放弃未保存修改？", content: "已保存的草稿版本会保留。", success: (result) => { if (result.confirm) emit("close"); } });
}
</script>

<template>
  <view class="editor surface-card">
    <text class="title">编辑文书草稿</text>
    <button size="mini" :disabled="busy" @click="close">返回草稿列表</button>
    <text class="hint">AI 辅助草稿，待律师复核。请补齐【待补充】字段，核验事实、金额和法律依据。</text>
    <text v-if="error" class="error">{{ error }}</text><text v-if="message" class="hint">{{ message }}</text>
    <template v-if="detail?.revisions.length">
      <picker :disabled="dirty || busy" :range="detail.revisions.map((r) => `版本 ${r.revision}`)" @change="select(Number($event.detail.value))"><view class="version">当前版本 {{ revision }} · 查看历史版本 ›</view></picker>
      <input v-model="title" maxlength="200" placeholder="文书标题" :disabled="busy" />
      <textarea v-model="body" maxlength="30000" :disabled="busy" auto-height />
      <view class="actions"><button size="mini" :disabled="busy || !title.trim() || !body.trim() || !dirty" @click="save">保存新版本</button><button size="mini" :disabled="busy || dirty" @click="download">导出 DOCX</button></view>
      <text v-if="dirty" class="hint">有未保存修改，请先保存再导出或切换版本。</text>
      <text class="title">材料来源</text>
      <text v-for="(source, index) in detail.sources" :key="source.id" class="source">[{{ index + 1 }}] {{ source.original_name }} · 第 {{ source.page_no || 1 }} 页{{ source.file_status !== 'available' ? '（已不可用）' : '' }}</text>
      <text class="hint">{{ detail.analysis.content?.limitations }}</text>
      <text class="hint">模型：{{ detail.analysis.model }} · 提示词版本：{{ detail.analysis.prompt_version_id }}</text>
    </template>
  </view>
</template>

<style scoped lang="scss">
.editor { margin-top: 28rpx; padding: 28rpx; }
.title { display: block; font-size: 30rpx; font-weight: 600; margin: 16rpx 0; }
.hint { display: block; font-size: 24rpx; color: $muted; margin: 16rpx 0; }
input, textarea { box-sizing: border-box; width: 100%; padding: 20rpx; background: #f6f8fc; border-radius: 12rpx; font-size: 27rpx; margin: 20rpx 0; }
input { height: 84rpx; } textarea { min-height: 500rpx; line-height: 1.8; }
.actions { display: flex; gap: 16rpx; button { margin: 0; } }
.source, .version { display: block; font-size: 25rpx; margin: 12rpx 0; overflow-wrap: anywhere; }
.error { display: block; color: #d64b52; font-size: 25rpx; }
</style>
