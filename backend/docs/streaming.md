# law-sse-v1 流式协议

HTTP POST `/api/v1/conversations/{conversation_id}/messages/stream`：

```http
Authorization: Bearer <access_token>
Content-Type: application/json

{"content":"请根据材料说明合同价款","client_message_id":"unique-client-id-001"}
```

`client_message_id` 在同一会话内唯一，最长 64 字符（字母、数字、下划线、连字符）。已受理的相同 ID 返回 409，应查历史，不能重试成另一次付费请求。新的提问必须生成新 ID。同一会话在途生成返回 409；全局容量/用户速率限制返回 429。鉴权/请求校验/配置错误发生在流开始之前，返回普通 JSON：

```json
{"error":{"code":"unauthorized","message":"请先登录"},"request_id":"..."}
```

成功建流返回 `text/event-stream; charset=utf-8`。事件顺序：

```text
event: meta
data: {"conversation_id":1,"message_id":2,"user_message_id":1,"protocol":"law-sse-v1"}

event: citations
data: {"sources":[{"chunk_id":1,"file_id":1,"case_id":1,"document_title":"合成合同.pdf","page_no":1,"quote":"约定价款...","rank":1,"relevance":0.8}]}

event: delta
data: {"text":"合同约定"}

event: delta
data: {"text":"价款为100万元。[1]"}

event: done
data: {"message_id":2,"status":"completed","usage":{"input_tokens":100,"output_tokens":30}}

```

`citations` 是此次召回的有权访问材料，`rank` 与答案中的 `[1]` 对应；来源为空时必须向用户说明材料不足。它不代表所有召回来源都被模型逐一使用。只传最终回答，禁止展示模型 reasoning_content。收到 `delta` 只代表收到部分文本，**必须以 `done.status == completed` 判定成功**。

流内失败仍为 HTTP 200，输出错误和终态，不能只看 HTTP 状态：

```text
event: error
data: {"code":"output_limit","message":"本次回答未完成，可查看历史后重新提问","retryable":true}

event: done
data: {"message_id":2,"status":"failed","usage":null}

```

错误可能为 `upstream_error`、`upstream_incomplete`、`generation_timeout`、`output_limit`、`invalid_citation`、`cancelled`。正常等待可能收到注释 `: keepalive`，客户端忽略即可。总生成超时覆盖检索和生成，不在部分 token 已输出后自动重试上游。

小程序须用增量 UTF-8 解码器处理分块，保留尚未组成完整字符的字节；再保留尚未组成 `\n\n` 的 SSE 帧。网络块与事件/JSON/中文字符不对齐，禁止对每块直接 `JSON.parse`。一个网络块可能包含多个事件，任何事件也可能跨多个网络块。不要依赖浏览器 EventSource，因为此接口是带 Authorization 的 POST。

主动取消：`POST /conversations/{conversation_id}/messages/{message_id}/cancel`。连接关闭会尝试关闭上游并将残缺消息保存为 cancelled；API 进程突然退出时，失效租约会在历史读取、下一次准入或 Worker 轮询时标 failed。部分文本约每秒检查点落库，突然崩溃最多丢失最近检查点后的片段；不会把残缺回答标为完成。

若没有收到 done，应先 `GET /conversations/{id}/messages`：返回按 seq 升序的一页消息，`next_cursor` 用作下一页的 `before_seq`（更早消息）。状态是 streaming/completed/failed/cancelled。只把 completed 的会话消息作为后续模型上下文。客户端不支持 SSE 字节偏移重放；恢复以持久化历史为准。
