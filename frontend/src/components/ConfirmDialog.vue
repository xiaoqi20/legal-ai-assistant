<script setup lang="ts">
withDefaults(
  defineProps<{
    visible: boolean;
    title: string;
    confirmText?: string;
    cancelText?: string;
    showCancel?: boolean;
  }>(),
  {
    confirmText: "确定",
    cancelText: "取消",
    showCancel: true,
  }
);

const emit = defineEmits<{
  (e: "confirm"): void;
  (e: "cancel"): void;
}>();
</script>

<template>
  <view v-if="visible" class="dialog-mask" @click="emit('cancel')">
    <view class="dialog" @click.stop>
      <text class="dialog-title">{{ title }}</text>
      <view class="dialog-actions" :class="{ 'dialog-actions--single': !showCancel }">
        <view
          v-if="showCancel"
          class="dialog-btn dialog-btn--ghost"
          @click="emit('cancel')"
        >
          {{ cancelText }}
        </view>
        <view
          class="dialog-btn dialog-btn--primary"
          :class="{ 'dialog-btn--single': !showCancel }"
          @click="emit('confirm')"
        >
          {{ confirmText }}
        </view>
      </view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.dialog-mask {
  position: absolute;
  inset: 0;
  z-index: 400;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.42);
  animation: maskIn 0.15s ease;
}

.dialog {
  width: 270px;
  padding: 24px 20px 20px;
  border-radius: 16px;
  background: #fff;
  text-align: center;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.18);
  animation: dialogIn 0.18s ease;
}

.dialog-title {
  display: block;
  font-size: 17px;
  font-weight: 600;
  color: #2b2b2b;
}

.dialog-actions {
  display: flex;
  gap: 12px;
  margin-top: 18px;
}

.dialog-btn {
  flex: 1;
  height: 38px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
}

.dialog-btn--ghost {
  border: 1px solid #dce4f4;
  background: #fff;
  color: #215cff;
}

.dialog-btn--primary {
  background: #215cff;
  color: #fff;
}

.dialog-actions--single {
  justify-content: center;
}

.dialog-btn--single {
  flex: none;
  width: 112px;
  border-radius: 19px;
}

@keyframes maskIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes dialogIn {
  from {
    opacity: 0.4;
    transform: scale(0.96);
  }
  to {
    opacity: 1;
    transform: none;
  }
}
</style>
