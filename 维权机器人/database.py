"""
database.py — PostgreSQL 数据库初始化与操作模块
支持：asyncpg 异步连接池 + 审计日志 + 证据管理
"""

import asyncpg
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

# ── 全局连接池 ─────────────────────────────────────────
_pool: asyncpg.Pool = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", 5432)),
            database=os.getenv("DB_NAME", "weiquan_bot"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", ""),
            min_size=2,
            max_size=10,
        )
        logger.info("✅ 数据库连接池已建立")
    return _pool


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        logger.info("数据库连接池已关闭")


# ── 初始化所有数据表 ───────────────────────────────────
async def init_db():
    pool = await get_pool()
    async with pool.acquire() as conn:
        # 案件主表
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS cases (
                id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                case_no       TEXT UNIQUE NOT NULL,
                created_at    TIMESTAMPTZ DEFAULT NOW(),
                updated_at    TIMESTAMPTZ DEFAULT NOW(),

                -- 用户信息
                tg_user_id    BIGINT NOT NULL,
                tg_username   TEXT,

                -- 案件详情
                platform      TEXT NOT NULL,
                amount        NUMERIC(20,6),
                coin          TEXT,
                incident_time TEXT,
                wallet_addr   TEXT,
                chain_type    TEXT,
                tx_hash       TEXT,
                contact       TEXT,

                -- 状态管理
                status        TEXT DEFAULT '待初步审核',
                admin_notes   TEXT,

                -- 风险评分
                risk_score    INTEGER DEFAULT 0,
                risk_label    TEXT DEFAULT '未评估'
            );
        """)
        # 兼容旧库：若 cases 表已存在但缺少 updated_at，则追加列（触发器依赖此列）
        await conn.execute("""
            ALTER TABLE cases ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();
        """)
        # 专员工作电报 ID/用户名，用于「Connect to Special Agent」链接
        await conn.execute("""
            ALTER TABLE cases ADD COLUMN IF NOT EXISTS agent_tg_id BIGINT;
            ALTER TABLE cases ADD COLUMN IF NOT EXISTS agent_username TEXT;
        """)

        # 证据文件表
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS evidences (
                id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                case_id     UUID REFERENCES cases(id) ON DELETE CASCADE,
                uploaded_at TIMESTAMPTZ DEFAULT NOW(),
                file_type   TEXT,
                file_id     TEXT,
                file_name   TEXT,
                description TEXT
            );
        """)
        # 兼容旧库：若 evidences 已存在但缺少新字段或默认值，则追加/修正
        await conn.execute("""
            ALTER TABLE evidences
                ADD COLUMN    IF NOT EXISTS file_name   TEXT,
                ADD COLUMN    IF NOT EXISTS description TEXT,
                ALTER COLUMN  id SET DEFAULT gen_random_uuid();
        """)

        # 审计日志表
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id          BIGSERIAL PRIMARY KEY,
                logged_at   TIMESTAMPTZ DEFAULT NOW(),
                actor_type  TEXT,
                actor_id    TEXT,
                action      TEXT NOT NULL,
                target_id   TEXT,
                detail      TEXT
            );
        """)

        # 状态变更历史表
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS status_history (
                id          BIGSERIAL PRIMARY KEY,
                case_id     UUID REFERENCES cases(id) ON DELETE CASCADE,
                changed_at  TIMESTAMPTZ DEFAULT NOW(),
                old_status  TEXT,
                new_status  TEXT,
                changed_by  TEXT,
                note        TEXT
            );
        """)

        # 自动更新 updated_at 触发器
        await conn.execute("""
            CREATE OR REPLACE FUNCTION update_updated_at()
            RETURNS TRIGGER AS $$
            BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
            $$ LANGUAGE plpgsql;
        """)
        await conn.execute("""
            DROP TRIGGER IF EXISTS trg_cases_updated ON cases;
            CREATE TRIGGER trg_cases_updated
            BEFORE UPDATE ON cases
            FOR EACH ROW EXECUTE FUNCTION update_updated_at();
        """)

        # ── Migration: reconcile existing DB schema with new code ──────
        # The existing DB uses different column names than our code expects.
        # We ADD the new column names as aliases where they don't exist yet.
        migrations = [
            # Core columns our code uses — may not exist in old schema
            "ALTER TABLE cases ADD COLUMN IF NOT EXISTS case_no TEXT",
            "ALTER TABLE cases ADD COLUMN IF NOT EXISTS tg_user_id BIGINT",
            "ALTER TABLE cases ADD COLUMN IF NOT EXISTS platform TEXT",
            "ALTER TABLE cases ADD COLUMN IF NOT EXISTS amount NUMERIC(20,6)",
            # Columns that exist under different names — ensure new names too
            "ALTER TABLE cases ADD COLUMN IF NOT EXISTS tg_username TEXT",
            "ALTER TABLE cases ADD COLUMN IF NOT EXISTS coin TEXT",
            "ALTER TABLE cases ADD COLUMN IF NOT EXISTS incident_time TEXT",
            "ALTER TABLE cases ADD COLUMN IF NOT EXISTS wallet_addr TEXT",
            "ALTER TABLE cases ADD COLUMN IF NOT EXISTS chain_type TEXT",
            "ALTER TABLE cases ADD COLUMN IF NOT EXISTS tx_hash TEXT",
            "ALTER TABLE cases ADD COLUMN IF NOT EXISTS contact TEXT",
            "ALTER TABLE cases ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'Pending Initial Review'",
            "ALTER TABLE cases ADD COLUMN IF NOT EXISTS admin_notes TEXT",
            "ALTER TABLE cases ADD COLUMN IF NOT EXISTS risk_score INTEGER DEFAULT 0",
            "ALTER TABLE cases ADD COLUMN IF NOT EXISTS risk_label TEXT DEFAULT 'Unassessed'",
        ]
        for sql in migrations:
            try:
                await conn.execute(sql)
            except Exception as e:
                logger.warning(f"Migration skipped: {e}")

        # Fix id column: ensure it has gen_random_uuid() as default
        try:
            await conn.execute("""
                ALTER TABLE cases
                ALTER COLUMN id SET DEFAULT gen_random_uuid()
            """)
            logger.info("✅ id column default set to gen_random_uuid()")
        except Exception as e:
            logger.warning(f"id default migration: {e}")

        # Add UNIQUE constraint on case_no if not already present
        try:
            await conn.execute("""
                DO $$ BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'cases_case_no_unique'
                    ) THEN
                        ALTER TABLE cases ADD CONSTRAINT cases_case_no_unique UNIQUE (case_no);
                    END IF;
                END $$;
            """)
        except Exception as e:
            logger.warning(f"Unique constraint: {e}")

        # Sync case_number → case_no for any existing rows
        try:
            await conn.execute("""
                UPDATE cases SET case_no = case_number
                WHERE case_no IS NULL AND case_number IS NOT NULL
            """)
        except Exception:
            pass

        # Sync user_id → tg_user_id for any existing rows
        try:
            await conn.execute("""
                UPDATE cases SET tg_user_id = user_id
                WHERE tg_user_id IS NULL AND user_id IS NOT NULL
            """)
        except Exception:
            pass

        logger.info("✅ Database initialized and migrations applied")


