"""Document access and per-workspace usage; application tables remain untouched."""

import sqlalchemy as sa
from alembic import op

revision = "20261001_workspaces"
down_revision = "20260930_pipeline"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "workspaces",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        schema="ingestion",
    )
    op.create_table(
        "workspace_memberships",
        sa.Column("user_id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), nullable=False),
        schema="ingestion",
    )
    op.create_index(
        "ix_ingestion_workspace_memberships_workspace_id",
        "workspace_memberships",
        ["workspace_id"],
        schema="ingestion",
    )
    op.create_table(
        "document_access",
        sa.Column("document_id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("shared_regulatory", sa.Boolean(), nullable=False),
        schema="ingestion",
    )
    op.create_index(
        "ix_ingestion_document_access_workspace_id",
        "document_access",
        ["workspace_id"],
        schema="ingestion",
    )
    op.create_table(
        "workspace_usage",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("uploads", sa.Integer(), nullable=False),
        sa.Column("bytes", sa.Integer(), nullable=False),
        sa.Column("ocr_pages", sa.Integer(), nullable=False),
        schema="ingestion",
    )
    bind = op.get_bind()
    op.create_table(
        "record_access",
        sa.Column("kind", sa.String(), primary_key=True),
        sa.Column("record_id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), nullable=False),
        schema="ingestion",
    )
    op.create_index(
        "ix_ingestion_record_access_workspace_id",
        "record_access",
        ["workspace_id"],
        schema="ingestion",
    )
    if sa.inspect(bind).has_table("users", schema="public"):
        bind.execute(
            sa.text(
                "INSERT INTO ingestion.workspaces (id,name) SELECT 'user:' || id, 'Private workspace' FROM public.users ON CONFLICT DO NOTHING"
            )
        )
        bind.execute(
            sa.text(
                "INSERT INTO ingestion.workspace_memberships (user_id,workspace_id) SELECT id, 'user:' || id FROM public.users ON CONFLICT DO NOTHING"
            )
        )
    if sa.inspect(bind).has_table("documents", schema="public"):
        bind.execute(
            sa.text(
                "INSERT INTO ingestion.document_access (document_id,workspace_id,shared_regulatory) SELECT id, COALESCE('user:' || uploaded_by_id, 'quarantine:unowned'), false FROM public.documents ON CONFLICT DO NOTHING"
            )
        )
    # Known user ownership is authoritative; organisation labels are not.
    for table, column, kind in [
        ("audit_logs", "user_id", "audit"),
        ("workflow_tasks", "created_by_id", "task"),
    ]:
        if sa.inspect(bind).has_table(table, schema="public"):
            bind.execute(
                sa.text(
                    f"INSERT INTO ingestion.record_access (kind,record_id,workspace_id) "
                    f"SELECT '{kind}', t.id, m.workspace_id FROM public.{table} t "
                    f"JOIN ingestion.workspace_memberships m ON m.user_id=t.{column} ON CONFLICT DO NOTHING"
                )
            )
    if sa.inspect(bind).has_table("agent_runs", schema="public") and sa.inspect(bind).has_table(
        "conversations", schema="public"
    ):
        bind.execute(
            sa.text(
                "INSERT INTO ingestion.record_access (kind,record_id,workspace_id) SELECT 'run', r.id, m.workspace_id "
                "FROM public.agent_runs r JOIN public.conversations c ON c.id=r.conversation_id "
                "JOIN ingestion.workspace_memberships m ON m.user_id=c.user_id ON CONFLICT DO NOTHING"
            )
        )
    if sa.inspect(bind).has_table("alerts", schema="public"):
        bind.execute(
            sa.text(
                "INSERT INTO ingestion.record_access (kind,record_id,workspace_id) SELECT 'alert', a.id, d.workspace_id "
                "FROM public.alerts a JOIN ingestion.document_access d ON d.document_id = a.related_document_ids->>0 "
                "WHERE a.alert_type='regulatory_document' AND CASE WHEN json_typeof(a.related_document_ids)='array' "
                "THEN json_array_length(a.related_document_ids) ELSE 0 END=1 ON CONFLICT DO NOTHING"
            )
        )
    if sa.inspect(bind).has_table("audit_logs", schema="public"):
        bind.execute(
            sa.text(
                "INSERT INTO ingestion.record_access (kind,record_id,workspace_id) SELECT 'audit', a.id, d.workspace_id "
                "FROM public.audit_logs a JOIN ingestion.document_access d ON a.resource='documents/' || d.document_id "
                "WHERE a.user_id IS NULL ON CONFLICT DO NOTHING"
            )
        )


def downgrade():
    raise RuntimeError("Workspace access history must not be dropped automatically")
