<script setup lang="ts">
import { onHide, onLoad, onShow, onUnload } from "@dcloudio/uni-app";
import { ref, shallowRef } from "vue";
import PageNav from "@/components/PageNav.vue";
import DraftEditor from "./components/DraftEditor.vue";
import { fetchDrafts } from "@/services/drafts";
import { triggerCaseAnalysis } from "@/services/caseContent";
import type { CaseAnalysisRecord } from "@/types/case";
const caseId = shallowRef(0);
const rows = ref<CaseAnalysisRecord[]>([]);
const selected = shallowRef(0);
const busy = shallowRef(false);
const error = shallowRef("");
const labels: Record<string, string> = { complaint_draft: "民事起诉状草稿", evidence_catalog: "证据目录草稿" };
const statuses: Record<string, string> = { pending: "等待生成", running: "正在生成", succeeded: "已生成 · 待复核", failed: "生成未完成，可重试或检查材料", cancelled: "已取消" };
let visible = false;
let timer: ReturnType<typeof setTimeout> | null = null;
let generation = 0;
function stop() { generation++; if (timer) clearTimeout(timer); timer = null; }
async function load() {
  const current = ++generation;
  try {
    const value = await fetchDrafts(caseId.value);
    if (!visible || current !== generation) return;
    rows.value = value;
    if (rows.value.some((row) => ["pending", "running"].includes(row.status))) timer = setTimeout(load, 2000);
  } catch (cause) { if (current === generation) error.value = cause instanceof Error ? cause.message : "加载失败"; }
}
onLoad((options) => { caseId.value = Number(options?.id); });
onShow(() => { visible = true; void load(); });
onHide(() => { visible = false; stop(); });
onUnload(stop);
async function generate(type: "complaint_draft" | "evidence_catalog") {
  if (busy.value) return;
  busy.value = true; error.value = "";
  try { await triggerCaseAnalysis(caseId.value, type); stop(); await load(); }
  catch (cause) { error.value = cause instanceof Error ? cause.message : "生成失败"; }
  finally { busy.value = false; }
}
</script>

<template>
  <view class="page-shell"><PageNav title="法律文书草稿" /><scroll-view scroll-y class="page-scroll"><view class="content">
    <template v-if="!selected">
    <view class="surface-card introduction"><text class="title">法律文书草稿</text><text class="hint">依据当前案件已识别的材料生成。请先上传并校对文档，生成后可编辑和导出。</text>
      <view class="actions"><button size="mini" :disabled="busy" @click="generate('evidence_catalog')">生成证据目录</button><button size="mini" :disabled="busy" @click="generate('complaint_draft')">生成民事起诉状</button></view>
    </view>
    <text v-if="error" class="error">{{ error }}</text>
    <text v-if="!rows.length" class="hint">暂无文书草稿</text>
    <view v-for="row in rows" :key="row.id" class="draft surface-card">
      <text class="title">{{ labels[row.analysis_type] }}</text><text class="hint">{{ statuses[row.status] }} · {{ new Date(row.created_at).toLocaleString() }}</text>
      <button v-if="row.status === 'succeeded'" size="mini" @click="selected = row.id">编辑与导出</button>
    </view>
    </template>
    <DraftEditor v-else :key="selected" :case-id="caseId" :draft-id="selected" @close="selected = 0" />
  </view></scroll-view></view>
</template>

<style scoped lang="scss">
.content { padding: 24rpx 32rpx 100rpx; }
.introduction, .draft { padding: 28rpx; margin-bottom: 24rpx; }
.title { display: block; font-size: 30rpx; font-weight: 600; }
.hint { display: block; color: $muted; font-size: 24rpx; margin: 16rpx 0; }
.actions { display: flex; flex-wrap: wrap; gap: 14rpx; button { margin: 0; } }
.error { display: block; color: #d64b52; padding: 20rpx 0; }
</style>
