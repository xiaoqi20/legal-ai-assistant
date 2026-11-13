<script setup lang="ts">
defineProps<{
  checked: boolean;
  bracketed?: boolean;
}>();

const emit = defineEmits<{
  (e: "toggle"): void;
}>();

function openAgreement() {
  uni.navigateTo({ url: "/pages/agreement/index" });
}
</script>

<template>
  <view class="agreement-row">
    <view
      class="checkbox"
      :class="{ 'checkbox--on': checked }"
      @click="emit('toggle')"
    >
      <text v-if="checked" class="checkbox-mark">✓</text>
    </view>
    <view class="agreement-text">
      <text>未注册手机号验证通过后将自动注册，并同意</text>
      <text class="agreement-link" @click="openAgreement">
        {{ bracketed ? "《用户服务》" : "用户服务" }}
      </text>
      <text>{{ bracketed ? " 和 " : "、" }}</text>
      <text class="agreement-link" @click="openAgreement">
        {{ bracketed ? "《隐私政策》" : "隐私政策" }}
      </text>
      <text> 和 </text>
      <text class="agreement-link" @click="openAgreement">
        {{ bracketed ? "《免费声明》" : "免费声明" }}
      </text>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.agreement-row {
  display: flex;
  align-items: flex-start;
  gap: 16rpx;
  padding: 0 44rpx;
  font-size: 24rpx;
  line-height: 1.65;
  color: #a6aab3;
}

.checkbox {
  flex: none;
  width: 40rpx;
  height: 40rpx;
  margin-top: 2rpx;
  border: 3rpx solid #d7d9df;
  border-radius: 50%;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
}

.checkbox--on {
  border-color: $brand;
  background: $brand;
}

.checkbox-mark {
  font-size: 24rpx;
  font-weight: 700;
  line-height: 1;
  color: #fff;
}

.agreement-text {
  flex: 1;
  min-width: 0;
}

.agreement-link {
  color: $brand;
}
</style>
