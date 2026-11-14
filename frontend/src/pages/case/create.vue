<script setup lang="ts">
import { onLoad } from "@dcloudio/uni-app";
import { storeToRefs } from "pinia";
import { computed, nextTick, ref } from "vue";
import PageNav from "@/components/PageNav.vue";
import {
  CASE_PROMPT_PRESETS,
  CREATE_CASE_TYPES,
  CREATE_ROLE_OPTIONS,
  CREATE_STAGE_OPTIONS,
} from "@/constants/case";
import { chooseCaseDocuments } from "@/platform/wechat/chooseDocuments";
import { useCaseCreateStore } from "@/stores/caseCreate";
import type { DraftPendingFieldKey, HandlingIdentity } from "@/types/case";

const store = useCaseCreateStore();
const { form, hasDraft } = storeToRefs(store);

const scrollIntoView = ref("");

const identities: Exclude<HandlingIdentity, "">[] = ["本人办理", "代理他人"];

const stageOptions = computed(() =>
  form.value.caseType
    ? CREATE_STAGE_OPTIONS[form.value.caseType] || []
    : ["尚未起诉/诉前咨询", "已进入诉讼/仲裁", "不确定"],
);

const roleOptions = computed(
  () => CREATE_ROLE_OPTIONS[form.value.caseType || "不确定"] || [],
);

const readyFiles = computed(() =>
  form.value.files.filter((file) => file.status !== "failed"),
);
const failedCount = computed(
  () => form.value.files.length - readyFiles.value.length,
);
const hasTextInput = computed(() =>
  Boolean(form.value.summary.trim() || form.value.claim.trim()),
);
const canOrganize = computed(
  () => readyFiles.value.length > 0 || hasTextInput.value,
);
const hasPending = computed(() =>
  Object.values(form.value.pendingFields).some(Boolean),
);
const partiesPending = computed(() => {
  const ourOk = form.value.ourParties.some((item) => item.trim());
  const oppOk = form.value.opponentParties.some((item) => item.trim());
  return Boolean(form.value.pendingFields.parties && (!ourOk || !oppOk));
});

const submitButtonText = computed(() =>
  readyFiles.value.length > 0 || hasTextInput.value
    ? "创建案件并开始分析"
    : "创建案件",
);

const draftFooterHint = computed(() => {
  if (failedCount.value > 0) {
    return "存在上传失败的文件，请返回修改后创建";
  }
  if (readyFiles.value.length > 0) {
    return `建案后将解析 ${readyFiles.value.length} 份材料并分析案情`;
  }
  if (hasTextInput.value) {
    return "建案后将分析案情";
  }
  return "将创建空白档案，进入详情后可随时补充";
});

onLoad(() => {
  if (hasDraft.value) {
    uni.showToast({ title: "已恢复上次未提交草稿", icon: "none" });
  }
});

function handlePageBack() {
  if (hasDraft.value) {
    uni.showToast({ title: "草稿已保留", icon: "none" });
  }
}

function handleClearDraft() {
  store.clearDraft();
  uni.showToast({ title: "已清空当前草稿", icon: "none" });
}

function applyPreset(summary: string) {
  store.applyPresetSummary(summary);
}

function handleRestoreSummary() {
  if (store.restoreRawSummary()) {
    uni.showToast({ title: "已恢复为整理前的案情描述", icon: "none" });
  }
}

async function handlePickFiles() {
  const remaining = 5 - form.value.files.length;
  const result = await chooseCaseDocuments(remaining);
  if (result.files.length) {
    store.appendFiles(result.files);
  }
  if (result.rejectedMessages.length) {
    uni.showToast({ title: result.rejectedMessages[0], icon: "none" });
  }
}

function fileTag(name: string): string {
  if (/\.pdf$/i.test(name)) return "PDF";
  if (/\.txt$/i.test(name)) return "TXT";
  return "DOCX";
}

function handleOrganize() {
  if (failedCount.value > 0) {
    uni.showToast({
      title: "存在上传失败的文件，请重试或移除后生成",
      icon: "none",
    });
    return;
  }
  if (!canOrganize.value) {
    uni.showToast({ title: "请先输入案情描述或上传材料", icon: "none" });
    return;
  }
  const pending = store.organizeWithAi();
  const hasAnyPending = Object.values(pending).some(Boolean);
  scrollIntoView.value = "";
  nextTick(() => {
    scrollIntoView.value = hasAnyPending ? "pending-anchor" : "draft-top";
  });
}

