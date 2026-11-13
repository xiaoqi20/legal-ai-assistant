<script setup lang="ts">
import { onMounted, ref } from "vue";
import { storeToRefs } from "pinia";
import ComposerBar from "@/components/ComposerBar.vue";
import { fetchRecommendations } from "@/services/assistant";
import { useHomeStore } from "@/stores/home";

const home = useHomeStore();
const { assistantDraft } = storeToRefs(home);

const emit = defineEmits<{
  (e: "start-chat", question: string): void;
}>();

const recommendations = ref<string[]>([]);
const attachOpen = ref(false);

const attachActions = [
  { label: "拍照", icon: "camera" },
  { label: "相册", icon: "album" },
  { label: "文档", icon: "doc" },
  { label: "通话", icon: "call" },
];

onMounted(async () => {
  recommendations.value = await fetchRecommendations();
});

function pickRecommendation(question: string) {
  emit("start-chat", question);
}

function toggleAttach() {
  attachOpen.value = !attachOpen.value;
}

function pickAttach() {
  attachOpen.value = false;
  uni.showToast({ title: "能力待接入", icon: "none" });
}

function openHistory() {
  uni.navigateTo({ url: "/pages/history/index" });
}

function send() {
  const question = assistantDraft.value.trim();
  if (!question) return;
  assistantDraft.value = "";
  emit("start-chat", question);
}

function openMic() {
  uni.showToast({ title: "语音待接入", icon: "none" });
}
</script>

<template>
  <view class="assistant-tab">
    <scroll-view scroll-y class="tab-scroll" :show-scrollbar="false">
      <view class="assistant-hero">
        <view class="hero-copy">
          <text class="hero-title">Hi～我是小诺！</text>
          <text class="hero-sub">
            您可以向我咨询任何法律问题哦，我能提供案件梳理、证据分析、法律文书书写～
          </text>
        </view>
        <image
          class="hero-robot"
          src="/static/images/robot.png"
          mode="aspectFit"
        />
      </view>

      <view class="rec-card">
        <text class="rec-title">推荐问</text>
        <view class="rec-list">
          <view
            v-for="question in recommendations"
            :key="question"
            class="rec-item"
            @click="pickRecommendation(question)"
          >
            <view class="rec-dot" />
            <text class="rec-text">{{ question }}</text>
          </view>
        </view>
      </view>

      <view class="history-hint" @click="openHistory">
        – 历史对话，下拉回顾 –
      </view>

      <view class="scroll-tail" />
    </scroll-view>

    <ComposerBar
      v-model="assistantDraft"
      placeholder="请在此输入您的提问～"
      solid
      @send="send"
      @toggle-attach="toggleAttach"
      @mic="openMic"
    >
      <view v-if="attachOpen" class="attach-panel">
        <view
          v-for="action in attachActions"
          :key="action.label"
          class="attach-btn"
          @click="pickAttach"
        >
          <view class="attach-icon" :class="`attach-icon--${action.icon}`" />
          <text class="attach-label">{{ action.label }}</text>
        </view>
      </view>
    </ComposerBar>
  </view>
</template>

<style lang="scss" scoped>
.assistant-tab {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.tab-scroll {
  flex: 1;
  height: 0;
}

.assistant-hero {
  position: relative;
  min-height: 356rpx;
  padding: 12rpx 36rpx 0;
}

.hero-copy {
  position: relative;
  z-index: 2;
  max-width: 440rpx;
  padding: 12rpx 0 0 10rpx;
}

.hero-title {
  display: block;
  font-size: 44rpx;
  font-weight: 700;
  line-height: 1.3;
  color: #2d2d2d;
}

.hero-sub {
  display: block;
  margin-top: 4rpx;
  font-size: 22rpx;
  line-height: 1.7;
  color: #333;
}

.hero-robot {
  position: absolute;
  z-index: 1;
  top: -76rpx;
  right: -16rpx;
  width: 330rpx;
  height: 364rpx;
}

.rec-card {
  position: relative;
  z-index: 3;
  margin: -68rpx 36rpx 0;
  padding: 32rpx 32rpx 28rpx;
  border-radius: $card-radius;
  background: linear-gradient(135deg, #e6f3ff 0%, #f4f8ff 48%, #fdfdff 100%);
  box-shadow: 0 12rpx 40rpx rgba(50, 90, 160, 0.07);
}

.rec-title {
  font-size: 32rpx;
  font-weight: 700;
  color: #333;
}

.rec-list {
  margin-top: 24rpx;
}

.rec-item {
  display: flex;
  align-items: flex-start;
}

.rec-item + .rec-item {
  margin-top: 24rpx;
}

.rec-dot {
  flex: none;
  width: 10rpx;
  height: 10rpx;
  margin: 12rpx 16rpx 0 2rpx;
  border-radius: 50%;
  background: $brand-bright;
}

.rec-text {
  font-size: 28rpx;
  line-height: 1.5;
  color: #333;
}

.history-hint {
  margin-top: 44rpx;
  text-align: center;
  font-size: 22rpx;
  color: #9aa1ad;
}

.scroll-tail {
  height: 24rpx;
}

.attach-panel {
  display: flex;
  padding: 12rpx 0 4rpx;
}

.attach-btn {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 18rpx 0;
  border: 1rpx solid #ebedf1;
  border-radius: 20rpx;
  background: #fff;

  & + & {
    margin-left: 14rpx;
  }
}

.attach-icon {
  position: relative;
  width: 40rpx;
  height: 40rpx;
  margin-bottom: 10rpx;
}

.attach-label {
  font-size: 22rpx;
  color: #5e6673;
}

.attach-icon--camera {
  height: 32rpx;
  border: 3rpx solid #5e6673;
  border-radius: 8rpx;

  &::before {
    content: "";
    position: absolute;
    top: 50%;
    left: 50%;
    width: 14rpx;
    height: 14rpx;
    border: 3rpx solid #5e6673;
    border-radius: 50%;
    transform: translate(-50%, -50%);
  }
}

.attach-icon--album {
  border: 3rpx solid #5e6673;
  border-radius: 6rpx;

  &::before {
    content: "";
    position: absolute;
    top: 8rpx;
    right: 8rpx;
    width: 6rpx;
    height: 6rpx;
    border-radius: 50%;
    background: #5e6673;
  }

  &::after {
    content: "";
    position: absolute;
    left: 6rpx;
    bottom: 6rpx;
    width: 0;
    height: 0;
    border-left: 12rpx solid transparent;
    border-right: 12rpx solid transparent;
    border-bottom: 14rpx solid #5e6673;
  }
}

.attach-icon--doc {
  width: 32rpx;
  height: 40rpx;
  margin-left: 4rpx;
  border: 3rpx solid #5e6673;
  border-radius: 4rpx;

  &::before,
  &::after {
    content: "";
    position: absolute;
    left: 7rpx;
    width: 16rpx;
    height: 3rpx;
    background: #5e6673;
  }

  &::before {
    top: 12rpx;
  }

  &::after {
    top: 21rpx;
  }
}

.attach-icon--call {
  border: 3rpx solid #5e6673;
  border-radius: 50%;

  &::before {
    content: "";
    position: absolute;
    left: 50%;
    bottom: -2rpx;
    width: 14rpx;
    height: 14rpx;
    border-right: 3rpx solid #5e6673;
    border-bottom: 3rpx solid #5e6673;
    transform: translateX(-50%) rotate(45deg);
  }
}
</style>