# ── 案件操作 ───────────────────────────────────────────
async def create_case(data: dict) -> str:
    """Insert case record. Handles amount parsing robustly."""
    pool = await get_pool()

    # Robust amount conversion — strip commas, handle None/"0"/""
    raw_amount = data.get('amount', '0') or '0'
    try:
        amount_val = float(str(raw_amount).replace(',', '').strip())
    except (ValueError, TypeError):
        amount_val = None
        logger.warning(f"Could not parse amount: {raw_amount!r}, storing NULL")

    async with pool.acquire() as conn:
        try:
            row = await conn.fetchrow("""
                INSERT INTO cases (
                    id,
                    case_number, case_no,
                    user_id, tg_user_id, tg_username,
                    platform, amount, coin, incident_time,
                    wallet_addr, chain_type, tx_hash, contact
                ) VALUES (
                    gen_random_uuid(),
                    $1::text, $2::text,
                    $3::bigint, $4::bigint, $5,
                    $6, $7, $8, $9,
                    $10, $11, $12, $13
                )
                RETURNING id, case_no, case_number
            """,
                str(data['case_no']),        # $1  case_number (character varying → cast to text)
                str(data['case_no']),        # $2  case_no     (text)
                int(data['tg_user_id']),     # $3  user_id
                int(data['tg_user_id']),     # $4  tg_user_id
                data.get('tg_username') or 'Anonymous',   # $5
                data.get('platform') or 'Not specified',  # $6
                amount_val,                                  # $7
                data.get('coin') or '',                  # $8
                data.get('incident_time') or 'Not specified',  # $9
                data.get('wallet_addr') or 'Unknown',    # $10
                data.get('chain_type') or 'Unknown',     # $11
                data.get('tx_hash') or 'None',           # $12
                data.get('contact') or 'Anonymous',      # $13
            )
        except Exception as e:
            logger.error(f"[DB] create_case INSERT failed: {e}")
            logger.error(f"[DB] data dump: {data}")
            raise

        await audit_log(
            conn, 'USER', str(data['tg_user_id']), 'CASE_CREATED',
            str(row['id']),
            f"case={data['case_no']} amount={amount_val} {data.get('coin','')} "
            f"platform={data.get('platform','')} uid={data['tg_user_id']}"
        )
        logger.info(f"[DB] Case created: {row['case_no']} id={row['id']}")
        return row['case_no']


