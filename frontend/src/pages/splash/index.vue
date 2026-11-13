<script setup lang="ts">
import { onHide, onShow, onUnload } from "@dcloudio/uni-app";
import { getNavMetrics } from "@/platform/wechat/nav";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const metrics = getNavMetrics();

let timer: ReturnType<typeof setTimeout> | null = null;
let navigated = false;

function clearTimer() {
  if (timer) {
    clearTimeout(timer);
    timer = null;
  }
}

function proceed() {
  if (navigated) return;
  navigated = true;
  clearTimer();
  const target = auth.isLoggedIn ? "/pages/index/index" : "/pages/auth/login";
  uni.reLaunch({ url: target });
}

onShow(() => {
  navigated = false;
  clearTimer();
  timer = setTimeout(proceed, 1800);
});

onHide(clearTimer);
onUnload(clearTimer);
</script>

<template>
  <view
    class="page-shell splash-page"
    :style="{ paddingTop: `${metrics.statusBarHeight}px` }"
    @click="proceed"
  >
    <image class="splash-robot" src="/static/images/robot.png" mode="aspectFit" />
    <text class="splash-title">您最可靠的案件助手!</text>
    <text class="splash-brand">欢迎来到 AI 英诺律法</text>
  </view>
</template>

<style lang="scss" scoped>
.splash-page {
  align-items: center;
  justify-content: flex-start;
  background:
    radial-gradient(
      120% 70% at 50% 8%,
      #dff3ff 0%,
      rgba(223, 243, 255, 0) 65%
    ),
    linear-gradient(180deg, #f2fbff 0%, #ffffff 60%, #fdfeff 100%);
}

.splash-robot {
  width: 300rpx;
  height: 300rpx;
  margin-top: 184rpx;
  filter: drop-shadow(0 36rpx 52rpx rgba(60, 130, 255, 0.14));
}

.splash-title {
  margin: 52rpx 0 16rpx;
  font-size: 34rpx;
  font-weight: 600;
  color: #333;
  letter-spacing: 2rpx;
}

.splash-brand {
  font-size: 44rpx;
  font-weight: 600;
  color: #2f6bff;
  letter-spacing: 8rpx;
}
</style>
