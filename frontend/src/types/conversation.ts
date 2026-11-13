import type { SseCitation } from "@/services/sse";

export type ConversationGroup = "本周" | "本月" | "半年";

export interface ConversationSummary {
  id: number;
  title: string;
  group: ConversationGroup;
  mode?: "assistant" | "case_qa";
  case_id?: number | null;
  updated_at?: string;
  active?: boolean;
}

export interface ConversationMessageRecord {
  id: number;
  conversation_id: number;
  seq: number;
  role: "user" | "assistant" | "system";
  content: string;
  status: "streaming" | "completed" | "failed" | "cancelled";
  created_at: string;
  citations?: SseCitation[];
}
