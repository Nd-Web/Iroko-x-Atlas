"""Pipeline-owned tables; no migration owns the application's existing tables."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase


def uid():
    return str(uuid4())


class PipelineBase(DeclarativeBase):
    metadata = MetaData(schema="ingestion")


class Workspace(PipelineBase):
    __tablename__ = "workspaces"
    id = Column(String, primary_key=True, default=uid)
    name = Column(String, nullable=False)


class Membership(PipelineBase):
    __tablename__ = "workspace_memberships"
    user_id = Column(String, primary_key=True)
    workspace_id = Column(String, nullable=False, index=True)


class DocumentAccess(PipelineBase):
    __tablename__ = "document_access"
    document_id = Column(String, primary_key=True)
    workspace_id = Column(String, nullable=False, index=True)
    shared_regulatory = Column(Boolean, nullable=False, default=False)


class WorkspaceUsage(PipelineBase):
    __tablename__ = "workspace_usage"
    key = Column(String, primary_key=True)
    uploads = Column(Integer, nullable=False, default=0)
    bytes = Column(Integer, nullable=False, default=0)
    ocr_pages = Column(Integer, nullable=False, default=0)


class RecordAccess(PipelineBase):
    """Ownership of private document-derived alerts, traces, audits and tasks."""

    __tablename__ = "record_access"
    kind = Column(String, primary_key=True)
    record_id = Column(String, primary_key=True)
    workspace_id = Column(String, nullable=False, index=True)


class Revision(PipelineBase):
    __tablename__ = "regulatory_documents"
    __table_args__ = (UniqueConstraint("source_key", "sha256"),)
    id = Column(String, primary_key=True)  # application Document.id
    source_key = Column(String, nullable=False, index=True)
    sha256 = Column(String(64), nullable=False)
    previous_id = Column(String)
    is_current = Column(Boolean, default=False, nullable=False)
    provenance = Column(JSON, default=dict, nullable=False)
    extraction = Column(JSON, default=dict, nullable=False)
    issues = Column(JSON, default=list, nullable=False)
    review_status = Column(String, default="pending", nullable=False)
    reviewed_by = Column(String)
    reviewed_at = Column(DateTime)
    review_note = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Page(PipelineBase):
    __tablename__ = "regulatory_document_pages"
    __table_args__ = (UniqueConstraint("document_id", "position"),)
    id = Column(String, primary_key=True, default=uid)
    document_id = Column(String, nullable=False, index=True)
    position = Column(Integer, nullable=False)
    page_number = Column(Integer)  # null for formats without physical pagination
    locator = Column(String)
    method = Column(String, nullable=False)
    raw_text = Column(Text, nullable=False)
    text = Column(Text, nullable=False)
    quality = Column(JSON, default=dict, nullable=False)


class Chunk(PipelineBase):
    __tablename__ = "regulatory_chunks"
    id = Column(String, primary_key=True)
    document_id = Column(String, nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    provenance = Column(JSON, default=dict, nullable=False)


class Job(PipelineBase):
    __tablename__ = "ingestion_jobs"
    id = Column(String, primary_key=True)  # document:<id> or source:<id>
    kind = Column(String, nullable=False)
    target_id = Column(String, nullable=False, index=True)
    state = Column(String, default="queued", nullable=False, index=True)
    attempts = Column(Integer, default=0, nullable=False)
    available_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    lease_until = Column(DateTime)
    lease_token = Column(String)
    error = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Source(PipelineBase):
    __tablename__ = "ingestion_sources"
    id = Column(String, primary_key=True, default=uid)
    regulator = Column(String, nullable=False)
    url = Column(String, nullable=False, unique=True)
    parser = Column(String, nullable=False)  # cbn_json | html_links
    enabled = Column(Boolean, default=False, nullable=False)
    interval_hours = Column(Integer, default=0, nullable=False)  # 0: manual collection only
    max_documents = Column(Integer, default=20, nullable=False)
    owner_id = Column(String, nullable=False)
    last_run = Column(DateTime)
    result = Column(JSON, default=dict, nullable=False)


class OcrBudget(PipelineBase):
    __tablename__ = "ingestion_ocr_budget"
    day = Column(String, primary_key=True)
    pages = Column(Integer, default=0, nullable=False)


class CrawlRun(PipelineBase):
    __tablename__ = "ingestion_crawl_runs"
    id = Column(String, primary_key=True, default=uid)
    source_id = Column(String, nullable=False, index=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at = Column(DateTime)
    result = Column(JSON, default=dict, nullable=False)
