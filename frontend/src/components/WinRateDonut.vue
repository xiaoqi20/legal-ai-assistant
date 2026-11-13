<script setup lang="ts">
import { computed } from "vue";
import type { CaseAnalysisStatus } from "@/types/case";

const props = withDefaults(
  defineProps<{
    status: CaseAnalysisStatus;
    winRate?: number | null;
    large?: boolean;
  }>(),
  {
    winRate: null,
    large: false,
  },
);

const progress = computed(() => {
  if (props.status === "analyzed" && props.winRate != null) {
    return Math.min(Math.max(props.winRate, 0), 100) / 100;
  }
  if (props.status === "analyzing") return 0.72;
  if (props.status === "not_analyzed") return 0.56;
  return 0.08;
});

const color = computed(() => {
  if (props.status === "not_analyzed") return "#B9D7FF";
  if (props.status === "failed") return "#F6AFAF";
  return "#2F6BFF";
});

const ringStyle = computed(() => ({
  background: `conic-gradient(${color.value} 0turn ${progress.value}turn, #E9F1FF ${progress.value}turn 1turn)`,
}));

const valueText = computed(() => {
  if (props.winRate == null) return "—";
  return `${Math.round(props.winRate)}%`;
});
</script>

<template>
  <view class="donut" :class="{ 'donut--large': large }">
    <view class="ring" :style="ringStyle" />
    <view class="hole">
      <text v-if="status === 'analyzed'" class="value">{{ valueText }}</text>
      <text v-else-if="status === 'analyzing'" class="value value--small">
        分析中
      </text>
      <text v-else-if="status === 'failed'" class="value value--small">
        分析失败
      </text>
      <text v-else class="value value--question">?</text>
      <text class="caption">胜诉率</text>
    </view>
    <image
      class="ticks"
      src="/static/images/donut-ticks.png"
      mode="aspectFit"
    />
    <view class="cap" :style="{ borderBottomColor: color }" />
  </view>
</template>

<style lang="scss" scoped>
.donut {
  position: relative;
  flex: none;
  width: 140rpx;
  height: 140rpx;
}

.ring {
  position: absolute;
  inset: 0;
  border-radius: 50%;
}

.hole {
  position: absolute;
  inset: 8rpx;
  border-radius: 50%;
  background: #fff;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.value {
  font-size: 40rpx;
  font-weight: 700;
  line-height: 1.1;
  color: $brand;
}

.value--question {
  font-size: 48rpx;
  font-weight: 600;
}

.value--small {
  font-size: 24rpx;
  font-weight: 600;
}

.caption {
  margin-top: 4rpx;
  font-size: 18rpx;
  line-height: 1;
  color: $text-secondary;
}

.ticks {
  position: absolute;
  top: 10%;
  left: 9%;
  width: 82%;
  height: 80%;
  opacity: 0.95;
}

.donut--large {
  width: 300rpx;
  height: 300rpx;
}

.donut--large .hole {
  inset: 16rpx;
}

.donut--large .value {
  font-size: 68rpx;
}

.donut--large .value--small {
  font-size: 36rpx;
}

.donut--large .value--question {
  font-size: 76rpx;
}

.donut--large .caption {
  font-size: 24rpx;
}

.donut--large .cap {
  top: -6rpx;
  border-left-width: 12rpx;
  border-right-width: 12rpx;
  border-bottom-width: 18rpx;
}

.cap {
  position: absolute;
  top: -4rpx;
  left: 50%;
  width: 0;
  height: 0;
  border-left: 8rpx solid transparent;
  border-right: 8rpx solid transparent;
  border-bottom: 12rpx solid $brand-bright;
  transform: translateX(-50%);
}
</style>
