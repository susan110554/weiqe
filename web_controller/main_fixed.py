import os

def _load_env(path=".env"):
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
    except FileNotFoundError:
        pass

_load_env()
"""
IC3 Multi-Channel Admin Web Controller (Windows优化版)
FastAPI backend - 使用单连接替代连接池以避免Windows网络问题
"""
from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List
import jwt
import os
import logging
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

# ── Lazy imports for core services ───────────────────────────────────────────
try:
    import asyncpg
    from core.case_manager import CaseManager
    from core.content_manager import ContentManager
    from core.signature_service import SignatureService
    import database as db
    SERVICES_AVAILABLE = True
except ImportError:
    SERVICES_AVAILABLE = False

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
SECRET_KEY  = os.getenv("WEB_SECRET_KEY", "change-me-in-production")
ADMIN_TOKEN = os.getenv("WEB_ADMIN_TOKEN", "admin-token")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60 * 8  # 8 hours

# ── App state ─────────────────────────────────────────────────────────────────
_db_conn       = None  # 使用单个连接而不是连接池
_case_manager  : "CaseManager"    = None
_content_manager: "ContentManager" = None
_signature_service: "SignatureService" = None


# ── Mock Pool for single connection ───────────────────────────────────────────
class MockPool:
    """模拟连接池，实际使用单个连接"""
    def __init__(self, conn):
        self._conn = conn
    
    def acquire(self):
        return MockConnection(self._conn)


