"""Existing 27-table law schema, preserved as a transactional migration snapshot."""
from pathlib import Path

from alembic import op

revision = "0001"
down_revision = None


def upgrade():
  sql = (Path(__file__).parents[1] / "sql" / "0001_initial.sql").read_text()
  # Alembic owns transaction boundaries. psycopg sends the whole DDL without parameters.
  lines = [line for line in sql.splitlines() if line.strip() not in {"BEGIN;", "COMMIT;"}]
  op.get_bind().exec_driver_sql("\n".join(lines), execution_options={"no_parameters": True})


def downgrade():
  raise RuntimeError("基线不可自动删除；请使用备份恢复，禁止意外清空案件与审计数据")
