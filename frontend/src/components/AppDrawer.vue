<script setup lang="ts">
import { computed, ref } from "vue";
import ConfirmDialog from "@/components/ConfirmDialog.vue";
import { getNavMetrics } from "@/platform/wechat/nav";
import { fetchProfile } from "@/services/profile";
import type { UserProfile } from "@/types/user";

defineProps<{
  visible: boolean;
}>();

const emit = defineEmits<{
  (e: "close"): void;
  (e: "select-tab", tab: "cases" | "assistant"): void;
  (e: "history"): void;
  (e: "profile"): void;
  (e: "legacy"): void;
  (e: "logout"): void;
}>();

const metrics = getNavMetrics();
const profile = ref<UserProfile | null>(null);
const logoutVisible = ref(false);

fetchProfile().then((data) => {
  profile.value = data;
});

const roleText = computed(() => {
  const roleLabel = profile.value?.role_label || "企业";
  const detail =
    profile.value?.position || profile.value?.legal_role || "用户";
  return `${roleLabel} · ${detail}`;
});

function close() {
  emit("close");
}

function selectTab(tab: "cases" | "assistant") {
  close();
  emit("select-tab", tab);
}

function goHistory() {
  close();
  emit("history");
}

function goProfile() {
  close();
  emit("profile");
}

function goLegacy() {
  close();
  emit("legacy");
}

function confirmLogout() {
  logoutVisible.value = false;
  close();
  emit("logout");
}
</script>

<template>
  <view v-if="visible" class="drawer-layer">
    <view class="drawer-mask" @click="close" />
    <view
      class="drawer-panel"
      :style="{ paddingTop: `${metrics.statusBarHeight + 20}px` }"
      @click.stop
    >
      <view class="drawer-user">
        <image
          class="drawer-avatar"
          :src="profile?.avatar_url || '/static/images/avatar.jpg'"
          mode="aspectFill"
        />
        <view class="drawer-meta">
          <text class="drawer-name">{{ profile?.display_name }}</text>
          <text class="drawer-role">{{ roleText }}</text>
        </view>
      </view>

      <view class="drawer-nav">
        <view class="drawer-item" @click="selectTab('cases')">
          <image class="drawer-icon" src="/static/images/icons/drawer-cases.png" />
          <text>案件</text>
        </view>
        <view class="drawer-item" @click="selectTab('assistant')">
          <image class="drawer-icon" src="/static/images/icons/drawer-assistant.png" />
          <text>助手</text>
        </view>
        <view class="drawer-item" @click="goHistory">
          <image class="drawer-icon" src="/static/images/icons/drawer-history.png" />
          <text>历史记录</text>
        </view>
        <view class="drawer-item" @click="goProfile">
          <image class="drawer-icon" src="/static/images/icons/drawer-profile.png" />
          <text>个人中心</text>
        </view>
        <view class="drawer-item" @click="goLegacy">
          <image class="drawer-icon" src="/static/images/icons/drawer-legacy.png" />
          <text>旧版案情梳理</text>
        </view>
      </view>

      <view class="drawer-logout" @click="logoutVisible = true">退出登录</view>
    </view>

    <ConfirmDialog
      :visible="logoutVisible"
      title="确定退出当前账号？"
      @cancel="logoutVisible = false"
      @confirm="confirmLogout"
    />
  </view>
</template>

<style lang="scss" scoped>
.drawer-layer {
  position: absolute;
  inset: 0;
  z-index: 250;
}

.drawer-mask {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.36);
  animation: drawerFade 0.15s ease;
}

.drawer-panel {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  z-index: 260;
  width: 282px;
  padding: 0 18px 30px;
  display: flex;
  flex-direction: column;
  background: #fff;
  box-shadow: 14px 0 40px rgba(0, 0, 0, 0.12);
  animation: drawerIn 0.2s ease;
}

.drawer-user {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-bottom: 20px;
  border-bottom: 1px solid #eef0f4;
}

.drawer-avatar {
  flex: none;
  width: 48px;
  height: 48px;
  border-radius: 50%;
}

.drawer-meta {
  display: flex;
  flex-direction: column;
}

.drawer-name {
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.drawer-role {
  margin-top: 3px;
  font-size: 12px;
  color: #999;
}

.drawer-nav {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: 14px;
}

.drawer-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 10px;
  border-radius: 12px;
  font-size: 15px;
  color: #333;
}

.drawer-item:active {
  background: #f4f7ff;
}

.drawer-icon {
  flex: none;
  width: 24px;
  height: 24px;
}

.drawer-logout {
  padding: 12px 10px;
  font-size: 14px;
  color: #8b8f98;
}

@keyframes drawerFade {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes drawerIn {
  from {
    transform: translateX(-100%);
  }
  to {
    transform: none;
  }
}
</style>