class MockConnection:
    """模拟连接上下文管理器"""
    def __init__(self, conn):
        self._conn = conn
    
    async def __aenter__(self):
        return self._conn
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle - 使用单连接"""
    global _db_conn, _case_manager, _content_manager, _signature_service, SERVICES_AVAILABLE
    if SERVICES_AVAILABLE:
        try:
            # 创建单个数据库连接
            _db_conn = await asyncpg.connect(
                host=os.getenv("DB_HOST", "localhost"),
                port=int(os.getenv("DB_PORT", 5432)),
                database=os.getenv("DB_NAME", "weiquan_bot"),
                user=os.getenv("DB_USER", "postgres"),
                password=os.getenv("DB_PASSWORD", ""),
            )
            logger.info("✅ Database connection established (single connection mode)")
            
            # 创建Mock Pool
            mock_pool = MockPool(_db_conn)
            
            # 初始化核心服务
            _content_manager   = ContentManager(mock_pool)
            _signature_service = SignatureService()
            _case_manager      = CaseManager(mock_pool, _content_manager, _signature_service)
            logger.info("✅ Core services initialised")
        except Exception as e:
            logger.error(f"❌ Failed to initialize services: {e}")
            SERVICES_AVAILABLE = False
    else:
        logger.warning("⚠️  Core services not available – running in stub mode")
    yield
    if _db_conn:
        await _db_conn.close()
        logger.info("Database connection closed")


app = FastAPI(
    title="IC3 Multi-Channel Admin API",
    version="1.0.0",
    description="Admin backend for the IC3 fraud-reporting platform (Windows optimized)",
    lifespan=lifespan,
)

# CORS配置 - 硬编码确保前端可以访问
CORS_ORIGINS_LIST = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS_LIST,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

# ── Auth helpers ──────────────────────────────────────────────────────────────

def _create_jwt(data: dict) -> str:
    payload = data | {"exp": datetime.utcnow() + timedelta(minutes=JWT_EXPIRE_MINUTES)}
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)


def _verify_jwt(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_auth(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    return _verify_jwt(credentials.credentials)


# ── Pydantic models ───────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    token: str

class TemplateUpdateRequest(BaseModel):
    channel: str
    content: str
    content_type: str = "text"
    title: Optional[str] = None
    variables: Optional[dict] = None

class TemplateCreateRequest(BaseModel):
    template_key: str
    channel: str
    content: str
    content_type: str = "text"
    title: Optional[str] = None
    variables: Optional[dict] = None

class CaseStatusUpdateRequest(BaseModel):
    new_status: str
    admin_notes: Optional[str] = None

class ChannelConfigUpdateRequest(BaseModel):
    configs: dict


class PushTaskCreateRequest(BaseModel):
    case_no: str
    phase: str
    push_type: str = "manual"
    scheduled_at: Optional[datetime] = None
    template_data: Optional[dict] = None


# ── Auth endpoints ────────────────────────────────────────────────────────────

@app.post("/api/auth/login", tags=["Auth"])
async def login(body: LoginRequest):
    """Exchange the admin token for a short-lived JWT."""
    if body.token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid admin token")
    jwt_token = _create_jwt({"sub": "admin", "role": "admin"})
    return {"access_token": jwt_token, "token_type": "bearer", "expires_in": JWT_EXPIRE_MINUTES * 60}


@app.get("/api/auth/me", tags=["Auth"])
async def me(user=Depends(require_auth)):
    return {"sub": user.get("sub"), "role": user.get("role")}


# ── Template endpoints ────────────────────────────────────────────────────────

@app.get("/api/templates", tags=["Templates"])
async def get_templates(
    channel: Optional[str] = Query(None, description="Filter by channel (telegram / whatsapp / web / default)"),
    _user=Depends(require_auth),
):
    """List all content templates, optionally filtered by channel."""
    if not SERVICES_AVAILABLE:
        raise HTTPException(503, "Core services unavailable")
    templates = await _content_manager.get_all_templates(channel)
    return {"templates": templates, "total": len(templates)}


@app.get("/api/templates/{template_key}", tags=["Templates"])
async def get_template(
    template_key: str,
    channel: str = Query(...),
    _user=Depends(require_auth),
):
    """Fetch a single template by key + channel."""
    if not SERVICES_AVAILABLE:
        raise HTTPException(503, "Core services unavailable")
    template = await _content_manager.get_template(template_key, channel)
    if not template:
        raise HTTPException(404, f"Template '{template_key}' not found for channel '{channel}'")
    return template


@app.post("/api/templates", status_code=201, tags=["Templates"])
async def create_template(body: TemplateCreateRequest, _user=Depends(require_auth)):
    """Create a new content template."""
    if not SERVICES_AVAILABLE:
        raise HTTPException(503, "Core services unavailable")
    ok = await _content_manager.update_template(
        body.template_key, body.channel, body.content,
        body.content_type, body.title, body.variables,
    )
    if not ok:
        raise HTTPException(500, "Failed to create template")
    return {"message": "Template created", "template_key": body.template_key, "channel": body.channel}


@app.put("/api/templates/{template_key}", tags=["Templates"])
async def update_template(template_key: str, body: TemplateUpdateRequest, _user=Depends(require_auth)):
    """Update an existing content template (triggers cache invalidation automatically)."""
    if not SERVICES_AVAILABLE:
        raise HTTPException(503, "Core services unavailable")
    ok = await _content_manager.update_template(
        template_key, body.channel, body.content,
        body.content_type, body.title, body.variables,
    )
    if not ok:
        raise HTTPException(500, "Failed to update template")
    return {"message": "Template updated", "template_key": template_key, "channel": body.channel}


@app.delete("/api/templates/{template_key}", tags=["Templates"])
async def delete_template(
    template_key: str,
    channel: str = Query(...),
    _user=Depends(require_auth),
):
    """Delete a template."""
    if not SERVICES_AVAILABLE:
        raise HTTPException(503, "Core services unavailable")
    ok = await _content_manager.delete_template(template_key, channel)
    if not ok:
        raise HTTPException(404, "Template not found or already deleted")
    return {"message": "Template deleted"}


@app.post("/api/templates/preview", tags=["Templates"])
async def preview_template(
    template_key: str = Query(...),
    channel: str = Query(...),
    variables: Optional[dict] = None,
    _user=Depends(require_auth),
):
    """Render a template with optional variables for live preview."""
    if not SERVICES_AVAILABLE:
        raise HTTPException(503, "Core services unavailable")
    rendered = await _content_manager.render_template(template_key, channel, variables or {})
    return rendered


@app.post("/api/templates/cache/refresh", tags=["Templates"])
async def refresh_template_cache(_user=Depends(require_auth)):
    """Force-clear the in-memory template cache."""
    if not SERVICES_AVAILABLE:
        raise HTTPException(503, "Core services unavailable")
    await _content_manager.refresh_cache()
    return {"message": "Cache refreshed"}


@app.get("/api/templates/stats", tags=["Templates"])
async def template_stats(_user=Depends(require_auth)):
    """Usage statistics for templates (per-channel counts, recently updated)."""
    if not SERVICES_AVAILABLE:
        raise HTTPException(503, "Core services unavailable")
    return await _content_manager.get_template_usage_stats()


# ── Case endpoints ────────────────────────────────────────────────────────────

@app.get("/api/cases", tags=["Cases"])
async def get_cases(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    channel: Optional[str] = None,
    _user=Depends(require_auth),
):
    """Paginated case list with optional status / channel filters."""
    if not SERVICES_AVAILABLE:
        raise HTTPException(503, "Core services unavailable")
    return await _case_manager.get_cases_paginated(page, limit, status, channel)


@app.get("/api/cases/{case_id}", tags=["Cases"])
async def get_case(case_id: str, _user=Depends(require_auth)):
    """Full case detail including evidences and status history."""
    if not SERVICES_AVAILABLE:
        raise HTTPException(503, "Core services unavailable")
    case = await _case_manager.get_case_by_id(case_id)
    if not case:
        raise HTTPException(404, f"Case '{case_id}' not found")
    return case


@app.put("/api/cases/{case_id}/status", tags=["Cases"])
async def update_case_status(case_id: str, body: CaseStatusUpdateRequest, user=Depends(require_auth)):
    """Update a case's status (admin only)."""
    if not SERVICES_AVAILABLE:
        raise HTTPException(503, "Core services unavailable")
    ok = await _case_manager.update_case_status(
        case_id, body.new_status, body.admin_notes, changed_by=user.get("sub", "admin")
    )
    if not ok:
        raise HTTPException(404, f"Case '{case_id}' not found")
    return {"message": "Status updated", "case_id": case_id, "new_status": body.new_status}


# ── Channel config endpoints ──────────────────────────────────────────────────

@app.get("/api/channels/config", tags=["Channels"])
async def get_channel_configs(_user=Depends(require_auth)):
    """Retrieve all channel configuration entries."""
    if not SERVICES_AVAILABLE or not _db_conn:
        raise HTTPException(503, "Core services unavailable")
    rows = await _db_conn.fetch("SELECT * FROM channel_configs ORDER BY channel_type, config_key")
    return {"configs": [dict(r) for r in rows]}


