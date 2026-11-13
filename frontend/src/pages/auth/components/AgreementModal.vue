<script setup lang="ts">
defineProps<{
  visible: boolean;
}>();

const emit = defineEmits<{
  (e: "close"): void;
  (e: "agree"): void;
}>();

function openAgreement() {
  uni.navigateTo({ url: "/pages/agreement/index" });
}
</script>

<template>
  <view v-if="visible" class="modal-mask" @click="emit('close')">
    <view class="modal-card" @click.stop>
      <view class="modal-close" @click="emit('close')">×</view>
      <text class="modal-title">请阅读勾选协议</text>
      <view class="modal-sub">
        <text>已阅读</text>
        <text class="modal-link" @click="openAgreement">用户服务、隐私政策</text>
        <text> 和 </text>
        <text class="modal-link" @click="openAgreement">免费声明</text>
      </view>
      <view class="modal-actions">
        <view class="modal-btn modal-btn--ghost" @click="emit('close')">不同意</view>
        <view class="modal-btn modal-btn--primary" @click="emit('agree')">同意</view>
      </view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.modal-mask {
  position: absolute;
  inset: 0;
  z-index: 300;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.42);
}

.modal-card {
  position: relative;
  width: 516rpx;
  padding: 52rpx 44rpx 48rpx;
  border-radius: 6rpx;
  background: #fff;
  text-align: center;
  box-shadow: 0 40rpx 120rpx rgba(0, 0, 0, 0.18);
}

.modal-close {
  position: absolute;
  top: 20rpx;
  right: 20rpx;
  width: 56rpx;
  height: 56rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 40rpx;
  line-height: 1;
  color: #999;
}

.modal-title {
  display: block;
  margin-bottom: 28rpx;
  font-size: 34rpx;
  font-weight: 700;
  color: #2b2b2b;
}

.modal-sub {
  font-size: 22rpx;
  line-height: 1.7;
  color: #666;
  white-space: nowrap;
}

.modal-link {
  color: $brand;
}

.modal-actions {
  display: flex;
  gap: 24rpx;
  margin-top: 44rpx;
}

.modal-btn {
  flex: 1;
  height: 76rpx;
  border-radius: 38rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28rpx;
  font-weight: 500;
}

.modal-btn--ghost {
  border: 2rpx solid #e2e2e2;
  background: #fff;
  color: #333;
}

.modal-btn--primary {
  background: $brand;
  color: #fff;
  box-shadow: 0 12rpx 32rpx rgba(33, 92, 255, 0.22);
}
</style>
