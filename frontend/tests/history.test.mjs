import assert from "node:assert/strict";
import { test } from "node:test";
import { loadService } from "./service-harness.mjs";

test("history requests carry the search keyword and cursor", async () => {
  const calls = [];
  const { service } = loadService("history", {
    request: async (path, options) => {
      calls.push({ path, options });
      return {
        items: [{
          id: 19,
          title: "合成历史记录",
          mode: "assistant",
          case_id: null,
          created_at: "2026-11-13T08:00:00Z",
          updated_at: "2026-11-13T09:00:00Z",
        }],
        next_cursor: 19,
      };
    },
  });

  const page = await service.fetchConversationsPage("合成", 25);
  assert.equal(calls[0].path, "/conversations");
  assert.equal(
    JSON.stringify(calls[0].options.query),
    JSON.stringify({ keyword: "合成", limit: 50, before_id: 25 }),
  );
  assert.equal(page.items[0].id, 19);
  assert.equal(page.next_cursor, 19);
});

test("message history forwards its older-message cursor", async () => {
  const calls = [];
  const { service } = loadService("history", {
    request: async (path, options) => {
      calls.push({ path, options });
      return { items: [], next_cursor: null };
    },
  });

  await service.fetchConversationMessagesPage(7, 101);
  assert.equal(calls[0].path, "/conversations/7/messages");
  assert.equal(
    JSON.stringify(calls[0].options.query),
    JSON.stringify({ limit: 100, before_seq: 101 }),
  );
});
