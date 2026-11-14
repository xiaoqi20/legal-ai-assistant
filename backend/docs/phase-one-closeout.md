# 一期收尾验收记录

日期：2026-11-13。数据为合成案件和合成材料，不涉及真实个人或案件。

## 本地验收结果

- PostgreSQL 17 + pgvector、FastAPI、独立 Worker、MinIO 已在本地运行；`GET /health/ready` 显示数据库就绪，AI 与 Embedding 配置已加载。H5 开发服务位于 `http://127.0.0.1:5173`。
- H5 关闭 Mock 后完成合成案件真实问答，DeepSeek 流式返回“合同总价为人民币100万元，乙方已支付80万元，尚欠尾款20万元[1]。”；引用展示了对应合成合同材料。阿里云 Embedding、文件 Worker、PostgreSQL 向量写入和显式权限过滤召回的真实联调结果见 [validation.md](validation.md)。
- 修复 `localhost` / `127.0.0.1` 本地预览跨域允许列表；微信手机号授权被拒绝后不再调用开发测试登录；真实模式隐藏虚构手机号。
- 通过开发种子脚本为身份 `demo` 新增合成案件 `case_id=4`，首页搜索、详情、人工证据目录与无案件文档空状态均已在 H5 检查；胜诉率保持空值，未伪造分析结果。此次验收发现并修正了人工维护证据目录被误标为 AI 生成的问题。
- SSE 适配器验证中文和 emoji 任意字节切分、CRLF、错误/取消、损坏帧和 EOF 缺少 `done`；历史会话与消息使用服务端游标分页；文件轮询超时显示仍在处理而不冒报完成。
- 材料列表现携带可用附件元数据并有后端集成断言。协议链接按类型打开；正式协议未发布时显示未发布状态，不把原型文本呈现为正式法律文本。

## 自动检查

- Backend: `uv run ruff check .` 通过；`LAW_TEST_S3=1 uv run pytest -q`，**16 passed**，使用专用 `law_backend_test` 数据库。
- Frontend: `pnpm test`，**18 passed**；`pnpm type-check`、`pnpm build:h5`、`pnpm build:mp-weixin` 均通过。
- 本次追加展示修复后重新运行 `pnpm type-check`、`pnpm build:h5`；开发种子脚本 `uv run ruff check scripts/seed.py` 通过。
- H5 构建仍输出当前依赖链的 Dart Sass legacy JS API 弃用告警；构建成功，本次未做与一期功能无关的依赖升级。

## 尚未通过的外部门槛

- 微信开发者工具当前未启用 CLI 服务端口，因此本次无法通过工具驱动编译预览；小程序 `manifest.json` 的 AppID 也需在本地部署配置中注入，不能留空发布。
- 尚无目标 iOS/Android 真机验收：微信手机号授权、不同基础库的 UTF-8 分块与中断取消、文件预览/下载、登录态恢复仍需验证。
- 尚无生产 HTTPS/反向代理 SSE 不缓冲验证、生产 S3/COS/OSS 网络及权限验证、备份恢复演练、并发/容量和费用账单验收。
- 正式用户服务协议、隐私政策、免责声明仍需定稿和发布；界面在缺文档时会明确提示未发布。

一期核心后端和本地 H5 联调已收尾，**不能据此标记微信小程序生产发布验收通过**。第二阶段建议仍以 OCR 与材料写入/律师复核闭环为候选，先关闭上述设备和部署门槛。
