<script setup lang="ts">
import { computed } from "vue";
import WinRateDonut from "@/components/WinRateDonut.vue";
import {
  ANALYSIS_STATUS_META,
  EVIDENCE_STATUS_META,
  PROCEDURE_LABELS,
} from "@/constants/case";
import type { CaseSummary } from "@/types/case";

const props = defineProps<{
  item: CaseSummary;
  showCheck?: boolean;
  selected?: boolean;
}>();

const emit = defineEmits<{
  (e: "open", item: CaseSummary): void;
}>();

const status = computed(() => ANALYSIS_STATUS_META[props.item.analysis_status]);
const evidence = computed(() => {
  const base = EVIDENCE_STATUS_META[props.item.evidence_upload_status];
  if (props.item.evidence_label) {
    return { ...base, label: props.item.evidence_label };
  }
  return base;
});
const procedure = computed(
  () => props.item.procedure_label || PROCEDURE_LABELS[props.item.procedure] || "其他",
);
</script>

<template>
  <view class="case-card" @click="emit('open', item)">
    <view v-if="showCheck" class="check" :class="{ 'check--on': selected }">
      <text v-if="selected" class="check-mark">✓</text>
    </view>
    <view class="status-pill" :class="`status-pill--${status.tone}`">
      {{ status.label }}
    </view>

    <text class="case-title" :class="{ 'case-title--checked': showCheck }">
      {{ item.title }}
    </text>
    <view class="case-row">
      <text class="row-label">证据上传：</text>
      <text class="row-value" :class="{ 'row-value--danger': !evidence.complete }">
        {{ evidence.label }}
      </text>
    </view>
    <view class="case-row">
      <text class="row-label">案件程序：</text>
      <text class="row-value">{{ procedure }}</text>
    </view>

    <WinRateDonut
      class="case-donut"
      :status="item.analysis_status"
      :win-rate-status="item.win_rate_status"
      :win-rate="item.win_rate"
    />
  </view>
</template>

<style lang="scss" scoped>
.case-card {
  position: relative;
  min-height: 254rpx;
  padding: 28rpx 52rpx 20rpx;
  border-radius: 26rpx;
  background: #fff;
  box-shadow: 0 4rpx 12rpx rgba(0, 0, 0, 0.05);
  overflow: hidden;
}

.status-pill {
  position: absolute;
  top: 0;
  right: 0;
  height: 44rpx;
  padding: 0 24rpx;
  border-radius: 24rpx 0 0 24rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24rpx;
  color: #fff;
}

.status-pill--green {
  background: $success;
}

.status-pill--pink {
  background: $pink;
}

.status-pill--lavender {
  background: $lavender;
}

.status-pill--red {
  background: #f08a8a;
}

.case-title {
  display: block;
  margin: 20rpx 0;
  padding-right: 120rpx;
  font-size: 30rpx;
  font-weight: 700;
  line-height: 1.4;
  color: #333;
}

.case-title--checked {
  padding-left: 48rpx;
}

.check {
  position: absolute;
  top: 20rpx;
  left: 20rpx;
  z-index: 3;
  width: 40rpx;
  height: 40rpx;
  border: 3rpx solid #d7dbe2;
  border-radius: 50%;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
}

.check--on {
  border-color: $brand;
  background: $brand;
}

.check-mark {
  font-size: 24rpx;
  font-weight: 700;
  line-height: 1;
  color: #fff;
}

.case-row {
  display: flex;
  align-items: baseline;
  margin: 10rpx 0;
  font-size: 24rpx;
  line-height: 1.4;
}

.row-label {
  color: $text-secondary;
}

.row-value {
  color: $brand;
}

.row-value--danger {
  color: #f05b5b;
}

.case-donut {
  position: absolute;
  right: 96rpx;
  bottom: 20rpx;
}
</style>
