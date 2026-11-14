<script setup lang="ts">
import { onMounted, onUnmounted, computed, nextTick, reactive, ref } from "vue";
import ComposerBar from "@/components/ComposerBar.vue";
import MarkdownContent from "@/components/chat/MarkdownContent.vue";
import { ANALYSIS_STATUS_META, PROCEDURE_LABELS } from "@/constants/case";
import { fetchRecommendations } from "@/services/assistant";
import { fetchCase } from "@/services/caseContent";
import {
  answerToPlainText,
  getMockAnswer,
  type AnswerBlock,
} from "@/services/chat";
import { openRemoteFile } from "@/services/files";
import {
  cancelConversationMessage,
  createConversation,
  fetchConversationMessagesPage,
  submitMessageFeedback,
} from "@/services/history";
import { USE_MOCK, createClientId } from "@/services/request";
import {
  streamSsePost,
  type SseCitation,
  type StreamHandle,
} from "@/services/sse";
import type { ConversationMessageRecord } from "@/types/conversation";
import type { CaseSummary } from "@/types/case";

interface ChatMessage {
  /** 前端列表渲染主键（本地自增） */
  id: number;
  /** 后端持久化消息 ID，流式 meta 事件返回后写入，用于取消生成与点赞反馈 */
  serverId?: number;
  role: "user" | "assistant";
  text: string;
  blocks?: AnswerBlock[];
  citations?: SseCitation[];
  feedback?: "like" | "dislike";
  streaming?: boolean;
  status?: "streaming" | "completed" | "failed" | "cancelled";
  errorMessage?: string;
}

const props = defineProps<{
  mode: "assistant" | "case";
  caseId?: number;
  /** 从历史对话页进入时携带的既有会话 ID */
  conversationId?: number;
  initialQuestion?: string;
}>();

const caseDetail = ref<CaseSummary | null>(null);
const messages = ref<ChatMessage[]>([]);
const draft = ref("");
const typing = ref(false);
const loadingHistory = ref(false);
const earlierCursor = ref<number | null>(null);
const attachOpen = ref(false);
const scrollTarget = ref("");
const activeConversationId = ref<number | null>(props.conversationId ?? null);
const activeServerMessageId = ref<number | null>(null);
const recommendations = ref<string[]>([
  "请帮我写一份关于民事诉讼的起诉书",
  "关于民事诉讼的答辩状",
  "别人欠我钱逾期未还怎么办",
  "怎么样快速收集案件证据",
]);

let sequence = 0;
let timer: ReturnType<typeof setTimeout> | null = null;
let streamHandle: StreamHandle | null = null;
let unmounted = false;
let generationVersion = 0;

const composerPlaceholder = computed(() => {
  if (messages.value.length) return "继续提问…";
  return props.mode === "case"
    ? "关于案件，有什么想要咨询的？"
    : "请在此输入您的提问～";
});
const caseStatus = computed(() =>
  caseDetail.value ? ANALYSIS_STATUS_META[caseDetail.value.analysis_status] : null,
);
const caseProcedure = computed(() =>
  caseDetail.value ? PROCEDURE_LABELS[caseDetail.value.procedure] : "",
);

/** 格式化消息列表顶部显示时间（HH:mm） */
const headerTime = computed(() => {
  const now = new Date();
  return `${String(now.getHours()).padStart(2, "0")}:${String(
    now.getMinutes(),
  ).padStart(2, "0")}`;
});

/** 清理本地 Mock 定时器或进行中的真实 SSE 流 */
function cleanupActiveGeneration() {
  if (timer) {
    clearTimeout(timer);
    timer = null;
  }
  if (streamHandle) {
    streamHandle.abort();
    streamHandle = null;
  }
}

