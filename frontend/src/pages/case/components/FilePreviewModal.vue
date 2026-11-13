<script setup lang="ts">
import { computed } from "vue";
import FileBadge from "@/components/FileBadge.vue";

const props = defineProps<{
  visible: boolean;
  fileName: string;
  fileType?: string;
}>();

const emit = defineEmits<{
  (e: "close"): void;
}>();

const resolvedType = computed(() => {
  if (props.fileType) return props.fileType;
  return props.fileName.toLowerCase().endsWith(".pdf") ? "pdf" : "docx";
});

const paperTitle = computed(() =>
  resolvedType.value.toLowerCase() === "pdf" ? "民事答辩状" : "民 事 答 辩 状",
);
</script>

<template>
  <view v-if="visible" class="preview-mask" @click="emit('close')">
    <view class="preview-modal" @click.stop>
      <view class="preview-head">
        <FileBadge :type="resolvedType" />
        <text class="preview-name">{{ fileName }}</text>
        <view class="preview-close" @click="emit('close')">×</view>
      </view>

      <scroll-view scroll-y class="preview-paper" :show-scrollbar="false">
        <text class="paper-title">{{ paperTitle }}</text>
        <text class="paper-p">答辩人（被告）：李某，男，汉族，住某市某区某路某号。</text>
        <text class="paper-p">因原告张某诉答辩人房屋买卖合同纠纷一案，答辩人现提出答辩如下：</text>
        <text class="paper-p">
          一、原告所述事实部分不实。答辩人与原告签订的房屋买卖合同系双方真实意思表示，合同合法有效，答辩人从未否认合同效力。
        </text>
        <text class="paper-p">
          二、原告主张的经济损失缺乏证据支持。原告未能提供充分证据证明其实际损失金额，其主张不应得到支持。
        </text>
        <text class="paper-p">
          三、答辩人进入房屋系为协商合同履行事宜，并非恶意侵占。相关事实有待庭审查明。
        </text>
        <text class="paper-p">综上，请求法院依法驳回原告不合理的诉讼请求。</text>
        <view class="paper-sign">
          <text class="paper-sign-line">答辩人：李某</text>
          <text class="paper-sign-line">2024年10月15日</text>
        </view>
      </scroll-view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.preview-mask {
  position: absolute;
  inset: 0;
  z-index: 400;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.42);
}

.preview-modal {
  width: calc(100% - 48px);
  max-width: 382px;
  padding: 18px 18px 16px;
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.18);
}

.preview-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}

.preview-name {
  flex: 1;
  min-width: 0;
  font-size: 15px;
  font-weight: 600;
  color: #333;
  word-break: break-all;
}

.preview-close {
  flex: none;
  width: 26px;
  height: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  line-height: 1;
  color: #999;
}

.preview-paper {
  height: 340px;
  padding: 16px;
  border-radius: 10px;
  background: #f7f8fa;
  box-sizing: border-box;
}

.paper-title {
  display: block;
  margin: 4px 0 14px;
  text-align: center;
  font-size: 17px;
  font-weight: 700;
  color: #333;
}

.paper-p {
  display: block;
  margin-bottom: 10px;
  font-size: 13px;
  line-height: 1.9;
  color: #444;
}

.paper-sign {
  margin-top: 8px;
  text-align: right;
}

.paper-sign-line {
  display: block;
  font-size: 13px;
  line-height: 1.9;
  color: #444;
}
</style>
