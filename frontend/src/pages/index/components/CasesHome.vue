<script setup lang="ts">
import { onMounted, ref } from "vue";
import { storeToRefs } from "pinia";
import CaseCard from "./CaseCard.vue";
import ComposerBar from "@/components/ComposerBar.vue";
import ConfirmDialog from "@/components/ConfirmDialog.vue";
import { fetchCases } from "@/services/cases";
import { useHomeStore } from "@/stores/home";
import type { CaseSummary } from "@/types/case";
import { getGreeting } from "@/utils/greeting";

const home = useHomeStore();
const { caseKeyword, caseDraft } = storeToRefs(home);

const cases = ref<CaseSummary[]>([]);
const loading = ref(false);
const errorMessage = ref("");
const caseAlertVisible = ref(false);
const selectingCase = ref(false);
const greeting = getGreeting();

let requestId = 0;

async function loadCases() {
  const current = ++requestId;
  loading.value = true;
  errorMessage.value = "";

  try {
    const result = await fetchCases(caseKeyword.value);
    if (current === requestId) cases.value = result;
  } catch (error) {
    if (current === requestId) {
      errorMessage.value =
        error instanceof Error ? error.message : "案件加载失败";
    }
  } finally {
    if (current === requestId) loading.value = false;
  }
}

function openCase(item: CaseSummary) {
  if (!selectingCase.value) {
    uni.navigateTo({ url: `/pages/case/detail?id=${item.id}` });
    return;
  }
  if (item.analysis_status !== "analyzed") {
    uni.showToast({ title: "该案件尚未完成分析，请稍后再试", icon: "none" });
    return;
  }
  const question = caseDraft.value.trim();
  selectingCase.value = false;
  if (!question) return;
  caseDraft.value = "";
  uni.navigateTo({
    url: `/pages/chat/index?mode=case&caseId=${item.id}&q=${encodeURIComponent(question)}`,
  });
}

function openAttach() {
  uni.showActionSheet({
    itemList: ["拍照", "相册", "文档", "通话"],
    success: () => {
      uni.showToast({ title: "能力待接入", icon: "none" });
    },
  });
}

function send() {
  const question = caseDraft.value.trim();
  if (!question) {
    uni.showToast({ title: "请输入咨询内容", icon: "none" });
    return;
  }
  caseAlertVisible.value = true;
}

function confirmCaseAlert() {
  caseAlertVisible.value = false;
  selectingCase.value = true;
}

function cancelSelection() {
  selectingCase.value = false;
}

function openMic() {
  uni.showToast({ title: "语音待接入", icon: "none" });
}

onMounted(loadCases);
</script>

<template>
  <view class="cases-tab">
    <scroll-view scroll-y class="tab-scroll" :show-scrollbar="false">
      <view class="hero">
        <image
          class="hero-robot"
          src="/static/images/robot.png"
          mode="aspectFit"
        />
        <view class="hero-copy">
          <text class="hero-title">Hi～我是小诺！</text>
          <text class="hero-sub">
            {{ greeting }}！我是您的案件智能小助手，您可以基于案件咨询你要问询的问题
          </text>
        </view>
      </view>

      <view class="search-wrap">
        <view class="search-box">
          <view class="search-icon" />
          <input
            v-model="caseKeyword"
            class="search-input"
            placeholder="请输入搜索内容"
            placeholder-style="color:#AEB4BE"
            confirm-type="search"
            @confirm="loadCases"
          />
          <view class="search-btn" @click="loadCases">搜索</view>
        </view>
      </view>

      <view v-if="loading" class="state-block">加载中…</view>

      <view v-else-if="errorMessage" class="state-block">
        <text>{{ errorMessage }}</text>
        <view class="retry" @click="loadCases">重试</view>
      </view>

      <view v-else-if="!cases.length" class="state-block">
        没有找到相关案件
      </view>

      <view v-else class="case-list">
        <view v-if="selectingCase" class="select-tip">
          <text class="select-tip-text">请选择一个已分析案件进行问答</text>
          <text class="select-tip-cancel" @click="cancelSelection">取消</text>
        </view>
        <view v-for="item in cases" :key="item.id" class="case-item">
          <CaseCard
            :item="item"
            :show-check="selectingCase"
            :selected="false"
            @open="openCase"
          />
        </view>
      </view>

      <view class="scroll-tail" />
    </scroll-view>

    <ComposerBar
      v-model="caseDraft"
      placeholder="关于案件，有什么想要咨询的？"
      @send="send"
      @toggle-attach="openAttach"
      @mic="openMic"
    />

    <ConfirmDialog
      :visible="caseAlertVisible"
      title="请先选择对应案件进行问答"
      :show-cancel="false"
      @confirm="confirmCaseAlert"
      @cancel="caseAlertVisible = false"
    />
  </view>
</template>

<style lang="scss" scoped>
.cases-tab {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.tab-scroll {
  flex: 1;
  height: 0;
}

.hero {
  display: flex;
  align-items: flex-start;
  padding: 4rpx 36rpx 8rpx 40rpx;
  margin-top: -34rpx;
}

.hero-robot {
  flex: none;
  width: 198rpx;
  height: 226rpx;
  margin-top: 4rpx;
}

.hero-copy {
  flex: 1;
  min-width: 0;
  padding: 56rpx 0 0 20rpx;
}

.hero-title {
  display: block;
  font-size: 44rpx;
  font-weight: 700;
  line-height: 1.3;
  letter-spacing: 0.2rpx;
  color: #2d2d2d;
}

.hero-sub {
  display: block;
  max-width: 436rpx;
  margin-top: 12rpx;
  font-size: 24rpx;
  line-height: 1.45;
  color: #333;
}

.search-wrap {
  padding: 4rpx 36rpx 8rpx;
}

.search-box {
  height: 88rpx;
  padding: 0 10rpx 0 28rpx;
  border-radius: 44rpx;
  background: #fff;
  box-shadow: 0 8rpx 32rpx rgba(40, 80, 150, 0.09);
  display: flex;
  align-items: center;
}

.search-icon {
  position: relative;
  flex: none;
  width: 30rpx;
  height: 30rpx;
  margin-right: 16rpx;
  border: 4rpx solid #9aa1ad;
  border-radius: 50%;

  &::after {
    content: "";
    position: absolute;
    right: -8rpx;
    bottom: -8rpx;
    width: 4rpx;
    height: 14rpx;
    border-radius: 2rpx;
    background: #9aa1ad;
    transform: rotate(-45deg);
  }
}

.search-input {
  flex: 1;
  min-width: 0;
  height: 100%;
  font-size: 28rpx;
  color: $text;
}

.search-btn {
  flex: none;
  height: 68rpx;
  padding: 0 34rpx;
  border-radius: 34rpx;
  background: #2f7cf6;
  color: #fff;
  font-size: 28rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.case-list {
  padding: 0 14rpx;
}

.select-tip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 4rpx 8rpx 16rpx;
  padding: 14rpx 24rpx;
  border-radius: 16rpx;
  background: $brand-soft;
  font-size: 24rpx;
}

.select-tip-text {
  color: $brand;
  font-weight: 500;
}

.select-tip-cancel {
  color: $text-secondary;
  padding-left: 16rpx;
}

.case-item + .case-item {
  margin-top: 26rpx;
}

.state-block {
  padding: 100rpx 36rpx;
  text-align: center;
  font-size: 26rpx;
  color: $muted;
}

.retry {
  margin-top: 16rpx;
  color: $brand;
}

.scroll-tail {
  height: 24rpx;
}
</style>