onMounted(async () => {
  // 1. 案件问答模式下预加载案件概要卡片
  if (props.mode === "case") {
    fetchCase(props.caseId ?? 1)
      .then((item) => {
        if (!unmounted) caseDetail.value = item;
      })
      .catch(() => undefined);
  }

  // 2. 助手模式下加载后端推荐问（失败则保留默认推荐问兜底）
  if (!USE_MOCK && props.mode === "assistant") {
    fetchRecommendations()
      .then((list) => {
        if (!unmounted && list.length) recommendations.value = list;
      })
      .catch(() => undefined);
  }

  // 3. 若从历史记录进入既有会话，优先拉取历史消息与引用
  if (!USE_MOCK && props.conversationId) {
    loadingHistory.value = true;
    try {
      const page = await fetchConversationMessagesPage(props.conversationId);
      if (!unmounted) {
        messages.value = mapHistory(page.items);
        earlierCursor.value = page.next_cursor;
        const last = messages.value[messages.value.length - 1];
        if (last) scrollToLastUser(last.id);
      }
    } catch (error) {
      const msg = error instanceof Error ? error.message : "加载历史消息失败";
      uni.showToast({ title: msg, icon: "none" });
    } finally {
      loadingHistory.value = false;
    }
  }

  // 4. 若携带首条提问（如首页快捷发问、案件卡片入口），自动发送
  const question = (props.initialQuestion || "").trim();
  if (question && !unmounted) {
    void send(question);
  }
});

function mapHistory(items: ConversationMessageRecord[]): ChatMessage[] {
  return items.filter((item) => item.role === "user" || item.role === "assistant")
    .map((item) => ({
      id: ++sequence,
      serverId: item.id,
      role: item.role as "user" | "assistant",
      text: item.content,
      citations: item.citations,
      status: item.status,
    }));
}

async function loadEarlier() {
  if (!props.conversationId || earlierCursor.value === null || loadingHistory.value || typing.value) return;
  loadingHistory.value = true;
  const previousFirst = messages.value[0]?.id;
  try {
    const page = await fetchConversationMessagesPage(props.conversationId, earlierCursor.value);
    if (unmounted) return;
    messages.value = [...mapHistory(page.items), ...messages.value];
    earlierCursor.value = page.next_cursor;
    if (previousFirst) scrollToLastUser(previousFirst);
  } catch (error) {
    uni.showToast({ title: error instanceof Error ? error.message : "加载历史消息失败", icon: "none" });
  } finally {
    loadingHistory.value = false;
  }
}

onUnmounted(() => {
  unmounted = true;
  generationVersion += 1;
  // 组件卸载前通知服务端中断流并关闭底层传输连接
  if (activeConversationId.value && activeServerMessageId.value) {
    void cancelConversationMessage(
      activeConversationId.value,
      activeServerMessageId.value,
    ).catch(() => undefined);
  }
  cleanupActiveGeneration();
});

function scrollToLastUser(id: number) {
  nextTick(() => {
    setTimeout(() => {
      scrollTarget.value = `msg-${id}`;
    }, 30);
  });
}

/**
 * 停止当前 AI 生成：
 * 1) 先调用服务端 cancel 接口标记消息 cancelled；
 * 2) 再中止客户端 SSE 连接并更新 UI 状态。
 */
async function stopGenerating() {
  generationVersion += 1;
  const convId = activeConversationId.value;
  const msgId = activeServerMessageId.value;
  cleanupActiveGeneration();
  typing.value = false;
  activeServerMessageId.value = null;

  const last = messages.value[messages.value.length - 1];
  if (last?.streaming) {
    last.streaming = false;
    last.status = "cancelled";
    if (!last.text) last.text = "已停止生成。";
  }

  if (!USE_MOCK && convId && msgId) {
    await cancelConversationMessage(convId, msgId).catch(() => undefined);
  }
}