@app.put("/api/channels/{channel_type}/config", tags=["Channels"])
async def update_channel_config(
    channel_type: str,
    body: ChannelConfigUpdateRequest,
    _user=Depends(require_auth),
):
    """Upsert configuration key/value pairs for a specific channel."""
    if not SERVICES_AVAILABLE or not _db_conn:
        raise HTTPException(503, "Core services unavailable")
    for key, value in body.configs.items():
        await _db_conn.execute("""
            INSERT INTO channel_configs (channel_type, config_key, config_value)
            VALUES ($1, $2, $3)
            ON CONFLICT (channel_type, config_key)
            DO UPDATE SET config_value = $3, updated_at = NOW()
        """, channel_type, key, str(value))
    return {"message": "Config updated", "channel_type": channel_type, "keys_updated": list(body.configs.keys())}


# ── Dashboard / stats endpoint ────────────────────────────────────────────────

@app.get("/api/dashboard/stats", tags=["Dashboard"])
async def dashboard_stats(_user=Depends(require_auth)):
    """Aggregate counts for the admin dashboard overview."""
    if not SERVICES_AVAILABLE or not _db_conn:
        raise HTTPException(503, "Core services unavailable")
    
    total_cases    = await _db_conn.fetchval("SELECT COUNT(*) FROM cases")
    pending_cases  = await _db_conn.fetchval("SELECT COUNT(*) FROM cases WHERE status = 'Pending'")
    resolved_cases = await _db_conn.fetchval("SELECT COUNT(*) FROM cases WHERE status ILIKE '%resolved%' OR status ILIKE '%closed%'")
    total_templates= await _db_conn.fetchval("SELECT COUNT(*) FROM content_templates")

    by_channel = await _db_conn.fetch("""
        SELECT channel, COUNT(*) AS count
        FROM cases GROUP BY channel ORDER BY count DESC
    """)
    by_status = await _db_conn.fetch("""
        SELECT status, COUNT(*) AS count
        FROM cases GROUP BY status ORDER BY count DESC
    """)
    recent_cases = await _db_conn.fetch("""
        SELECT case_no, channel, status, created_at
        FROM cases ORDER BY created_at DESC LIMIT 5
    """)

    return {
        "totals": {
            "cases": total_cases,
            "pending": pending_cases,
            "resolved": resolved_cases,
            "templates": total_templates,
        },
        "by_channel": [dict(r) for r in by_channel],
        "by_status":  [dict(r) for r in by_status],
        "recent_cases": [dict(r) for r in recent_cases],
    }


# ── Message logs endpoints ─────────────────────────────────────────────────────

@app.get("/api/messages", tags=["Messages"])
async def get_messages(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    channel: Optional[str] = None,
    _user=Depends(require_auth),
):
    """Paginated message logs."""
    if not _db_conn:
        raise HTTPException(503, "Database unavailable")
    offset = (page - 1) * limit
    conditions, params = [], []
    if channel:
        conditions.append(f"channel_type = ${len(params)+1}"); params.append(channel)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = await _db_conn.fetch(
        f"SELECT * FROM message_logs {where} ORDER BY sent_at DESC LIMIT ${len(params)+1} OFFSET ${len(params)+2}",
        *params, limit, offset
    )
    total = await _db_conn.fetchval(
        f"SELECT COUNT(*) FROM message_logs {where}", *params
    )
    return {"messages": [dict(r) for r in rows], "total": total, "page": page}


# ── Broadcast endpoints ────────────────────────────────────────────────────────

class BroadcastCreateRequest(BaseModel):
    title: str
    content: str
    channel: str
    scheduled_at: Optional[str] = None
    target_filter: Optional[dict] = None

@app.get("/api/broadcasts", tags=["Broadcasts"])
async def get_broadcasts(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _user=Depends(require_auth),
):
    """List scheduled broadcasts."""
    if not _db_conn:
        raise HTTPException(503, "Database unavailable")
    offset = (page - 1) * limit
    rows = await _db_conn.fetch(
        "SELECT * FROM scheduled_broadcasts ORDER BY created_at DESC LIMIT $1 OFFSET $2",
        limit, offset
    )
    total = await _db_conn.fetchval("SELECT COUNT(*) FROM scheduled_broadcasts")
    return {"broadcasts": [dict(r) for r in rows], "total": total}


@app.post("/api/broadcasts", status_code=201, tags=["Broadcasts"])
async def create_broadcast(body: BroadcastCreateRequest, user=Depends(require_auth)):
    """Create a new broadcast message."""
    if not _db_conn:
        raise HTTPException(503, "Database unavailable")
    row = await _db_conn.fetchrow("""
        INSERT INTO scheduled_broadcasts (title, content, channel, scheduled_at, status, created_by)
        VALUES ($1, $2, $3, $4::timestamptz, 'pending', $5)
        RETURNING id, title, channel, status
    """, body.title, body.content, body.channel,
        body.scheduled_at, user.get("sub", "admin"))
    return {"message": "Broadcast created", "broadcast": dict(row)}