function goToInputStep() {
  form.value.step = "input";
  scrollIntoView.value = "";
  nextTick(() => {
    scrollIntoView.value = "input-top";
  });
}

function clearPending(field: DraftPendingFieldKey) {
  store.clearPendingField(field);
}

function onPartyInput(
  side: "our" | "opponent",
  index: number,
  event: unknown,
) {
  const detail = (event as { detail?: { value?: string } } | null)?.detail;
  store.updateParty(side, index, detail?.value ?? "");
}

function handleSubmitCase() {
  if (failedCount.value > 0) {
    uni.showToast({
      title: "存在上传失败的文件，请重试或移除后创建",
      icon: "none",
    });
    return;
  }
  const created = store.createLocalCase();
  uni.redirectTo({ url: `/pages/case/detail?id=${created.id}` });
}
</script>

<template>
  <view class="page-shell create-page">
    <PageNav title="新建案件" @back="handlePageBack">
      <view v-if="hasDraft" class="nav-clear-btn" @click="handleClearDraft">
        清空
      </view>
    </PageNav>

    <scroll-view
      scroll-y
      class="page-scroll create-scroll"
      :scroll-into-view="scrollIntoView"
      :show-scrollbar="false"
    >
      <view v-if="form.step === 'input'" id="input-top" class="scroll-inner">
        <view class="intake-hero">
          <image
            class="intake-robot"
            src="/static/images/robot.png"
            mode="aspectFit"
          />
          <view class="intake-hero-copy">
            <text class="intake-hero-title">说说情况，AI 帮你整理建案</text>
            <text class="intake-hero-sub">
              用自然语言描述或上传首批材料，一键生成可编辑草稿
            </text>
          </view>
        </view>

        <view class="surface-card create-card intake-card">
          <view class="form-item form-item--flush">
            <view class="form-label">
              <text class="form-label-text">案情描述</text>
              <text
                v-if="form.rawSummary"
                class="restore-btn"
                @click="handleRestoreSummary"
              >
                恢复原文
              </text>
              <text v-else class="form-sub">{{ form.summary.length }} 字</text>
            </view>
            <textarea
              v-model="form.summary"
              class="form-textarea intake-textarea"
              :maxlength="2000"
              placeholder="• 发生了什么纠纷，双方是什么关系？&#10;• 关键时间节点、金额及当前进展（如尚未起诉）？&#10;• 希望对方赔偿或解决什么问题？"
              placeholder-style="color:#b4bac5"
            />
          </view>

          <view class="prompt-chips-wrap">
            <text class="prompt-chips-label">
              不知道怎么写？点选常见场景快速填入：
            </text>
            <view class="prompt-chips">
              <view
                v-for="preset in CASE_PROMPT_PRESETS"
                :key="preset.key"
                class="prompt-chip"
                @click="applyPreset(preset.summary)"
              >
                {{ preset.label }}
              </view>
            </view>
          </view>
        </view>

        <view class="surface-card create-card upload-card">
          <view class="upload-dropzone" @click="handlePickFiles">
            <view class="drop-icon">
              <view class="upload-arrow" />
            </view>
            <view class="drop-copy">
              <text class="drop-title">
                点击上传首批案件材料（选填 · {{ form.files.length }}/5）
              </text>
              <text class="drop-sub">
                支持文字版 PDF / DOCX / TXT（≤20MB），
                <text class="drop-sub-warn">暂不支持扫描件 OCR</text>
              </text>
            </view>
          </view>

          <view v-if="form.files.length" class="upload-file-list">
            <view
              v-for="(file, idx) in form.files"
              :key="`${file.name}-${idx}`"
              class="upload-file-item"
              :class="{ 'upload-file-item--failed': file.status === 'failed' }"
            >
              <text
                class="upload-file-tag"
                :class="{ 'upload-file-tag--pdf': fileTag(file.name) === 'PDF' }"
              >
                {{ fileTag(file.name) }}
              </text>
              <text class="upload-file-name">{{ file.name }}</text>
              <text
                v-if="file.status === 'failed'"
                class="upload-file-retry"
                @click="store.retryFile(idx)"
              >
                失败重试
              </text>
              <text v-else class="upload-file-size">{{ file.sizeText }}</text>
              <view class="upload-file-rm" @click="store.removeFile(idx)">
                ×
              </view>
            </view>
          </view>
        </view>
      </view>

      <view v-else id="draft-top" class="scroll-inner">
        <view class="xiaonuo-draft-row">
          <image
            class="xiaonuo-avatar"
            src="/static/images/robot.png"
            mode="aspectFit"
          />
          <view class="xiaonuo-bubble">
            <view class="xiaonuo-bubble-head">
              <text class="xiaonuo-bubble-title">小诺已整理建案草稿</text>
              <text class="xiaonuo-bubble-back" @click="goToInputStep">
                重改描述
              </text>
            </view>
            <text class="xiaonuo-bubble-text">
              {{
                hasPending
                  ? "标橙「待确认」字段可直接补充，也可跳过后直接创建。"
                  : "已识别核心要素，核对或微调任意字段后即可创建案件。"
              }}
            </text>
          </view>
        </view>

        <view id="pending-anchor" class="surface-card create-card">
          <view class="section-head">
            <view class="section-head-left">
              <view class="section-bar" />
              <text class="section-title">AI 生成信息（可修改）</text>
            </view>
            <text
              class="step-badge"
              :class="hasPending ? 'step-badge--soft' : 'step-badge--done'"
            >
              {{ hasPending ? "含待确认项" : "已识别完整" }}
            </text>
          </view>

          <view
            class="form-item"
            :class="{ 'field-pending': form.pendingFields.title }"
          >
            <view class="form-label">
              <view class="form-label-left">
                <text class="form-label-text">案件名称</text>
                <text v-if="form.pendingFields.title" class="pending-badge">
                  待确认
                </text>
              </view>
              <text class="form-sub">{{ form.title.length }}/200</text>
            </view>
            <input
              v-model="form.title"
              class="form-input"
              maxlength="200"
              placeholder="未填将记为「未命名案件（待完善）」"
              placeholder-style="color:#b4bac5"
              @input="form.title.trim() && clearPending('title')"
            />
          </view>

          <view
            class="form-item"
            :class="{ 'field-pending': form.pendingFields.caseType }"
          >
            <view class="form-label">
              <view class="form-label-left">
                <text class="form-label-text">案件类型</text>
                <text v-if="form.pendingFields.caseType" class="pending-badge">
                  待确认
                </text>
              </view>
              <text class="form-sub">
                {{ form.caseType ? `已选：${form.caseType}` : "未选可跳过" }}
              </text>
            </view>
            <view class="pill-group">
              <view
                v-for="item in CREATE_CASE_TYPES"
                :key="item"
                class="opt-pill"
                :class="{ 'opt-pill--on': form.caseType === item }"
                @click="store.setCaseType(item)"
              >
                {{ item }}
              </view>
            </view>
          </view>

          <view
            class="form-item form-item--last"
            :class="{ 'field-pending': form.pendingFields.stage }"
          >
            <view class="form-label">
              <view class="form-label-left">
                <text class="form-label-text">当前办理阶段</text>
                <text v-if="form.pendingFields.stage" class="pending-badge">
                  待确认
                </text>
              </view>
              <text class="form-sub">
                {{ form.stage ? `已选：${form.stage}` : "未选可跳过" }}
              </text>
            </view>
            <view class="pill-group">
              <view
                v-for="stage in stageOptions"
                :key="stage"
                class="opt-pill"
                :class="{ 'opt-pill--on': form.stage === stage }"
                @click="store.setStage(stage)"
              >
                {{ stage }}
              </view>
            </view>
          </view>
        </view>

        <view class="surface-card create-card">
          <view class="section-head">
            <view class="section-head-left">
              <view class="section-bar" />
              <text class="section-title">案情摘要与诉求</text>
            </view>
            <text
              v-if="form.rawSummary"
              class="restore-btn"
              @click="handleRestoreSummary"
            >
              恢复原文
            </text>
          </view>

          <view class="form-item">
            <view class="form-label">
              <text class="form-label-text">案情摘要（可直接修改）</text>
            </view>
            <textarea
              v-model="form.summary"
              class="form-textarea form-textarea--compact"
              :maxlength="2000"
              placeholder-style="color:#b4bac5"
            />
          </view>

          <view
            class="form-item"
            :class="{
              'field-pending': form.pendingFields.claim,
              'form-item--last': !form.files.length,
            }"
          >
            <view class="form-label">
              <view class="form-label-left">
                <text class="form-label-text">核心诉求</text>
                <text v-if="form.pendingFields.claim" class="pending-badge">
                  待确认
                </text>
              </view>
              <text class="form-sub">可修改或跳过</text>
            </view>
            <input
              v-model="form.claim"
              class="form-input"
              placeholder="如：追回借款本金及利息 / 履行维修义务"
              placeholder-style="color:#b4bac5"
              @input="form.claim.trim() && clearPending('claim')"
            />
          </view>

          <view v-if="form.files.length" class="form-item form-item--last">
            <view class="form-label">
              <text class="form-label-text">
                已附材料 ({{ readyFiles.length }} 份)
              </text>
              <text class="link-btn" @click="goToInputStep">返回修改材料</text>
            </view>
            <view class="upload-file-list">
              <view
                v-for="(file, idx) in form.files"
                :key="`${file.name}-draft-${idx}`"
                class="upload-file-item"
              >
                <text
                  class="upload-file-tag"
                  :class="{
                    'upload-file-tag--pdf': fileTag(file.name) === 'PDF',
                  }"
                >
                  {{ fileTag(file.name) }}
                </text>
                <text class="upload-file-name">{{ file.name }}</text>
                <text class="upload-file-size">{{ file.sizeText }}</text>
              </view>
            </view>
          </view>
        </view>

        <view class="surface-card create-card">
          <view class="section-head">
            <view class="section-head-left">
              <view class="section-bar" />
              <text class="section-title">当事人信息</text>
              <text v-if="partiesPending" class="pending-badge">待确认</text>
            </view>
            <text class="step-badge step-badge--soft">可修改 · 可跳过</text>
          </view>

          <view class="form-item">
            <view class="form-label">
              <text class="form-label-text">办理身份</text>
              <text class="form-sub">选择后再展示诉讼地位</text>
            </view>
            <view class="pill-group">
              <view
                v-for="identity in identities"
                :key="identity"
                class="opt-pill"
                :class="{ 'opt-pill--on': form.handlingIdentity === identity }"
                @click="store.setHandlingIdentity(identity)"
              >
                {{ identity }}
              </view>
            </view>
          </view>

          <view v-if="form.handlingIdentity" class="form-item">
            <view class="form-label">
              <text class="form-label-text">
                {{
                  form.handlingIdentity === "代理他人"
                    ? "委托方诉讼地位"
                    : "我方诉讼地位"
                }}
              </text>
            </view>
            <view class="pill-group">
              <view
                v-for="role in roleOptions"
                :key="role"
                class="opt-pill"
                :class="{ 'opt-pill--on': form.partyRole === role }"
                @click="store.setPartyRole(role)"
              >
                {{ role }}
              </view>
            </view>
          </view>

          <view
            class="form-item"
            :class="{
              'field-pending':
                form.pendingFields.parties &&
                !form.ourParties.some((item) => item.trim()),
            }"
          >
            <view class="form-label">
              <view class="form-label-left">
                <text class="form-label-text">我方 / 委托方名称</text>
                <text
                  v-if="
                    form.pendingFields.parties &&
                    !form.ourParties.some((item) => item.trim())
                  "
                  class="pending-badge"
                >
                  待确认
                </text>
              </view>
              <text class="form-sub">可跳过</text>
            </view>
            <view class="multi-party-list">
              <view
                v-for="(val, idx) in form.ourParties"
                :key="`our-${idx}`"
                class="multi-party-row"
              >
                <input
                  class="form-input form-input--flex"
                  :value="val"
                  :placeholder="
                    idx === 0
                      ? '选填，如：张某 / 某科技有限公司'
                      : '补充其他共同主体'
                  "
                  placeholder-style="color:#b4bac5"
                  @input="onPartyInput('our', idx, $event)"
                />
                <view
                  v-if="form.ourParties.length > 1"
                  class="party-rm-btn"
                  @click="store.removeParty('our', idx)"
                >
                  ×
                </view>
              </view>
            </view>
            <view class="add-party-btn" @click="store.addParty('our')">
              + 添加我方主体
            </view>
          </view>

          <view
            class="form-item form-item--last"
            :class="{
              'field-pending':
                form.pendingFields.parties &&
                !form.opponentParties.some((item) => item.trim()),
            }"
          >
            <view class="form-label">
              <view class="form-label-left">
                <text class="form-label-text">对方当事人名称</text>
                <text
                  v-if="
                    form.pendingFields.parties &&
                    !form.opponentParties.some((item) => item.trim())
                  "
                  class="pending-badge"
                >
                  待确认
                </text>
              </view>
              <text class="form-sub">可跳过</text>
            </view>
            <view class="multi-party-list">
              <view
                v-for="(val, idx) in form.opponentParties"
                :key="`opp-${idx}`"
                class="multi-party-row"
              >
                <input
                  class="form-input form-input--flex"
                  :value="val"
                  :placeholder="
                    idx === 0
                      ? '选填，如：李某 / 某物业公司'
                      : '补充其他对方主体'
                  "
                  placeholder-style="color:#b4bac5"
                  @input="onPartyInput('opponent', idx, $event)"
                />
                <view
                  v-if="form.opponentParties.length > 1"
                  class="party-rm-btn"
                  @click="store.removeParty('opponent', idx)"
                >
                  ×
                </view>
              </view>
            </view>
            <view class="add-party-btn" @click="store.addParty('opponent')">
              + 添加对方主体
            </view>
          </view>
        </view>
      </view>
      <view class="scroll-tail" />
    </scroll-view>

    <view class="create-footer">
      <template v-if="form.step === 'input'">
        <text v-if="failedCount > 0" class="create-footer-hint">
          存在上传失败的文件，请重试或移除后生成草稿
        </text>
        <view
          class="btn-primary"
          :class="{ 'btn-primary--disabled': !canOrganize }"
          @click="handleOrganize"
        >
          <text class="btn-sparkle">✦</text>
          <text>生成建案草稿</text>
        </view>
      </template>

      <template v-else>
        <text class="create-footer-hint">{{ draftFooterHint }}</text>
        <view class="step-footer-row">
          <view class="btn-soft-back" @click="goToInputStep">修改描述</view>
          <view
            class="btn-primary btn-primary--flex"
            @click="handleSubmitCase"
          >
            {{ submitButtonText }}
          </view>
        </view>
      </template>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.nav-clear-btn {
  height: 52rpx;
  padding: 0 20rpx;
  border-radius: 26rpx;
  background: rgba(255, 255, 255, 0.8);
  font-size: 23rpx;
  font-weight: 600;
  color: #667085;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
}

