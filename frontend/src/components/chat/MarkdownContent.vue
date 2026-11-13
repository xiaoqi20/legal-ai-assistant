<script setup lang="ts">
import { computed } from "vue";
import { parseMarkdown } from "@/utils/markdown";

const props = defineProps<{
  content: string;
}>();

const blocks = computed(() => parseMarkdown(props.content));
</script>

<template>
  <view class="md-root">
    <template v-for="(block, idx) in blocks" :key="idx">
      <!-- 标题 -->
      <view
        v-if="block.type === 'heading'"
        class="md-heading"
        :class="`md-heading--h${block.level}`"
      >
        <text
          v-for="(span, sIdx) in block.spans"
          :key="sIdx"
          :class="{
            'md-bold': span.bold,
            'md-code-inline': span.code,
            'md-link': span.link,
          }"
        >{{ span.text }}</text>
      </view>

      <!-- 分割线 -->
      <view v-else-if="block.type === 'hr'" class="md-hr" />

      <!-- 代码块 / 文书模板块 -->
      <view v-else-if="block.type === 'code'" class="md-code-block">
        <text v-if="block.lang" class="md-code-lang">{{ block.lang }}</text>
        <text class="md-code-body" selectable user-select>{{ block.text }}</text>
      </view>

      <!-- 引用块 -->
      <view v-else-if="block.type === 'quote'" class="md-quote">
        <text
          v-for="(span, sIdx) in block.spans"
          :key="sIdx"
          :class="{
            'md-bold': span.bold,
            'md-code-inline': span.code,
            'md-link': span.link,
          }"
        >{{ span.text }}</text>
      </view>

      <!-- 列表 -->
      <view v-else-if="block.type === 'list'" class="md-list">
        <view
          v-for="(item, itemIdx) in block.items"
          :key="itemIdx"
          class="md-list-item"
        >
          <text class="md-list-marker">{{ item.marker }}</text>
          <view class="md-list-body">
            <text
              v-for="(span, sIdx) in item.spans"
              :key="sIdx"
              :class="{
                'md-bold': span.bold,
                'md-code-inline': span.code,
                'md-link': span.link,
              }"
            >{{ span.text }}</text>
          </view>
        </view>
      </view>

      <!-- 表格 -->
      <view v-else-if="block.type === 'table'" class="md-table">
        <view class="md-tr md-tr--head">
          <text v-for="(h, hIdx) in block.headers" :key="hIdx" class="md-td md-td--head">
            {{ h }}
          </text>
        </view>
        <view v-for="(row, rIdx) in block.rows" :key="rIdx" class="md-tr">
          <text v-for="(cell, cIdx) in row" :key="cIdx" class="md-td">
            {{ cell }}
          </text>
        </view>
      </view>

      <!-- 正文段落 -->
      <view v-else class="md-para">
        <text
          v-for="(span, sIdx) in block.spans"
          :key="sIdx"
          :class="{
            'md-bold': span.bold,
            'md-code-inline': span.code,
            'md-link': span.link,
          }"
        >{{ span.text }}</text>
      </view>
    </template>
  </view>
</template>

<style lang="scss" scoped>
.md-root {
  display: flex;
  flex-direction: column;
  gap: 14rpx;
  font-size: 28rpx;
  line-height: 1.75;
  color: #333;
  word-break: break-word;
}

.md-heading {
  font-weight: 700;
  color: #1f2430;
  line-height: 1.45;
}

.md-heading--h1 {
  font-size: 34rpx;
  margin-top: 6rpx;
}

.md-heading--h2 {
  font-size: 31rpx;
  margin-top: 6rpx;
}

.md-heading--h3,
.md-heading--h4 {
  font-size: 29rpx;
}

.md-para {
  white-space: pre-wrap;
}

.md-bold {
  font-weight: 700;
  color: #1f2430;
}

.md-code-inline {
  padding: 2rpx 10rpx;
  border-radius: 8rpx;
  background: #f1f4fb;
  color: $brand;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 25rpx;
}

.md-link {
  color: $brand;
  text-decoration: underline;
}

.md-hr {
  height: 1rpx;
  margin: 6rpx 0;
  background: #e9ecf3;
}

.md-code-block {
  padding: 20rpx 22rpx;
  border-radius: 16rpx;
  background: #f7f9fc;
  border: 1rpx solid #e7ecf5;
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.md-code-lang {
  font-size: 21rpx;
  color: $muted;
  text-transform: uppercase;
}

.md-code-body {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 26rpx;
  line-height: 1.75;
  color: #2b3240;
}

.md-quote {
  padding: 12rpx 18rpx;
  border-left: 6rpx solid $brand;
  background: #f6f9ff;
  border-radius: 0 12rpx 12rpx 0;
  color: $text-secondary;
  white-space: pre-wrap;
}

.md-list {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.md-list-item {
  display: flex;
  align-items: flex-start;
  gap: 10rpx;
}

.md-list-marker {
  flex: none;
  min-width: 28rpx;
  color: $brand;
  font-weight: 700;
}

.md-list-body {
  flex: 1;
  min-width: 0;
  white-space: pre-wrap;
}

.md-table {
  border: 1rpx solid #e7ecf5;
  border-radius: 12rpx;
  overflow: hidden;
}

.md-tr {
  display: flex;
  border-bottom: 1rpx solid #eef1f7;

  &:last-child {
    border-bottom: none;
  }
}

.md-tr--head {
  background: #f5f7fc;
  font-weight: 700;
}

.md-td {
  flex: 1;
  min-width: 0;
  padding: 12rpx 14rpx;
  font-size: 24rpx;
  line-height: 1.5;
  border-right: 1rpx solid #eef1f7;

  &:last-child {
    border-right: none;
  }
}
</style>