@app.delete("/api/broadcasts/{broadcast_id}", tags=["Broadcasts"])
async def delete_broadcast(broadcast_id: str, _user=Depends(require_auth)):
    """Delete a broadcast."""
    if not _db_conn:
        raise HTTPException(503, "Database unavailable")
    result = await _db_conn.execute(
        "DELETE FROM scheduled_broadcasts WHERE id = $1", broadcast_id
    )
    if result == "DELETE 0":
        raise HTTPException(404, "Broadcast not found")
    return {"message": "Broadcast deleted"}


# ── PDF Templates endpoints ────────────────────────────────────────────────────

@app.get("/api/pdf-templates", tags=["PDF"])
async def get_pdf_templates(_user=Depends(require_auth)):
    """List all PDF templates."""
    if not _db_conn:
        raise HTTPException(503, "Database unavailable")
    rows = await _db_conn.fetch("SELECT * FROM pdf_templates ORDER BY updated_at DESC")
    return {"templates": [dict(r) for r in rows], "total": len(rows)}


@app.get("/api/pdf-templates/{template_name}", tags=["PDF"])
async def get_pdf_template(template_name: str, _user=Depends(require_auth)):
    """Get a single PDF template."""
    if not _db_conn:
        raise HTTPException(503, "Database unavailable")
    row = await _db_conn.fetchrow(
        "SELECT * FROM pdf_templates WHERE template_name = $1", template_name
    )
    if not row:
        raise HTTPException(404, "PDF template not found")
    return dict(row)


class PDFTemplateUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    html_content: str
    css_content: Optional[str] = None
    variables: Optional[dict] = None

@app.put("/api/pdf-templates/{template_name}", tags=["PDF"])
async def update_pdf_template(
    template_name: str, body: PDFTemplateUpdateRequest, _user=Depends(require_auth)
):
    """Update a PDF template."""
    if not _db_conn:
        raise HTTPException(503, "Database unavailable")
    await _db_conn.execute("""
        UPDATE pdf_templates
        SET html_content = $2, css_content = $3, variables = $4::jsonb,
            updated_at = NOW()
        WHERE template_name = $1
    """, template_name, body.html_content, body.css_content,
        __import__('json').dumps(body.variables or {}))
    return {"message": "PDF template updated", "template_name": template_name}


# ── User management ───────────────────────────────────────────────────────────

@app.get("/api/users", tags=["Users"])
async def get_users(page: int = Query(1, ge=1), limit: int = Query(20, le=100),
                    search: Optional[str] = None, status: Optional[str] = None,
                    _user=Depends(require_auth)):
    if not _db_conn: raise HTTPException(503, "Database unavailable")
    offset = (page - 1) * limit
    conditions, params = [], []
    if search:
        conditions.append(f"(CAST(tg_user_id AS TEXT) ILIKE ${len(params)+1} OR tg_username ILIKE ${len(params)+1})")
        params.append(f"%{search}%")
    if status:
        conditions.append(f"status = ${len(params)+1}")
        params.append(status)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = await _db_conn.fetch(f"SELECT * FROM users {where} ORDER BY created_at DESC LIMIT ${len(params)+1} OFFSET ${len(params)+2}", *params, limit, offset)
    total = await _db_conn.fetchval(f"SELECT COUNT(*) FROM users {where}", *params)
    return {"users": [dict(r) for r in rows], "total": total, "page": page}

@app.get("/api/users/{user_id}", tags=["Users"])
async def get_user(user_id: int, _user=Depends(require_auth)):
    if not _db_conn: raise HTTPException(503, "Database unavailable")
    row = await _db_conn.fetchrow("SELECT * FROM users WHERE tg_user_id = $1", user_id)
    if not row: raise HTTPException(404, "User not found")
    cases = await _db_conn.fetch("SELECT case_no, status, created_at FROM cases WHERE tg_user_id = $1 ORDER BY created_at DESC LIMIT 10", user_id)
    return {**dict(row), "cases": [dict(r) for r in cases]}

class UserUpdateRequest(BaseModel):
    status: Optional[str] = None
    admin_notes: Optional[str] = None

@app.put("/api/users/{user_id}", tags=["Users"])
async def update_user(user_id: int, body: UserUpdateRequest, _user=Depends(require_auth)):
    if not _db_conn: raise HTTPException(503, "Database unavailable")
    await _db_conn.execute("UPDATE users SET status = COALESCE($2, status), updated_at = NOW() WHERE tg_user_id = $1", user_id, body.status)
    return {"message": "User updated"}

@app.post("/api/users/{user_id}/ban", tags=["Users"])
async def ban_user(user_id: int, _user=Depends(require_auth)):
    if not _db_conn: raise HTTPException(503, "Database unavailable")
    await _db_conn.execute("INSERT INTO blacklist (tg_user_id, reason, banned_by, is_active) VALUES ($1, 'Admin ban', $2, true) ON CONFLICT DO NOTHING", user_id, _user.get("sub"))
    return {"message": "User banned"}

@app.delete("/api/users/{user_id}/ban", tags=["Users"])
async def unban_user(user_id: int, _user=Depends(require_auth)):
    if not _db_conn: raise HTTPException(503, "Database unavailable")
    await _db_conn.execute("UPDATE blacklist SET is_active = false, unbanned_at = NOW() WHERE tg_user_id = $1", user_id)
    return {"message": "User unbanned"}


