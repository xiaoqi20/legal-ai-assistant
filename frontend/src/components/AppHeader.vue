<script setup lang="ts">
import { getNavMetrics } from "@/platform/wechat/nav";
import type { HomeTab } from "@/types/home";

defineProps<{
  active: HomeTab;
}>();

const emit = defineEmits<{
  (e: "update:active", tab: HomeTab): void;
  (e: "menu"): void;
  (e: "profile"): void;
}>();

const metrics = getNavMetrics();
</script>

<template>
  <view
    class="app-header"
    :style="{ paddingTop: `${metrics.statusBarHeight}px` }"
  >
    <view
      class="header-bar"
      :style="{
        height: `${metrics.navBarHeight}px`,
        paddingRight: metrics.capsuleInset
          ? `${metrics.capsuleInset}px`
          : undefined,
      }"
    >
      <view class="menu" @click="emit('menu')">
        <image class="menu-icon" src="/static/images/icons/menu.png" mode="aspectFit" />
      </view>

      <view class="tabs">
        <view
          class="tab"
          :class="{ 'tab--active': active === 'cases' }"
          @click="emit('update:active', 'cases')"
        >
          <text class="tab-text">案件</text>
          <view v-if="active === 'cases'" class="tab-underline" />
        </view>
        <view
          class="tab"
          :class="{ 'tab--active': active === 'assistant' }"
          @click="emit('update:active', 'assistant')"
        >
          <text class="tab-text">助手</text>
          <view v-if="active === 'assistant'" class="tab-underline" />
        </view>
      </view>

      <image
        class="avatar"
        src="/static/images/avatar.jpg"
        mode="aspectFill"
        @click="emit('profile')"
      />
    </view>
  </view>
</template>

<style lang="scss" scoped>
.app-header {
  flex: none;
  position: relative;
  z-index: 10;
}

.header-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 18px;
  box-sizing: border-box;
}

.menu {
  width: 26px;
  height: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
}

.menu-icon {
  width: 24px;
  height: 24px;
}

.tabs {
  flex: 1;
  min-width: 0;
  height: 100%;
  display: flex;
  align-items: flex-end;
  margin-left: 8px;
  padding-top: 2px;
}

.tab {
  position: relative;
  display: flex;
  padding: 0 6px 8px;
}

.tab + .tab {
  margin-left: 24px;
}

.tab-text {
  font-size: 15px;
  font-weight: 700;
  color: #333;
  line-height: 1;
}

.tab--active .tab-text {
  font-size: 18px;
  color: $brand;
}

.tab-underline {
  position: absolute;
  left: 50%;
  bottom: 0;
  width: 18px;
  height: 3px;
  border-radius: 2px;
  background: $brand;
  transform: translateX(-50%);
}

.avatar {
  flex: none;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  border: 1px solid rgba(255, 255, 255, 0.8);
}
</style>
