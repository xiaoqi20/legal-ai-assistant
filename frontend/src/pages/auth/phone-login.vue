<script setup lang="ts">
import { onLoad, onUnload } from "@dcloudio/uni-app";
import { storeToRefs } from "pinia";
import { ref } from "vue";
import PageNav from "@/components/PageNav.vue";
import { sendSmsCode, smsLogin } from "@/services/auth";
import { USE_MOCK } from "@/services/request";
import { useAuthStore } from "@/stores/auth";
import AgreementBar from "./components/AgreementBar.vue";
import AgreementModal from "./components/AgreementModal.vue";

const auth = useAuthStore();
const { agreed } = storeToRefs(auth);

const phone = ref("");
const code = ref("");
const codeLeft = ref(0);
const sendingCode = ref(false);
const loggingIn = ref(false);
const agreementModalVisible = ref(false);
const pendingAction = ref<"sendCode" | "login">("login");

let codeTimer: ReturnType<typeof setInterval> | null = null;

function clearCodeTimer() {
  if (codeTimer) {
    clearInterval(codeTimer);
    codeTimer = null;
  }
}

onLoad(() => {
  if (!USE_MOCK) {
    auth.ensureAgreements().catch(() => undefined);
  }
});

onUnload(clearCodeTimer);

function startCountdown(seconds: number) {
  codeLeft.value = seconds;
  clearCodeTimer();
  codeTimer = setInterval(() => {
    codeLeft.value -= 1;
    if (codeLeft.value <= 0) {
      codeLeft.value = 0;
      clearCodeTimer();
    }
  }, 1000);
}

async function performSendCode() {
  const digits = phone.value.trim();
  if (USE_MOCK) {
    startCountdown(60);
    // ponytail: simulated SMS verification code for mock demo when VITE_USE_MOCK=true.
    uni.showToast({ title: "验证码已发送：1234", icon: "none" });
    return;
  }
  if (sendingCode.value) return;
  sendingCode.value = true;
  try {
    const res = await auth.withAgreementIds((docIds) =>
      sendSmsCode(digits, docIds),
    );
    startCountdown(res.retry_after_seconds || 60);
    const tip = res.mock && res.code ? `验证码已发送：${res.code}` : res.message;
    uni.showToast({ title: tip || "验证码已发送", icon: "none" });
  } catch (error) {
    const msg = error instanceof Error ? error.message : "发送验证码失败";
    uni.showToast({ title: msg, icon: "none" });
  } finally {
    sendingCode.value = false;
  }
}

function sendCode() {
  const digits = phone.value.trim();
  if (!/^1\d{10}$/.test(digits)) {
    uni.showToast({ title: "请输入正确的手机号", icon: "none" });
    return;
  }
  if (codeLeft.value > 0 || sendingCode.value) return;
  if (!USE_MOCK && !agreed.value) {
    pendingAction.value = "sendCode";
    agreementModalVisible.value = true;
    return;
  }
  void performSendCode();
}

async function completePhoneLogin() {
  const digits = phone.value.trim();
  const smsCode = code.value.trim();
  if (USE_MOCK) {
    auth.loginMock(digits);
    uni.navigateTo({ url: "/pages/auth/role" });
    return;
  }
  if (loggingIn.value) return;
  loggingIn.value = true;
  try {
    const res = await auth.withAgreementIds((docIds) =>
      smsLogin(digits, smsCode, docIds),
    );
    const needsOnboarding = await auth.applyAuthToken(res);
    if (needsOnboarding) {
      uni.navigateTo({ url: "/pages/auth/role" });
      return;
    }
    uni.reLaunch({ url: "/pages/index/index" });
  } catch (error) {
    const msg = error instanceof Error ? error.message : "登录失败，请重试";
    uni.showToast({ title: msg, icon: "none" });
  } finally {
    loggingIn.value = false;
  }
}

function submitLogin() {
  const digits = phone.value.trim();
  const smsCode = code.value.trim();
  if (!/^1\d{10}$/.test(digits)) {
    uni.showToast({ title: "请输入正确的手机号", icon: "none" });
    return;
  }
  const codeValid = USE_MOCK ? smsCode.length >= 4 : /^\d{6}$/.test(smsCode);
  if (!codeValid) {
    uni.showToast({
      title: USE_MOCK ? "请输入验证码" : "请输入6位数字验证码",
      icon: "none",
    });
    return;
  }
  if (!agreed.value) {
    pendingAction.value = "login";
    agreementModalVisible.value = true;
    return;
  }
  void completePhoneLogin();
}

function handleAgreeAndLogin() {
  auth.setAgreed(true);
  agreementModalVisible.value = false;
  if (pendingAction.value === "sendCode") {
    void performSendCode();
    return;
  }
  void completePhoneLogin();
}
</script>

<template>
  <view class="page-shell phone-login-page">
    <PageNav title="" fallback-url="/pages/auth/login" />

    <view class="phone-login-body">
      <text class="login-title">手机号登录</text>

      <view class="fields">
        <view class="field">
          <text class="prefix">+86</text>
          <view class="sep" />
          <input
            v-model="phone"
            class="field-input"
            type="number"
            maxlength="11"
            placeholder="请输入手机号码"
            placeholder-style="color:#C3C6CC"
          />
        </view>

        <view class="field">
          <input
            v-model="code"
            class="field-input"
            type="number"
            maxlength="6"
            placeholder="请输入验证码"
            placeholder-style="color:#C3C6CC"
          />
          <view
            class="code-btn"
            :class="{ 'code-btn--disabled': codeLeft > 0 }"
            @click="sendCode"
          >
            {{ codeLeft > 0 ? `${codeLeft}s 后重发` : "发送验证码" }}
          </view>
        </view>
      </view>

      <view class="btn-login" @click="submitLogin">登录</view>

      <view class="agreement-wrap">
        <AgreementBar
          :checked="agreed"
          bracketed
          @toggle="auth.toggleAgreed()"
        />
      </view>
    </view>

    <AgreementModal
      :visible="agreementModalVisible"
      @close="agreementModalVisible = false"
      @agree="handleAgreeAndLogin"
    />
  </view>
</template>

<style lang="scss" scoped>
.phone-login-page {
  background: #f7f7f9;
}

.phone-login-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding-bottom: calc(56rpx + env(safe-area-inset-bottom));
}

.login-title {
  display: block;
  margin-top: 120rpx;
  text-align: center;
  font-size: 48rpx;
  font-weight: 700;
  color: #2b2b2b;
}

.fields {
  display: flex;
  flex-direction: column;
  gap: 28rpx;
  padding: 0 80rpx;
  margin-top: 104rpx;
}

.field {
  height: 100rpx;
  padding: 0 36rpx;
  border-radius: 50rpx;
  background: #fff;
  display: flex;
  align-items: center;
  gap: 20rpx;
}

.prefix {
  flex: none;
  font-size: 30rpx;
  color: #333;
}

.sep {
  flex: none;
  width: 2rpx;
  height: 36rpx;
  background: #e8e8e8;
}

.field-input {
  flex: 1;
  min-width: 0;
  height: 100%;
  font-size: 30rpx;
  color: #333;
}

.code-btn {
  flex: none;
  height: 40rpx;
  padding-left: 24rpx;
  border-left: 2rpx solid #ececec;
  display: flex;
  align-items: center;
  font-size: 30rpx;
  color: $brand;
  white-space: nowrap;
}

.code-btn--disabled {
  color: #9ba3b2;
}

.btn-login {
  height: 96rpx;
  margin: 64rpx 80rpx 0;
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

.agreement-wrap {
  margin-top: auto;
  padding-top: 40rpx;
}
</style>
