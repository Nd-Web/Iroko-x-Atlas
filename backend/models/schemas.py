from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Any, Dict
from datetime import datetime
from enum import Enum


# ─── Auth ─────────────────────────────────────────────────────────────────────

class UserRole(str, Enum):
    superadmin = "superadmin"
    admin = "admin"
    analyst = "analyst"
    viewer = "viewer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str]
    organisation: Optional[str]
    department: Optional[str]
    role: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime]

    class Config:
        from_attributes = True


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ─── Invite flow ──────────────────────────────────────────────────────────────

class InviteRequest(BaseModel):
    email: EmailStr
    role: UserRole = UserRole.viewer
    department: Optional[str] = None
    personal_message: Optional[str] = None


class AcceptInviteRequest(BaseModel):
    token: str
    full_name: str = Field(min_length=2)
    password: str = Field(min_length=8)


class InviteTokenValidation(BaseModel):
    valid: bool
    email: Optional[str] = None
    role: Optional[str] = None
    department: Optional[str] = None
    invited_by: Optional[str] = None
    expires_at: Optional[datetime] = None


class InvitationResponse(BaseModel):
    id: str
    email: str
    role: str
    department: Optional[str]
    invited_by: Optional[str]
    expires_at: datetime
    used_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class InvitationListResponse(BaseModel):
    invitations: List[InvitationResponse]
    total: int


# ─── Password reset ───────────────────────────────────────────────────────────

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8)


# ─── User management ──────────────────────────────────────────────────────────

class UpdateUserRequest(BaseModel):
    full_name: Optional[str] = None
    department: Optional[str] = None
    role: Optional[UserRole] = None


class UserListResponse(BaseModel):
    users: List[UserResponse]
    total: int


# ─── Documents ────────────────────────────────────────────────────────────────

class DocumentStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    indexed = "indexed"
    failed = "failed"


class DocumentResponse(BaseModel):
    id: str
    title: str
    filename: str
    file_type: str
    file_size: Optional[int]
    department: Optional[str]
    tags: List[str]
    status: str
    blob_url: Optional[str] = None
    chunk_count: int
    error_message: Optional[str] = None
    source_connector_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse]
    total: int


# ─── Document Analytics ───────────────────────────────────────────────────────

class DocumentStatusBreakdown(BaseModel):
    indexed: int
    processing: int
    failed: int
    pending: int


class DocumentAnalyticsResponse(BaseModel):
    total_documents: int
    total_chunks: int
    total_size_bytes: int
    indexed_rate: float
    status_breakdown: DocumentStatusBreakdown
    by_file_type: List[Dict[str, Any]]
    by_department: List[Dict[str, Any]]
    upload_trend: List[Dict[str, Any]]
    failed_documents: List[Dict[str, Any]]


# ─── Document Search ──────────────────────────────────────────────────────────

class DocumentSearchRequest(BaseModel):
    """Body for POST /api/documents/search."""
    query: str = Field(..., min_length=1, max_length=500, description="Full-text / semantic search query")
    top: int = Field(10, ge=1, le=50, description="Number of results to return (max 50)")
    department: Optional[str] = Field(None, description="Filter by department name")
    doc_type: Optional[str] = Field(None, description="Filter by file/document type (pdf, docx, …)")
    language: Optional[str] = Field(None, description="Filter by language code (e.g. 'en')")
    classification: Optional[str] = Field(None, description="Filter by classification (e.g. 'internal', 'confidential')")
    source: Optional[str] = Field(None, description="Filter by source filename (exact match)")
    rerank: bool = Field(True, description="Apply Cohere reranking when available")


class DocumentSearchHit(BaseModel):
    """A single document chunk returned by the search index."""
    chunk_id: str
    doc_id: str
    title: str
    excerpt: str
    source: Optional[str] = None
    blob_url: Optional[str] = None
    department: Optional[str] = None
    doc_type: Optional[str] = None
    language: Optional[str] = None
    classification: Optional[str] = None
    chunk_index: Optional[int] = None
    search_score: Optional[float] = None
    rerank_score: Optional[float] = None
    created_at: Optional[str] = None


class DocumentSearchResponse(BaseModel):
    query: str
    total_hits: int
    results: List[DocumentSearchHit]
    knowledge_gap: bool = False
    confidence: float = 1.0


# ─── Agent Trace ──────────────────────────────────────────────────────────────

class AgentAction(BaseModel):
    agent: str
    tool: str
    args: Dict[str, Any] = {}
    result_preview: Optional[str] = None
    duration_ms: Optional[int] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class Citation(BaseModel):
    document_id: str
    document_title: str
    excerpt: str
    relevance_score: float = 1.0


# ─── Ask / Chat ───────────────────────────────────────────────────────────────

class AskRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    conversation_id: Optional[str] = None
    department_filter: Optional[str] = None
    stream: bool = False


class AskResponse(BaseModel):
    conversation_id: str
    message_id: str
    answer: str
    agent_trace: List[AgentAction] = []
    citations: List[Citation] = []
    suggested_followups: List[str] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ─── Alerts ───────────────────────────────────────────────────────────────────