async def get_case_by_no(case_no: str) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Try case_no first, fall back to case_number (old schema)
        row = await conn.fetchrow(
            "SELECT * FROM cases WHERE case_no = $1 OR case_number = $1",
            case_no.upper()
        )
        return dict(row) if row else None


async def update_case_status(case_no: str, new_status: str, admin_id: str, note: str = "",
                            agent_code: str = None, agent_tg_id: int = None,
                            agent_username: str = None) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id, status FROM cases WHERE case_no=$1", case_no)
        if not row:
            return False
        old_status = row['status']
        if agent_code is not None:
            if agent_tg_id is not None or agent_username is not None:
                await conn.execute(
                    """UPDATE cases SET status=$1, agent_code=$2, agent_tg_id=$3, agent_username=$4, updated_at=NOW()
                       WHERE case_no=$5""",
                    new_status, agent_code, agent_tg_id, (agent_username or "").strip().lstrip("@") or None, case_no
                )
            else:
                await conn.execute(
                    "UPDATE cases SET status=$1, agent_code=$2, updated_at=NOW() WHERE case_no=$3",
                    new_status, agent_code, case_no
                )
        else:
            await conn.execute("UPDATE cases SET status=$1, updated_at=NOW() WHERE case_no=$2", new_status, case_no)
        await conn.execute("""
            INSERT INTO status_history (case_id, old_status, new_status, changed_by, note)
            VALUES ($1,$2,$3,$4,$5)
        """, row['id'], old_status, new_status, admin_id, note)
        await audit_log(conn, 'ADMIN', admin_id, 'STATUS_UPDATED',
                        str(row['id']), f"{old_status} → {new_status}")
        return True