# ── Case phase management ──────────────────────────────────────────────────────

class PhaseAdvanceRequest(BaseModel):
    new_phase: str
    notes: Optional[str] = None
    force: bool = False

@app.put("/api/cases/{case_id}/phase", tags=["Cases"])
async def advance_case_phase(case_id: str, body: PhaseAdvanceRequest, user=Depends(require_auth)):
    if not _db_conn: raise HTTPException(503, "Database unavailable")
    row = await _db_conn.fetchrow("SELECT * FROM cases WHERE case_no = $1", case_id)
    if not row: raise HTTPException(404, "Case not found")
    await _db_conn.execute("UPDATE cases SET status = $2, updated_at = NOW(), admin_notes = COALESCE($3, admin_notes) WHERE case_no = $1", case_id, body.new_phase, body.notes)
    await _db_conn.execute("INSERT INTO status_history (case_id, old_status, new_status, changed_by, notes) VALUES ($1, $2, $3, $4, $5)", row['id'], row['status'], body.new_phase, user.get("sub"), body.notes)
    return {"message": "Phase updated", "case_no": case_id, "new_phase": body.new_phase}

@app.get("/api/cases/{case_id}/history", tags=["Cases"])
async def get_case_history(case_id: str, _user=Depends(require_auth)):
    if not _db_conn: raise HTTPException(503, "Database unavailable")
    row = await _db_conn.fetchrow("SELECT id FROM cases WHERE case_no = $1", case_id)
    if not row: raise HTTPException(404, "Case not found")
    history = await _db_conn.fetch("SELECT * FROM status_history WHERE case_id = $1 ORDER BY changed_at DESC", row['id'])
    return {"history": [dict(r) for r in history]}

@app.get("/api/cases/{case_id}/evidences", tags=["Cases"])
async def get_case_evidences(case_id: str, _user=Depends(require_auth)):
    if not _db_conn: raise HTTPException(503, "Database unavailable")
    row = await _db_conn.fetchrow("SELECT id FROM cases WHERE case_no = $1", case_id)
    if not row: raise HTTPException(404, "Case not found")
    evs = await _db_conn.fetch("SELECT * FROM evidences WHERE case_id = $1 ORDER BY uploaded_at DESC", row['id'])
    return {"evidences": [dict(r) for r in evs]}

class CaseOverridesRequest(BaseModel):
    overrides: dict

@app.put("/api/cases/{case_id}/overrides", tags=["Cases"])
async def update_case_overrides(case_id: str, body: CaseOverridesRequest, _user=Depends(require_auth)):
    if not _db_conn: raise HTTPException(503, "Database unavailable")
    import json
    await _db_conn.execute("UPDATE cases SET case_cmp_overrides = $2::jsonb, updated_at = NOW() WHERE case_no = $1", case_id, json.dumps(body.overrides))
    return {"message": "Case overrides updated"}

@app.get("/api/cases/{case_id}/messages", tags=["Cases"])
async def get_case_messages(case_id: str, _user=Depends(require_auth)):
    if not _db_conn: raise HTTPException(503, "Database unavailable")
    msgs = await _db_conn.fetch("SELECT * FROM liaison_messages WHERE case_no = $1 ORDER BY sent_at ASC", case_id)
    return {"messages": [dict(r) for r in msgs]}

class SendMessageRequest(BaseModel):
    content: str
    sender_type: str = "admin"

@app.post("/api/cases/{case_id}/messages", tags=["Cases"])
async def send_case_message(case_id: str, body: SendMessageRequest, user=Depends(require_auth)):
    if not _db_conn: raise HTTPException(503, "Database unavailable")
    await _db_conn.execute("INSERT INTO liaison_messages (case_no, content, sender_type, sender_id, sent_at) VALUES ($1, $2, $3, $4, NOW())", case_id, body.content, body.sender_type, user.get("sub"))
    return {"message": "Message sent"}


class AutoPushRequest(BaseModel):
    enabled: bool = False
    schedule: Optional[str] = None  # 修改为字符串格式，如 "2024-01-15 14:30:00"

@app.put("/api/cases/{case_id}/auto-push", tags=["Cases"])
async def update_auto_push(case_id: str, body: AutoPushRequest, user=Depends(require_auth)):
    """Update auto-push settings for a case"""
    if not _db_conn: raise HTTPException(503, "Database unavailable")
    import json
    
    # 构建保存的数据结构
    settings = {
        "enabled": body.enabled, 
        "schedule": body.schedule,
        "updated_at": datetime.utcnow().isoformat(),
        "updated_by": user.get("sub", "admin")
    }
    
    await _db_conn.execute(
        "UPDATE cases SET auto_push_settings = $2::jsonb, updated_at = NOW() WHERE case_no = $1",
        case_id, json.dumps(settings)
    )
    return {"message": "Auto-push settings updated", "case_no": case_id, "settings": settings}


class PersonalPushRequest(BaseModel):
    message: Optional[str] = None  # 可选，管理员自定义消息
    scheduledAt: Optional[str] = None
    immediate: bool = True

