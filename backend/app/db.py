from types import SimpleNamespace

from pgvector.sqlalchemy import Vector  # noqa: F401 - registers reflected PostgreSQL vector type
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import Settings


class Database:
  def __init__(self, settings: Settings):
    self.engine = create_async_engine(
      settings.database_url.get_secret_value(), pool_pre_ping=True,
      pool_size=10, max_overflow=10,
      connect_args={"server_settings": {"search_path": "law,public", "statement_timeout": "15000"}},
    )
    self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
    self.metadata = MetaData(schema="law")
    self.t = SimpleNamespace()

  async def connect(self):
    async with self.engine.connect() as conn:
      await conn.run_sync(self.metadata.reflect, schema="law")
    required = {"users", "cases", "files", "doc_chunks", "ai_messages", "async_jobs"}
    names = {table.name for table in self.metadata.tables.values()}
    if not required <= names:
      raise RuntimeError("数据库未初始化，请先执行 Alembic 迁移")
    self.t = SimpleNamespace(**{table.name: table for table in self.metadata.tables.values()})

  async def close(self):
    await self.engine.dispose()
