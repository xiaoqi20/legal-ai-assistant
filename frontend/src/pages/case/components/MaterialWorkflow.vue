<script setup lang="ts">
import { onHide, onShow, onUnload } from "@dcloudio/uni-app";
import { computed, onUnmounted, ref, shallowRef, watch } from "vue";
import { actOnMaterial, analyzeMaterial, fetchMaterialEvents, type MaterialEvent } from "@/services/materials";
import { fetchCaseAnalysisRecord } from "@/services/caseContent";
import { openRemoteFile } from "@/services/files";
import type { CaseAnalysisRecord, CaseMaterial } from "@/types/case";

const props = defineProps<{ material: CaseMaterial }>();
const emit = defineEmits<{ changed: [] }>();
const comment = shallowRef("");
const busy = shallowRef(false);
const error = shallowRef("");
const events = ref<MaterialEvent[]>([]);
const advice = ref<CaseAnalysisRecord | null>(null);
const analysisId = shallowRef<number | null>(null);
const editable = computed(() => props.material.permissions?.can_edit);
const reviewable = computed(() => props.material.permissions?.can_review && props.material.status === "lawyer_pending");
const canEdit = computed(() => editable.value && ["draft", "withdrawn", "lawyer_rejected", "ai_failed", "ai_passed"].includes(props.material.status));
const canWithdraw = computed(() => editable.value && ["lawyer_pending", "lawyer_approved"].includes(props.material.status));
const adviceSections = computed(() => {
  const data = advice.value?.content;
  if (!data) return [];
  return [["summary", "材料概况"], ["strengths", "支持因素"], ["issues", "待核实问题"], ["suggestions", "补充建议"], ["limitations", "分析范围"]].map(([key, title]) => {
    const value = data[key];
    return { title, text: Array.isArray(value) ? value.join("\n\n") : String(value || "") };
  }).filter((section) => section.text);
});
let timer: ReturnType<typeof setTimeout> | null = null;
let visible = true;
let generation = 0;
function stop() { generation++; if (timer) clearTimeout(timer); timer = null; }
async function refresh() {
  const current = ++generation;
  try {
    const [history, record] = await Promise.all([fetchMaterialEvents(props.material.case_id, props.material.id),
      analysisId.value ? fetchCaseAnalysisRecord(props.material.case_id, analysisId.value) : Promise.resolve(null)]);
    if (!visible || current !== generation) return;
    events.value = history;
    advice.value = record;
    if (record && ["pending", "running"].includes(record.status)) timer = setTimeout(refresh, 2000);
  } catch (cause) { if (current === generation) error.value = cause instanceof Error ? cause.message : "记录加载失败"; }
}
watch(() => [props.material.id, props.material.revision, props.material.ai_analysis_id], () => {
  stop(); analysisId.value = props.material.ai_analysis_id || null; void refresh();
}, { immediate: true });
onHide(() => { visible = false; stop(); });
onUnload(stop);
onUnmounted(() => { visible = false; stop(); });
onShow(() => { visible = true; void refresh(); });
async function action(name: string) {
  if (busy.value) return;
  if (name === "reject" && !comment.value.trim()) { error.value = "请填写退回原因"; return; }
  busy.value = true; error.value = "";
  try {
    await actOnMaterial(props.material.case_id, props.material.id, props.material.revision || 1, name, comment.value);
    comment.value = ""; emit("changed");
  } catch (cause) { error.value = cause instanceof Error ? cause.message : "操作失败"; }
  finally { busy.value = false; }
}
async function analyze() {
  busy.value = true; error.value = "";
  try {
    const result = await analyzeMaterial(props.material.case_id, props.material.id);
    analysisId.value = result.analysis_id; stop(); await refresh();
  } catch (cause) { error.value = cause instanceof Error ? cause.message : "分析失败"; }
  finally { busy.value = false; }
}
function edit() { uni.navigateTo({ url: `/pages/case/material-edit?id=${props.material.case_id}&mid=${props.material.id}` }); }
async function openSource(fileId: number) {
  try { await openRemoteFile(fileId); }
  catch (cause) { error.value = cause instanceof Error ? cause.message : "来源文件打开失败"; }
}
const labels: Record<string, string> = { created: "保存草稿", edited: "修改材料", submit: "提交复核", withdraw: "撤回", approve: "律师通过", reject: "律师退回" };
</script>

