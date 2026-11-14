import assert from "node:assert/strict";
import { test } from "node:test";
import { loadService } from "./service-harness.mjs";

const frame = (event, data, newline = "\n") =>
  `event: ${event}${newline}data: ${JSON.stringify(data)}${newline}${newline}`;
const done = frame("done", { message_id: 1, status: "completed" });
const bytes = (text) => new TextEncoder().encode(text);
function response(chunks, type = "text/event-stream") {
  return new Response(new ReadableStream({ start(controller) {
    for (const chunk of chunks) controller.enqueue(chunk);
    controller.close();
  } }), { headers: { "content-type": type } });
}

for (const platform of ["H5", "MP-WEIXIN"]) {
  function setup(chunks, handlers = {}) {
    let chunkCallback;
    const globals = platform === "H5" ? {
      fetch: async () => response(chunks),
    } : {
      uni: { request: (options) => {
        queueMicrotask(() => {
          for (const chunk of chunks) chunkCallback({ data: chunk.buffer.slice(chunk.byteOffset, chunk.byteOffset + chunk.byteLength) });
          options.success({ statusCode: 200 });
        });
        return { onChunkReceived: (cb) => { chunkCallback = cb; }, abort() {} };
      } },
    };
    const { service } = loadService("sse", { platform, globals });
    return service.streamSsePost("/conversations/1/messages/stream", { content: "合成问题" }, handlers);
  }

  test(`${platform}: every byte boundary preserves Chinese/emoji and CRLF frames`, async () => {
    let text = "";
    let terminal;
    const body = frame("meta", { message_id: 1, conversation_id: 1 }) +
      frame("delta", { text: "中文🙂律师\n第二行" }, "\r\n") + done;
    await setup([...bytes(body)].map((byte) => Uint8Array.of(byte)), {
      onDelta: (delta) => { text += delta; }, onDone: (event) => { terminal = event.status; },
    }).done;
    assert.equal(text, "中文🙂律师\n第二行");
    assert.equal(terminal, "completed");
  });

  test(`${platform}: EOF after partial answer must reject without done`, async () => {
    let text = "";
    await assert.rejects(setup([bytes(frame("delta", { text: "保留的片段" }))], {
      onDelta: (delta) => { text += delta; },
    }).done, { code: "stream_incomplete" });
    assert.equal(text, "保留的片段");
  });

  test(`${platform}: unterminated done frame must not claim completion`, async () => {
    await assert.rejects(setup([bytes(done.trimEnd())]).done, { code: "stream_incomplete" });
  });

  test(`${platform}: corrupt JSON fails instead of silently dropping data`, async () => {
    await assert.rejects(setup([bytes("event: delta\ndata: {broken}\n\n" + done)]).done,
      { code: "stream_protocol_error" });
  });

  test(`${platform}: server failure status is delivered and partial text survives`, async () => {
    const received = [];
    await setup([bytes(frame("delta", { text: "部分回答" }) +
      frame("error", { code: "upstream_error", message: "本次未完成" }) +
      frame("done", { message_id: 1, status: "failed" }))], {
      onDelta: (text) => received.push(text), onError: (e) => received.push(e.code),
      onDone: (e) => received.push(e.status),
    }).done;
    assert.deepEqual(received, ["部分回答", "upstream_error", "failed"]);
  });
}

test("H5: non-SSE successful response is rejected", async () => {
  const { service } = loadService("sse", { globals: { fetch: async () => response([bytes("<html>proxy error</html>")], "text/html") } });
  await assert.rejects(service.streamSsePost("/stream", {}, {}).done, { code: "stream_protocol_error" });
});

test("H5: authentication failure redirects once and preserves server error", async () => {
  const { service, redirects } = loadService("sse", { globals: {
    fetch: async () => new Response(JSON.stringify({ error: { code: "unauthorized", message: "请先登录" } }), { status: 401 }),
  } });
  await assert.rejects(service.streamSsePost("/stream", {}, {}).done, { status: 401, code: "unauthorized" });
  assert.equal(redirects(), 1);
});

test("H5: explicit cancel settles without reporting a network failure", async () => {
  const { service } = loadService("sse", { globals: { fetch: async (_url, { signal }) =>
    new Promise((_resolve, reject) => signal.addEventListener("abort", () => reject(new Error("aborted")))) } });
  const stream = service.streamSsePost("/stream", {}, {});
  stream.abort();
  await stream.done;
});

test("WeChat: missing chunk support fails explicitly and aborts transport", async () => {
  let aborted = false;
  const { service } = loadService("sse", { platform: "MP-WEIXIN", globals: {
    uni: { request: () => ({ abort: () => { aborted = true; } }) },
  } });
  await assert.rejects(service.streamSsePost("/stream", {}, {}).done, { code: "stream_unsupported" });
  assert.equal(aborted, true);
});
