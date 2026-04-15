"""
Utility helpers for the IC3 Admin Web Controller.
"""
from __future__ import annotations
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional
import asyncpg

logger = logging.getLogger(__name__)


# ── Pagination ────────────────────────────────────────────────────────────────

def paginate(total: int, page: int, limit: int) -> Dict[str, int]:
    """Return pagination metadata."""
    total_pages = max(1, -(-total // limit))  # ceiling division
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }


# ── Database row serialiser ───────────────────────────────────────────────────

def serialize_row(row) -> Dict[str, Any]:
    """Convert an asyncpg Record to a JSON-safe dict."""
    result = {}
    for key, value in dict(row).items():
        if isinstance(value, datetime):
            result[key] = value.isoformat()
        elif isinstance(value, bytes):
            result[key] = value.decode("utf-8", errors="replace")
        else:
            result[key] = value
    return result


def serialize_rows(rows) -> list:
    return [serialize_row(r) for r in rows]


# ── Environment helpers ───────────────────────────────────────────────────────

def require_env(name: str) -> str:
    """Return env var value or raise a clear RuntimeError."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Required environment variable '{name}' is not set")
    return value


# ── Audit log helper ──────────────────────────────────────────────────────────

async def write_audit_log(
    pool: asyncpg.Pool,
    action: str,
    actor_id: str,
    target_id: Optional[str],
    detail: Optional[str] = None,
    actor_type: str = "ADMIN",
) -> None:
    """Insert a row into audit_logs. Swallows errors to avoid breaking request flow."""
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO audit_logs (action, actor_type, actor_id, target_id, detail)
                VALUES ($1, $2, $3, $4, $5)
                """,
                action, actor_type, actor_id, target_id, detail,
            )
    except Exception as exc:
        logger.warning(f"Audit log write failed: {exc}")


# ── Response envelope ─────────────────────────────────────────────────────────

def ok(data: Any = None, message: str = "OK") -> Dict[str, Any]:
    """Consistent success envelope."""
    return {"success": True, "message": message, "data": data}


def err(message: str, code: int = 400) -> Dict[str, Any]:
    """Consistent error envelope (for non-exception paths)."""
    return {"success": False, "message": message, "code": code}
