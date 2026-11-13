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

const fallbackSections = [
  {
    h: "欢迎您使用英诺律法产品及服务！",
    p: "为使用英诺律法产品及服务，您应当阅读并遵守《英诺律法用户服务协议》以及《个人信息及隐私保护政策》。请审慎阅读并充分理解各条款内容，特别是免除或限制责任的条款。",
  },
  {
    h: "一、协议的范围",
    p: "本协议是您与安徽英诺欣科技有限公司及其关联公司之间关于访问、使用英诺律法产品及服务所订立的协议。",
  },
  {
    h: "二、账号注册与使用",
    p: "您应妥善保管账号及密码，并对通过账号进行的操作负责。如发现账号被非法使用，请立即通知我们并采取必要措施。",
  },
  {
    h: "三、服务内容",
    p: "英诺律法为您提供案件管理、证据分析、案情梳理、法律文书辅助生成等服务，具体以产品页面展示为准。",
  },
  {
    h: "四、用户行为规范",
    p: "您不得利用本产品从事违反法律法规、侵犯他人合法权益或扰乱平台秩序的行为。上传的案件材料应来源合法。",
  },
  {
    h: "五、隐私保护",
    p: "我们重视个人信息保护，将按照隐私政策收集、使用和保护您的信息。未经授权，不会向第三方提供您的案件材料，法律法规另有规定的除外。",
  },
  {
    h: "六、免责声明",
    p: "因不可抗力、网络故障、系统维护等原因导致服务中断的，我们将尽力恢复。AI 分析结果仅供参考，不构成正式法律意见。",
  },
  {
    h: "七、协议终止",
    p: "您可随时停止使用服务并申请注销账号。账号注销后，相关数据将按照法律法规及隐私政策处理。",
  },
  {
    h: "八、法律适用与争议解决",
    p: "本协议适用中华人民共和国法律。因本协议产生的争议，双方应友好协商解决；协商不成的，可向英诺欣所在地有管辖权的人民法院提起诉讼。",
  },
];

const activeDoc = computed(() => {
  if (!remoteDocs.value.length) return null;
  if (docTypeFilter.value) {
    return (
      remoteDocs.value.find((doc) => doc.doc_type === docTypeFilter.value) ||
      remoteDocs.value[0]
    );
  }
  return remoteDocs.value[0];
});

const navTitle = computed(() => activeDoc.value?.title || "用户服务");
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
  if (USE_MOCK) return;
  auth
    .ensureAgreements()
    .then((docs) => {
      remoteDocs.value = docs;
    })
    .catch(() => {
      // keep fallback text if agreements haven't been published yet
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
          <text class="title">英诺律法用户服务协议</text>
          <text class="date">更新日期：2024 年 7 月 9 日</text>
          <text class="date">生效日期：2024 年 7 月 9 日</text>
          <view
            v-for="section in fallbackSections"
            :key="section.h"
            class="section"
          >
            <text class="heading">{{ section.h }}</text>
            <text class="paragraph">{{ section.p }}</text>
          </view>
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

.heading {
  display: block;
  font-size: 28rpx;
  font-weight: 700;
  color: #333;
}

.paragraph {
  display: block;
  margin-top: 10rpx;
  font-size: 26rpx;
  line-height: 1.8;
  color: $text-secondary;
}

.tail {
  height: 60rpx;
}
</style>