@app.post("/api/cases/{case_id}/personal-push", tags=["Cases"])
async def send_personal_push(case_id: str, body: PersonalPushRequest, user=Depends(require_auth)):
    """
    发送案件 Case Overview 推送给单个用户 (P1-P12阶段)
    系统自动构建 Case Overview 消息，不需要管理员输入
    """
    if not _db_conn: raise HTTPException(503, "Database unavailable")
    
    # 获取案件完整信息
    case = await _db_conn.fetchrow(
        """SELECT c.*, u.telegram_id, u.full_name, u.username
           FROM cases c 
           LEFT JOIN users u ON c.user_id = u.id 
           WHERE c.case_no = $1""", 
        case_id
    )
    if not case:
        raise HTTPException(404, f"Case '{case_id}' not found")
    
    tg_user_id = case.get("telegram_id") or case.get("tg_user_id")
    if not tg_user_id:
        raise HTTPException(400, f"Case '{case_id}' has no associated Telegram user")
    
    # 创建推送任务
    from datetime import datetime
    scheduled_time = datetime.utcnow() + timedelta(seconds=5) if body.immediate else (
        datetime.fromisoformat(body.scheduledAt.replace('Z', '+00:00')) if body.scheduledAt else datetime.utcnow() + timedelta(minutes=5)
    )
    
    # 构建 Case Overview 消息 (P1-P12阶段自动构建)
    phase = case.get("status") or "P1"
    platform = case.get("platform") or "N/A"
    amount = case.get("amount") or "N/A"
    coin = case.get("coin") or ""
    wallet = case.get("wallet_addr") or "N/A"
    chain = case.get("chain_type") or "N/A"
    tx_hash = case.get("tx_hash") or "N/A"
    created_at = str(case.get("created_at"))[:10] if case.get("created_at") else "N/A"
    user_name = case.get("full_name") or case.get("username") or "User"
    
    # 管理员自定义消息（可选）
    admin_note = ""
    if body.message and body.message.strip():
        admin_note = f"""
━━━━━━━━━━━━━━━━━━━━━
💬 <b>管理员备注:</b>
{body.message.strip()}
━━━━━━━━━━━━━━━━━━━━━"""
    
    # 构建完整的 Case Overview 推送消息
    message_text = f"""📋 <b>Case Overview Update</b>

👤 <b>User:</b> {user_name}
🆔 <b>Case ID:</b> <code>{case_id}</code>
📊 <b>Current Phase:</b> {phase}
📅 <b>Submitted:</b> {created_at}

━━━━━━━━━━━━━━━━━━━━━
� <b>Financial Details:</b>
• Amount: {amount} {coin}
• Platform: {platform}

🔗 <b>Blockchain Info:</b>
• Chain: {chain}
• Wallet: <code>{wallet[:20]}...</code> {wallet if len(wallet) <= 20 else ''}
• TX Hash: <code>{tx_hash[:20]}...</code> {tx_hash if len(tx_hash) <= 20 else ''}
{admin_note}
━━━━━━━━━━━━━━━━━━━━━

<i>Open M03 Case Tracking for full details and updates.</i>"""
    
    task_id = await db.push_task_create(
        case_no=case_id,
        tg_user_id=tg_user_id,
        phase=phase,
        push_type="manual",  # 个人手动推送
        scheduled_at=scheduled_time,
        template_data={
            "case_overview": {
                "phase": phase,
                "platform": platform,
                "amount": str(amount),
                "coin": coin,
                "chain": chain,
                "wallet": wallet,
                "tx_hash": tx_hash,
                "created_at": created_at
            },
            "sender": user.get("sub", "admin"),
            "admin_note": body.message if body.message else None
        }
    )
    
    # 如果是立即发送，直接发送Telegram消息
    if body.immediate and SERVICES_AVAILABLE:
        try:
            from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton
            bot = Bot(token=os.getenv("BOT_TOKEN", ""))
            
            # 添加 Case Tracking 按钮
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📂 Open Case Tracking", callback_data=f"case|{case_id}")],
                [InlineKeyboardButton("💬 Contact Officer", callback_data=f"flow|ch|{case_id}")]
            ])
            
            # 发送消息
            msg = await bot.send_message(
                chat_id=tg_user_id,
                text=message_text,
                parse_mode="HTML",
                reply_markup=keyboard
            )
            
            # 更新任务状态为已发送
            await db.push_task_mark_sent(task_id, msg.message_id)
            
            return {
                "message": "Case Overview push sent immediately",
                "task_id": task_id,
                "case_no": case_id,
                "tg_message_id": msg.message_id,
                "sent_at": datetime.utcnow().isoformat()
            }
        except Exception as e:
            # 发送失败，更新任务状态
            await db.push_task_mark_failed(task_id, str(e))
            raise HTTPException(500, f"Failed to send push: {str(e)}")
    
    return {
        "message": "Case Overview push scheduled" if not body.immediate else "Case Overview queued for immediate send",
        "task_id": task_id,
        "case_no": case_id,
        "scheduled_at": scheduled_time.isoformat()
    }


# ── Agents ─────────────────────────────────────────────────────────────────────

@app.get("/api/agents", tags=["Agents"])
async def get_agents(_user=Depends(require_auth)):
    if not _db_conn: raise HTTPException(503, "Database unavailable")
    rows = await _db_conn.fetch("SELECT * FROM agents ORDER BY created_at DESC")
    return {"agents": [dict(r) for r in rows]}

