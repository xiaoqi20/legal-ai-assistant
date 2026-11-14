"""Persist user-provided case intake details and party sides."""
from alembic import op

revision = "0006"
down_revision = "0005"


def upgrade():
  op.execute("""
    ALTER TABLE law.cases
      ADD COLUMN summary text,
      ADD COLUMN claim text,
      ADD COLUMN handling_identity varchar(12),
      ADD COLUMN party_role_label varchar(80),
      ADD CONSTRAINT cases_handling_identity_check
        CHECK (handling_identity IS NULL OR handling_identity IN ('self', 'agent'))
  """)
  op.execute("""
    ALTER TABLE law.case_parties
      ADD COLUMN side varchar(12),
      ADD CONSTRAINT case_parties_side_check
        CHECK (side IS NULL OR side IN ('our', 'opponent'))
  """)
  op.execute("CREATE INDEX case_parties_intake_side_idx ON law.case_parties(case_id, side, sort_order) WHERE side IS NOT NULL")


def downgrade():
  op.execute("DROP INDEX law.case_parties_intake_side_idx")
  op.execute("ALTER TABLE law.case_parties DROP CONSTRAINT case_parties_side_check, DROP COLUMN side")
  op.execute("ALTER TABLE law.cases DROP CONSTRAINT cases_handling_identity_check, DROP COLUMN party_role_label, DROP COLUMN handling_identity, DROP COLUMN claim, DROP COLUMN summary")
