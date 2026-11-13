<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{
  type: string;
}>();

const isPdf = computed(() => props.type.toLowerCase() === "pdf");
</script>

<template>
  <view class="file-badge" :class="isPdf ? 'file-badge--pdf' : 'file-badge--doc'">
    <text>{{ isPdf ? "PDF" : "W" }}</text>
  </view>
</template>

<style lang="scss" scoped>
.file-badge {
  flex: none;
  width: 48rpx;
  height: 48rpx;
  border-radius: 8rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18rpx;
  font-weight: 700;
  color: #fff;
}

.file-badge--doc {
  background: #4c8dff;
}

.file-badge--pdf {
  background: #f05b5b;
}
</style>
