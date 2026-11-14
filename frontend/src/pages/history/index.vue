<script setup lang="ts">
import { onShow } from "@dcloudio/uni-app";
import { computed, onUnmounted, ref, watch } from "vue";
import PageNav from "@/components/PageNav.vue";
import SearchInput from "@/components/SearchInput.vue";
import {
  deleteConversations,
  fetchConversationsPage,
  renameConversation,
} from "@/services/history";
import { USE_MOCK } from "@/services/request";
import type { ConversationGroup, ConversationSummary } from "@/types/conversation";

const conversations = ref<ConversationSummary[]>([]);
const keyword = ref("");
const activeGroup = ref<"全部" | ConversationGroup>("全部");
const groups: ("全部" | ConversationGroup)[] = ["全部", "本周", "本月", "半年"];
const multiMode = ref(false);
const selected = ref<number[]>([]);
const loading = ref(true);
const loadingMore = ref(false);
const nextCursor = ref<number | null>(null);
const loadError = ref("");
let loadVersion = 0;
let searchTimer: ReturnType<typeof setTimeout> | undefined;

const filtered = computed(() => {
  const query = keyword.value.trim();
  return conversations.value.filter((item) => {
    const groupOk = activeGroup.value === "全部" || item.group === activeGroup.value;
    const queryOk = !query || item.title.includes(query);
    return groupOk && queryOk;
  });
});

const grouped = computed(() => {
  const order: ConversationGroup[] = ["本周", "本月", "半年"];
  return order
    .map((group) => ({
      group,
      items: filtered.value.filter((item) => item.group === group),
    }))
    .filter((entry) => entry.items.length);
});

const allSelected = computed(
  () => filtered.value.length > 0 && selected.value.length === filtered.value.length,
);

async function load(more = false) {
  if (more && (loading.value || loadingMore.value || nextCursor.value === null)) return;
  const version = ++loadVersion;
  const query = keyword.value.trim();
  if (more) loadingMore.value = true;
  else {
    loading.value = true;
    loadingMore.value = false;
    selected.value = [];
  }
  loadError.value = "";
  try {
    const page = await fetchConversationsPage(query, more ? nextCursor.value! : undefined);
    if (version !== loadVersion) return;
    conversations.value = more ? [...conversations.value, ...page.items] : page.items;
    nextCursor.value = page.next_cursor;
  } catch (error) {
    if (version !== loadVersion) return;
    loadError.value = error instanceof Error ? error.message : "加载历史对话失败";
  } finally {
    if (version === loadVersion) {
      loading.value = false;
      loadingMore.value = false;
    }
  }
}

onShow(() => {
  clearTimeout(searchTimer);
  void load();
});
watch(keyword, () => {
  // Invalidate the previous search immediately, including its pending next page.
  loadVersion += 1;
  loading.value = true;
  loadingMore.value = false;
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => { void load(); }, 250);
});
onUnmounted(() => {
  loadVersion += 1;
  clearTimeout(searchTimer);
});

function open(conversation: ConversationSummary) {
  if (multiMode.value) {
    toggleSelected(conversation.id);
    return;
  }
  if (USE_MOCK) {
    uni.navigateTo({
      url: `/pages/chat/index?mode=assistant&q=${encodeURIComponent(conversation.title)}`,
    });
    return;
  }
  const params = conversation.case_id
    ? `mode=case&caseId=${conversation.case_id}&conversationId=${conversation.id}`
    : `mode=assistant&conversationId=${conversation.id}`;
  uni.navigateTo({ url: `/pages/chat/index?${params}` });
}

function promptRename(conversation: ConversationSummary) {
  uni.showModal({
    title: "重命名会话",
    editable: true,
    placeholderText: "请输入新的会话标题",
    content: conversation.title,
    success: async ({ confirm, content }) => {
      if (!confirm) return;
      const nextTitle = (content || "").trim();
      if (!nextTitle) return;
      try {
        if (!USE_MOCK) {
          await renameConversation(conversation.id, nextTitle);
        }
        conversation.title = nextTitle;
        uni.showToast({ title: "已重命名", icon: "none" });
      } catch (error) {
        const msg = error instanceof Error ? error.message : "重命名失败";
        uni.showToast({ title: msg, icon: "none" });
      }
    },
  });
}

