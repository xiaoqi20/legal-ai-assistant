"""Durable job leases and distributed streaming admission."""
from alembic import op

revision = "0002"
down_revision = "0001"


def upgrade():
  op.execute("ALTER TABLE law.async_jobs ADD COLUMN lease_token uuid, ADD COLUMN lease_expires_at timestamptz")
  op.execute("ALTER TABLE law.ai_messages ADD COLUMN lease_expires_at timestamptz")
  op.execute("CREATE UNIQUE INDEX ai_messages_one_stream_per_conversation ON law.ai_messages(conversation_id) WHERE status = 'streaming'")
  op.execute("CREATE INDEX doc_chunks_content_trgm_idx ON law.doc_chunks USING gin(content public.gin_trgm_ops)")
  op.execute("CREATE INDEX async_jobs_running_lease_idx ON law.async_jobs(lease_expires_at) WHERE status = 'running'")


def downgrade():
  op.execute("DROP INDEX law.async_jobs_running_lease_idx")
  op.execute("DROP INDEX law.doc_chunks_content_trgm_idx")
  op.execute("DROP INDEX law.ai_messages_one_stream_per_conversation")
  op.execute("ALTER TABLE law.ai_messages DROP COLUMN lease_expires_at")
  op.execute("ALTER TABLE law.async_jobs DROP COLUMN lease_token, DROP COLUMN lease_expires_at")
