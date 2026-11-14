<script setup lang="ts">
import { onLoad } from "@dcloudio/uni-app";
import { computed, ref } from "vue";
import PageNav from "@/components/PageNav.vue";
import type { LegalDocument } from "@/services/auth";
import { USE_MOCK } from "@/services/request";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const docTypeFilter = ref("");
const remoteDocs = ref<LegalDocument[]>([]);
const loading = ref(true);
const loadFailed = ref(false);

const activeDoc = computed(() => {
  if (!remoteDocs.value.length) return null;
  if (docTypeFilter.value) {
    return remoteDocs.value.find((doc) => doc.doc_type === docTypeFilter.value) || null;
  }
  return remoteDocs.value[0];
});

const navTitle = computed(() => activeDoc.value?.title || ({
  user_service: "用户服务",
  privacy_policy: "隐私政策",
  disclaimer: "免责声明",
}[docTypeFilter.value] || "用户协议"));
const docParagraphs = computed(() =>
  activeDoc.value
    ? activeDoc.value.content
        .split(/\n{2,}/)
        .map((item) => item.trim())
        .filter(Boolean)
    : [],
);

onLoad((query) => {
  docTypeFilter.value = typeof query?.docType === "string" ? query.docType : "";
  if (USE_MOCK) {
    loading.value = false;
    return;
  }
  auth
    .ensureAgreements()
    .then((docs) => {
      remoteDocs.value = docs;
    })
    .catch(() => {
      loadFailed.value = true;
    })
    .finally(() => {
      loading.value = false;
    });
});
</script>

<template>
  <view class="page-shell agreement-page">
    <PageNav :title="navTitle" />
    <scroll-view scroll-y class="page-scroll">
      <view class="content">
        <template v-if="activeDoc">
          <text class="title">{{ activeDoc.title }}</text>
          <text class="date">版本：{{ activeDoc.version }}</text>
          <text class="date">生效日期：{{ activeDoc.effective_at.slice(0, 10) }}</text>
          <view
            v-for="(paragraph, index) in docParagraphs"
            :key="index"
            class="section"
          >
            <text class="paragraph">{{ paragraph }}</text>
          </view>
        </template>
        <template v-else>
          <text class="title">{{ loadFailed ? "协议加载失败" : loading ? "正在加载协议…" : "协议暂未发布" }}</text>
          <text class="paragraph empty-state">
            {{ loadFailed ? "请检查网络连接后返回重试。" : "当前没有可展示的正式协议，请稍后再试。" }}
          </text>
        </template>
      </view>
      <view class="tail" />
    </scroll-view>
  </view>
</template>

<style lang="scss" scoped>
.agreement-page {
  background: #fff;
}

.content {
  padding: 20rpx 40rpx 0;
}

.title {
  display: block;
  text-align: center;
  font-size: 36rpx;
  font-weight: 700;
  color: #333;
}

.date {
  display: block;
  margin-top: 10rpx;
  text-align: center;
  font-size: 22rpx;
  color: $muted;
}

.section {
  margin-top: 30rpx;
}

.paragraph {
  display: block;
  margin-top: 10rpx;
  font-size: 26rpx;
  line-height: 1.8;
  color: $text-secondary;
}

.empty-state {
  margin-top: 40rpx;
  text-align: center;
}

.tail {
  height: 60rpx;
}
</style>