<template>
  <view class="workflow surface-card">
    <text class="title">材料复核</text>
    <text class="hint">提交人可修改或撤回；其他有案件权限的法务成员负责复核。AI 意见供复核参考。</text>
    <text class="purpose">证明目的：{{ material.purpose || '待补充' }}</text>
    <text v-if="error" class="error">{{ error }}</text>
    <textarea v-if="reviewable" v-model="comment" maxlength="3000" placeholder="复核意见（退回时必填）" auto-height />
    <view class="actions">
      <button v-if="canEdit" size="mini" :disabled="busy" @click="edit">编辑材料</button>
      <button v-if="canEdit" size="mini" :disabled="busy" @click="action('submit')">提交律师复核</button>
      <button v-if="canWithdraw" size="mini" :disabled="busy" @click="action('withdraw')">撤回材料</button>
      <button v-if="reviewable" size="mini" :disabled="busy" @click="action('approve')">复核通过</button>
      <button v-if="reviewable" size="mini" :disabled="busy" @click="action('reject')">退回修改</button>
    </view>
    <text class="title">AI 辅助意见</text>
    <button v-if="editable || material.permissions?.can_review" size="mini" :disabled="busy || advice?.status === 'pending' || advice?.status === 'running'" @click="analyze">{{ advice?.status === 'pending' || advice?.status === 'running' ? '分析中…' : '分析此材料' }}</button>
    <text v-if="advice?.status === 'failed'" class="error">分析未完成，材料可能已更新或附件未就绪，请核实后重试。</text>
    <view v-for="section in adviceSections" :key="section.title"><text class="subtitle">{{ section.title }}</text><text class="advice">{{ section.text }}</text></view>
    <view v-for="(source, index) in advice?.sources || []" :key="source.id" class="source" @click="openSource(source.file_id)">[{{ index + 1 }}] {{ source.original_name }} · 第 {{ source.page_no || 1 }} 页 · 查看原文</view>
    <text class="title">操作记录</text>
    <text v-if="!events.length" class="hint">暂无操作记录</text>
    <view v-for="event in events" :key="event.id" class="event">
      <text>{{ labels[event.action] || event.action }} · v{{ event.revision }} · 成员 #{{ event.actor_id }}</text>
      <text class="hint">{{ new Date(event.created_at).toLocaleString() }}</text>
      <text v-if="event.comment">{{ event.comment }}</text>
    </view>
  </view>
</template>

<style scoped lang="scss">
.workflow { padding: 28rpx; margin-top: 24rpx; }
.title { display: block; font-size: 28rpx; font-weight: 600; margin: 24rpx 0 16rpx; }
.subtitle { display: block; font-size: 26rpx; font-weight: 600; margin-top: 24rpx; }
.source { color: #2f6bff; overflow-wrap: anywhere; font-size: 24rpx; padding: 12rpx 0; }
.hint { display: block; color: $muted; font-size: 24rpx; margin: 12rpx 0; }
.purpose, .advice { display: block; font-size: 26rpx; white-space: pre-wrap; overflow-wrap: anywhere; margin: 20rpx 0; }
.actions { display: flex; flex-wrap: wrap; gap: 16rpx; button { margin: 0; } }
textarea { width: 100%; box-sizing: border-box; background: #f6f8fc; padding: 20rpx; margin: 20rpx 0; font-size: 26rpx; }
.error { display: block; color: #d64b52; font-size: 24rpx; margin: 16rpx 0; }
.event { border-top: 1rpx solid #edf0f5; padding: 20rpx 0; font-size: 25rpx; }
</style>
