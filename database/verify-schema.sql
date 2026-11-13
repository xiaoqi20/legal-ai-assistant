-- 合成数据回归；整个事务回滚，不保留测试业务数据。
\set ON_ERROR_STOP on
BEGIN;
SET LOCAL search_path = law, public;

CREATE FUNCTION pg_temp.expect_error(statement text, expected_state text)
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
  BEGIN
    EXECUTE statement;
  EXCEPTION WHEN OTHERS THEN
    IF SQLSTATE = expected_state THEN RETURN; END IF;
    RAISE EXCEPTION '期望 SQLSTATE %，实际 %：%', expected_state, SQLSTATE, SQLERRM;
  END;
  RAISE EXCEPTION '预期拒绝但实际成功：%', statement;
END;
$$;

INSERT INTO users (id, display_name) VALUES (-1, '测试用户甲'), (-2, '测试用户乙');
INSERT INTO user_profiles (user_id, role_type, real_name) VALUES (-1, 'individual', '测试用户甲');
SELECT pg_temp.expect_error($q$INSERT INTO user_profiles (user_id, role_type, real_name, company_name) VALUES (-2, 'enterprise', '测试用户乙', '测试企业')$q$, '23514');
SELECT pg_temp.expect_error($q$UPDATE user_profiles SET real_name = ' ' WHERE user_id = -1$q$, '23514');
SELECT pg_temp.expect_error($q$UPDATE users SET status = 'unknown' WHERE id = -1$q$, '23514');

INSERT INTO cases (id, owner_user_id, title) VALUES (-1, -1, '合成案件甲'), (-2, -2, '合成案件乙');
INSERT INTO evidence_requirements (id, case_id, title, category, source)
VALUES (-1, -1, '合同', 'written', 'manual'), (-2, -2, '合同', 'written', 'manual');
INSERT INTO evidence_items (id, case_id, requirement_id, category, title) VALUES (-1, -1, -1, 'written', '材料甲');
SELECT pg_temp.expect_error($q$INSERT INTO evidence_items (case_id, requirement_id, category, title) VALUES (-1, -2, 'written', '串案材料')$q$, '23503');

INSERT INTO files (id, case_id, uploaded_by, bucket, object_key, original_name, mime_type, size_bytes)
VALUES (-1, -1, -1, 'test', 'case-a.pdf', '合成甲.pdf', 'application/pdf', 100),
       (-2, -2, -2, 'test', 'case-b.pdf', '合成乙.pdf', 'application/pdf', 100),
       (-3, NULL, -1, 'test', 'assistant-a.pdf', '助手甲.pdf', 'application/pdf', 100),
       (-4, NULL, -2, 'test', 'assistant-b.pdf', '助手乙.pdf', 'application/pdf', 100),
       (-5, -1, -1, 'test', 'case-a2.pdf', '合成甲2.pdf', 'application/pdf', 100);
INSERT INTO evidence_item_files (evidence_item_id, file_id, case_id) VALUES (-1, -1, -1);
SELECT pg_temp.expect_error($q$INSERT INTO evidence_item_files (evidence_item_id, file_id, case_id) VALUES (-1, -2, -1)$q$, '23503');
SELECT pg_temp.expect_error($q$INSERT INTO files (bucket, object_key, original_name, mime_type, size_bytes) VALUES ('test', 'unowned', '无归属.pdf', 'application/pdf', 100)$q$, '23514');
SELECT pg_temp.expect_error($q$INSERT INTO case_documents (case_id, title) VALUES (-1, '缺失文件')$q$, '23502');
SELECT pg_temp.expect_error($q$INSERT INTO doc_chunks (file_id, case_id, chunk_index, content) VALUES (-1, NULL, 0, '漏填案件')$q$, '23502');
INSERT INTO doc_chunks (id, file_id, case_id, chunk_index, content) VALUES (-1, -1, -1, 0, 'Synthetic contract clause');
SELECT pg_temp.expect_error($q$INSERT INTO doc_chunks (file_id, case_id, chunk_index, content) VALUES (-2, -1, 0, '串案分块')$q$, '23503');

INSERT INTO case_analyses (id, case_id, analysis_type) VALUES (-1, -1, 'case_summary');
INSERT INTO analysis_sources (analysis_id, case_id, file_id, chunk_id) VALUES (-1, -1, -1, -1);
SELECT pg_temp.expect_error($q$INSERT INTO analysis_sources (analysis_id, case_id, file_id) VALUES (-1, -1, -2)$q$, '23503');
SELECT pg_temp.expect_error($q$UPDATE analysis_sources SET file_id = -5 WHERE analysis_id = -1 AND chunk_id = -1$q$, '23503');

