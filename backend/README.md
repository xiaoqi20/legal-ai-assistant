# 律法 AI 后端（一期）

Python **3.12.14** + FastAPI **0.162.5** + Pydantic **2.14.3** + SQLAlchemy **2.1.8** + Alembic **1.20.1**，精确依赖见 `uv.lock`。使用现有 `law` schema 的 27 张业务表，不另建一套案件/用户数据。API 前缀 `/api/v1`，交互文档 `/docs`，机器契约 `/openapi.json`。

## 已实现范围

- 微信小程序 `login_code` + `phone_code` 服务端换取身份/手机号；不可混用两种 code。开发登录和短信 Mock 默认关闭，生产强制禁用。协议版本确认、角色档案、哈希会话令牌与退出撤销。
- 案件列表/搜索/详情与新建，证据目录/材料/附件、案件文档和分析结果查询；个人归属或有效组织成员权限检查。建案写入案件摘要、诉求及当事人并记录审计日志，编辑案件暂不开放。
- 私有 S3 兼容上传 POST 策略（5 分钟、服务端生成 key、精确大小/类型），完成确认后创建持久化任务。下载地址有效 2 分钟。必须启用对象版本控制，固定版本读取，Worker 重新校验 SHA-256。
- PDF、DOCX、UTF-8 TXT 及 JPEG/PNG 图片解析；扫描 PDF 与图片由 PostgreSQL 持久 Worker 异步调用阿里云 OCR，保留页码、文字块坐标、置信度、识别来源及原文。低于阈值（默认 0.85）的页面需人工校对；审核通过后排队进入重叠分块、阿里云 `text-embedding-v4`（显式 1536 维）和现有 RAG。OCR Key 使用独立的 `LAW_OCR_ACCESS_KEY_ID`、`LAW_OCR_ACCESS_KEY_SECRET`，需开通 OCR API 权限；支持 region、阈值和单文档 OCR 页数配置。识别结果会传输至阿里云 OCR 服务，部署前需确认数据处理授权及费用。
- 显式 SQL 工作流：权限过滤 → pgvector 余弦召回 + pg_trgm 候选 → RRF 排序 → 上下文预算 → 版本化提示词 → DeepSeek。无 LangChain、Agent 或独立向量库。助手模式只使用本人的对话上下文，不擅自检索所有案件。
- DeepSeek POST SSE：元信息、召回来源、中文增量、错误、结束事件；消息/引用/模型/提示词/耗时/用量落库。成本为配置价格的估算，价格或上游 usage 缺失时保留 `null`。不输出或保存模型 reasoning_content。
- 同一会话单次生成、幂等键、跨实例数据库并发/速率限制、上下文/输出限制、总超时、显式取消、断连与失效租约恢复。截断/上游不完整流不会标成功。不自动重试已消费的生成请求，避免重复计费。
- 案情摘要、时间轴、司法推理、争议焦点、证据链/清单异步分析，使用显式 RAG + DeepSeek JSON 输出与 Pydantic 校验，保存来源指纹与分析来源。分析可取消；结果仅覆盖检索片段，不声称遍历了完整卷宗。不生成胜诉率。
- 对话历史分页、重命名、反馈、批量软删除及追加审计。
- 二期新增材料草稿、版本、附件关联、提交/撤回、法务复核与操作快照；材料 AI 意见独立存储。新增证据目录和民事起诉状草稿、编辑历史版本、指定版本 DOCX 导出。规则和待办见 [二期推进记录](docs/phase-two-progress.md)。

外部服务未配置时返回明确错误，应用不会回退 Mock AI。测试中的替身仅存在于 `tests/`。`frontend/` 已有真实 API 适配，可通过 `VITE_USE_MOCK=false` 连接认证、案件、会话/SSE、文件、分析、历史与资料接口；小程序真机授权、SSE 分块、上传/下载和正式网络仍需端到端验收。

## 本地运行

在仓库根目录启动既有 PostgreSQL：

```sh
docker compose --env-file .env.local up -d --wait
cd backend
uv sync --frozen
```

首次配置时复制 `.env.example` 为 `.env`；已有配置不要覆盖。设置 URL 编码后的数据库连接串、DeepSeek API Key、阿里云 Embedding Key、模型名、地区对应的 base URL、S3 密钥。`.env` 已忽略，建议权限 `0600`。本机已完成真实 DeepSeek、阿里云 Embedding 和微信 access_token 联调，脱敏记录见 `docs/live-validation.json`；微信完整手机号登录仍待真机验收。

