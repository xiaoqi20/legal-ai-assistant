import { defineStore } from "pinia";
import { ref } from "vue";
import type { HomeTab } from "@/types/home";

export const useHomeStore = defineStore("home", () => {
  const activeTab = ref<HomeTab>("cases");
  const caseKeyword = ref("");
  const caseDraft = ref("");
  const assistantDraft = ref("");

  function setActiveTab(tab: HomeTab) {
    activeTab.value = tab;
  }

  return {
    activeTab,
    caseKeyword,
    caseDraft,
    assistantDraft,
    setActiveTab,
  };
});
