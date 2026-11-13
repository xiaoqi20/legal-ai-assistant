# 本地 PostgreSQL

本项目已在 `law-postgres-dev` 执行 `database-schema.sql`，创建 `law_dev` 数据库中 `law` schema 下的 27 张业务表。开发用 PostgreSQL 17 镜像按 digest 固定，包含 pgvector 与 pg_trgm。数据位于 Docker 命名卷 `law_postgres-data`。

连接参数：主机 `127.0.0.1`，端口 `55432`，数据库 `law_dev`，用户 `law_admin`，schema `law`。密码在仓库根目录 `.env.local` 中，权限为 0600，已加入 `.gitignore`；本机 psql 可用时也可使用同目录 `.pgpass.local`。不要提交这两个文件。

## 启动与连接

以下命令在仓库根目录运行。已有本地配置可直接启动；新环境先复制 `.env.example` 为 `.env.local` 并设置随机密码。

```sh
docker compose --env-file .env.local up -d --wait
docker exec -it law-postgres-dev psql -X -U law_admin -d law_dev
```

应用查询使用 `law.users` 等完整表名，或为应用连接配置 `search_path=law,public`。容器内不发布给公网，宿主机仅绑定回环地址。当前为本地开发管理员；部署后端时请使用独立迁移账号与受限运行账号，授权示例见 `backend/docs/runtime-role.sql`。

## 首次初始化

当前实例已经执行成功，无需再次执行。仅用于新数据库，整个 DDL 在一个事务内执行；已有同名表会失败并回滚，禁止把此文件当作增量升级脚本。

```sh
docker exec -i law-postgres-dev psql -X -U law_admin -d law_dev \
  -v ON_ERROR_STOP=1 < database-schema.sql
```

`vector` 与 `pg_trgm` 扩展位于 `public`，业务表位于 `law`。初始基线向量固定 1536 维；`backend/` 已提供阿里云 Embedding 适配与显式 pgvector/pg_trgm 召回，真实账号仍需配置和联调。全文检索生成列采用 `simple`，不声称已实现中文分词。

## 验证

```sh
docker exec -i law-postgres-dev psql -X -U law_admin -d law_dev \
  -v ON_ERROR_STOP=1 < database/verify-schema.sql
```

验证使用合成数据并回滚事务，覆盖正常案件与助手附件写入、跨案件关联、错误文件/分块归属、可空案件范围、他人附件、幂等键、角色必填项、组织所有者转让与审计只追加。测试过程中可能推进 identity 序列，但不会留下业务行。

复合外键保证案件归属一致；触发器补足可空复合外键的 NULL 比较、助手附件上传人和组织 owner 的有效性。会话/文件/消息的归属字段不可原地更改；材料迁移应复制记录。用户/组织动态访问授权仍须由应用层检查，不能只凭数据库中 ID 存在就授权。

## 停止

```sh
docker compose --env-file .env.local stop
```

停止容器保留数据卷；重新启动沿用原数据库，修改环境文件不会自动修改现有数据库密码。

## 后端增量迁移

`backend/` 使用 Alembic 管理基线后的增量。已有本地数据库先在 `backend/` 运行 `uv run python -m scripts.adopt_database`，该命令对比完整结构清单，仅校验一致时标记 `0001`；再运行 `uv run alembic upgrade head`。已有版本记录时直接升级。新空库直接升级即可，无需手动执行初始 SQL。当前增量保持 27 张业务表，增加队列租约、流式租约、检索索引与版本化提示词。详见 `backend/README.md`。