数据库迁移：

```sh
# 全新空数据库
uv run alembic upgrade head

# 如果已执行根目录 database-schema.sql：先精确校验列/约束/索引/触发器/函数，校验通过才接管。
uv run python -m scripts.adopt_database
uv run alembic upgrade head
```

已有 Alembic 版本的数据库直接 `upgrade head`。禁止对既有数据重复执行初始 DDL，禁止直接 `stamp head` 绕过实际迁移。迁移不会在 API 启动时自动运行；API 校验数据库当前版本。0001 基线不可自动回滚删除业务库；0002~0006 可逆，提示词回滚采用退役，保留历史引用。基线快照见 `migrations/sql/0001_initial.sql`。

当前版本为 `0007`，增加材料证明目的/版本、复核快照和文书历史版本；API/Worker 均需重启。0007 回滚前如已有新状态材料或文书分析，须先显式迁移这些数据，避免静默丢失。结构化 JSON 输出使用独立 `LAW_STRUCTURED_OUTPUT_TOKENS`（默认 8192）与非思考模式，避免思考占用输出额度导致截断；仍执行总超时、长度、Schema 和来源编号校验。

启动本地对象存储（`backend/.env` 设置独立随机 S3 密钥）：

```sh
docker compose up -d --wait
uv run python -m scripts.init_storage
```

MinIO 使用已验证的 **2025-09-07** 版本镜像 digest，数据位于独立 `law-backend_minio-data` 卷，端口 `59000` / 控制台 `59001` 仅绑定回环地址。若镜像源不可用，通过 `LAW_MINIO_IMAGE` 指定同版本的可信镜像仓库；本机已验证的缓存 digest 可直接启动。初始化创建私有桶并启用版本控制；本地 MinIO 与 API 默认允许 `http://localhost:5173` 和 `http://127.0.0.1:5173`，改预览来源时同步修改 `LAW_S3_CORS_ORIGINS` 与应用 `LAW_CORS_ORIGINS`。

分别在两个终端运行：

```sh
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
uv run python -m app.worker
```

健康检查：`GET /health/live` / `GET /health/ready`。ready 验证数据库并列出模型配置是否存在，不代表外部账号调用已通过。

开发演示需显式设置 `LAW_ALLOW_DEV_LOGIN=true`，随后在 `/docs` 调用 `POST /api/v1/auth/dev-login`：

```json
{"identity":"demo","agreed":true,"document_ids":[]}
```

仅当数据库尚未发布协议时，开发登录允许空 `document_ids`；发布后必须提交 `GET /agreements` 返回的全部最新协议 ID。生产必须发布三类正式协议，并配置微信资质及密钥。令牌为高熵不透明 Bearer，只保存 SHA-256 哈希；无永久开发后门、无客户端指定 user_id。当前会话过期需要重新登录。

用同一开发身份预置合成案件：

```sh
uv run python -m scripts.seed --identity demo
```

不会预设分析结果或胜诉率。文档必须自行上传合成资料。默认单文件 20 MiB、500 PDF 页、最多 100 张 OCR 页、50 万字符；DOCX 解压总量 50 MiB。PDF 页面在隔离子进程中渲染，文档解析进程可在任务超时时终止，Linux 子进程另有内存限制。

## 联调顺序

