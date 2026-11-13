-- 由迁移/管理员执行。角色密码通过独立密钥管理设置，不写入本文件。
-- 应用账号只访问 law schema；迁移必须使用独立具备 DDL 权限的账号。
CREATE ROLE law_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
GRANT USAGE ON SCHEMA law, public TO law_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA law TO law_app;
REVOKE UPDATE, DELETE ON law.audit_logs FROM law_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA law TO law_app;
GRANT SELECT ON public.alembic_version TO law_app;
-- 后续迁移新建对象后，需要同一迁移所有者补齐相应授权。