@app.get("/api/agents/{agent_code}/inbox", tags=["Agents"])
async def get_agent_inbox(agent_code: str, _user=Depends(require_auth)):
    if not _db_conn: raise HTTPException(503, "Database unavailable")
    rows = await _db_conn.fetch("SELECT * FROM agent_inbox WHERE agent_code = $1 ORDER BY created_at DESC LIMIT 50", agent_code)
    return {"inbox": [dict(r) for r in rows]}


# ── Admin management ───────────────────────────────────────────────────────────

class AdminCreateRequest(BaseModel):
    username: str
    email: Optional[str] = None
    role: str = "L2"
    token: str

@app.get("/api/admins", tags=["Admins"])
async def get_admins(_user=Depends(require_auth)):
    if not _db_conn: raise HTTPException(503, "Database unavailable")
    rows = await _db_conn.fetch("SELECT id, agent_code, tg_user_id, office_id, is_active, created_at FROM agents ORDER BY created_at DESC")
    return {"admins": [{**dict(r), 'username': r['agent_code'], 'role': 'L3', 'status': 'active' if r['is_active'] else 'inactive'} for r in rows]}


# ── Audit logs ─────────────────────────────────────────────────────────────────

@app.get("/api/audit-logs", tags=["Audit"])
async def get_audit_logs(page: int = Query(1, ge=1), limit: int = Query(20, le=100),
                         action_type: Optional[str] = None, actor_id: Optional[str] = None,
                         _user=Depends(require_auth)):
    if not _db_conn: raise HTTPException(503, "Database unavailable")
    offset = (page - 1) * limit
    conditions, params = [], []
    if action_type:
        conditions.append(f"action = ${len(params)+1}"); params.append(action_type)
    if actor_id:
        conditions.append(f"actor_id = ${len(params)+1}"); params.append(actor_id)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = await _db_conn.fetch(f"SELECT * FROM audit_logs {where} ORDER BY logged_at DESC LIMIT ${len(params)+1} OFFSET ${len(params)+2}", *params, limit, offset)
    total = await _db_conn.fetchval(f"SELECT COUNT(*) FROM audit_logs {where}", *params)
    return {"logs": [{**dict(r), 'action_type': r['action'], 'created_at': r['logged_at'], 'description': r['detail']} for r in rows], "total": total}


# ── System config ──────────────────────────────────────────────────────────────

@app.get("/api/system-config", tags=["System"])
async def get_system_config(_user=Depends(require_auth)):
    if not _db_conn: raise HTTPException(503, "Database unavailable")
    rows = await _db_conn.fetch("SELECT * FROM system_configs ORDER BY config_key")
    return {"configs": {r['config_key']: r['config_value'] for r in rows}}

class SystemConfigUpdateRequest(BaseModel):
    configs: dict

@app.put("/api/system-config", tags=["System"])
async def update_system_config(body: SystemConfigUpdateRequest, _user=Depends(require_auth)):
    if not _db_conn: raise HTTPException(503, "Database unavailable")
    for key, value in body.configs.items():
        await _db_conn.execute("INSERT INTO system_configs (config_key, config_value) VALUES ($1, $2) ON CONFLICT (config_key) DO UPDATE SET config_value = $2, updated_at = NOW()", key, str(value))
    return {"message": "System config updated"}


# ── Blacklist/Whitelist ────────────────────────────────────────────────────────

@app.get("/api/blacklist", tags=["Security"])
async def get_blacklist(page: int = Query(1, ge=1), limit: int = Query(20, le=100),
                        list_type: str = Query("blacklist"), _user=Depends(require_auth)):
    if not _db_conn: raise HTTPException(503, "Database unavailable")
    offset = (page - 1) * limit
    rows = await _db_conn.fetch("SELECT * FROM blacklist WHERE is_active = true ORDER BY banned_at DESC LIMIT $1 OFFSET $2", limit, offset)
    total = await _db_conn.fetchval("SELECT COUNT(*) FROM blacklist WHERE is_active = true")
    return {"entries": [{**dict(r), 'created_at': r['banned_at'], 'created_by': r['banned_by']} for r in rows], "total": total}

class BlacklistAddRequest(BaseModel):
    tg_user_id: Optional[int] = None
    wallet_address: Optional[str] = None
    chain: Optional[str] = None
    label: Optional[str] = None
    reason: Optional[str] = None

@app.post("/api/blacklist", status_code=201, tags=["Security"])
async def add_to_blacklist(body: BlacklistAddRequest, user=Depends(require_auth)):
    if not _db_conn: raise HTTPException(503, "Database unavailable")
    await _db_conn.execute("INSERT INTO blacklist (tg_user_id, reason, banned_by, is_active) VALUES ($1, $2, $3, true) ON CONFLICT DO NOTHING",
        body.tg_user_id, body.reason or body.label, user.get("sub"))
    return {"message": "Added to blacklist"}

@app.delete("/api/blacklist/{entry_id}", tags=["Security"])
async def remove_from_blacklist(entry_id: str, _user=Depends(require_auth)):
    if not _db_conn: raise HTTPException(503, "Database unavailable")
    await _db_conn.execute("UPDATE blacklist SET is_active = false, unbanned_at = NOW() WHERE id = $1", entry_id)
    return {"message": "Removed from blacklist"}