.create-scroll {
  padding: 0 28rpx;
  box-sizing: border-box;
}

.scroll-inner {
  padding-top: 8rpx;
}

.scroll-tail {
  height: 24rpx;
}

.intake-hero {
  display: flex;
  align-items: center;
  gap: 20rpx;
  padding: 4rpx 4rpx 24rpx;
}

.intake-robot {
  flex: none;
  width: 96rpx;
  height: 96rpx;
}

.intake-hero-copy {
  flex: 1;
  min-width: 0;
}

.intake-hero-title {
  display: block;
  font-size: 32rpx;
  font-weight: 700;
  color: #1c273d;
  line-height: 1.35;
}

.intake-hero-sub {
  display: block;
  margin-top: 4rpx;
  font-size: 23rpx;
  color: #61708a;
  line-height: 1.45;
}

.create-card {
  padding: 28rpx 28rpx 20rpx;
  margin-bottom: 24rpx;
}

.intake-card {
  padding-bottom: 26rpx;
}

.upload-card {
  padding: 26rpx 28rpx;
}

.form-item {
  margin-bottom: 22rpx;
}

.form-item--flush {
  margin-bottom: 0;
}

.form-item--last {
  margin-bottom: 8rpx;
}

.form-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12rpx;
}

.form-label-left {
  display: flex;
  align-items: center;
}

