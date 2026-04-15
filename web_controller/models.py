"""
Pydantic models for IC3 Multi-Channel Admin Web Controller API.

All request/response schemas in one place for easy maintenance.
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime


# ── Authentication Models ─────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    """Admin login request."""
    token: str = Field(..., description="Admin token from WEB_ADMIN_TOKEN env var")


class LoginResponse(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Token expiration time in seconds")


class UserInfo(BaseModel):
    """Authenticated user information."""
    sub: str
    role: str


# ── Template Models ───────────────────────────────────────────────────────────

class TemplateCreateRequest(BaseModel):
    """Create a new content template."""
    template_key: str = Field(..., min_length=1, max_length=100)
    channel: str = Field(..., description="telegram, whatsapp, web, or default")
    content: str = Field(..., min_length=1)
    content_type: str = Field(default="text", description="text, html, or markdown")
    title: Optional[str] = Field(None, max_length=200)
    variables: Optional[Dict[str, str]] = Field(None, description="Template variable definitions")

    @validator('channel')
    def validate_channel(cls, v):
        allowed = {'telegram', 'whatsapp', 'web', 'default'}
        if v not in allowed:
            raise ValueError(f"Channel must be one of {allowed}")
        return v


class TemplateUpdateRequest(BaseModel):
    """Update an existing template."""
    channel: str = Field(..., description="telegram, whatsapp, web, or default")
    content: str = Field(..., min_length=1)
    content_type: str = Field(default="text")
    title: Optional[str] = Field(None, max_length=200)
    variables: Optional[Dict[str, str]] = None

    @validator('channel')
    def validate_channel(cls, v):
        allowed = {'telegram', 'whatsapp', 'web', 'default'}
        if v not in allowed:
            raise ValueError(f"Channel must be one of {allowed}")
        return v


class TemplateResponse(BaseModel):
    """Template data response."""
    id: str
    template_key: str
    channel_type: str
    content_type: str
    title: Optional[str]
    content: str
    variables: Optional[Dict]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TemplatePreviewRequest(BaseModel):
    """Preview a template with variables."""
    template_key: str
    channel: str
    variables: Optional[Dict[str, Any]] = None


# ── Case Models ───────────────────────────────────────────────────────────────

class CaseStatusUpdateRequest(BaseModel):
    """Update case status."""
    new_status: str = Field(..., min_length=1)
    admin_notes: Optional[str] = Field(None, description="Admin notes for this status change")

    @validator('new_status')
    def validate_status(cls, v):
        # 常见的案件状态
        allowed_statuses = {
            '待初步审核', '审核中', '需补充材料', '证据已补充',
            '待支付', '支付已确认', '处理中', '已结案', '已关闭'
        }
        if v not in allowed_statuses:
            # 允许自定义状态，但记录警告
            import logging
            logging.getLogger(__name__).warning(f"Non-standard status used: {v}")
        return v


class CaseListResponse(BaseModel):
    """Paginated case list response."""
    cases: List[Dict[str, Any]]
    total: int
    page: int
    limit: int
    total_pages: int


class CaseDetailResponse(BaseModel):
    """Full case detail response."""
    case_no: str
    channel: str
    status: str
    platform: str
    amount: str
    created_at: datetime
    updated_at: datetime
    evidences: List[Dict[str, Any]] = []
    status_history: List[Dict[str, Any]] = []


# ── Channel Config Models ─────────────────────────────────────────────────────

class ChannelConfigUpdateRequest(BaseModel):
    """Update channel configuration."""
    configs: Dict[str, Any] = Field(..., description="Key-value pairs to upsert")


class ChannelConfigResponse(BaseModel):
    """Channel configuration response."""
    configs: List[Dict[str, Any]]


# ── Dashboard Models ──────────────────────────────────────────────────────────

class DashboardStats(BaseModel):
    """Dashboard statistics response."""
    totals: Dict[str, int]
    by_channel: List[Dict[str, Any]]
    by_status: List[Dict[str, Any]]
    recent_cases: List[Dict[str, Any]]


# ── Generic Response Models ───────────────────────────────────────────────────

class SuccessResponse(BaseModel):
    """Generic success response."""
    message: str
    data: Optional[Any] = None


class ErrorResponse(BaseModel):
    """Generic error response."""
    detail: str
    code: Optional[int] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    services_available: bool
    time: str
    version: str = "1.0.0"
