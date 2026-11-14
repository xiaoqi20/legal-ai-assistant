import {
  API_BASE_URL,
  ApiError,
  getStoredToken,
  parseApiError,
  redirectToLogin,
} from "./request";

export interface SseCitation {
  chunk_id?: number;
  file_id?: number;
  case_id: number;
  document_title: string;
  quote: string;
  page_no?: number | null;
  rank: number;
  relevance?: number | null;
}

export interface SseMetaEvent {
  conversation_id: number;
  message_id: number;
  user_message_id: number;
  protocol: string;
}

export interface SseDoneEvent {
  message_id: number;
  status: "completed" | "failed" | "cancelled";
  usage?: { input_tokens?: number; output_tokens?: number } | null;
}

export interface SseErrorEvent {
  code: string;
  message: string;
  retryable?: boolean;
}

export interface StreamHandlers {
  onMeta?: (payload: SseMetaEvent) => void;
  onCitations?: (sources: SseCitation[]) => void;
  onDelta?: (text: string) => void;
  onError?: (payload: SseErrorEvent) => void;
  onDone?: (payload: SseDoneEvent) => void;
}

// Stateful UTF-8 decoder safe across both H5 and WeChat JSCore chunk boundaries.
class IncrementalUtf8Decoder {
  private pending: number[] = [];

  push(bytes: Uint8Array): string {
    if (!bytes.length) return "";
    const merged = this.pending.length
      ? this.concat(this.pending, bytes)
      : bytes;
    this.pending = [];

    let out = "";
    let i = 0;
    while (i < merged.length) {
      const b0 = merged[i];
      if (b0 < 0x80) {
        out += String.fromCharCode(b0);
        i += 1;
      } else if ((b0 & 0xe0) === 0xc0) {
        if (i + 1 >= merged.length) {
          this.pending = Array.from(merged.slice(i));
          break;
        }
        const cp = ((b0 & 0x1f) << 6) | (merged[i + 1] & 0x3f);
        out += String.fromCodePoint(cp);
        i += 2;
      } else if ((b0 & 0xf0) === 0xe0) {
        if (i + 2 >= merged.length) {
          this.pending = Array.from(merged.slice(i));
          break;
        }
        const cp =
          ((b0 & 0x0f) << 12) |
          ((merged[i + 1] & 0x3f) << 6) |
          (merged[i + 2] & 0x3f);
        out += String.fromCodePoint(cp);
        i += 3;
      } else if ((b0 & 0xf8) === 0xf0) {
        if (i + 3 >= merged.length) {
          this.pending = Array.from(merged.slice(i));
          break;
        }
        const cp =
          ((b0 & 0x07) << 18) |
          ((merged[i + 1] & 0x3f) << 12) |
          ((merged[i + 2] & 0x3f) << 6) |
          (merged[i + 3] & 0x3f);
        out += String.fromCodePoint(cp);
        i += 4;
      } else {
        out += "\ufffd";
        i += 1;
      }
    }
    return out;
  }

  flush(): string {
    if (!this.pending.length) return "";
    this.pending = [];
    return "\ufffd";
  }

  private concat(prefix: number[], tail: Uint8Array): Uint8Array {
    const buf = new Uint8Array(prefix.length + tail.length);
    buf.set(prefix, 0);
    buf.set(tail, prefix.length);
    return buf;
  }
}

class SseFrameParser {
  private buffer = "";
  private handlers: StreamHandlers;
  private terminal = false;
  private errorSeen = false;

  constructor(handlers: StreamHandlers) {
    this.handlers = handlers;
  }

  feed(text: string) {
    if (!text) return;
    this.buffer = (this.buffer + text).replace(/\r\n/g, "\n");
    let boundary = this.buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const rawFrame = this.buffer.slice(0, boundary);
      this.buffer = this.buffer.slice(boundary + 2);
      this.dispatchFrame(rawFrame);
      boundary = this.buffer.indexOf("\n\n");
    }
  }

  flush() {
    // EOF is not an SSE event boundary. A missing/truncated done event is a failure.
    if (!this.terminal || this.buffer.trim()) {
      throw new ApiError(502, "stream_incomplete", "回答连接中断，请查看历史记录后重新提问");
    }
  }

  private dispatchFrame(frame: string) {
    const lines = frame.split("\n");
    let eventName = "message";
    const dataLines: string[] = [];

    for (const line of lines) {
      if (!line || line.startsWith(":")) continue;
      if (line.startsWith("event:")) {
        eventName = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).trimStart());
      }
    }

    if (!dataLines.length) return;
    if (this.terminal) {
      throw new ApiError(502, "stream_protocol_error", "回答流格式异常");
    }
    const rawData = dataLines.join("\n");
    let parsed: unknown = rawData;
    try {
      parsed = JSON.parse(rawData);
    } catch {
      throw new ApiError(502, "stream_protocol_error", "回答流格式异常");
    }
    if (!parsed || typeof parsed !== "object") {
      throw new ApiError(502, "stream_protocol_error", "回答流格式异常");
    }

    if (eventName === "meta") {
      this.handlers.onMeta?.(parsed as SseMetaEvent);
    } else if (eventName === "citations") {
      const payload = parsed as { sources?: SseCitation[] };
      this.handlers.onCitations?.(payload.sources ?? []);
    } else if (eventName === "delta") {
      const payload = parsed as { text?: string };
      if (payload.text) this.handlers.onDelta?.(payload.text);
    } else if (eventName === "error") {
      this.errorSeen = true;
      this.handlers.onError?.(parsed as SseErrorEvent);
    } else if (eventName === "done") {
      const done = parsed as SseDoneEvent;
      if (!["completed", "failed", "cancelled"].includes(done.status) ||
          (this.errorSeen && done.status === "completed")) {
        throw new ApiError(502, "stream_protocol_error", "回答结束状态异常");
      }
      this.terminal = true;
      this.handlers.onDone?.(parsed as SseDoneEvent);
    }
  }
}