# ── Fee config ─────────────────────────────────────────────────────────────────

@app.get("/api/fee-config", tags=["Fees"])
async def get_fee_config(_user=Depends(require_auth)):
    if not _db_conn: raise HTTPException(503, "Database unavailable")
    rows = await _db_conn.fetch("SELECT * FROM fee_config ORDER BY key")
    return {"fees": [{**dict(r), 'id': r['key'], 'fee_type': r['key'], 'enabled': True} for r in rows]}

class FeeUpdateRequest(BaseModel):
    fee_type: str
    amount: float
    currency: str = "USD"
    crypto_address: Optional[str] = None
    network: Optional[str] = None
    enabled: bool = True

@app.put("/api/fee-config/{fee_id}", tags=["Fees"])
async def update_fee_config(fee_id: str, body: FeeUpdateRequest, _user=Depends(require_auth)):
    if not _db_conn: raise HTTPException(503, "Database unavailable")
    await _db_conn.execute("UPDATE fee_config SET amount = $2, currency = $3, updated_at = NOW(), updated_by = $4 WHERE key = $1",
        fee_id, body.amount, body.currency, 'admin')
    return {"message": "Fee config updated"}


# ── Push Tasks (P1-P12 stage push task management) ───────────────────────────────

@app.get("/api/cases/{case_no}/push-tasks", tags=["Push Tasks"])
async def get_case_push_tasks(case_no: str, _user=Depends(require_auth)):
    """获取案件的所有推送任务"""
    if not _db_conn:
        raise HTTPException(503, "Database unavailable")
    tasks = await db.push_task_fetch_by_case(case_no)
    return {"tasks": tasks, "total": len(tasks)}


@app.post("/api/cases/{case_no}/push-tasks", status_code=201, tags=["Push Tasks"])
async def create_push_task(case_no: str, body: PushTaskCreateRequest, user=Depends(require_auth)):
    """创建推送任务（手动推送）"""
    if not _db_conn:
        raise HTTPException(503, "Database unavailable")
    
    # 获取案件信息
    case = await _db_conn.fetchrow(
        "SELECT tg_user_id FROM cases WHERE UPPER(case_no) = UPPER($1)",
        case_no
    )
    if not case:
        raise HTTPException(404, f"Case '{case_no}' not found")
    
    # 如果没有指定时间，默认立即发送（延迟5秒让后台处理）
    scheduled = body.scheduled_at or (datetime.utcnow() + timedelta(seconds=5))
    
    task_id = await db.push_task_create(
        case_no=case_no,
        tg_user_id=case["tg_user_id"],
        phase=body.phase,
        push_type=body.push_type,
        scheduled_at=scheduled,
        template_data=body.template_data,
    )
    
    return {
        "message": "Push task created",
        "task_id": task_id,
        "case_no": case_no,
        "phase": body.phase,
        "scheduled_at": scheduled.isoformat(),
    }


@app.post("/api/push-tasks/{task_id}/send-now", tags=["Push Tasks"])
async def send_push_task_now(task_id: int, user=Depends(require_auth)):
    """立即发送等待中的推送任务"""
    if not _db_conn:
        raise HTTPException(503, "Database unavailable")
    
    # 获取任务信息
    task = await _db_conn.fetchrow(
        "SELECT * FROM push_tasks WHERE id = $1 AND status = 'pending'",
        task_id
    )
    if not task:
        raise HTTPException(404, "Task not found or not in pending status")
    
    # TODO: 集成Telegram适配器发送消息
    # 临时模拟发送成功
    tg_message_id = None
    success = await db.push_task_mark_sent(task_id, tg_message_id)
    
    if success:
        return {"message": "Push sent successfully", "task_id": task_id}
    else:
        raise HTTPException(500, "Failed to send push")


@app.post("/api/push-tasks/{task_id}/retry", tags=["Push Tasks"])
async def retry_push_task(task_id: int, user=Depends(require_auth)):
    """重试失败的推送任务"""
    if not _db_conn:
        raise HTTPException(503, "Database unavailable")
    
    # 重新安排为立即发送
    new_time = datetime.utcnow() + timedelta(seconds=5)
    ok = await db.push_task_reschedule(task_id, new_time)
    
    if not ok:
        raise HTTPException(400, "Task not found or not in failed/cancelled status")
    
    return {
        "message": "Task rescheduled for retry",
        "task_id": task_id,
        "new_scheduled_at": new_time.isoformat(),
    }


@app.post("/api/push-tasks/{task_id}/cancel", tags=["Push Tasks"])
async def cancel_push_task(task_id: int, user=Depends(require_auth)):
    """取消等待中的推送任务"""
    if not _db_conn:
        raise HTTPException(503, "Database unavailable")
    
    ok = await db.push_task_cancel(task_id, user.get("sub", "admin"))
    
    if not ok:
        raise HTTPException(400, "Task not found or not in pending status")
    
    return {"message": "Task cancelled", "task_id": task_id}


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health", include_in_schema=False)
async def health():
    return {
        "status": "ok",
        "services_available": SERVICES_AVAILABLE,
        "connection_mode": "single_connection",
        "time": datetime.utcnow().isoformat()
    }