class AlertSeverity(str, Enum):
    critical = "critical"
    warning = "warning"
    info = "info"


class AlertStatus(str, Enum):
    new = "new"
    acknowledged = "acknowledged"
    resolved = "resolved"
    dismissed = "dismissed"


class AlertResponse(BaseModel):
    id: str
    title: str
    summary: str
    severity: str
    status: str
    alert_type: str
    extra_metadata: Dict[str, Any] = {}
    suggested_actions: List[str]
    draft_content: Optional[str]
    related_document_ids: List[str]
    created_at: datetime

    class Config:
        from_attributes = True


class AlertListResponse(BaseModel):
    alerts: List[AlertResponse]
    total: int
    critical_count: int
    warning_count: int


# ─── Activity Feed ───────────────────────────────────────────────────────────

class ActivityItem(BaseModel):
    id: str
    user_name: str
    user_email: Optional[str] = None
    action: str
    resource: str
    details: Dict[str, Any] = {}
    timestamp: datetime


class ActivityFeedResponse(BaseModel):
    activities: List[ActivityItem]
    total: int


# ─── Analytics ────────────────────────────────────────────────────────────────

class DashboardStats(BaseModel):
    total_documents: int
    documents_indexed: int
    total_queries_today: int
    total_queries_this_week: int
    active_alerts: int
    critical_alerts: int
    avg_query_response_ms: float
    top_departments: List[Dict[str, Any]]
    query_trend: List[Dict[str, Any]]
    most_queried_topics: List[Dict[str, Any]]


class HealthReport(BaseModel):
    overall_status: str
    checks: List[Dict[str, Any]]
    generated_at: datetime


# ─── Connectors ────────────────────────────────────────────────────────────────

class ConnectorType(str, Enum):
    sharepoint = "sharepoint"
    onedrive = "onedrive"
    microsoft_teams = "microsoft_teams"
    slack = "slack"
    servicenow = "servicenow"


class ConnectorCreateRequest(BaseModel):
    """Exchange an OAuth2 authorization code to create a connector."""
    connector_type: ConnectorType
    auth_code: str
    redirect_uri: str
    site_id: Optional[str] = None        # SharePoint site ID
    display_name: Optional[str] = None   # auto-generated if omitted
    extra_config: Dict[str, Any] = {}    # platform-specific settings


class ConnectorUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    site_id: Optional[str] = None
    drive_id: Optional[str] = None
    root_folder: Optional[str] = None
    auto_sync: Optional[bool] = None
    sync_interval_minutes: Optional[int] = None
    extra_config: Optional[Dict[str, Any]] = None


class ConnectorResponse(BaseModel):
    id: str
    connector_type: str
    display_name: str
    site_id: Optional[str]
    drive_id: Optional[str]
    root_folder: str
    extra_config: Dict[str, Any] = {}
    status: str
    auto_sync: bool
    sync_interval_minutes: int
    last_sync_at: Optional[datetime] = None
    last_synced_at: Optional[datetime] = None
    document_count: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ConnectorListResponse(BaseModel):
    connectors: List[ConnectorResponse]
    total: int


class DriveItemResponse(BaseModel):
    id: str
    name: str
    item_type: str   # "file" or "folder"
    size: Optional[int] = None
    mime_type: Optional[str] = None
    modified_at: Optional[datetime] = None
    web_url: Optional[str] = None
    download_url: Optional[str] = None


class BrowseResponse(BaseModel):
    connector_id: str
    path: str
    items: List[DriveItemResponse]


class SharePointSiteResponse(BaseModel):
    site_id: str
    name: str
    display_name: str
    web_url: str


class ImportFileRequest(BaseModel):
    """Import specific files from a connected source."""
    item_ids: List[str]
    department: Optional[str] = None
    tags: List[str] = []


class ImportFileResult(BaseModel):
    item_id: str
    filename: str
    document_id: Optional[str] = None
    success: bool
    error: Optional[str] = None


class ImportResponse(BaseModel):
    connector_id: str
    results: List[ImportFileResult]
    total_imported: int
    total_failed: int


# ─── Slack-specific ───────────────────────────────────────────────────────────

class SlackChannelResponse(BaseModel):
    id: str
    name: str
    is_private: bool = False
    topic: Optional[str] = None
    member_count: Optional[int] = None


class SlackMessageResponse(BaseModel):
    id: str
    channel_id: str
    channel_name: str
    user_name: Optional[str] = None
    text: str
    timestamp: str
    has_files: bool = False


# ─── Microsoft Teams-specific ─────────────────────────────────────────────────

class TeamsTeamResponse(BaseModel):
    id: str
    display_name: str
    description: Optional[str] = None


class TeamsChannelResponse(BaseModel):
    id: str
    team_id: str
    display_name: str
    description: Optional[str] = None


# ─── ServiceNow-specific ──────────────────────────────────────────────────────

class ServiceNowRecordResponse(BaseModel):
    sys_id: str
    number: str
    short_description: str
    state: Optional[str] = None
    priority: Optional[str] = None
    assigned_to: Optional[str] = None
    created_on: Optional[str] = None
    table: str