function onLongPress(conversation: ConversationSummary) {
  if (multiMode.value) return;
  uni.showActionSheet({
    itemList: ["重命名", "删除会话", "多选"],
    success: ({ tapIndex }) => {
      if (tapIndex === 0) {
        promptRename(conversation);
        return;
      }
      if (tapIndex === 2) {
        multiMode.value = true;
        selected.value = [conversation.id];
        return;
      }
      uni.showModal({
        title: "删除会话",
        content: "删除选中的 1 个会话？",
        success: async ({ confirm }) => {
          if (!confirm) return;
          try {
            await deleteConversations([conversation.id]);
            conversations.value = conversations.value.filter(
              (item) => item.id !== conversation.id,
            );
            uni.showToast({ title: "已删除", icon: "none" });
          } catch (error) {
            const msg = error instanceof Error ? error.message : "删除失败";
            uni.showToast({ title: msg, icon: "none" });
          }
        },
      });
    },
  });
}

function toggleSelected(id: number) {
  selected.value = selected.value.includes(id)
    ? selected.value.filter((item) => item !== id)
    : [...selected.value, id];
}

function toggleAll() {
  selected.value = allSelected.value
    ? []
    : filtered.value.map((item) => item.id);
}

function removeSelected() {
  if (!selected.value.length) return;
  const ids = [...selected.value];
  uni.showModal({
    title: "删除会话",
    content: `删除选中的 ${ids.length} 个会话？`,
    success: async ({ confirm }) => {
      if (!confirm) return;
      try {
        await deleteConversations(ids);
        conversations.value = conversations.value.filter(
          (item) => !ids.includes(item.id),
        );
        selected.value = [];
        multiMode.value = false;
        uni.showToast({ title: "已删除", icon: "none" });
      } catch (error) {
        const msg = error instanceof Error ? error.message : "删除失败";
        uni.showToast({ title: msg, icon: "none" });
      }
    },
  });
}

function finishMulti() {
  multiMode.value = false;
  selected.value = [];
}

function newChat() {
  uni.navigateTo({ url: "/pages/chat/index?mode=assistant" });
}
</script>

