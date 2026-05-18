from sqlalchemy import (
    create_engine, Column, String, Integer, Float,
    Boolean, DateTime, Text, JSON, ForeignKey, Enum
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker, relationship
from sqlalchemy.sql import func
from datetime import datetime
import uuid
import os
import enum
from sqlalchemy import text

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./atlas.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def generate_id():
    return str(uuid.uuid4())


# ─── Enums ────────────────────────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    superadmin = "superadmin"
    admin = "admin"
    analyst = "analyst"
    viewer = "viewer"


class DocumentStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    indexed = "indexed"
    failed = "failed"


class AlertSeverity(str, enum.Enum):
    critical = "critical"
    warning = "warning"
    info = "info"


class AlertStatus(str, enum.Enum):
    new = "new"
    acknowledged = "acknowledged"
    resolved = "resolved"
    dismissed = "dismissed"


class AgentType(str, enum.Enum):
    researcher = "researcher"
    analyst = "analyst"
    watchdog = "watchdog"
    scribe = "scribe"
    strategist = "strategist"


class ConnectorType(str, enum.Enum):
    sharepoint = "sharepoint"
    onedrive = "onedrive"
    microsoft_teams = "microsoft_teams"
    slack = "slack"
    servicenow = "servicenow"


class ConnectorStatus(str, enum.Enum):
    active = "active"
    expired = "expired"
    revoked = "revoked"


# ─── Models ───────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_id)
    email = Column(String, unique=True, nullable=False, index=True)
    full_name = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    organisation = Column(String, nullable=True)
    department = Column(String, nullable=True)
    role = Column(String, default=UserRole.viewer)
    is_active = Column(Boolean, default=True)
    api_key = Column(String, nullable=True, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    conversations = relationship("Conversation", back_populates="user")
    documents = relationship("Document", back_populates="uploaded_by")


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=generate_id)
    title = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    file_type = Column(String, nullable=False)  # pdf, docx, xlsx, txt
    file_size = Column(Integer, nullable=True)
    department = Column(String, nullable=True)
    tags = Column(JSON, default=list)
    status = Column(String, default=DocumentStatus.pending)
    blob_url = Column(String, nullable=True)
    chunk_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    extra_metadata = Column(JSON, default=dict)
    uploaded_by_id = Column(String, ForeignKey("users.id"), nullable=True)
    source_connector_id = Column(String, ForeignKey("connectors.id"), nullable=True)
    source_item_id = Column(String, nullable=True)  # Microsoft Graph drive item ID
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    uploaded_by = relationship("User", back_populates="documents")
    source_connector = relationship("Connector", back_populates="documents")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=generate_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", order_by="Message.created_at")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=generate_id)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    role = Column(String, nullable=False)  # user | assistant
    content = Column(Text, nullable=False)
    agent_trace = Column(JSON, default=list)  # list of agent actions for this message
    citations = Column(JSON, default=list)    # documents referenced
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(String, primary_key=True, default=generate_id)
    title = Column(String, nullable=False)
    summary = Column(Text, nullable=False)
    severity = Column(String, default=AlertSeverity.info)
    status = Column(String, default=AlertStatus.new)
    alert_type = Column(String, nullable=False)  # contract_expiry | complaint_spike | policy_conflict | etc
    extra_metadata = Column(JSON, default=dict)         # extra data specific to alert type
    suggested_actions = Column(JSON, default=list)
    draft_content = Column(Text, nullable=True)   # pre-drafted email/report by Scribe
    related_document_ids = Column(JSON, default=list)
    organisation = Column(String, nullable=True)
    acknowledged_by = Column(String, ForeignKey("users.id"), nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = Column(String, primary_key=True, default=generate_id)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=True)
    agent_type = Column(String, nullable=False)
    input_query = Column(Text, nullable=False)
    output = Column(Text, nullable=True)
    steps = Column(JSON, default=list)           # full trace of every tool call
    duration_ms = Column(Integer, nullable=True)
    token_count = Column(Integer, nullable=True)
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=generate_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    action = Column(String, nullable=False)
    resource = Column(String, nullable=False)
    details = Column(JSON, default=dict)
    ip_address = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class OrgMemory(Base):
    __tablename__ = "org_memory"

    id = Column(String, primary_key=True, default=generate_id)
    organisation = Column(String, nullable=False, index=True)
    memory_type = Column(String, nullable=False)  # fact | preference | pattern
    key = Column(String, nullable=False)
    value = Column(Text, nullable=False)
    confidence = Column(Float, default=1.0)
    source_document_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class KnowledgeGap(Base):
    """
    Records queries that Atlas could not answer due to insufficient documents.
    Surfaced on the admin dashboard so document owners know what to upload.
    """
    __tablename__ = "knowledge_gaps"

    id = Column(String, primary_key=True, default=generate_id)
    query = Column(Text, nullable=False)
    department_filter = Column(String, nullable=True)
    confidence_score = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class UserInvitation(Base):
    __tablename__ = "user_invitations"

    id = Column(String, primary_key=True, default=generate_id)
    email = Column(String, nullable=False, index=True)
    token = Column(String, nullable=False, unique=True, index=True)
    invited_by_id = Column(String, ForeignKey("users.id"), nullable=False)
    role = Column(String, default=UserRole.viewer)
    department = Column(String, nullable=True)
    personal_message = Column(Text, nullable=True)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    invited_by = relationship("User", foreign_keys=[invited_by_id])


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(String, primary_key=True, default=generate_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    token = Column(String, nullable=False, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", foreign_keys=[user_id])


class Connector(Base):
    """Tracks a user's connected external data source."""
    __tablename__ = "connectors"

    id = Column(String, primary_key=True, default=generate_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    connector_type = Column(String, nullable=False)   # sharepoint|onedrive|microsoft_teams|slack|servicenow
    display_name = Column(String, nullable=False)      # e.g. "My OneDrive", "#general"
    site_id = Column(String, nullable=True)            # SharePoint site ID (null for OneDrive)
    drive_id = Column(String, nullable=True)           # Graph drive ID
    root_folder = Column(String, default="/")          # Sync root path
    extra_config = Column(JSON, default=dict)          # Connector-specific settings
    encrypted_refresh_token = Column(Text, nullable=False)
    status = Column(String, default=ConnectorStatus.active)
    auto_sync = Column(Boolean, default=True)
    sync_interval_minutes = Column(Integer, default=30)
    last_synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User")
    documents = relationship("Document", back_populates="source_connector")


# ─── Init ─────────────────────────────────────────────────────────────────────

def _add_column_if_missing(conn, table: str, column: str, col_def: str):
    """Add a column only if it doesn't already exist. Works with both SQLite and PostgreSQL."""
    from sqlalchemy import text, inspect
    try:
        inspector = inspect(conn)
        existing = [c["name"] for c in inspector.get_columns(table)]
        if column not in existing:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}"))
            print(f"  migrated: {table}.{column} added")
    except Exception:
        # Table may not exist yet — create_all will handle it
        pass


def init_db():
    # Import network models so their tables are registered with Base.metadata
    import models.network_models  # noqa: F401
    Base.metadata.create_all(bind=engine)

    # ── Column-level migrations (add new columns to existing tables) ─────────
    with engine.begin() as conn:
        _add_column_if_missing(conn, "documents", "source_connector_id", "VARCHAR REFERENCES connectors(id)")
        _add_column_if_missing(conn, "documents", "source_item_id", "VARCHAR")
        _add_column_if_missing(conn, "connectors", "last_sync_at", "TIMESTAMP")

    print("Atlas DB initialised — all tables created.")
