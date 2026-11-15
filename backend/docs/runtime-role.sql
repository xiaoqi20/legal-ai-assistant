-- 由迁移/管理员执行。角色密码通过独立密钥管理设置，不写入本文件。
-- 应用账号只访问 law schema；迁移必须使用独立具备 DDL 权限的账号。
CREATE ROLE law_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
GRANT USAGE ON SCHEMA law, public TO law_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA law TO law_app;
REVOKE UPDATE, DELETE ON law.audit_logs FROM law_app;
REVOKE UPDATE, DELETE ON law.material_events, law.document_draft_revisions FROM law_app;
-- 研判检查点与步骤仅由应用层经过权限和租约校验后访问，不向客户端开放原始表。
-- 0009 迁移会为已有 law_app 补齐研判表和序列授权。
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA law TO law_app;
GRANT SELECT ON public.alembic_version TO law_app;
-- 后续迁移新建对象后，需要同一迁移所有者补齐相应授权。
