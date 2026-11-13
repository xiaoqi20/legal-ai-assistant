<script setup lang="ts">
import { storeToRefs } from "pinia";
import { onMounted, ref } from "vue";
import AgreementBar from "./components/AgreementBar.vue";
import AgreementModal from "./components/AgreementModal.vue";
import { getNavMetrics } from "@/platform/wechat/nav";
import { devLogin, wechatLogin, type AuthTokenResponse } from "@/services/auth";
import { ApiError, USE_MOCK } from "@/services/request";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const { agreed, profile } = storeToRefs(auth);
const metrics = getNavMetrics();
const agreementModalVisible = ref(false);
const loggingIn = ref(false);

onMounted(() => {
  if (!USE_MOCK) {
    auth.ensureAgreements().catch(() => undefined);
  }
});

async function finishAuth(res: AuthTokenResponse) {
  const needsOnboarding = await auth.applyAuthToken(res);
  if (needsOnboarding) {
    uni.navigateTo({ url: "/pages/auth/role" });
    return;
  }
  uni.reLaunch({ url: "/pages/index/index" });
}

async function completeDevOrMockLogin() {
  if (USE_MOCK) {
    auth.loginMock(profile.value.phone);
    uni.navigateTo({ url: "/pages/auth/role" });
    return;
  }
  if (loggingIn.value) return;
  loggingIn.value = true;
  try {
    const res = await auth.withAgreementIds((docIds) =>
      devLogin("demo-user", docIds),
    );
    await finishAuth(res);
  } catch (error) {
    const msg =
      error instanceof ApiError && error.status === 404
        ? "请使用手机号验证码登录"
        : error instanceof Error
          ? error.message
          : "登录失败，请重试";
    uni.showToast({ title: msg, icon: "none" });
  } finally {
    loggingIn.value = false;
  }
}

function handleOneClickLogin() {
  if (!agreed.value) {
    agreementModalVisible.value = true;
    return;
  }
  void completeDevOrMockLogin();
}

function handleAgreeAndContinue() {
  auth.setAgreed(true);
  agreementModalVisible.value = false;
  // #ifdef MP-WEIXIN
  if (!USE_MOCK) {
    uni.showToast({ title: "已同意协议，请再次点击一键登录", icon: "none" });
    return;
  }
  // #endif
  void completeDevOrMockLogin();
}

// #ifdef MP-WEIXIN
function getWechatLoginCode(): Promise<string> {
  return new Promise((resolve, reject) => {
    uni.login({
      provider: "weixin",
      success: (res) => {
        if (res.code) resolve(res.code);
        else reject(new Error("获取微信登录凭证失败"));
      },
      fail: () => reject(new Error("微信登录调用失败")),
    });
  });
}

async function handleWechatPhoneNumber(event: {
  detail?: { code?: string; errMsg?: string };
}) {
  if (USE_MOCK) {
    auth.loginMock(profile.value.phone);
    uni.navigateTo({ url: "/pages/auth/role" });
    return;
  }
  const phoneCode = event?.detail?.code;
  if (!phoneCode) {
    await completeDevOrMockLogin();
    return;
  }
  if (loggingIn.value) return;
  loggingIn.value = true;
  try {
    const loginCode = await getWechatLoginCode();
    const res = await auth.withAgreementIds((docIds) =>
      wechatLogin(loginCode, phoneCode, docIds),
    );
    await finishAuth(res);
  } catch (error) {
    const msg = error instanceof Error ? error.message : "微信登录失败";
    uni.showToast({ title: msg, icon: "none" });
  } finally {
    loggingIn.value = false;
  }
}
// #endif

function openPhoneLogin() {
  uni.navigateTo({ url: "/pages/auth/phone-login" });
}
</script>

<template>
  <view
    class="page-shell login-page"
    :style="{ paddingTop: `${metrics.statusBarHeight}px` }"
  >
    <image class="login-logo" src="/static/images/logo.png" mode="aspectFit" />
    <text class="phone-big">{{ profile.phone || "135****8890" }}</text>
    <text class="phone-sub">
      {{ USE_MOCK ? "中国移动提供认证服务" : "微信/开发快捷登录认证" }}
    </text>

    <view class="actions">
      <!-- #ifdef MP-WEIXIN -->
      <button
        v-if="agreed && !USE_MOCK"
        class="btn-primary btn-native"
        open-type="getPhoneNumber"
        :disabled="loggingIn"
        @getphonenumber="handleWechatPhoneNumber"
      >
        {{ loggingIn ? "登录中..." : "本机号码一键登录" }}
      </button>
      <view v-else class="btn-primary" @click="handleOneClickLogin">
        {{ loggingIn ? "登录中..." : "本机号码一键登录" }}
      </view>
      <!-- #endif -->
      <!-- #ifndef MP-WEIXIN -->
      <view class="btn-primary" @click="handleOneClickLogin">
        {{ loggingIn ? "登录中..." : "本机号码一键登录" }}
      </view>
      <!-- #endif -->
      <view class="alt-link" @click="openPhoneLogin">其他手机号/账号登录</view>
    </view>

    <view class="agreement-wrap">
      <AgreementBar :checked="agreed" @toggle="auth.toggleAgreed()" />
    </view>

    <AgreementModal
      :visible="agreementModalVisible"
      @close="agreementModalVisible = false"
      @agree="handleAgreeAndContinue"
    />
  </view>
</template>

<style lang="scss" scoped>
.login-page {
  align-items: center;
  background: #fff;
}

.login-logo {
  width: 212rpx;
  height: 212rpx;
  margin-top: 148rpx;
}

.phone-big {
  margin-top: 114rpx;
  font-size: 60rpx;
  font-weight: 700;
  color: #1d1d1d;
  letter-spacing: 4rpx;
}

.phone-sub {
  margin-top: 28rpx;
  font-size: 28rpx;
  color: #9b9b9b;
}

.actions {
  width: 100%;
  padding: 0 80rpx;
  margin-top: 74rpx;
  display: flex;
  flex-direction: column;
  gap: 36rpx;
}

.btn-primary {
  height: 96rpx;
  border-radius: 52rpx;
  background: $brand;
  color: #fff;
  font-size: 32rpx;
  font-weight: 500;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 12rpx 32rpx rgba(33, 92, 255, 0.22);
}

.btn-native {
  width: 100%;
  margin: 0;
  padding: 0;
  border: none;
  line-height: normal;

  &::after {
    border: none;
  }
}

.alt-link {
  padding: 8rpx;
  text-align: center;
  font-size: 32rpx;
  color: $brand;
}

.agreement-wrap {
  position: absolute;
  left: 0;
  right: 0;
  bottom: calc(96rpx + env(safe-area-inset-bottom));
}
</style>