INSERT INTO ai_conversations (id, user_id, case_id, mode)
VALUES (-1, -1, -1, 'case_qa'), (-2, -1, NULL, 'assistant'), (-3, -2, NULL, 'assistant');
INSERT INTO ai_messages (id, conversation_id, case_id, seq, role, client_message_id)
VALUES (-1, -1, -1, 1, 'user', 'test-client-key'), (-2, -1, -1, 2, 'assistant', NULL),
       (-3, -2, NULL, 1, 'user', NULL), (-4, -3, NULL, 1, 'user', NULL);
SELECT pg_temp.expect_error($q$INSERT INTO ai_messages (conversation_id, case_id, seq, role) VALUES (-1, NULL, 3, 'user')$q$, '23514');
SELECT pg_temp.expect_error($q$INSERT INTO ai_messages (conversation_id, case_id, seq, role) VALUES (-2, -1, 2, 'user')$q$, '23514');
SELECT pg_temp.expect_error($q$INSERT INTO ai_messages (conversation_id, case_id, seq, role, client_message_id) VALUES (-1, -1, 3, 'user', 'test-client-key')$q$, '23505');
INSERT INTO ai_message_files (message_id, file_id, case_id) VALUES (-1, -1, -1), (-3, -3, NULL);
SELECT pg_temp.expect_error($q$INSERT INTO ai_message_files (message_id, file_id) VALUES (-3, -4)$q$, '23514');
SELECT pg_temp.expect_error($q$INSERT INTO ai_message_files (message_id, file_id) VALUES (-3, -1)$q$, '23514');
SELECT pg_temp.expect_error($q$INSERT INTO ai_message_files (message_id, file_id, case_id) VALUES (-2, -1, -1)$q$, '23514');
SELECT pg_temp.expect_error($q$UPDATE files SET uploaded_by = -2 WHERE id = -3$q$, '23514');
SELECT pg_temp.expect_error($q$UPDATE ai_conversations SET user_id = -2 WHERE id = -2$q$, '23514');
INSERT INTO ai_citations (message_id, case_id, file_id, chunk_id, document_title, quote, rank)
VALUES (-2, -1, -1, -1, '合成甲', 'Synthetic contract clause', 1);
SELECT pg_temp.expect_error($q$INSERT INTO ai_citations (message_id, case_id, file_id, document_title, quote, rank) VALUES (-2, -2, -2, '串案', '错误', 2)$q$, '23503');
SELECT pg_temp.expect_error($q$INSERT INTO ai_citations (message_id, case_id, file_id, chunk_id, document_title, quote, rank) VALUES (-2, -1, -5, -1, '错误文件', '错误', 2)$q$, '23503');

INSERT INTO prompt_versions (id, prompt_key, version, content, status) VALUES (-1, 'test', 1, '合成提示词', 'active');
SELECT pg_temp.expect_error($q$INSERT INTO prompt_versions (prompt_key, version, content, status) VALUES ('test', 2, '合成提示词2', 'active')$q$, '23505');

INSERT INTO organizations (id, name, owner_user_id) VALUES (-1, '合成组织', -1);
INSERT INTO organization_members (org_id, user_id, role, status) VALUES (-1, -1, 'owner', 'active');
SET CONSTRAINTS ALL IMMEDIATE;
SELECT pg_temp.expect_error($q$INSERT INTO organization_members (org_id, user_id, role, status) VALUES (-1, -2, 'owner', 'active')$q$, '23505');
SELECT pg_temp.expect_error($q$UPDATE organization_members SET status = 'removed' WHERE org_id = -1 AND user_id = -1$q$, '23514');
SET CONSTRAINTS ALL DEFERRED;
UPDATE organization_members SET role = 'admin' WHERE org_id = -1 AND user_id = -1;
INSERT INTO organization_members (org_id, user_id, role, status) VALUES (-1, -2, 'owner', 'active');
UPDATE organizations SET owner_user_id = -2 WHERE id = -1;
SET CONSTRAINTS ALL IMMEDIATE;

INSERT INTO audit_logs (id, user_id, action, resource_type) VALUES (-1, -1, 'test', 'synthetic');
SELECT pg_temp.expect_error($q$UPDATE audit_logs SET action = 'changed' WHERE id = -1$q$, '23514');
SELECT pg_temp.expect_error($q$DELETE FROM audit_logs WHERE id = -1$q$, '23514');
SELECT pg_temp.expect_error($q$TRUNCATE audit_logs$q$, '23514');

DO $$
BEGIN
  IF (SELECT count(*) FROM information_schema.tables WHERE table_schema = 'law' AND table_type = 'BASE TABLE') <> 27 THEN
    RAISE EXCEPTION '业务表数量不匹配';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM law.doc_chunks WHERE id = -1 AND search_vector @@ to_tsquery('simple', 'contract')) THEN
    RAISE EXCEPTION '全文检索生成列不工作';
  END IF;
END;
$$;
ROLLBACK;
\echo 'PASS: 27 张表、正常写入及约束拒绝测试通过；合成数据已回滚。'