async def get_recent_cases(limit: int = 10) -> list:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT *,
                COALESCE(case_no, case_number) AS display_case_no,
                COALESCE(tg_user_id, user_id)  AS display_user_id
            FROM cases ORDER BY created_at DESC LIMIT $1
        """, limit)
        return [dict(r) for r in rows]


async def get_case_count() -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM cases")


# ── 证据操作 ───────────────────────────────────────────
async def add_evidence(case_no: str, file_type: str, file_id: str,
                       file_name: str, description: str = "") -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id FROM cases WHERE case_no=$1", case_no)
        if not row:
            return False
        await conn.execute("""
            INSERT INTO evidences (case_id, file_type, file_id, file_name, description)
            VALUES ($1,$2,$3,$4,$5)
        """, row['id'], file_type, file_id, file_name, description)
        await audit_log(conn, 'SYSTEM', 'BOT', 'EVIDENCE_ADDED',
                        str(row['id']), f"文件={file_name}")
        return True


async def get_evidences(case_no: str) -> list:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT e.* FROM evidences e
            JOIN cases c ON c.id = e.case_id
            WHERE c.case_no = $1
            ORDER BY e.uploaded_at DESC
        """, case_no)
        return [dict(r) for r in rows]


# ── 审计日志 ───────────────────────────────────────────
async def audit_log(conn, actor_type: str, actor_id: str,
                    action: str, target_id: str = "", detail: str = ""):
    try:
        await conn.execute("""
            INSERT INTO audit_logs (actor_type, actor_id, action, target_id, detail)
            VALUES ($1,$2,$3,$4,$5)
        """, actor_type, str(actor_id), action, target_id, detail)
    except Exception as e:
        logger.error(f"审计日志写入失败: {e}")


async def log_audit(actor_type: str, actor_id: str, action: str,
                    target_id: str = "", detail: str = ""):
    """独立调用：无需传入 conn，用于 bot 等直接记录审计日志。"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await audit_log(conn, actor_type, actor_id, action, target_id, detail)


async def get_audit_logs(limit: int = 20) -> list:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM audit_logs ORDER BY logged_at DESC LIMIT $1", limit
        )
        return [dict(r) for r in rows]


# ── Security & UID-Case Binding ────────────────────────────────────────────────

async def get_active_case_by_uid(tg_user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT *
            FROM cases
            WHERE tg_user_id = $1
            ORDER BY created_at DESC
            LIMIT 1
            """,
            tg_user_id,
        )
        return dict(row) if row else None


async def verify_case_ownership(case_no: str, uid: int) -> bool:
    """Layer 2: check the case belongs to this uid."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT tg_user_id FROM cases WHERE case_no = $1 OR case_number = $1",
            case_no.upper()
        )
        if not row:
            return False
        stored = row["tg_user_id"]
        if stored is None:
            return True   # case exists but uid unrecorded → allow
        return int(stored) == int(uid)


async def log_security_event(uid: int, action: str, detail: str = "") -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO audit_logs (actor_type, actor_id, action, detail)
            VALUES ($1, $2, $3, $4)
            """,
            "user",
            str(uid),
            action,
            detail,
        )


async def set_case_owner_if_unbound(case_no: str, uid: int) -> bool:
    """
    Bind a case to a Telegram user if it is not yet bound.

    Returns True if the case exists and was updated, False otherwise.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Only update when tg_user_id is NULL to avoid hijacking ownership.
        result = await conn.execute(
            """
            UPDATE cases
            SET tg_user_id = $1
            WHERE (case_no = $2 OR case_number = $2)
              AND (tg_user_id IS NULL)
            """,
            int(uid),
            case_no.upper(),
        )
        # result looks like "UPDATE <rowcount>"
        try:
            _, count_str = result.split()
            return int(count_str) > 0
        except Exception:
            return False


async def set_liaison(case_no: str, is_open: bool) -> bool:
    """Set is_liaison_open for a case. Returns True if case exists and was updated."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE cases
            SET is_liaison_open = $1
            WHERE case_no = $2 OR case_number = $2
            """,
            bool(is_open),
            case_no.upper(),
        )
        try:
            _, count_str = result.split()
            return int(count_str) > 0
        except Exception:
            return False


async def get_open_liaison_case(tg_user_id: int):
    """Return the case (dict) for this user that has liaison channel open, or None."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM cases
            WHERE tg_user_id = $1 AND is_liaison_open = TRUE
            ORDER BY updated_at DESC NULLS LAST, created_at DESC
            LIMIT 1
            """,
            int(tg_user_id),
        )
        return dict(row) if row else None

