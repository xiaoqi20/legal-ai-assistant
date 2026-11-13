<script setup lang="ts">
withDefaults(
  defineProps<{
    modelValue: string;
    placeholder?: string;
    button?: boolean;
    tone?: "white" | "gray";
  }>(),
  {
    placeholder: "请输入搜索内容",
    button: true,
    tone: "white",
  },
);

const emit = defineEmits<{
  (e: "update:modelValue", value: string): void;
  (e: "search"): void;
}>();

function onInput(event: { detail: { value: string } }) {
  emit("update:modelValue", event.detail.value);
}
</script>

<template>
  <view class="search-wrap">
    <view class="search-box" :class="{ 'search-box--gray': tone === 'gray' }">
      <view class="search-icon" />
      <input
        class="search-input"
        :value="modelValue"
        :placeholder="placeholder"
        placeholder-style="color:#AEB4BE"
        confirm-type="search"
        @input="onInput"
        @confirm="emit('search')"
      />
      <view v-if="button" class="search-btn" @click="emit('search')">
        搜索
      </view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.search-wrap {
  padding: 4rpx 36rpx 16rpx;
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

.search-box--gray {
  background: #f4f6fa;
  box-shadow: none;
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
</style>