.form-label-text {
  font-size: 26rpx;
  font-weight: 600;
  color: #333;
}

.form-sub {
  font-size: 22rpx;
  color: #9aa1ad;
}

.form-input {
  width: 100%;
  height: 80rpx;
  border-radius: 40rpx;
  background: #f6f8fc;
  border: 2rpx solid #e6ebf4;
  padding: 0 28rpx;
  font-size: 27rpx;
  color: #333;
  box-sizing: border-box;
}

.form-input--flex {
  flex: 1;
  min-width: 0;
}

.form-textarea {
  width: 100%;
  min-height: 240rpx;
  border-radius: 24rpx;
  background: #f7f9fd;
  border: 2rpx solid #e6ebf5;
  padding: 20rpx 24rpx;
  font-size: 27rpx;
  line-height: 1.6;
  color: #333;
  box-sizing: border-box;
}

.form-textarea--compact {
  min-height: 160rpx;
}

.prompt-chips-wrap {
  margin-top: 22rpx;
  padding-top: 20rpx;
  border-top: 2rpx dashed #e9eff8;
}

.prompt-chips-label {
  display: block;
  font-size: 22rpx;
  color: #828ea3;
  margin-bottom: 14rpx;
}

.prompt-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 14rpx;
}

.prompt-chip {
  height: 56rpx;
  padding: 0 22rpx;
  border-radius: 28rpx;
  background: #f2f6ff;
  border: 2rpx solid #dce6ff;
  color: #2f59c4;
  font-size: 23rpx;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
}

