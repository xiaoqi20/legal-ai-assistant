import type {
  ConversationGroup,
  ConversationMessageRecord,
  ConversationSummary,
} from "@/types/conversation";
import { USE_MOCK, request } from "./request";

const mockConversations: ConversationSummary[] = [
  { id: 1, title: "未命名对话", group: "本周" },
  { id: 2, title: "关于民事诉讼的案情梳理", group: "本周", active: true },
  { id: 3, title: "王家村房屋拆迁补偿纠纷案件梳理", group: "本周" },
  { id: 4, title: "未命名对话", group: "本月" },
  { id: 5, title: "关于民事诉讼的案情梳理", group: "本月" },
  { id: 6, title: "王家村房屋拆迁补偿纠纷案件梳理", group: "本月" },
  { id: 7, title: "王家村房屋拆迁补偿纠纷案件梳理", group: "半年" },
];

interface BackendConversationRow {
  id: number;
  title: string;
  mode: "assistant" | "case_qa";
  case_id: number | null;
  created_at: string;
  updated_at: string;
}

function resolveGroup(iso: string): ConversationGroup {
  const ts = Date.parse(iso);
  if (Number.isNaN(ts)) return "本周";
  const diffDays = (Date.now() - ts) / (1000 * 60 * 60 * 24);
  if (diffDays <= 7) return "本周";
  if (diffDays <= 30) return "本月";
  return "半年";
}

function mapConversation(row: BackendConversationRow): ConversationSummary {
  return {
    id: row.id,
    title: row.title || "未命名对话",
    group: resolveGroup(row.updated_at || row.created_at),
    mode: row.mode,
    case_id: row.case_id,
    updated_at: row.updated_at || row.created_at,
  };
}

export interface HistoryPage<T> {
  items: T[];
  next_cursor: number | null;
}

export async function fetchConversationsPage(
  keyword = "",
  beforeId?: number,
): Promise<HistoryPage<ConversationSummary>> {
  if (USE_MOCK) {
    return {
      items: mockConversations.filter((item) => item.title.includes(keyword))
        .map((item) => ({ ...item })),
      next_cursor: null,
    };
  }
  const res = await request<HistoryPage<BackendConversationRow>>("/conversations", {
    query: { keyword, limit: 50, before_id: beforeId },
  });
  return { items: res.items.map(mapConversation), next_cursor: res.next_cursor };
}

export async function createConversation(payload: {
  case_id?: number | null;
  title?: string;
}): Promise<ConversationSummary> {
  const row = await request<BackendConversationRow>("/conversations", {
    method: "POST",
    data: {
      case_id: payload.case_id ?? null,
      title: payload.title || "新对话",
    },
  });
  return mapConversation(row);
}

export function renameConversation(
  conversationId: number,
  title: string,
): Promise<{ id: number; title: string }> {
  return request<{ id: number; title: string }>(
    `/conversations/${conversationId}`,
    {
      method: "PATCH",
      data: { title },
    },
  );
}

export async function deleteConversations(ids: number[]): Promise<void> {
  if (USE_MOCK || !ids.length) return;
  await request<void>("/conversations/delete", {
    method: "POST",
    data: { ids },
  });
}

export async function fetchConversationMessagesPage(
  conversationId: number,
  beforeSeq?: number,
): Promise<HistoryPage<ConversationMessageRecord>> {
  const res = await request<{
    items: ConversationMessageRecord[];
    next_cursor: number | null;
  }>(`/conversations/${conversationId}/messages`, {
    query: { limit: 100, before_seq: beforeSeq },
  });
  return res;
}

export function cancelConversationMessage(
  conversationId: number,
  messageId: number,
): Promise<{ id: number; status: string }> {
  return request<{ id: number; status: string }>(
    `/conversations/${conversationId}/messages/${messageId}/cancel`,
    { method: "POST" },
  );
}

export function submitMessageFeedback(
  conversationId: number,
  messageId: number,
  rating: "like" | "dislike",
  comment?: string,
): Promise<{ status: string }> {
  return request<{ status: string }>(
    `/conversations/${conversationId}/messages/${messageId}/feedback`,
    {
      method: "PUT",
      data: comment ? { rating, comment } : { rating },
    },
  );
}
