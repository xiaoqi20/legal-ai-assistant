<script setup lang="ts">
const props = defineProps<{
  caseId: number;
}>();

function goCase() {
  uni.navigateTo({ url: `/pages/case/detail?id=${props.caseId}` });
}
</script>

<template>
  <view class="return-case" @click="goCase">
    <text>返回</text>
    <text>案件</text>
    <text class="chevron">›</text>
  </view>
</template>

<style lang="scss" scoped>
.return-case {
  position: absolute;
  right: 24rpx;
  bottom: calc(60rpx + env(safe-area-inset-bottom));
  z-index: 20;
  width: 108rpx;
  height: 108rpx;
  border-radius: 50%;
  background: rgba(92, 124, 255, 0.82);
  box-shadow: 0 12rpx 32rpx rgba(60, 90, 200, 0.28);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 20rpx;
  line-height: 1.25;
}

.chevron {
  font-size: 22rpx;
  line-height: 1;
}
</style>
