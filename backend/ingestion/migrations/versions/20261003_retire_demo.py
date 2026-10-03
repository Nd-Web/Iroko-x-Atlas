"""Recoverably archive only the eight legacy seed document identities.

No extracted revision, upload Blob or source connector is modified. Existing
user/customer and real regulator records remain untouched. Original records are
retained for operator-reviewed recovery; this does not drop historical evidence.
"""

import sqlalchemy as sa
from alembic import op

from ingestion.retired_demo import RETIRED_DOCUMENT_IDS

revision = "20261003_retire_demo"
down_revision = "20261001_workspaces"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "retired_demo_documents",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("original_record", sa.JSON(), nullable=False),
        sa.Column("retired_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        schema="ingestion",
    )
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("documents", schema="public"):
        return
    statement = sa.text(
        "SELECT d.* FROM public.documents d WHERE d.id IN :ids "
        "AND d.blob_url IS NULL AND d.source_connector_id IS NULL "
        "AND NOT EXISTS (SELECT 1 FROM ingestion.regulatory_documents r WHERE r.id=d.id)"
    ).bindparams(sa.bindparam("ids", expanding=True))
    for row in bind.execute(statement, {"ids": RETIRED_DOCUMENT_IDS}).mappings():
        original = {
            key: value.isoformat() if hasattr(value, "isoformat") else value
            for key, value in row.items()
        }
        archive = sa.table(
            "retired_demo_documents",
            sa.column("id"),
            sa.column("original_record", sa.JSON()),
            schema="ingestion",
        )
        bind.execute(archive.insert().values(id=row["id"], original_record=original))
        bind.execute(
            sa.text("UPDATE public.documents SET status='archived' WHERE id=:id"), {"id": row["id"]}
        )
        # Remove access to seed-derived records; retain their rows for recovery/audit.
        bind.execute(
            sa.text("DELETE FROM ingestion.document_access WHERE document_id=:id"),
            {"id": row["id"]},
        )


def downgrade():
    raise RuntimeError(
        "Retired demo records must not be restored to evidence automatically. Recover explicitly from the archive if needed."
    )