.upload-dropzone {
  display: flex;
  align-items: center;
  gap: 22rpx;
  padding: 26rpx 24rpx;
  border-radius: 24rpx;
  background: #f8faff;
  border: 2rpx dashed #bfd4ff;
}

.drop-icon {
  flex: none;
  width: 76rpx;
  height: 76rpx;
  border-radius: 22rpx;
  background: #e6efff;
  display: flex;
  align-items: center;
  justify-content: center;
}

.upload-arrow {
  position: relative;
  width: 26rpx;
  height: 28rpx;
  border-bottom: 4rpx solid $brand;

  &::before {
    content: "";
    position: absolute;
    left: 11rpx;
    top: 2rpx;
    width: 4rpx;
    height: 18rpx;
    border-radius: 2rpx;
    background: $brand;
  }

  &::after {
    content: "";
    position: absolute;
    left: 5rpx;
    top: 2rpx;
    width: 12rpx;
    height: 12rpx;
    border-top: 4rpx solid $brand;
    border-left: 4rpx solid $brand;
    transform: rotate(45deg);
  }
}

.drop-copy {
  flex: 1;
  min-width: 0;
}

.drop-title {
  display: block;
  font-size: 26rpx;
  font-weight: 600;
  color: #1f2a44;
  line-height: 1.35;
}

