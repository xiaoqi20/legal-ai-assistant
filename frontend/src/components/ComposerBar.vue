<script setup lang="ts">
defineProps<{
  modelValue: string;
  placeholder: string;
  solid?: boolean;
}>();

const emit = defineEmits<{
  (e: "update:modelValue", value: string): void;
  (e: "send"): void;
  (e: "toggle-attach"): void;
  (e: "mic"): void;
}>();

function onInput(event: { detail: { value: string } }) {
  emit("update:modelValue", event.detail.value);
}
</script>

<template>
  <view class="composer-wrap" :class="{ 'composer-wrap--solid': solid }">
    <view class="composer">
      <view class="plus" @click="emit('toggle-attach')">
        <image
          class="plus-icon"
          src="/static/images/icons/plus.png"
          mode="aspectFit"
        />
      </view>

      <view class="composer-box">
        <input
          class="composer-input"
          :value="modelValue"
          :placeholder="placeholder"
          placeholder-style="color:#AEB4BE"
          confirm-type="send"
          :adjust-position="true"
          @input="onInput"
          @confirm="emit('send')"
        />
        <view v-if="modelValue.trim()" class="send" @click="emit('send')">
          <image
            class="send-icon"
            src="/static/images/icons/send.png"
            mode="aspectFit"
          />
        </view>
        <view v-else class="mic" @click="emit('mic')">
          <image
            class="mic-icon"
            src="/static/images/icons/mic.png"
            mode="aspectFit"
          />
        </view>
      </view>
    </view>

    <slot />
  </view>
</template>

<style lang="scss" scoped>
.composer-wrap {
  flex: none;
  padding: 8px 18px calc(10px + env(safe-area-inset-bottom));
  background: linear-gradient(180deg, rgba(255, 255, 255, 0), #fff 34%);
}

/* #ifdef H5 */
.composer-wrap {
  padding-bottom: 12px;
}
/* #endif */

.composer-wrap--solid {
  padding-top: 10px;
  border-top: 1px solid #f4f5f7;
  background: #fff;
}

.composer {
  display: flex;
  align-items: center;
}

.plus {
  flex: none;
  width: 36px;
  height: 36px;
  margin-right: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.plus-icon {
  width: 30px;
  height: 30px;
}

.composer-box {
  flex: 1;
  min-width: 0;
  height: 48px;
  padding: 0 12px 0 16px;
  border: 1px solid rgba(228, 233, 242, 0.9);
  border-radius: 24px;
  background: #fff;
  box-shadow: 0 4px 18px rgba(30, 60, 120, 0.13);
  display: flex;
  align-items: center;
}

.composer-input {
  flex: 1;
  min-width: 0;
  height: 100%;
  font-size: 14px;
  color: $text;
}

.mic,
.send {
  flex: none;
  width: 28px;
  height: 28px;
  margin-left: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.send {
  width: 30px;
  height: 30px;
}

.mic-icon,
.send-icon {
  width: 24px;
  height: 24px;
}
</style>