async function send(
  text = draft.value,
  scrollToUser = messages.value.length > 0,
) {
  const question = text.trim();
  if (!question || typing.value || loadingHistory.value || unmounted) return;
  const version = ++generationVersion;
  const isCurrent = () => !unmounted && version === generationVersion;

  draft.value = "";
  attachOpen.value = false;
  const userMessage: ChatMessage = {
    id: ++sequence,
    role: "user",
    text: question,
  };
  messages.value.push(userMessage);
  typing.value = true;
  if (scrollToUser) scrollToLastUser(userMessage.id);

  // Mock 模式维持原有本地结构化答复演示
  if (USE_MOCK) {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => {
      const blocks = getMockAnswer(question);
      messages.value.push({
        id: ++sequence,
        role: "assistant",
        text: answerToPlainText(blocks),
        blocks,
      });
      typing.value = false;
    }, 700);
    return;
  }

  // 真实后端模式：先确保会话存在，再占位 assistant 气泡并通过 SSE 增量拼接
  const assistantMessage = reactive<ChatMessage>({
    id: ++sequence,
    role: "assistant",
    text: "",
    citations: [],
    streaming: true,
    status: "streaming",
  });
  messages.value.push(assistantMessage);

  try {
    if (!activeConversationId.value) {
      const created = await createConversation({
        case_id: props.mode === "case" ? props.caseId ?? 1 : null,
        title: question.slice(0, 30),
      });
      if (!isCurrent()) return;
      activeConversationId.value = created.id;
    }

    const convId = activeConversationId.value;
    scrollToLastUser(assistantMessage.id);

    streamHandle = streamSsePost(
      `/conversations/${convId}/messages/stream`,
      {
        content: question,
        client_message_id: createClientId("msg"),
      },
      {
        onMeta: (payload) => {
          if (!isCurrent()) return;
          // 记录后端持久化的 assistant message_id，供取消与反馈使用
          assistantMessage.serverId = payload.message_id;
          activeServerMessageId.value = payload.message_id;
        },
        onCitations: (sources) => {
          if (!isCurrent()) return;
          assistantMessage.citations = sources;
        },
        onDelta: (chunk) => {
          if (!isCurrent()) return;
          assistantMessage.text += chunk;
        },
        onError: (errPayload) => {
          if (!isCurrent()) return;
          assistantMessage.errorMessage = errPayload.message || "本次回答未完成";
          if (!assistantMessage.text) {
            assistantMessage.text = errPayload.message || "回答生成中断，请重试";
          } else {
            uni.showToast({
              title: errPayload.message || "流式输出中断",
              icon: "none",
            });
          }
        },
        onDone: (payload) => {
          if (!isCurrent()) return;
          assistantMessage.status = payload.status;
          assistantMessage.streaming = false;
          activeServerMessageId.value = null;
        },
      },
    );

    await streamHandle.done;
  } catch (error) {
    if (!isCurrent()) return;
    const msg = error instanceof Error ? error.message : "发送消息失败";
    assistantMessage.status = "failed";
    assistantMessage.errorMessage = msg;
    if (!assistantMessage.text) {
      assistantMessage.text = msg;
    } else {
      uni.showToast({ title: msg, icon: "none" });
    }
  } finally {
    if (isCurrent()) {
      assistantMessage.streaming = false;
      typing.value = false;
      activeServerMessageId.value = null;
      streamHandle = null;
    }
  }
}

function useRecommendation(question: string) {
  void send(question);
}

function toggleAttach() {
  attachOpen.value = !attachOpen.value;
}

function pickAttach() {
  attachOpen.value = false;
  if (!USE_MOCK && props.mode === "case" && props.caseId) {
    // 引导前往当前案件文档页上传新材料
    uni.navigateTo({ url: `/pages/case/documents?id=${props.caseId}` });
    return;
  }
  uni.showToast({ title: "可在案件详情文档页上传材料", icon: "none" });
}

function copy(message: ChatMessage) {
  uni.setClipboardData({
    data: message.text,
    success: () => uni.showToast({ title: "已复制", icon: "none" }),
  });
}

function download() {
  uni.showToast({ title: "可通过右上角或复制保存答复", icon: "none" });
}

async function feedback(message: ChatMessage, type: "like" | "dislike") {
  const prev = message.feedback;
  // The API stores one rating; it does not support clearing a submitted rating.
  const next = USE_MOCK && prev === type ? undefined : type;
  if (prev === next) return;
  message.feedback = next;

  if (USE_MOCK || !next) return;
  if (!activeConversationId.value || !message.serverId) {
    return;
  }
  try {
    await submitMessageFeedback(
      activeConversationId.value,
      message.serverId,
      next,
    );
    uni.showToast({
      title: next === "like" ? "感谢点赞反馈" : "已记录您的反馈",
      icon: "none",
    });
  } catch (error) {
    message.feedback = prev;
    const msg = error instanceof Error ? error.message : "提交反馈失败";
    uni.showToast({ title: msg, icon: "none" });
  }
}

async function openCitation(citation: SseCitation) {
  if (!citation.file_id) return;
  try {
    await openRemoteFile(citation.file_id);
  } catch (error) {
    const msg = error instanceof Error ? error.message : "无法打开引用文档";
    uni.showToast({ title: msg, icon: "none" });
  }
}

