<script setup lang="ts">
import { getNavMetrics } from "@/platform/wechat/nav";

const props = withDefaults(
  defineProps<{
    title: string;
    fallbackUrl?: string;
  }>(),
  {
    fallbackUrl: "/pages/index/index",
  },
);

const emit = defineEmits<{
  (e: "back"): void;
}>();

const metrics = getNavMetrics();

function goBack() {
  emit("back");
  const pages = getCurrentPages();
  if (pages.length > 1) {
    uni.navigateBack();
    return;
  }
  uni.reLaunch({ url: props.fallbackUrl });
}
</script>

<template>
  <view
    class="page-nav"
    :style="{ paddingTop: `${metrics.statusBarHeight}px` }"
  >
    <view
      class="nav-bar"
      :style="{
        height: `${metrics.navBarHeight}px`,
        paddingRight: metrics.capsuleInset
          ? `${metrics.capsuleInset}px`
          : undefined,
      }"
    >
      <view class="nav-side">
        <view class="nav-back" @click="goBack">
          <image class="back-icon" src="/static/images/icons/nav-back.png" mode="aspectFit" />
        </view>
      </view>
      <text class="nav-title">{{ title }}</text>
      <view class="nav-side nav-side--right">
        <slot />
      </view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.page-nav {
  flex: none;
  position: relative;
  z-index: 10;
}

.nav-bar {
  display: flex;
  align-items: center;
  padding: 0 18px;
  box-sizing: border-box;
}

.nav-side {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
}

.nav-side--right {
  justify-content: flex-end;
}

.nav-back {
  width: 36px;
  height: 36px;
  margin-left: -8px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.back-icon {
  width: 24px;
  height: 24px;
}

.nav-title {
  flex: 1;
  text-align: center;
  font-size: 17px;
  font-weight: 600;
  color: #2f2f2f;
  letter-spacing: 0.3px;
}
</style>