1. 登录取得 Bearer token，填写 `/profile`。创建新案件时 `POST /cases`，字段包括 `title`、`case_type`、`procedure`、`summary`、`claim`、`handling_identity`（`self` / `agent`）、`party_role_label`、`our_parties` 和 `opponent_parties`；案件与当事人同事务保存，并归属当前用户。暂不传文件名或本地文件路径，文件需在案件创建成功后走上传接口。无参数也可创建空白案件，分析状态保持 `not_analyzed`。
2. 查询 `/cases` 取得有权访问的 case_id。`GET /cases/{id}` 返回案件详情及当事人数组/我方与对方名称列表。
3. `POST /files/uploads` 申请上传，向返回的 `upload.url` 提交 multipart 表单，原样带上全部 `upload.fields`，文件字段名必须是 `file` 且放最后。随后 `POST /files/{id}/complete`。
4. 轮询 `GET /files/{id}`，只有 `available` 文件参与召回和下载。任务最多自动执行 3 次，退避 10/20 秒；永久解析错误直接结束。`dead` 任务可由上传人 `POST /files/{id}/retry`，哈希不匹配隔离文件必须重新上传。
5. `POST /conversations` 传 `{ "case_id": 123 }` 建立案件会话，传 `{}` 建立通用助手会话。
6. `POST /conversations/{id}/messages/stream`，内容见 [SSE 协议](docs/streaming.md)。网络断开先查消息历史；同一 `client_message_id` 再发返回 409，不重新调用模型。
7. 用 `POST /cases/{id}/analyses` 创建结构化分析：`{"analysis_type":"case_summary","client_request_id":"a-001"}`，返回 analysis_id/job_id；轮询 `/cases/{id}/analyses/{analysis_id}`。相同请求 ID 幂等，同案件同类型只能有一个在途任务。

完整路由和请求校验以 `/docs` 为准。案件列表保持前端 `CaseSummary[]` 形状；材料、分析等由服务层映射为页面模型。`VITE_API_BASE_URL` 应包含 `/api/v1`；通用请求与 SSE 适配器会带上 Bearer Authorization。前后端当前的代码适配与本地 H5 验收记录见 [一期收尾记录](docs/phase-one-closeout.md)；关闭 Mock 后仍须按真实账号和目标设备验收，不要将单一 H5 请求成功视为小程序全链路通过。

## 测试与部署

```sh
uv run ruff check .
uv run python -m compileall -q app migrations scripts
uv run pytest -q
```

测试需在 `.env.test` 中显式配置独立、名称以 `_test` 结尾的 PostgreSQL 数据库。测试会**删除并重建该测试库的 law schema**，每个场景独立迁移；禁止填业务数据库。核心测试使用真实 PostgreSQL/pgvector 与替身上游，覆盖权限、SQL 检索、任务重试/租约、流式生命周期、幂等与软删除，不需要付费 API Key。真实 S3 和真实上游账号的联调必须另行验证。

```sh
docker build -t law-backend:0.1.0 .
# API 使用镜像默认命令；Worker 复用同一镜像：
# /app/.venv/bin/python -m app.worker
```

镜像固定 Python 补丁与 uv 版本，按 `uv.lock` 安装，非 root 运行。容器连接串/对象存储地址必须使用部署网络可达主机，不能照抄宿主机 `127.0.0.1`。部署前通过独立迁移账号运行迁移，应用账号使用受限 DML 权限（示例见 `docs/runtime-role.sql`）。API 与 Worker 独立部署，Worker 建议至少 1 GiB 内存限制。

任务队列一期采用 PostgreSQL 的 `FOR UPDATE SKIP LOCKED`，租约、随机 fencing token、指数退避和业务结果同库保存；进程崩溃不丢任务，过期旧 Worker 不能提交结果。数据库全局短事务串行化 AI 资源准入，避免多实例绕过并发限制。后续吞吐需要时再迁移 Redis/Celery；本期不需要 Redis。

代理示例见 `docs/nginx.conf`，必须关闭 SSE 缓冲。微信端使用 `wx.request(enableChunked)` 的分块适配器，仍需 iOS/Android 真机验证 UTF-8 跨块、主动取消、断网与代理行为。真实模型和微信凭据验证范围见 `docs/validation.md`，不替代完整微信登录和端侧验收。

## 官方接口参考

- [FastAPI StreamingResponse](https://fastapi.tiangolo.com/advanced/custom-response/)
- [pgvector Python / SQLAlchemy](https://github.com/pgvector/pgvector-python)
- [DeepSeek 流式 Chat Completion](https://api-docs.deepseek.com/api/create-chat-completion/)
- [DeepSeek JSON Output](https://api-docs.deepseek.com/guides/json_mode/)
- [阿里云 OpenAI Embedding 兼容接口](https://www.alibabacloud.com/help/zh/model-studio/embedding-interfaces-compatible-with-openai)：v4 支持 1536 维、每批最多 10 条；新工作空间域名可配置，旧北京域名仍受支持。
- [微信手机号授权](https://developers.weixin.qq.com/miniprogram/dev/framework/open-ability/getPhoneNumber)