function openMic() {
  uni.showToast({ title: "语音待接入", icon: "none" });
}
</script>

<template>
  <view class="chat-conversation">
    <scroll-view
      scroll-y
      class="chat-scroll"
      :show-scrollbar="false"
      :scroll-into-view="scrollTarget"
    >
      <view v-if="earlierCursor !== null" class="chat-time" @click="loadEarlier">
        {{ loadingHistory ? "加载中…" : "加载更早消息" }}
      </view>
      <view v-if="messages.length" class="chat-time">{{ headerTime }}</view>
      <view v-if="mode === 'case' && caseDetail" class="context-card">
        <text class="context-title">{{ caseDetail.title }}</text>
        <view class="context-grid">
          <text>
            证据上传：{{
              caseDetail.evidence_upload_status === "completed"
                ? "已完成"
                : caseDetail.evidence_upload_status === "partial"
                  ? "部分上传"
                  : "未上传"
            }}
          </text>
          <text>
            胜诉率：{{
              caseDetail.win_rate_status === "not_applicable"
                ? "暂不适用"
                : caseDetail.win_rate == null
                  ? "—"
                  : `${caseDetail.win_rate}%`
            }}
          </text>
          <text>案件程序：{{ caseProcedure }}</text>
          <text>分析状态：{{ caseStatus?.label }}</text>
        </view>
      </view>

      <view v-if="loadingHistory" class="welcome">
        <text class="welcome-sub">正在加载历史对话…</text>
      </view>
      <view v-else-if="!messages.length" class="welcome">
        <image class="welcome-robot" src="/static/images/robot.png" mode="aspectFit" />
        <text class="welcome-title">Hi～我是小诺！</text>
        <text class="welcome-sub">
          {{ mode === "case" ? "我已加载当前案件材料，可以基于案件继续提问。" : "您可以向我咨询任何法律问题，我能提供案件梳理、证据分析和文书书写。" }}
        </text>
      </view>

      <view class="messages">
        <view
          v-for="message in messages"
          :id="`msg-${message.id}`"
          :key="message.id"
          class="message"
          :class="message.role === 'user' ? 'message--user' : 'message--assistant'"
        >
          <view v-if="message.role === 'user'" class="bubble-user">
            {{ message.text }}
          </view>
          <view v-else class="bubble-assistant">
            <template v-if="message.blocks">
              <view
                v-for="(block, blockIndex) in message.blocks"
                :key="blockIndex"
                class="answer-block"
                :class="{
                  'answer-block--heading': block.heading,
                  'answer-block--indent': block.indent,
                  'answer-block--right': block.right,
                  'answer-block--blue': block.blue,
                }"
              >
                <view
                  v-for="(line, lineIndex) in block.lines"
                  :key="lineIndex"
                  class="answer-line"
                >
                  <text
                    v-for="(segment, segmentIndex) in line"
                    :key="segmentIndex"
                    :class="{
                      'answer-bold': segment.bold,
                      'answer-num': segment.num,
                    }"
                  >{{ segment.text }}</text>
                </view>
              </view>
            </template>
            <MarkdownContent v-else-if="message.text" :content="message.text" />
            <text v-else class="answer-text">
              {{ message.streaming ? "正在思考…" : "" }}
            </text>
            <text v-if="message.status === 'failed' || message.status === 'cancelled' ||
              (!message.streaming && message.status === 'streaming')" class="answer-disclaimer">
              {{ message.errorMessage || (message.status === 'cancelled' ? "已停止生成，以上内容未完成" : "本次回答未完成，请查看历史记录后重新提问") }}
            </text>

            <!-- 引用来源卡片：展示文档标题、页码与原文片段，支持点击打开原文档 -->
            <view
              v-if="message.citations && message.citations.length"
              class="citations"
            >
              <text class="citations-title">参考依据（{{ message.citations.length }}）</text>
              <view
                v-for="citation in message.citations"
                :key="`${citation.rank}-${citation.chunk_id || citation.document_title}`"
                class="citation-item"
                @click="openCitation(citation)"
              >
                <text class="citation-head">
                  [{{ citation.rank }}] {{ citation.document_title }}
                  {{ citation.page_no ? ` · 第${citation.page_no}页` : "" }}
                </text>
                <text v-if="citation.quote" class="citation-quote">
                  {{ citation.quote }}
                </text>
              </view>
            </view>

            <!-- 生成完成后在卡片底部展示免责声明，流式输出期间先不显示 -->
            <text
              v-if="!message.streaming && (message.text || (message.blocks && message.blocks.length))"
              class="answer-disclaimer"
            >
              内容由 AI 生成，仅供参考
            </text>

            <view v-if="!message.streaming" class="answer-actions">
              <view class="action" @click="copy(message)">
                <image
                  class="action-icon"
                  src="/static/images/icons/action-copy.png"
                  mode="aspectFit"
                />
              </view>
              <view class="action" @click="download">
                <image
                  class="action-icon"
                  src="/static/images/icons/action-download.png"
                  mode="aspectFit"
                />
              </view>
              <view class="action-spacer" />
              <view class="action" @click="feedback(message, 'like')">
                <image
                  class="action-icon"
                  :src="
                    message.feedback === 'like'
                      ? '/static/images/icons/action-like-active.png'
                      : '/static/images/icons/action-like.png'
                  "
                  mode="aspectFit"
                />
              </view>
              <view class="action" @click="feedback(message, 'dislike')">
                <image
                  class="action-icon"
                  :src="
                    message.feedback === 'dislike'
                      ? '/static/images/icons/action-dislike-active.png'
                      : '/static/images/icons/action-dislike.png'
                  "
                  mode="aspectFit"
                />
              </view>
            </view>
          </view>
        </view>

        <view v-if="typing" class="typing-row">
          <view class="typing">
            <view class="dot" />
            <view class="dot" />
            <view class="dot" />
          </view>
          <view
            v-if="!USE_MOCK"
            class="stop-btn"
            @click="stopGenerating"
          >
            停止生成
          </view>
        </view>

        <view v-if="!messages.length && !loadingHistory && mode === 'assistant'" class="rec">
          <text class="rec-title">推荐问</text>
          <view
            v-for="question in recommendations"
            :key="question"
            class="rec-item"
            @click="useRecommendation(question)"
          >
            <view class="rec-dot" />
            <text>{{ question }}</text>
          </view>
        </view>
      </view>
    </scroll-view>

    <ComposerBar
      v-model="draft"
      :placeholder="composerPlaceholder"
      @send="send()"
      @toggle-attach="toggleAttach"
      @mic="openMic"
    >
      <view v-if="attachOpen" class="attach-panel">
        <view
          v-for="label in ['拍照', '相册', '文档', '通话']"
          :key="label"
          class="attach-btn"
          @click="pickAttach"
        >
          {{ label }}
        </view>
      </view>
    </ComposerBar>
  </view>