<template>
  <view class="page-shell history-page">
    <PageNav title="历史对话">
      <text v-if="multiMode" class="done" @click="finishMulti">完成</text>
    </PageNav>
    <scroll-view scroll-y class="page-scroll history-scroll">
      <image class="robot" src="/static/images/robot.png" mode="aspectFit" />
      <text class="greet">Hi～我是小诺！</text>

      <SearchInput v-model="keyword" placeholder="搜索历史对话" />

      <scroll-view scroll-x class="chips" :show-scrollbar="false">
        <view class="chips-inner">
          <view
            v-for="group in groups"
            :key="group"
            class="chip"
            :class="{ 'chip--active': activeGroup === group }"
            @click="activeGroup = group"
          >
            {{ group }}
          </view>
        </view>
      </scroll-view>

      <view v-if="loading" class="state">加载中…</view>
      <view v-else-if="loadError" class="state" @click="load()">{{ loadError }}，点击重试</view>
      <view v-else-if="!grouped.length" class="state">没有找到相关对话</view>

      <view v-else class="groups">
        <view v-for="entry in grouped" :key="entry.group" class="group">
          <text class="group-title">{{ entry.group }}</text>
          <view
            v-for="item in entry.items"
            :key="item.id"
            class="row"
            :class="{ 'row--active': item.active }"
            @click="open(item)"
            @longpress="onLongPress(item)"
          >
            <view v-if="multiMode" class="check" :class="{ 'check--on': selected.includes(item.id) }">
              <text v-if="selected.includes(item.id)">✓</text>
            </view>
            <view v-else class="chat-icon">
              <view class="chat-icon-dot" />
            </view>
            <text class="row-title" :class="{ 'row-title--blue': item.active && !multiMode }">
              {{ item.title }}
            </text>
          </view>
        </view>
      </view>
      <view v-if="!loading && nextCursor !== null && !loadError" class="state" @click="load(true)">
        {{ loadingMore ? "加载中…" : "加载更多对话" }}
      </view>
      <view class="tail" />
    </scroll-view>

    <view v-if="multiMode" class="multi-bar">
      <view class="select-all" @click="toggleAll">
        <view class="check" :class="{ 'check--on': allSelected }">
          <text v-if="allSelected">✓</text>
        </view>
        <text>全选</text>
      </view>
      <text class="count">已选 {{ selected.length }} 个</text>
      <view class="delete" @click="removeSelected">删除</view>
    </view>

    <view v-else class="new-chat" @click="newChat">
      <text class="plus">+</text>
      <text>新建对话</text>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.history-page {
  background:
    radial-gradient(100% 38% at 90% 0%, rgba(112, 186, 255, 0.65) 0%, rgba(112, 186, 255, 0) 62%),
    linear-gradient(180deg, #fbfcff 0%, #f7f8ff 30%, #ffffff 55%);
}

.done {
  font-size: 14px;
  color: $brand;
}

.robot {
  width: 112px;
  height: 124px;
  margin: 4rpx auto 0;
}

.greet {
  display: block;
  margin: 8rpx 0 18rpx;
  text-align: center;
  font-size: 34rpx;
  font-weight: 600;
  color: #2f2f2f;
}

.chips {
  width: 100%;
  white-space: nowrap;
  padding-bottom: 10rpx;
}

.chips-inner {
  display: inline-flex;
  padding: 0 24rpx;
}

.chip {
  flex: none;
  height: 58rpx;
  margin-right: 12rpx;
  padding: 0 28rpx;
  border-radius: 29rpx;
  border: 1rpx solid #e4e7ee;
  background: rgba(255, 255, 255, 0.8);
  color: #777;
  font-size: 24rpx;
  display: flex;
  align-items: center;
}

.chip--active {
  background: $brand-soft;
  border-color: transparent;
  color: $brand;
  font-weight: 600;
}

.groups {
  padding: 0 36rpx;
}

.group {
  margin-bottom: 12rpx;
}

.group-title {
  display: block;
  margin: 18rpx 0 6rpx;
  font-size: 24rpx;
  font-weight: 600;
  color: #b3b8c2;
}

.row {
  display: flex;
  align-items: center;
  min-height: 92rpx;
  padding: 8rpx 4rpx;
  border-radius: 12rpx;
}

.row--active {
  background: rgba(234, 241, 255, 0.5);
}

.chat-icon {
  position: relative;
  flex: none;
  width: 34rpx;
  height: 30rpx;
  margin-right: 16rpx;
  border: 3rpx solid #a9afb9;
  border-radius: 10rpx;

  &::after {
    content: "";
    position: absolute;
    left: 6rpx;
    bottom: -8rpx;
    width: 10rpx;
    height: 10rpx;
    border-left: 3rpx solid #a9afb9;
    border-bottom: 3rpx solid #a9afb9;
    transform: skewY(-35deg);
    background: #fff;
  }
}

.chat-icon-dot {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 12rpx;
  height: 3rpx;
  background: #a9afb9;
  transform: translate(-50%, -50%);
}

.row-title {
  flex: 1;
  min-width: 0;
  font-size: 28rpx;
  color: #333;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.row-title--blue {
  color: $brand;
}

.check {
  flex: none;
  width: 38rpx;
  height: 38rpx;
  margin-right: 14rpx;
  border-radius: 50%;
  border: 2rpx solid #d7dbe2;
  background: #fff;
  color: #fff;
  font-size: 22rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.check--on {
  background: $brand;
  border-color: $brand;
}

.state {
  padding: 100rpx 0;
  text-align: center;
  color: $muted;
  font-size: 26rpx;
}

.tail {
  height: 160rpx;
}

.new-chat {
  position: absolute;
  left: 50%;
  bottom: calc(40rpx + env(safe-area-inset-bottom));
  transform: translateX(-50%);
  min-width: 300rpx;
  height: 88rpx;
  padding: 0 44rpx;
  border-radius: 44rpx;
  background: $brand;
  color: #fff;
  font-size: 28rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 12rpx 32rpx rgba(33, 92, 255, 0.28);
}

.plus {
  margin-right: 10rpx;
  font-size: 36rpx;
}

.multi-bar {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 18rpx 36rpx calc(18rpx + env(safe-area-inset-bottom));
  background: #fff;
  border-top: 1rpx solid $line;
  display: flex;
  align-items: center;
}

.select-all {
  display: flex;
  align-items: center;
  font-size: 26rpx;
  color: #333;
}

.count {
  flex: 1;
  margin-left: 18rpx;
  font-size: 24rpx;
  color: $muted;
}

.delete {
  height: 64rpx;
  padding: 0 32rpx;
  border-radius: 32rpx;
  background: #fdeaea;
  color: #e15a5a;
  font-size: 26rpx;
  display: flex;
  align-items: center;
}
</style>