.drop-sub {
  display: block;
  font-size: 22rpx;
  color: #778399;
  margin-top: 6rpx;
  line-height: 1.45;
}

.drop-sub-warn {
  color: #c25e00;
  font-weight: 600;
}

.upload-file-list {
  display: flex;
  flex-direction: column;
  gap: 14rpx;
  margin-top: 20rpx;
}

.upload-file-item {
  display: flex;
  align-items: center;
  gap: 14rpx;
  background: #fff;
  border: 2rpx solid #e6ecf6;
  border-radius: 20rpx;
  padding: 16rpx 20rpx;
  font-size: 24rpx;
  color: #333;
}

.upload-file-item--failed {
  border-color: #f8c6c6;
  background: #fff9f9;
}

.upload-file-tag {
  flex: none;
  height: 36rpx;
  padding: 0 12rpx;
  border-radius: 8rpx;
  background: #eaf1ff;
  color: #2f6bff;
  font-size: 20rpx;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
}

.upload-file-tag--pdf {
  background: #ffecec;
  color: #e24c4c;
}

.upload-file-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.upload-file-size {
  flex: none;
  font-size: 22rpx;
  color: #98a2b3;
}

.upload-file-retry {
  flex: none;
  height: 44rpx;
  padding: 0 16rpx;
  border-radius: 22rpx;
  background: #ffecec;
  color: #e24c4c;
  font-size: 22rpx;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
}

