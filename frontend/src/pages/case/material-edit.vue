<script setup lang="ts">
import { onLoad } from "@dcloudio/uni-app";
import { reactive, shallowRef } from "vue";
import PageNav from "@/components/PageNav.vue";
import MaterialAttachments from "./components/MaterialAttachments.vue";
import { EVIDENCE_CATEGORY_LABELS } from "@/constants/case";
import { fetchMaterial, fetchEvidenceRequirements } from "@/services/caseContent";
import { saveMaterial, type MaterialPayload } from "@/services/materials";
import type { EvidenceRequirement } from "@/types/case";

const caseId = shallowRef(0);
const materialId = shallowRef(0);
const revision = shallowRef(1);
const ready = shallowRef(false);
const saving = shallowRef(false);
const error = shallowRef("");
const requirements = shallowRef<EvidenceRequirement[]>([]);
const categories = Object.entries(EVIDENCE_CATEGORY_LABELS);
const form = reactive<MaterialPayload>({ title: "", category: "written", purpose: "", description: "", source: "", occurred_on: null, requirement_id: null, file_ids: [] });
onLoad(async (options) => {
  caseId.value = Number(options?.id);
  materialId.value = Number(options?.mid || 0);
  form.requirement_id = Number(options?.eid) || null;
  try {
    requirements.value = await fetchEvidenceRequirements(caseId.value);
    if (materialId.value) {
      const item = await fetchMaterial(materialId.value, caseId.value);
      Object.assign(form, { title: item.name, category: item.category_code || "written", purpose: item.purpose || "",
        description: item.description === "暂无材料说明" ? "" : item.description, source: item.source === "—" ? "" : item.source,
        occurred_on: item.occurred_at === "—" ? null : item.occurred_at,
        requirement_id: item.requirement_id || null, file_ids: item.files.flatMap((f) => f.id ? [f.id] : []) });
      revision.value = item.revision || 1;
    }
    ready.value = true;
  } catch (cause) { error.value = cause instanceof Error ? cause.message : "加载失败"; }
});
async function save() {
  if (saving.value) return;
  if (!form.title.trim() || !form.purpose.trim()) { error.value = "请填写材料名称和证明目的"; return; }
  saving.value = true;
  error.value = "";
  try {
    const result = await saveMaterial(caseId.value, form, materialId.value || undefined, revision.value);
    uni.redirectTo({ url: `/pages/case/material-detail?id=${caseId.value}&mid=${result.id}` });
  } catch (cause) { error.value = cause instanceof Error ? cause.message : "保存失败"; }
  finally { saving.value = false; }
}
</script>

<template>
  <view class="page-shell"><PageNav :title="materialId ? '编辑材料' : '新增材料'" />
    <scroll-view scroll-y class="page-scroll"><view class="content">
      <text v-if="error" class="error">{{ error }}</text>
      <view v-if="ready" class="form surface-card">
        <text class="label">材料名称 *</text><input v-model="form.title" maxlength="200" placeholder="例如：借款协议" />
        <text class="label">证据分类</text>
        <view class="choices"><button v-for="[code, label] in categories" :key="code" size="mini" :class="{ active: form.category === code }" @click="form.category = code">{{ label }}</button></view>
        <text class="label">关联证据目录</text>
        <picker :range="['不关联目录', ...requirements.map((r) => r.title)]" @change="form.requirement_id = requirements[Number($event.detail.value) - 1]?.id || null">
          <view class="picker">{{ requirements.find((r) => r.id === form.requirement_id)?.title || '不关联目录' }} ›</view>
        </picker>
        <text class="label">证明目的 *</text><textarea v-model="form.purpose" maxlength="3000" placeholder="说明这份材料要证明什么事实" auto-height />
        <text class="label">材料说明</text><textarea v-model="form.description" maxlength="5000" placeholder="材料内容、取得过程和需核实事项" auto-height />
        <text class="label">材料来源</text><input v-model="form.source" maxlength="100" placeholder="例如：本人保存的银行回单" />
        <text class="label">形成日期</text><picker mode="date" @change="form.occurred_on = $event.detail.value"><view class="picker">{{ form.occurred_on || '请选择（选填）' }}</view></picker>
        <MaterialAttachments v-model="form.file_ids" :case-id="caseId" />
        <button class="save" :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存草稿' }}</button>
      </view>
    </view></scroll-view>
  </view>
</template>

<style scoped lang="scss">
.content { padding: 24rpx 32rpx 80rpx; }
.form { padding: 28rpx; }
.label { display: block; margin: 24rpx 0 14rpx; font-size: 27rpx; font-weight: 600; }
input, textarea, .picker { box-sizing: border-box; width: 100%; background: #f6f8fc; border-radius: 14rpx; padding: 20rpx; font-size: 26rpx; }
input { height: 80rpx; } textarea { min-height: 130rpx; }
.choices { display: flex; flex-wrap: wrap; gap: 12rpx; button { margin: 0; } .active { color: #2f6bff; background: #e9f1ff; } }
.save { margin-top: 36rpx; background: #2f6bff; color: white; border-radius: 40rpx; }
.error { display: block; color: #d64b52; padding: 20rpx 0; }
</style>
