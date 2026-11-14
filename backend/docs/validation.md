# 一期后端验收记录

日期：2026-11-14。使用合成数据，无真实案件或用户文档。

## 已通过

- Python 3.12.14 / `uv sync --frozen`，依赖锁文件可用于 macOS arm64 与 Linux arm64 容器。
- `uv run ruff check .`、`uv run python -m compileall -q app migrations scripts`。
- `uv run pytest -q`：**19 passed, 1 skipped**。覆盖新建案件、字段校验、用户隔离、详情读取和创建后上传；OCR 图片校对与扫描 PDF 页级续跑使用合成数据和假 OCR。测试业务数据仅写入显式配置的 `law_backend_test`，每个集成场景从新 schema 迁移。真实 S3 测试需另行启用 `LAW_TEST_S3=1`。
- 真实 PostgreSQL 17 + pgvector：认证/登出、角色必填校验、用户隔离、组织成员撤销后的案件/召回/历史隔离、混合检索、材料引用、流式持久化、用量与估算成本、消息幂等、并发准入、软删除和审计。
- 流式状态：中文增量、上游异常、输出截断、正常完成、显式取消、首个事件后断连、部分内容后断连、失效租约恢复；不将残缺流标为成功。
- 实际 OpenAI Python SDK + HTTP 测试传输层：DeepSeek SSE 中文、usage 和结束块解析，Embedding 1536 维参数与错误维度拒绝。此项验证协议适配，不是实际付费服务调用。
- 文档：真实 PDF 文本提取、扫描/加密 PDF 行为、DOCX 段落/表格与独立解析进程、Unicode 重叠分块；假 OCR 图片流程覆盖置信度门禁、页坐标/来源持久化、人工校订及校订后才向量化。
- 持久化任务：并发领取互斥、租约过期恢复、哈希不匹配隔离、结构化分析 JSON 校验/来源记录/请求幂等、无材料明确失败、排队分析取消。
- 真实 MinIO：签名 POST 上传、匿名 GET 拒绝、CORS、对象版本固定、确认后覆盖同 key 时仍解析和下载原始版本，测试对象版本已清理。
- Alembic 空库和隔离测试库逐版迁移至 `0006`，本次建案 API 集成测试在隔离库通过。既有 `law_dev` 结构签名比对、接管与升级为此前验收记录；本次未在 `law_dev` 应用 `0006`。
- 根目录 `database/verify-schema.sql` 在增量迁移后的 `law_dev` 回归通过；原有复合外键、NULL 安全触发器、组织 owner、角色字段、幂等和只追加审计约束继续生效，回归数据回滚。
- 本地 HTTP `health/live`、`health/ready`、OpenAPI 32 个路径、未登录 401、缺少模型配置 503。
- Docker 镜像 `law-backend:0.1.0` 构建通过；镜像内 API 数据库连接/就绪检查、非 root UID 10001、独立 Worker 启动通过。临时验收容器已停止并删除。
- 本地 `.env`、`.env.test`、Python 缓存和 `.venv` 的 Git 忽略规则验证通过；Docker context 排除配置密钥和本地虚拟环境。

## 本地交付状态

OCR 开发功能验证使用合成图片和可注入的假 OCR 服务；没有声称真实阿里云 OCR 已验收。启用真实识别需在 `backend/.env` 单独配置 OCR AccessKey，并确认阿里云 OCR 服务已开通。

本机 Docker Hub/Quay 对 MinIO 对应仓库拉取失败；使用本机已经存在且核对版本的官方镜像 digest 完成验证。新环境若无法取得该 digest，需配置可信镜像源 `LAW_MINIO_IMAGE`。API 镜像本身从固定版本的 Python/uv 基础镜像构建成功。

## 仍需外部验收

- 真实 DeepSeek 和阿里云 API Key、账号可用模型、工作空间/地域 URL、生产费用单价与实际账单核对。当前未执行付费模型请求，缺密钥时不返回伪造 AI 回答。
- 微信小程序 AppID/密钥/手机号授权资质、正式三类协议发布，iOS/Android 真机授权、分块 UTF-8/Markdown、断网/取消与文档打开。
- 前端多数页面仍为本地 Mock，需按后端 `/api/v1` 契约接入认证、上传、会话和分析。此次未修改前端，不声称前后端已完成联调。
- 生产 HTTPS/代理链路的 SSE 不缓冲验证，部署网络中的私有 S3/COS/OSS、受限数据库/存储账号、备份恢复与实际容量测试。

本期支持案件新建；暂不提供案件编辑/删除、真实短信网关、语音 ASR、实时通话或未经确认的胜诉率计算。

## 真实凭据联调补充（2026-11-13）

本节取代前文“未配置凭据/未执行真实模型请求”的当前状态描述；前文保留首次工程验收记录。

2026-11-13 收尾后的前端 H5 联调与当前待验项见 [phase-one-closeout.md](phase-one-closeout.md)。本节后续“前端仍未切换真实数据源”的历史描述以该收尾记录为准；前文首次验收事实不作改写。

- 检测到 `.env` 已配置真实凭据，但旧 API/Worker 尚未加载；已重启两个服务并确认 readiness 的 AI/Embedding 配置均为 true。
- 阿里云真实调用：`text-embedding-v4` 返回 1536 维向量；合成 TXT 经真实 MinIO 上传、独立 Worker 解析、真实向量化写入 PostgreSQL，再经真实问题向量化和显式权限过滤召回通过。
- DeepSeek 真实 SSE：首个答案片段约 1.41 秒，答案为“总价100万元，已付款80万元，尚欠尾款20万元[1]。”。终态 completed，引用与用量已落库；输入 305 token、输出 38 token。
- DeepSeek 真实结构化 `case_summary` 任务 succeeded，JSON 校验、材料来源、提示词版本和分析结果持久化通过。
- 微信 AppID/AppSecret 成功获取 access_token（有效期 7200 秒），令牌和密钥未输出或保存到验收记录。手机号完整登录仍须真机/开发者工具生成 `login_code` 与 `phone_code`，此次未冒充通过。
- 为便于复查，保留合成案件 case_id=2、文件 file_id=4、对话 conversation_id=2、分析 analysis_id=1，归属开发身份 demo。未使用真实案件或个人资料。
- 详细脱敏结果见 `live-validation.json`。只执行少量真实服务联调，未重复触发付费模型回归。