.upload-file-rm {
  flex: none;
  width: 40rpx;
  height: 40rpx;
  border-radius: 50%;
  background: #f2f4f7;
  color: #667085;
  font-size: 28rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.xiaonuo-draft-row {
  display: flex;
  align-items: flex-start;
  gap: 18rpx;
  margin: 4rpx 0 24rpx;
}

.xiaonuo-avatar {
  flex: none;
  width: 76rpx;
  height: 76rpx;
  margin-top: 4rpx;
}

.xiaonuo-bubble {
  flex: 1;
  min-width: 0;
  background: linear-gradient(135deg, #ffffff 0%, #f3f7ff 100%);
  border: 2rpx solid #dce7ff;
  border-radius: 8rpx 28rpx 28rpx 28rpx;
  padding: 18rpx 24rpx;
  box-shadow: 0 6rpx 24rpx rgba(45, 111, 255, 0.06);
}

.xiaonuo-bubble-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
  margin-bottom: 6rpx;
}

.xiaonuo-bubble-title {
  font-size: 24rpx;
  font-weight: 700;
  color: #1f2e4d;
}

.xiaonuo-bubble-back {
  flex: none;
  font-size: 23rpx;
  font-weight: 600;
  color: #2f6bff;
}

.xiaonuo-bubble-text {
  display: block;
  font-size: 23rpx;
  color: #5b6a84;
  line-height: 1.45;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24rpx;
}

.section-head-left {
  display: flex;
  align-items: center;
}

.section-bar {
  width: 8rpx;
  height: 32rpx;
  border-radius: 4rpx;
  background: #2f6bff;
  margin-right: 14rpx;
}

.section-title {
  font-size: 30rpx;
  font-weight: 600;
  color: #333;
}

.step-badge {
  height: 40rpx;
  padding: 0 16rpx;
  border-radius: 20rpx;
  font-size: 22rpx;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
}

.step-badge--soft {
  background: #eef4ff;
  color: #2f6bff;
}

.step-badge--done {
  background: #e8f8ed;
  color: #2b8a4e;
}

.pending-badge {
  display: inline-flex;
  align-items: center;
  height: 36rpx;
  padding: 0 14rpx;
  border-radius: 18rpx;
  background: #fff4e5;
  border: 2rpx solid #ffd59e;
  color: #c25e00;
  font-size: 20rpx;
  font-weight: 700;
  margin-left: 12rpx;
}

.field-pending {
  padding: 16rpx 20rpx;
  margin-left: -20rpx;
  margin-right: -20rpx;
  border-radius: 20rpx;
  background: #fffaf2;
  border: 2rpx solid #ffe0b5;
}

.restore-btn {
  height: 44rpx;
  padding: 0 16rpx;
  border-radius: 22rpx;
  background: #eef4ff;
  color: #2f6bff;
  font-size: 22rpx;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
}

.link-btn {
  font-size: 22rpx;
  color: #2f6bff;
  font-weight: 600;
}

.pill-group {
  display: flex;
  flex-wrap: wrap;
  gap: 16rpx;
}

.opt-pill {
  height: 60rpx;
  padding: 0 24rpx;
  border-radius: 30rpx;
  background: #fff;
  border: 2rpx solid #dfe3ec;
  font-size: 24rpx;
  color: #666;
  display: inline-flex;
  align-items: center;
}

.opt-pill--on {
  background: #dde7ff;
  border-color: transparent;
  color: $brand;
  font-weight: 600;
}

.multi-party-list {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.multi-party-row {
  display: flex;
  align-items: center;
  gap: 16rpx;
}

.party-rm-btn {
  flex: none;
  width: 56rpx;
  height: 56rpx;
  border-radius: 50%;
  background: #f2f4f7;
  color: #667085;
  font-size: 32rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.add-party-btn {
  margin-top: 12rpx;
  height: 56rpx;
  padding: 0 22rpx;
  border-radius: 28rpx;
  background: #f2f6ff;
  color: #2f6bff;
  font-size: 24rpx;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
}

.create-footer {
  flex: none;
  padding: 16rpx 32rpx calc(20rpx + env(safe-area-inset-bottom));
  background: rgba(255, 255, 255, 0.94);
  border-top: 2rpx solid #ecf0f8;
  box-shadow: 0 -8rpx 24rpx rgba(35, 70, 120, 0.04);
}

.create-footer-hint {
  display: block;
  text-align: center;
  font-size: 22rpx;
  color: #7b869c;
  margin-bottom: 12rpx;
}

.step-footer-row {
  display: flex;
  align-items: center;
  gap: 16rpx;
}

.btn-soft-back {
  flex: none;
  height: 88rpx;
  padding: 0 28rpx;
  border-radius: 44rpx;
  background: #f2f5fc;
  color: #4a5975;
  font-size: 26rpx;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.btn-primary {
  height: 88rpx;
  border-radius: 44rpx;
  background: $brand;
  color: #fff;
  font-size: 30rpx;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10rpx;
  box-shadow: 0 12rpx 28rpx rgba(33, 92, 255, 0.24);
}

.btn-primary--flex {
  flex: 1;
}

.btn-primary--disabled {
  opacity: 0.48;
  box-shadow: none;
}

.btn-sparkle {
  font-size: 28rpx;
  line-height: 1;
}
</style>