</template>

<style lang="scss" scoped>
.chat-conversation {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.chat-scroll {
  flex: 1;
  height: 0;
  padding: 4px 18px 20px;
  box-sizing: border-box;
}

.chat-time {
  margin: 8px 0 12px;
  text-align: center;
  font-size: 11px;
  color: #9aa1ad;
}

.context-card {
  margin: 4rpx 24rpx 16rpx 0;
  padding: 22rpx 24rpx;
  border-radius: 18rpx;
  background: #f4f6fa;
}

.context-title {
  display: block;
  font-size: 28rpx;
  font-weight: 700;
  color: #333;
}

.context-grid {
  display: flex;
  flex-wrap: wrap;
  margin-top: 10rpx;
  font-size: 22rpx;
  color: $text-secondary;

  text {
    width: 50%;
    margin-top: 6rpx;
  }
}

.welcome {
  padding: 30rpx 48rpx 0;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.welcome-robot {
  width: 180rpx;
  height: 200rpx;
}

.welcome-title {
  margin-top: 12rpx;
  font-size: 36rpx;
  font-weight: 700;
  color: #2d2d2d;
}

.welcome-sub {
  margin-top: 10rpx;
  text-align: center;
  font-size: 24rpx;
  line-height: 1.6;
  color: $text-secondary;
}

.messages {
  padding: 0;
}

.message {
  margin: 0;
}

.message--user {
  display: flex;
  justify-content: flex-end;
  margin: 8px 0 0;
}

.messages > .message--user:first-child {
  margin-top: 0;
}

.message--assistant {
  margin-top: 24px;
}

.bubble-user {
  max-width: 76%;
  padding: 12px 16px;
  border-radius: 12px;
  background: $brand;
  color: #fff;
  font-size: 15px;
  line-height: 1.5;
  box-shadow: 0 4px 12px rgba(33, 92, 255, 0.16);
}

.bubble-assistant {
  padding: 16px 16px 10px;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 8px 24px rgba(40, 70, 120, 0.08);
  font-size: 14px;
  line-height: 1.8;
  color: #333;
}

.answer-block {
  margin: 0 0 12px;
}

.answer-block--heading {
  margin: 2px 0 10px;
  font-size: 16px;
  font-weight: 700;
  line-height: 1.5;
}

.answer-block--indent {
  padding-left: 18px;
}

.answer-block--right {
  text-align: right;
}

.answer-block--blue {
  color: #215cff;
}

.answer-line {
  line-height: 1.8;
}

.answer-bold {
  font-weight: 700;
}

.answer-num {
  color: #215cff;
  font-weight: 700;
}

.answer-text {
  display: block;
  white-space: pre-line;
  font-size: 14px;
  line-height: 1.8;
  color: #333;
}

.answer-disclaimer {
  display: block;
  margin-top: 10px;
  font-size: 11px;
  line-height: 1.5;
  color: #9aa3b2;
}

.answer-actions {
  display: flex;
  align-items: center;
  gap: 26px;
  margin-top: 6px;
  padding: 9px 2px 2px;
  border-top: 1px solid #f3f4f7;
  color: #8b92a0;
}

.action {
  display: flex;
  align-items: center;
  justify-content: center;
}

.action-icon {
  width: 18px;
  height: 18px;
}

.action-spacer {
  flex: 1;
}

.typing {
  display: flex;
  gap: 8rpx;
  width: max-content;
  margin-bottom: 20rpx;
  padding: 18rpx 22rpx;
  border-radius: 18rpx;
  background: #fff;
  box-shadow: 0 8rpx 24rpx rgba(40, 70, 120, 0.08);
}

.dot {
  width: 10rpx;
  height: 10rpx;
  border-radius: 50%;
  background: #c7d2e6;
}

.rec {
  margin-top: 24rpx;
  padding: 28rpx;
  border-radius: 24rpx;
  background: linear-gradient(135deg, #e6f3ff 0%, #f7faff 70%, #fff 100%);
}

.rec-title {
  display: block;
  margin-bottom: 16rpx;
  font-size: 28rpx;
  font-weight: 700;
  color: #333;
}

.rec-item {
  display: flex;
  align-items: flex-start;
  padding: 10rpx 0;
  font-size: 26rpx;
  color: #333;
}

.rec-dot {
  flex: none;
  width: 10rpx;
  height: 10rpx;
  margin: 12rpx 14rpx 0 0;
  border-radius: 50%;
  background: $brand-bright;
}

.attach-panel {
  display: flex;
  padding: 12rpx 0 4rpx;
}

.attach-btn {
  flex: 1;
  margin: 0 6rpx;
  padding: 20rpx 0;
  border: 1rpx solid #ebedf1;
  border-radius: 18rpx;
  text-align: center;
  font-size: 24rpx;
  color: #5e6673;
  background: #fff;
}

.typing-row {
  display: flex;
  align-items: center;
  gap: 16rpx;
}

.stop-btn {
  padding: 8rpx 20rpx;
  border-radius: 999rpx;
  background: #f1f4fb;
  color: $brand;
  font-size: 22rpx;
}

.citations {
  margin-top: 20rpx;
  padding-top: 16rpx;
  border-top: 1rpx solid $line;
  display: flex;
  flex-direction: column;
  gap: 10rpx;
}

.citations-title {
  font-size: 22rpx;
  font-weight: 600;
  color: $muted;
}

.citation-item {
  padding: 12rpx 16rpx;
  border-radius: 12rpx;
  background: #f7f9fc;
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}

.citation-head {
  font-size: 23rpx;
  font-weight: 600;
  color: $brand;
}

.citation-quote {
  font-size: 22rpx;
  line-height: 1.5;
  color: $text-secondary;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
