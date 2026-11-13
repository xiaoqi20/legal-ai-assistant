from alembic import context
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import make_url

from app.config import get_settings

# Dedicated synchronous psycopg connection supports the transactional SQL baseline.
url = make_url(get_settings().database_url.get_secret_value()).set(drivername="postgresql+psycopg")
if context.is_offline_mode():
  raise RuntimeError("本项目迁移包含 SQL 基线，请连接数据库执行迁移")
engine = create_engine(url, poolclass=pool.NullPool)
with engine.connect() as connection:
  context.configure(connection=connection, target_metadata=None, transactional_ddl=True)
  with context.begin_transaction():
    context.run_migrations()
engine.dispose()
