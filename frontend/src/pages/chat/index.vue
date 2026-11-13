<script setup lang="ts">
import { onLoad } from "@dcloudio/uni-app";
import { computed, ref } from "vue";
import AppDrawer from "@/components/AppDrawer.vue";
import AppHeader from "@/components/AppHeader.vue";
import PageNav from "@/components/PageNav.vue";
import ChatConversation from "@/components/chat/ChatConversation.vue";
import { useAuthStore } from "@/stores/auth";
import { useHomeStore } from "@/stores/home";
import type { HomeTab } from "@/types/home";

const mode = ref<"assistant" | "case">("assistant");
const caseId = ref(1);
const conversationId = ref<number | undefined>(undefined);
const initialQuestion = ref("");
const drawerOpen = ref(false);
const auth = useAuthStore();
const home = useHomeStore();

const title = computed(() => (mode.value === "case" ? "AI问答" : "小诺助手"));

onLoad((options) => {
  mode.value = options?.mode === "case" ? "case" : "assistant";
  caseId.value = Number(options?.caseId || 1);
  const convId = Number(options?.conversationId || 0);
  conversationId.value = convId > 0 ? convId : undefined;
  try {
    initialQuestion.value = decodeURIComponent(options?.q || "");
  } catch {
    initialQuestion.value = options?.q || "";
  }
});

function switchHomeTab(tab: HomeTab) {
  drawerOpen.value = false;
  home.setActiveTab(tab);
  uni.reLaunch({ url: "/pages/index/index" });
}

function openProfile() {
  drawerOpen.value = false;
  uni.navigateTo({ url: "/pages/profile/index" });
}

function openHistory() {
  drawerOpen.value = false;
  uni.navigateTo({ url: "/pages/history/index" });
}

function openLegacy() {
  drawerOpen.value = false;
  uni.navigateTo({ url: "/pages/case/analysis?id=1" });
}

function handleDrawerLogout() {
  auth.logout();
}
</script>

<template>
  <view class="page-shell chat-page" :class="{ 'chat-page--assistant': mode === 'assistant' }">
    <AppHeader
      v-if="mode === 'assistant'"
      active="assistant"
      @update:active="switchHomeTab"
      @menu="drawerOpen = true"
      @profile="openProfile"
    />
    <PageNav v-else :title="title" />

    <ChatConversation
      :key="`${mode}-${caseId}-${conversationId || 0}-${initialQuestion}`"
      :mode="mode"
      :case-id="caseId"
      :conversation-id="conversationId"
      :initial-question="initialQuestion"
    />

    <AppDrawer
      v-if="mode === 'assistant'"
      :visible="drawerOpen"
      @close="drawerOpen = false"
      @select-tab="switchHomeTab"
      @history="openHistory"
      @profile="openProfile"
      @legacy="openLegacy"
      @logout="handleDrawerLogout"
    />
  </view>
</template>

<style lang="scss" scoped>
.chat-page {
  background: linear-gradient(180deg, #f7f9ff 0%, #ffffff 45%);
}

/* 与首页助手模式（.home-shell--assistant）保持一致，避免从历史记录进入时背景发白割裂 */
.chat-page--assistant {
  background:
    radial-gradient(
      110% 55% at 100% 0%,
      rgba(112, 186, 255, 0.78) 0%,
      rgba(112, 186, 255, 0) 58%
    ),
    radial-gradient(
      90% 45% at 40% 20%,
      rgba(231, 214, 255, 0.6) 0%,
      rgba(231, 214, 255, 0) 70%
    ),
    linear-gradient(180deg, #fbfcff 0%, #f7f8ff 45%, #ffffff 75%);
}
</style>