export interface StreamHandle {
  abort: () => void;
  done: Promise<void>;
}

export function streamSsePost(
  path: string,
  body: Record<string, unknown>,
  handlers: StreamHandlers,
): StreamHandle {
  const token = getStoredToken();
  const url = `${API_BASE_URL}${path}`;
  const utf8 = new IncrementalUtf8Decoder();
  const parser = new SseFrameParser(handlers);

  // #ifdef H5
  const controller = new AbortController();
  let h5Aborted = false;
  const timeout = setTimeout(() => controller.abort(), 130000);
  const done = (async () => {
    try {
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      };
      if (token) headers.Authorization = `Bearer ${token}`;

      const response = await fetch(url, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      if (!response.ok) {
        let data: unknown = null;
        try {
          data = await response.json();
        } catch {
          data = null;
        }
        if (response.status === 401) redirectToLogin();
        throw parseApiError(response.status, data);
      }

      if (!response.body) {
        throw new ApiError(500, "stream_unsupported", "当前环境不支持流式响应");
      }
      if (!response.headers.get("content-type")?.includes("text/event-stream")) {
        throw new ApiError(502, "stream_protocol_error", "服务器未返回流式回答");
      }

      const reader = response.body.getReader();
      try {
        while (true) {
          const { value, done: streamDone } = await reader.read();
          if (streamDone) break;
          if (value) parser.feed(utf8.push(value));
        }
        parser.feed(utf8.flush());
        parser.flush();
      } finally {
        await reader.cancel().catch(() => undefined);
        reader.releaseLock();
      }
    } catch (error) {
      if (h5Aborted) return;
      if (controller.signal.aborted) {
        throw new ApiError(504, "stream_timeout", "回答超时，请查看历史记录后重新提问");
      }
      throw error;
    } finally {
      clearTimeout(timeout);
    }
  })();

  return {
    abort: () => { h5Aborted = true; controller.abort(); },
    done,
  };
  // #endif

  // #ifndef H5
  let requestTask: UniApp.RequestTask | null = null;
  let aborted = false;
  const mpDone = new Promise<void>((resolve, reject) => {
    const header: Record<string, string> = {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    };
    if (token) header.Authorization = `Bearer ${token}`;

    requestTask = uni.request({
      url,
      method: "POST",
      data: body,
      header,
      enableChunked: true,
      responseType: "arraybuffer",
      timeout: 130000,
      success: (response) => {
        if (aborted) {
          resolve();
          return;
        }
        if (response.statusCode >= 200 && response.statusCode < 300) {
          try {
            parser.feed(utf8.flush());
            parser.flush();
            resolve();
          } catch (error) {
            reject(error);
          }
          return;
        }
        let parsedError: unknown = null;
        if (response.data instanceof ArrayBuffer) {
          const text = new IncrementalUtf8Decoder().push(
            new Uint8Array(response.data),
          );
          try {
            parsedError = JSON.parse(text);
          } catch {
            parsedError = null;
          }
        } else {
          parsedError = response.data;
        }
        if (response.statusCode === 401) redirectToLogin();
        reject(parseApiError(response.statusCode, parsedError));
      },
      fail: (error) => {
        if (aborted) {
          resolve();
          return;
        }
        reject(new Error(error.errMsg || "流式连接失败"));
      },
    }) as unknown as UniApp.RequestTask;

    const chunkTask = requestTask as unknown as {
      onChunkReceived?: (cb: (res: { data: ArrayBuffer }) => void) => void;
    };
    if (!chunkTask?.onChunkReceived) {
      reject(new ApiError(501, "stream_unsupported", "当前微信版本不支持分块回答，请升级微信后重试"));
      requestTask?.abort();
      return;
    }
    chunkTask.onChunkReceived((res) => {
      if (aborted) return;
      try {
        if (res?.data) parser.feed(utf8.push(new Uint8Array(res.data)));
      } catch (error) {
        reject(error);
        requestTask?.abort();
      }
    });
  });

  return {
    abort: () => {
      aborted = true;
      requestTask?.abort();
    },
    done: mpDone,
  };
  // #endif
}
