"""Verify the exact DDL baseline before adopting an existing database into Alembic."""
import json
from pathlib import Path

import psycopg
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url

from app.config import get_settings

MANIFEST = Path(__file__).parents[1] / "migrations" / "baseline-manifest.json"


def signature(conn):
  # Only baseline structure; exclude known additions from runtime migrations.
  runtime_indexes = {"ai_messages_one_stream_per_conversation", "doc_chunks_content_trgm_idx",
                     "async_jobs_running_lease_idx", "case_analyses_one_active_type"}
  result = {}
  result["columns"] = conn.execute("""SELECT c.relname, a.attname, format_type(a.atttypid,a.atttypmod),
    a.attnotnull, a.attidentity, a.attgenerated, pg_get_expr(d.adbin,d.adrelid)
    FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
    JOIN pg_attribute a ON a.attrelid=c.oid
    LEFT JOIN pg_attrdef d ON d.adrelid=c.oid AND d.adnum=a.attnum
    WHERE n.nspname='law' AND c.relkind='r' AND a.attnum>0 AND NOT a.attisdropped
    AND NOT (c.relname IN ('ai_messages','async_jobs') AND a.attname IN ('lease_token','lease_expires_at'))
    ORDER BY c.relname,a.attnum""").fetchall()
  result["constraints"] = conn.execute("""SELECT c.relname,k.conname,pg_get_constraintdef(k.oid)
    FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid
    JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='law'
    ORDER BY c.relname,k.conname""").fetchall()
  result["indexes"] = [row for row in conn.execute("""SELECT tablename,indexname,indexdef
    FROM pg_indexes WHERE schemaname='law' ORDER BY tablename,indexname""").fetchall()
    if row[1] not in runtime_indexes]
  result["triggers"] = conn.execute("""SELECT c.relname,t.tgname,pg_get_triggerdef(t.oid)
    FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='law' AND NOT t.tgisinternal ORDER BY c.relname,t.tgname""").fetchall()
  result["functions"] = conn.execute("""SELECT p.proname,pg_get_functiondef(p.oid)
    FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='law'
    ORDER BY p.proname""").fetchall()
  return json.loads(json.dumps(result))


def main():
  url = make_url(get_settings().database_url.get_secret_value()).set(drivername="postgresql")
  with psycopg.connect(url.render_as_string(hide_password=False)) as conn:
    actual = signature(conn)
    expected = json.loads(MANIFEST.read_text())
    if actual != expected:
      mismatch = [key for key in expected if expected[key] != actual[key]]
      raise RuntimeError("数据库与已验证基线不一致，停止自动接管：" + ", ".join(mismatch))
    if conn.execute("SELECT to_regclass('public.alembic_version')").fetchone()[0]:
      raise RuntimeError("数据库已由 Alembic 管理，请直接运行 alembic upgrade head")
  command.stamp(Config(str(Path(__file__).parents[1] / "alembic.ini")), "0001")
  print("现有数据库结构与基线一致；已标记 0001，业务数据保持原样。请继续 alembic upgrade head。")


if __name__ == "__main__":
  main()
