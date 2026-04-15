"""
IC3 Multi-Channel Admin Web Controller
FastAPI backend - calls existing core services directly
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
# These exist in the project; imported at runtime so this file can be read
# standalone (e.g. linted) without the full dependency tree installed.
try:
    import asyncpg
    import database as db
    from core.case_manager import CaseManager
    from core.content_manager import ContentManager
    from core.signature_service import SignatureService
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
_db_pool       = None
_case_manager  : "CaseManager"    = None
_content_manager: "ContentManager" = None
_signature_service: "SignatureService" = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    global _db_pool, _case_manager, _content_manager, _signature_service
    if SERVICES_AVAILABLE:
        _db_pool           = await db.get_pool()
        _content_manager   = ContentManager(_db_pool)
        _signature_service = SignatureService()
        _case_manager      = CaseManager(_db_pool, _content_manager, _signature_service)
        logger.info("Core services initialised")
    else:
        logger.warning("Core services not available – running in stub mode")
    yield
    if _db_pool:
        await _db_pool.close()


app = FastAPI(
    title="IC3 Multi-Channel Admin API",
    version="1.0.0",
    description="Admin backend for the IC3 fraud-reporting platform",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
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
    if not SERVICES_AVAILABLE:
        raise HTTPException(503, "Core services unavailable")
    async with _db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM channel_configs ORDER BY channel_type, config_key")
    return {"configs": [dict(r) for r in rows]}


@app.put("/api/channels/{channel_type}/config", tags=["Channels"])
async def update_channel_config(
    channel_type: str,
    body: ChannelConfigUpdateRequest,
    _user=Depends(require_auth),
):
    """Upsert configuration key/value pairs for a specific channel."""
    if not SERVICES_AVAILABLE:
        raise HTTPException(503, "Core services unavailable")
    async with _db_pool.acquire() as conn:
        for key, value in body.configs.items():
            await conn.execute("""
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
    if not SERVICES_AVAILABLE:
        raise HTTPException(503, "Core services unavailable")
    async with _db_pool.acquire() as conn:
        total_cases    = await conn.fetchval("SELECT COUNT(*) FROM cases")
        pending_cases  = await conn.fetchval("SELECT COUNT(*) FROM cases WHERE status = '待初步审核'")
        resolved_cases = await conn.fetchval("SELECT COUNT(*) FROM cases WHERE status ILIKE '%resolved%' OR status ILIKE '%closed%'")
        total_templates= await conn.fetchval("SELECT COUNT(*) FROM content_templates")

        by_channel = await conn.fetch("""
            SELECT channel, COUNT(*) AS count
            FROM cases GROUP BY channel ORDER BY count DESC
        """)
        by_status = await conn.fetch("""
            SELECT status, COUNT(*) AS count
            FROM cases GROUP BY status ORDER BY count DESC
        """)
        recent_cases = await conn.fetch("""
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


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health", include_in_schema=False)
async def health():
    return {"status": "ok", "services_available": SERVICES_AVAILABLE, "time": datetime.utcnow().isoformat()}
