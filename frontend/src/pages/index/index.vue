<script setup lang="ts">
import { onShow } from "@dcloudio/uni-app";
import { storeToRefs } from "pinia";
import { ref } from "vue";
import AppDrawer from "@/components/AppDrawer.vue";
import AppHeader from "@/components/AppHeader.vue";
import AssistantHome from "./components/AssistantHome.vue";
import CasesHome from "./components/CasesHome.vue";
import ChatConversation from "@/components/chat/ChatConversation.vue";
import { useAuthStore } from "@/stores/auth";
import { useHomeStore } from "@/stores/home";
import type { HomeTab } from "@/types/home";

const auth = useAuthStore();
const home = useHomeStore();
const { activeTab } = storeToRefs(home);
const drawerOpen = ref(false);
const chatOpen = ref(false);
const chatQuestion = ref("");
const casesHomeRef = ref<{ loadCases: () => Promise<void> } | null>(null);
let hasShownOnce = false;

onShow(() => {
  if (!hasShownOnce) {
    hasShownOnce = true;
    return;
  }
  if (activeTab.value === "cases") {
    casesHomeRef.value?.loadCases();
  }
});

function openDrawer() {
  drawerOpen.value = true;
}

function openHistory() {
  drawerOpen.value = false;
  uni.navigateTo({ url: "/pages/history/index" });
}

function openProfile() {
  drawerOpen.value = false;
  uni.navigateTo({ url: "/pages/profile/index" });
}

function handleTabChange(tab: HomeTab) {
  chatOpen.value = false;
  home.setActiveTab(tab);
}

function selectTab(tab: HomeTab) {
  drawerOpen.value = false;
  chatOpen.value = false;
  home.setActiveTab(tab);
}

function startAssistantChat(question: string) {
  chatQuestion.value = question;
  chatOpen.value = true;
  home.setActiveTab("assistant");
}

function openLegacy() {
  drawerOpen.value = false;
  uni.navigateTo({ url: "/pages/case/analysis?id=1" });
}

function handleLogout() {
  auth.logout();
}
</script>

<template>
  <view
    class="home-shell"
    :class="activeTab === 'cases' ? 'home-shell--cases' : 'home-shell--assistant'"
  >
    <AppHeader
      :active="activeTab"
      @update:active="handleTabChange"
      @menu="openDrawer"
      @profile="openProfile"
    />
    <CasesHome v-if="activeTab === 'cases'" ref="casesHomeRef" />
    <template v-else>
      <ChatConversation
        v-if="chatOpen"
        :key="chatQuestion"
        mode="assistant"
        :initial-question="chatQuestion"
      />
      <AssistantHome v-else @start-chat="startAssistantChat" />
    </template>

    <AppDrawer
      :visible="drawerOpen"
      @close="drawerOpen = false"
      @select-tab="selectTab"
      @history="openHistory"
      @profile="openProfile"
      @legacy="openLegacy"
      @logout="handleLogout"
    />
  </view>
</template>

<style lang="scss" scoped>
.home-shell {
  position: relative;
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.home-shell--cases {
  background:
    radial-gradient(
      95% 62% at 100% 2%,
      rgba(103, 181, 255, 0.72) 0%,
      rgba(103, 181, 255, 0) 62%
    ),
    radial-gradient(
      85% 48% at 52% 18%,
      rgba(224, 213, 255, 0.55) 0%,
      rgba(224, 213, 255, 0) 72%
    ),
    linear-gradient(180deg, #fbfcff 0%, #f6f8ff 34%, #ffffff 62%);
}

.home-shell--assistant {
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

/* #ifdef H5 */
.home-shell {
  max-width: 430px;
  margin: 0 auto;
  box-shadow: 0 0 40px rgba(35, 70, 120, 0.12);
}
/* #endif */
</style>
