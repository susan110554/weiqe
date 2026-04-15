"""
database.py — PostgreSQL 数据库初始化与操作模块
支持：asyncpg 异步连接池 + 审计日志 + 证据管理
"""

import asyncpg
import inspect
import json
import logging
import os
import re
from datetime import date, datetime
from decimal import Decimal

logger = logging.getLogger(__name__)

# ── 案件状态变更后钩子（异步，由 bot 注册；失败不影响状态已提交）──
_CASE_STATUS_CHANGE_HOOK = None


def register_case_status_change_hook(fn):
    """注册 async (case_no, old_status, new_status) -> None，在 update_case_status 成功后调用。"""
    global _CASE_STATUS_CHANGE_HOOK
    _CASE_STATUS_CHANGE_HOOK = fn


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
            min_size=1,  # 减少到 1 以避免 Windows 网络问题
            max_size=3,  # 减少到 3 以避免连接过多
            command_timeout=30,  # 添加命令超时
            server_settings={
                'application_name': 'weiquan_bot',
                'tcp_keepalives_idle': '600',
                'tcp_keepalives_interval': '30',
                'tcp_keepalives_count': '3'
            }
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

        # 办公室表 (Phase 2)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS offices (
                id       SERIAL PRIMARY KEY,
                name_en  TEXT NOT NULL,
                name_zh  TEXT
            );
        """)

        # 探员表 (Phase 2)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                id          SERIAL PRIMARY KEY,
                agent_code  TEXT UNIQUE NOT NULL,
                tg_user_id  BIGINT,
                office_id   INTEGER REFERENCES offices(id),
                is_active   BOOLEAN DEFAULT TRUE,
                created_at  TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        # 探员收件箱（未读与最近一条）
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_inbox (
                case_no          TEXT PRIMARY KEY,
                agent_code       TEXT NOT NULL,
                user_tg_id       BIGINT,
                unread_count     INTEGER NOT NULL DEFAULT 0,
                last_message     TEXT,
                last_from        TEXT,
                last_message_at  TIMESTAMPTZ DEFAULT NOW(),
                last_admin_id    TEXT,
                last_read_at     TIMESTAMPTZ
            );
        """)

        # 联络消息流水（管理员/用户/系统）
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS liaison_messages (
                id            BIGSERIAL PRIMARY KEY,
                case_no       TEXT NOT NULL,
                sender_type   TEXT NOT NULL,
                sender_id     TEXT,
                message_text  TEXT,
                coc_hash      TEXT,
                created_at    TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        # 用户表 (Phase 2) — 从 cases 聚合或同步
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                tg_user_id     BIGINT PRIMARY KEY,
                username       TEXT,
                status         TEXT DEFAULT 'active',
                suspended_until TIMESTAMPTZ,
                created_at     TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        # 用户暂停记录 (Phase 2)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_suspensions (
                id          BIGSERIAL PRIMARY KEY,
                tg_user_id  BIGINT NOT NULL,
                reason      TEXT,
                until       TIMESTAMPTZ,
                admin_id    TEXT,
                created_at  TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        # 用户 PIN 表 (重置 PIN 用)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_pins (
                tg_user_id  BIGINT PRIMARY KEY,
                pin_hash    TEXT NOT NULL,
                updated_at  TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        # 案件 PIN 表（与案件号绑定的 1 次性签名 PIN）
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS case_pins (
                case_no    TEXT PRIMARY KEY,
                pin_hash   TEXT NOT NULL,
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        # 案件数字签名表 (CERTIFY-TRANSMIT 后 HMAC 签名)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS case_signatures (
                id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                case_no      TEXT NOT NULL,
                tg_user_id   BIGINT NOT NULL,
                signed_at    TIMESTAMPTZ DEFAULT NOW(),
                signature_hex TEXT NOT NULL,
                ip_address  TEXT,
                auth_ref     TEXT,
                UNIQUE(case_no)
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
            FOR EACH ROW EXECUTE PROCEDURE update_updated_at();
        """)

        # ── Migration: reconcile existing DB schema with new code ──────
        # The existing DB uses different column names than our code expects.
        # We ADD the new column names as aliases where they don't exist yet.
        migrations = [
            # audit_logs: 确保表存在且 actor_type 等列存在（兼容旧表结构）
            """DO $$ BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='audit_logs') THEN
                    CREATE TABLE audit_logs (id BIGSERIAL PRIMARY KEY, logged_at TIMESTAMPTZ DEFAULT NOW(),
                        actor_type TEXT, actor_id TEXT, action TEXT NOT NULL, target_id TEXT, detail TEXT);
                END IF;
            END $$""",
            "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS actor_type TEXT",
            "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS actor_id TEXT",
            "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS target_id TEXT",
            "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS detail TEXT",
            # 旧库若 audit_logs.id 为 BIGINT 且无 DEFAULT，INSERT ... DEFAULT 会变成 NULL 触发 NOT NULL 错误
            # 注意：PostgreSQL 对 uuid 无 max() 聚合；若 id 为 uuid 则只补 gen_random_uuid() 默认，不走序列。
            """DO $$
            BEGIN
              IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'audit_logs'
                  AND column_name = 'id'
                  AND column_default IS NULL
                  AND data_type IN ('bigint', 'integer', 'smallint')
              ) THEN
                CREATE SEQUENCE IF NOT EXISTS audit_logs_id_seq AS BIGINT;
                PERFORM setval(
                  'audit_logs_id_seq',
                  COALESCE((SELECT MAX(id) FROM audit_logs), 0),
                  true
                );
                ALTER TABLE audit_logs ALTER COLUMN id SET DEFAULT nextval('audit_logs_id_seq');
                ALTER SEQUENCE audit_logs_id_seq OWNED BY audit_logs.id;
              ELSIF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'audit_logs'
                  AND column_name = 'id'
                  AND column_default IS NULL
                  AND data_type = 'uuid'
              ) THEN
                ALTER TABLE audit_logs ALTER COLUMN id SET DEFAULT gen_random_uuid();
              END IF;
            END $$""",
            # case_signatures: 确保表存在且结构完整
            "CREATE TABLE IF NOT EXISTS case_signatures (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), case_no TEXT NOT NULL, tg_user_id BIGINT NOT NULL, signed_at TIMESTAMPTZ DEFAULT NOW(), signature_hex TEXT NOT NULL, ip_address TEXT, auth_ref TEXT)",
            "ALTER TABLE case_signatures ADD COLUMN IF NOT EXISTS signature_hex TEXT DEFAULT ''",
            "ALTER TABLE case_signatures ADD COLUMN IF NOT EXISTS signature TEXT",
            "ALTER TABLE case_signatures ADD COLUMN IF NOT EXISTS ip_address TEXT",
            "ALTER TABLE case_signatures ADD COLUMN IF NOT EXISTS auth_ref TEXT",
            # case_signatures: ON CONFLICT 需要 UNIQUE 约束
            "CREATE UNIQUE INDEX IF NOT EXISTS case_signatures_case_no_key ON case_signatures(case_no)",
            # 旧表可能有 signature NOT NULL，改为可空（若列存在）
            """DO $$ BEGIN
                IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='case_signatures' AND column_name='signature') THEN
                    ALTER TABLE case_signatures ALTER COLUMN signature DROP NOT NULL;
                END IF;
            END $$""",
            # Core columns our code uses — may not exist in old schema
            "ALTER TABLE cases ADD COLUMN IF NOT EXISTS case_no TEXT",
            "ALTER TABLE cases ADD COLUMN IF NOT EXISTS case_number TEXT",
            "ALTER TABLE cases ADD COLUMN IF NOT EXISTS user_id BIGINT",
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
            "ALTER TABLE cases ADD COLUMN IF NOT EXISTS agent_code TEXT",
            # 查询优化：案件号、用户、时间排序常用索引
            "CREATE INDEX IF NOT EXISTS idx_cases_case_no ON cases(case_no)",
            "CREATE INDEX IF NOT EXISTS idx_cases_case_number ON cases(case_number)",
            "CREATE INDEX IF NOT EXISTS idx_cases_tg_user_id ON cases(tg_user_id)",
            "CREATE INDEX IF NOT EXISTS idx_cases_created_at ON cases(created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_case_signatures_case_no ON case_signatures(case_no)",
            "CREATE INDEX IF NOT EXISTS idx_case_signatures_signature_hex ON case_signatures(signature_hex)",
            "CREATE INDEX IF NOT EXISTS idx_agent_inbox_agent_code ON agent_inbox(agent_code)",
            "CREATE INDEX IF NOT EXISTS idx_agent_inbox_unread ON agent_inbox(unread_count DESC, last_message_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_liaison_messages_case_no ON liaison_messages(case_no, created_at DESC)",
            # 提交时完整 PDF 载荷（多笔交易、CRS 等），供长期下载还原
            "ALTER TABLE cases ADD COLUMN IF NOT EXISTS case_pdf_snapshot JSONB",
            # P9+ 阶段：TX / TronScan、P10–P12 费用等（JSON 合并写入）
            "ALTER TABLE cases ADD COLUMN IF NOT EXISTS case_cmp_overrides JSONB DEFAULT '{}'::jsonb",
            # P1–P8 自动化状态推进（美国联邦工作日调度）
            """
            CREATE TABLE IF NOT EXISTS case_progress_jobs (
                id BIGSERIAL PRIMARY KEY,
                case_no TEXT NOT NULL,
                kind TEXT NOT NULL,
                run_at TIMESTAMPTZ NOT NULL,
                meta JSONB DEFAULT '{}'::jsonb,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                processed_at TIMESTAMPTZ,
                cancelled BOOLEAN NOT NULL DEFAULT FALSE
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_case_progress_jobs_run ON case_progress_jobs (run_at) "
            "WHERE processed_at IS NULL AND NOT cancelled",
            # TRC20 USDT 承包商支付会话（P5 优先费 / P10–P12 等）
            """
            CREATE TABLE IF NOT EXISTS crypto_payment_sessions (
                id BIGSERIAL PRIMARY KEY,
                public_id TEXT UNIQUE NOT NULL,
                case_no TEXT NOT NULL,
                payment_kind TEXT NOT NULL,
                tg_user_id BIGINT NOT NULL,
                deposit_address TEXT NOT NULL,
                amount_expected NUMERIC(20,6) NOT NULL,
                amount_min NUMERIC(20,6) NOT NULL,
                amount_max NUMERIC(20,6) NOT NULL,
                status TEXT NOT NULL DEFAULT 'awaiting_transfer',
                tx_hash TEXT,
                confirmations INT NOT NULL DEFAULT 0,
                block_number BIGINT,
                portal_chat_id BIGINT,
                portal_message_id BIGINT,
                expires_at TIMESTAMPTZ NOT NULL,
                confirmed_at TIMESTAMPTZ,
                extra JSONB DEFAULT '{}'::jsonb,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_cryptopay_poll ON crypto_payment_sessions (status, expires_at)",
            "CREATE INDEX IF NOT EXISTS idx_cryptopay_public ON crypto_payment_sessions (public_id)",
            # user_settings table for User Center
            """CREATE TABLE IF NOT EXISTS user_settings (
                tg_user_id        BIGINT PRIMARY KEY,
                timezone          TEXT DEFAULT 'UTC',
                notification_email TEXT,
                notification_phone TEXT,
                updated_at        TIMESTAMPTZ DEFAULT NOW()
            )""",
            "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS notify_telegram BOOLEAN DEFAULT TRUE",
            "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS notify_email BOOLEAN DEFAULT TRUE",
            "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS quiet_hour_start SMALLINT",
            "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS quiet_hour_end SMALLINT",
            """
            CREATE TABLE IF NOT EXISTS notification_rules (
                id SERIAL PRIMARY KEY,
                event_key TEXT NOT NULL UNIQUE,
                channels TEXT NOT NULL DEFAULT 'telegram',
                template_key TEXT NOT NULL DEFAULT 'default',
                enabled BOOLEAN NOT NULL DEFAULT TRUE,
                max_retries INT NOT NULL DEFAULT 5,
                retry_base_sec INT NOT NULL DEFAULT 60
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS notification_outbox (
                id BIGSERIAL PRIMARY KEY,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                event_key TEXT NOT NULL,
                case_no TEXT,
                target_tg_id BIGINT,
                target_email TEXT,
                channel TEXT NOT NULL,
                subject TEXT,
                body_html TEXT,
                body_text TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                attempts INT NOT NULL DEFAULT 0,
                next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                last_error TEXT,
                meta JSONB DEFAULT '{}'::jsonb
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_notification_outbox_due ON notification_outbox (next_attempt_at) WHERE status = 'pending'",
            """
            CREATE TABLE IF NOT EXISTS payment_reconciliation_log (
                id BIGSERIAL PRIMARY KEY,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                public_id TEXT,
                case_no TEXT NOT NULL,
                event_type TEXT NOT NULL,
                detail JSONB DEFAULT '{}'::jsonb
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_payrecon_case ON payment_reconciliation_log (case_no, created_at DESC)",
            """
            CREATE TABLE IF NOT EXISTS ops_review_queue (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                case_no TEXT NOT NULL,
                queue_kind TEXT NOT NULL,
                title TEXT NOT NULL,
                detail TEXT,
                status TEXT NOT NULL DEFAULT 'open',
                assigned_to TEXT,
                meta JSONB DEFAULT '{}'::jsonb
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_opsq_open ON ops_review_queue (status, created_at DESC)",
            """
            CREATE TABLE IF NOT EXISTS sla_tickets (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                case_no TEXT NOT NULL,
                ref_type TEXT NOT NULL,
                ref_id TEXT NOT NULL,
                deadline_at TIMESTAMPTZ NOT NULL,
                breach_notified_user BOOLEAN NOT NULL DEFAULT FALSE,
                breach_notified_admin BOOLEAN NOT NULL DEFAULT FALSE,
                resolved BOOLEAN NOT NULL DEFAULT FALSE
            )
            """,
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_sla_ref ON sla_tickets (ref_type, ref_id)",
            "CREATE INDEX IF NOT EXISTS idx_sla_due ON sla_tickets (deadline_at) WHERE NOT resolved",
            """
            CREATE TABLE IF NOT EXISTS case_progress_dlq (
                id BIGSERIAL PRIMARY KEY,
                original_job_id BIGINT NOT NULL,
                case_no TEXT NOT NULL,
                kind TEXT NOT NULL,
                run_at_orig TIMESTAMPTZ,
                meta JSONB DEFAULT '{}'::jsonb,
                error_text TEXT,
                failure_count INT NOT NULL DEFAULT 0,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                resolved BOOLEAN NOT NULL DEFAULT FALSE,
                resolved_note TEXT
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_cpdlq_unresolved ON case_progress_dlq (created_at DESC) WHERE NOT resolved",
            """
            CREATE TABLE IF NOT EXISTS adri_public_display_counter (
                singleton SMALLINT PRIMARY KEY DEFAULT 1 CHECK (singleton = 1),
                bump_total BIGINT NOT NULL DEFAULT 0
            )
            """,
            """
            INSERT INTO adri_public_display_counter (singleton, bump_total)
            VALUES (1, 0)
            ON CONFLICT (singleton) DO NOTHING
            """,
            # ── Scheduled broadcast jobs ──────────────────────────────────
            """
            CREATE TABLE IF NOT EXISTS scheduled_broadcasts (
                id             BIGSERIAL PRIMARY KEY,
                created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                created_by     TEXT NOT NULL,
                scheduled_at   TIMESTAMPTZ NOT NULL,
                executed_at    TIMESTAMPTZ,
                cancelled      BOOLEAN NOT NULL DEFAULT FALSE,
                cancelled_by   TEXT,
                target_kind    TEXT NOT NULL DEFAULT 'all',
                target_case_no TEXT,
                target_phase   INT,
                template_kind  TEXT NOT NULL DEFAULT 'custom',
                custom_body    TEXT,
                sent_count     INT NOT NULL DEFAULT 0,
                error_count    INT NOT NULL DEFAULT 0
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_sched_bc_due ON scheduled_broadcasts (scheduled_at) WHERE executed_at IS NULL AND NOT cancelled",
            # ── Blacklist ──────────────────────────────────────────────────
            """
            CREATE TABLE IF NOT EXISTS blacklist (
                id           BIGSERIAL PRIMARY KEY,
                tg_user_id   BIGINT NOT NULL,
                reason       TEXT,
                banned_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                banned_by    TEXT NOT NULL,
                unbanned_at  TIMESTAMPTZ,
                unbanned_by  TEXT,
                is_active    BOOLEAN NOT NULL DEFAULT TRUE,
                notes        TEXT
            )
            """,
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_blacklist_active ON blacklist (tg_user_id) WHERE is_active",
            "CREATE INDEX IF NOT EXISTS idx_blacklist_uid ON blacklist (tg_user_id, banned_at DESC)",
            # ── Global fee config ──────────────────────────────────────────
            """
            CREATE TABLE IF NOT EXISTS fee_config (
                key        TEXT PRIMARY KEY,
                amount     NUMERIC(12,2) NOT NULL,
                currency   TEXT NOT NULL DEFAULT 'USD',
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_by TEXT NOT NULL DEFAULT 'system'
            )
            """,
            """
            INSERT INTO fee_config (key, amount, currency, updated_by) VALUES
                ('p5_fee', 50.00, 'USD', 'system'),
                ('p9_fee_default', 0.00, 'USD', 'system')
            ON CONFLICT (key) DO NOTHING
            """,
            # ── Push delivery tracking (Telegram auto-push + manual push) ──
            """
            CREATE TABLE IF NOT EXISTS push_log (
                id                   BIGSERIAL PRIMARY KEY,
                created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                case_no              TEXT NOT NULL,
                tg_user_id           BIGINT NOT NULL,
                phase                INT,
                event_kind           TEXT NOT NULL,
                tg_message_id        BIGINT,
                delivered_at         TIMESTAMPTZ,
                first_interaction_at TIMESTAMPTZ,
                nudge_sent_at        TIMESTAMPTZ,
                retry_count          INT NOT NULL DEFAULT 0,
                last_error           TEXT
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_push_log_user ON push_log (tg_user_id, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_push_log_case ON push_log (case_no, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_push_log_nudge ON push_log (delivered_at, first_interaction_at, nudge_sent_at) WHERE delivered_at IS NOT NULL AND first_interaction_at IS NULL AND nudge_sent_at IS NULL",
            """
            CREATE TABLE IF NOT EXISTS user_activity_logs (
                id BIGSERIAL PRIMARY KEY,
                logged_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                tg_user_id BIGINT NOT NULL,
                case_no TEXT,
                action TEXT NOT NULL,
                detail TEXT
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_user_activity_tg ON user_activity_logs (tg_user_id, logged_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_user_activity_case ON user_activity_logs (case_no, logged_at DESC)",
        ]
        for sql in migrations:
            try:
                await conn.execute(sql)
            except Exception as e:
                logger.warning(f"Migration skipped: {e}")

        try:
            await conn.execute(
                """
                INSERT INTO notification_rules (event_key, channels, template_key, enabled, max_retries, retry_base_sec)
                VALUES
                    ('admin_payment_alert', 'telegram', 'default', true, 5, 60),
                    ('admin_sla_breach', 'telegram', 'default', true, 5, 60),
                    ('user_sla_reminder', 'telegram', 'default', true, 3, 120),
                    ('email_case_update', 'email', 'default', true, 5, 120)
                ON CONFLICT (event_key) DO NOTHING
                """
            )
        except Exception as e:
            logger.warning("seed notification_rules: %s", e)

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

        # 预置办公室数据（仅当表为空时）
        try:
            cnt = int(await conn.fetchval("SELECT COUNT(*) FROM offices") or 0)
            if cnt == 0:
                await conn.execute("""
                    INSERT INTO offices (name_en, name_zh) VALUES
                    ('Miami Field Office', '迈阿密地区办公室'),
                    ('New York Field Office', '纽约地区办公室'),
                    ('Los Angeles Field Office', '洛杉矶地区办公室'),
                    ('Chicago Field Office', '芝加哥地区办公室'),
                    ('Atlanta Field Office', '亚特兰大地区办公室')
                """)
        except Exception as e:
            logger.warning("Could not seed offices: %s", e)

        logger.info("✅ Database initialized and migrations applied")


# ── 案件操作 ───────────────────────────────────────────
def _is_duplicate_or_constraint(err: Exception) -> bool:
    """是否重复键或约束类错误（用于 create_case 复用已有案件）。"""
    s = str(err).lower()
    return any(x in s for x in ("unique", "duplicate", "唯一", "重复键"))


def _is_column_or_null_case_number(err: Exception) -> bool:
    """是否缺列或 case_number 为 null 导致错误（兼容旧表）。"""
    s = str(err).lower()
    return "column" in s or ("null" in s and "case_number" in s)


async def _existing_case_no(conn, case_no_val: str) -> str | None:
    """若案件已存在（case_no 或 case_number 匹配）则返回案号，否则 None。"""
    row = await conn.fetchrow(
        "SELECT case_no FROM cases WHERE case_no = $1",
        case_no_val,
    )
    if row:
        return row["case_no"] or case_no_val
    row = await conn.fetchrow(
        "SELECT case_no FROM cases WHERE case_number = $1",
        case_no_val,
    )
    if row:
        return row["case_no"] or case_no_val
    return None


def _json_safe_for_storage(obj):
    """将 PDF 快照转为可 JSON 序列化结构（写入 JSONB）。"""
    if obj is None:
        return None
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, (int, float, str)):
        return obj
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {str(k): _json_safe_for_storage(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe_for_storage(x) for x in obj]
    if isinstance(obj, (bytes, bytearray)):
        return obj.decode("utf-8", errors="replace")
    return str(obj)


async def _write_case_pdf_snapshot(conn, case_no_val: str, snapshot: dict) -> None:
    """将完整 PDF 载荷写入 cases.case_pdf_snapshot。"""
    if not snapshot:
        return
    safe = _json_safe_for_storage(snapshot)
    blob = json.dumps(safe, ensure_ascii=False)
    try:
        await conn.execute(
            "UPDATE cases SET case_pdf_snapshot = $1::jsonb WHERE case_no = $2 OR case_number = $2",
            blob,
            case_no_val,
        )
    except Exception:
        await conn.execute(
            "UPDATE cases SET case_pdf_snapshot = $1::jsonb WHERE case_no = $2",
            blob,
            case_no_val,
        )


def _legacy_pdf_data_from_case_row(c: dict) -> dict:
    """无 case_pdf_snapshot 的旧行：与 bot 端 DB 回退 PDF 结构一致。"""
    created_at = c.get("created_at")
    updated_at = c.get("updated_at") or created_at
    created_str = created_at.strftime("%Y-%m-%d %H:%M") if created_at else "N/A"
    last_updated_str = (
        updated_at.strftime("%Y-%m-%d %H:%M UTC") if updated_at else "N/A"
    )
    amt = c.get("amount")
    if amt is not None and not isinstance(amt, str):
        try:
            amt = str(amt)
        except Exception:
            amt = "—"
    else:
        amt = amt or "—"
    is_bank = (c.get("wallet_addr") == "Bank / Wire")
    return {
        "case_no": c.get("case_no") or c.get("case_number"),
        "registered": created_str,
        "uid": str(c.get("tg_user_id") or c.get("user_id") or ""),
        "status": c.get("status", "SUBMITTED"),
        "last_updated": last_updated_str,
        "fullname": "Not on file",
        "address": "—",
        "phone": "—",
        "email": c.get("contact", "—"),
        "amount": amt,
        "coin": c.get("coin"),
        "incident_time": c.get("incident_time"),
        "tx_hash": c.get("tx_hash"),
        "victim_wallet": "—",
        "wallet_addr": c.get("wallet_addr"),
        "chain_type": c.get("chain_type"),
        "platform": c.get("platform"),
        "scammer_id": "—",
        "evidence_files": [],
        "transaction_type": "bank" if is_bank else "crypto",
        "vic_bank": "—",
        "vic_acct": "—",
        "sub_name": "—",
        "sub_bank": "—",
        "sub_acct": "—",
    }


def pdf_data_from_case_row(c: dict, evidence_files: list | None = None) -> dict:
    """
    从数据库行组装 generate_case_pdf 所需 dict。
    优先使用 case_pdf_snapshot；否则走旧列拼接。
    始终用当前 status / last_updated / evidence_files 覆盖（与案件进展同步）。
    """
    snap = c.get("case_pdf_snapshot")
    if isinstance(snap, str):
        try:
            snap = json.loads(snap)
        except json.JSONDecodeError:
            snap = None
    if isinstance(snap, dict) and snap:
        out = dict(snap)
    else:
        out = _legacy_pdf_data_from_case_row(c)
    if c.get("status"):
        out["status"] = c["status"]
    if evidence_files is not None:
        out["evidence_files"] = evidence_files
    created_at = c.get("created_at")
    updated_at = c.get("updated_at") or created_at
    if created_at and hasattr(created_at, "strftime"):
        out.setdefault("registered", created_at.strftime("%Y-%m-%d %H:%M"))
    if updated_at and hasattr(updated_at, "strftime"):
        out["last_updated"] = updated_at.strftime("%Y-%m-%d %H:%M UTC")
    return out


async def create_case(data: dict) -> str:
    """Insert case record. 重复键时复用已有案件；兼容 case_number/user_id 旧表。"""
    pool = await get_pool()
    raw_amount = data.get('amount', '0') or '0'
    s = str(raw_amount).strip()
    m = re.search(r"([\d,.]+)", s)
    if m:
        try:
            amount_val = float(m.group(1).replace(",", ""))
        except (ValueError, TypeError):
            amount_val = None
            logger.warning("Could not parse amount %r, storing NULL", raw_amount)
    else:
        amount_val = None
        logger.warning("Could not parse amount %r, storing NULL", raw_amount)

    case_no_val = str(data['case_no']).strip()
    tg_uid = int(data['tg_user_id'])
    vals = (
        case_no_val, tg_uid,
        data.get('tg_username') or 'Anonymous',
        data.get('platform') or 'Not specified',
        amount_val,
        data.get('coin') or '',
        data.get('incident_time') or 'Not specified',
        data.get('wallet_addr') or 'Unknown',
        data.get('chain_type') or 'Unknown',
        data.get('tx_hash') or 'None',
        data.get('contact') or 'Anonymous',
        "SUBMITTED",
    )

    async with pool.acquire() as conn:
        row = None
        try:
            row = await conn.fetchrow("""
                INSERT INTO cases (
                    case_no, tg_user_id, tg_username,
                    platform, amount, coin, incident_time,
                    wallet_addr, chain_type, tx_hash, contact, status
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                RETURNING id, case_no
            """, *vals)
        except Exception as e:
            if _is_duplicate_or_constraint(e):
                existing = await _existing_case_no(conn, case_no_val)
                if existing:
                    logger.info("[DB] create_case: case exists (retry), reusing case_no=%s", case_no_val)
                    return case_no_val
            if _is_column_or_null_case_number(e):
                try:
                    row = await conn.fetchrow("""
                        INSERT INTO cases (
                            case_number, case_no, user_id, tg_user_id, tg_username,
                            platform, amount, coin, incident_time,
                            wallet_addr, chain_type, tx_hash, contact, status
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                        RETURNING id, case_no
                    """,
                        case_no_val, case_no_val, tg_uid, tg_uid,
                        data.get('tg_username') or 'Anonymous',
                        data.get('platform') or 'Not specified',
                        amount_val, data.get('coin') or '',
                        data.get('incident_time') or 'Not specified',
                        data.get('wallet_addr') or 'Unknown',
                        data.get('chain_type') or 'Unknown',
                        data.get('tx_hash') or 'None',
                        data.get('contact') or 'Anonymous',
                        "SUBMITTED",
                    )
                except Exception as e2:
                    if _is_duplicate_or_constraint(e2):
                        existing = await _existing_case_no(conn, case_no_val)
                        if existing:
                            logger.info("[DB] create_case: case exists (retry), reusing case_no=%s", case_no_val)
                            return case_no_val
                    logger.error("[DB] create_case INSERT failed: %s", e2)
                    logger.error("[DB] data dump: %s", data)
                    raise
            else:
                logger.error("[DB] create_case INSERT failed: %s", e)
                logger.error("[DB] data dump: %s", data)
                raise

        await audit_log(
            conn, 'USER', str(data['tg_user_id']), 'CASE_CREATED',
            str(row['id']),
            f"case={data['case_no']} amount={amount_val} {data.get('coin','')} "
            f"platform={data.get('platform','')} uid={data['tg_user_id']}"
        )
        snap = data.get("case_pdf_snapshot")
        if snap is not None:
            try:
                await _write_case_pdf_snapshot(conn, case_no_val, snap)
            except Exception as e:
                logger.error("[DB] case_pdf_snapshot update failed: %s", e)
        logger.info("[DB] Case created: %s id=%s", row['case_no'], row['id'])
        try:
            await adri_public_display_bump(conn)
        except Exception as e:
            logger.warning("adri_public_display bump (new case): %s", e)
        return row['case_no']


async def adri_public_display_bump(conn) -> int:
    """
    仅增加「展示用」全局计数（不含 ADRI_DISPLAY_CASES_BASE）。
    与 cases 表真实条数无关；运营看真实数据请用 get_case_count()。
    """
    await conn.execute(
        """
        INSERT INTO adri_public_display_counter (singleton, bump_total)
        VALUES (1, 0)
        ON CONFLICT (singleton) DO NOTHING
        """
    )
    v = await conn.fetchval(
        """
        UPDATE adri_public_display_counter
        SET bump_total = bump_total + 1
        WHERE singleton = 1
        RETURNING bump_total
        """
    )
    return int(v or 0)


async def adri_public_display_bump_for_start() -> int:
    """用户发送 /start 时 +1，返回当前 bump_total。"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await adri_public_display_bump(conn)


async def adri_public_display_get_bump() -> int:
    """当前 bump 值（不含基数），用于 HOME 等不递增的场景。"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO adri_public_display_counter (singleton, bump_total)
            VALUES (1, 0)
            ON CONFLICT (singleton) DO NOTHING
            """
        )
        v = await conn.fetchval(
            "SELECT bump_total FROM adri_public_display_counter WHERE singleton = 1"
        )
        return int(v or 0)


async def get_user_email_from_cases(tg_user_id: int) -> str | None:
    """从用户最近提交的案件中获取 contact，若为邮箱格式则返回。"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT contact FROM cases WHERE tg_user_id = $1 ORDER BY created_at DESC LIMIT 1",
            int(tg_user_id),
        )
        if not row:
            return None
        c = (row.get("contact") or "").strip()
        if "@" in c and "." in c:
            return c
        return None


async def has_user_submitted_case(tg_user_id: int) -> bool:
    """用户是否曾提交过案件（用于判断是否首次申请）。"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT 1 FROM cases WHERE tg_user_id = $1 LIMIT 1",
            int(tg_user_id),
        )
        return row is not None


async def get_case_by_no(case_no: str) -> dict | None:
    """按案号查询案件，兼容 case_no / case_number 列。"""
    key = (case_no or "").strip()
    if not key:
        return None
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM cases WHERE case_no = $1 OR case_number = $1",
            key.upper(),
        )
        return dict(row) if row else None


async def merge_case_cmp_overrides(case_no: str, patch: dict) -> bool:
    """浅合并写入 cases.case_cmp_overrides（JSONB）。"""
    if not patch:
        return False
    key = (case_no or "").strip().upper()
    if not key:
        return False
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT case_cmp_overrides FROM cases WHERE case_no = $1 OR case_number = $1",
            key,
        )
        if not row:
            return False
        cur = row["case_cmp_overrides"] or {}
        if isinstance(cur, str):
            try:
                cur = json.loads(cur)
            except Exception:
                cur = {}
        if not isinstance(cur, dict):
            cur = {}
        cur = {**cur, **patch}
        blob = json.dumps(_json_safe_for_storage(cur), ensure_ascii=False)
        await conn.execute(
            "UPDATE cases SET case_cmp_overrides = $1::jsonb, updated_at = NOW() "
            "WHERE case_no = $2 OR case_number = $2",
            blob,
            key,
        )
        return True


async def update_case_status(
    case_no: str,
    new_status: str,
    admin_id: str,
    note: str = "",
    *,
    agent_code: str | None = None,
    agent_tg_id: int | None = None,
    agent_username: str | None = None,
) -> bool:
    key = (case_no or "").strip()
    if not key:
        return False
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, status FROM cases WHERE case_no = $1 OR case_number = $1",
            key,
        )
        if not row:
            return False
        old_status = row['status']
        case_id_val = row['id']
        if agent_code is not None:
            await conn.execute(
                "UPDATE cases SET status=$1, agent_code=$2, updated_at=NOW() WHERE id = $3",
                new_status, agent_code, case_id_val,
            )
        else:
            await conn.execute("UPDATE cases SET status=$1, updated_at=NOW() WHERE id = $2", new_status, case_id_val)
        await conn.execute("""
            INSERT INTO status_history (case_id, old_status, new_status, changed_by, note)
            VALUES ($1,$2,$3,$4,$5)
        """, case_id_val, old_status, new_status, admin_id, note)
        await audit_log(conn, 'ADMIN', admin_id, 'STATUS_UPDATED',
                        str(case_id_val), f"{old_status} → {new_status}")
        # 人工改状态：取消未执行的自动推进（系统账号 auto_progress 不取消）
        aid = (admin_id or "").strip()
        if aid and aid not in ("system", "auto_progress"):
            await conn.execute(
                """
                UPDATE case_progress_jobs
                SET cancelled = TRUE
                WHERE UPPER(TRIM(case_no)) = UPPER($1)
                  AND processed_at IS NULL AND NOT cancelled
                """,
                key,
            )
        hook = _CASE_STATUS_CHANGE_HOOK
        if hook is not None:
            try:
                res = hook(key, old_status, new_status)
                if inspect.isawaitable(res):
                    await res
            except Exception:
                logger.exception("case status change hook failed")
        return True


async def merge_case_pdf_snapshot(case_no: str, patch: dict) -> bool:
    """浅合并写入 cases.case_pdf_snapshot（JSONB），供 PDF / 前端共用字段。"""
    if not patch:
        return False
    key = (case_no or "").strip().upper()
    if not key:
        return False
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT case_pdf_snapshot FROM cases WHERE case_no = $1 OR case_number = $1",
            key,
        )
        if not row:
            return False
        cur = row["case_pdf_snapshot"] or {}
        if isinstance(cur, str):
            try:
                cur = json.loads(cur)
            except Exception:
                cur = {}
        if not isinstance(cur, dict):
            cur = {}
        cur = {**cur, **patch}
        blob = json.dumps(_json_safe_for_storage(cur), ensure_ascii=False)
        await conn.execute(
            "UPDATE cases SET case_pdf_snapshot = $1::jsonb, updated_at = NOW() "
            "WHERE case_no = $2 OR case_number = $2",
            blob,
            key,
        )
        return True


async def case_progress_enqueue(
    case_no: str, kind: str, run_at, meta: dict | None = None,
) -> int | None:
    """排队一条自动化状态任务。run_at 为 timezone-aware datetime。返回 job id 供 SLA 登记。"""
    cn = (case_no or "").strip().upper()
    if not cn or not kind:
        return None
    pool = await get_pool()
    blob = json.dumps(_json_safe_for_storage(meta or {}), ensure_ascii=False)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO case_progress_jobs (case_no, kind, run_at, meta)
            VALUES ($1, $2, $3, $4::jsonb)
            RETURNING id
            """,
            cn, kind, run_at, blob,
        )
        return int(row["id"]) if row else None


async def case_progress_fetch_due(limit: int = 40) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, case_no, kind, run_at, meta, created_at
            FROM case_progress_jobs
            WHERE run_at <= NOW() AND processed_at IS NULL AND NOT cancelled
            ORDER BY run_at ASC, id ASC
            LIMIT $1
            """,
            int(limit),
        )
        return [dict(r) for r in rows]


async def case_progress_mark_processed(job_id: int) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE case_progress_jobs SET processed_at = NOW() WHERE id = $1",
            int(job_id),
        )


async def case_progress_jobs_pending_list(limit: int = 50) -> list[dict]:
    """未处理且未取消的自动推进任务（含未到时间与已到期），按 run_at 升序。"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, case_no, kind, run_at, meta, created_at
            FROM case_progress_jobs
            WHERE processed_at IS NULL AND NOT cancelled
            ORDER BY run_at ASC, id ASC
            LIMIT $1
            """,
            int(limit),
        )
        return [dict(r) for r in rows]


async def case_progress_pending_count() -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        v = await conn.fetchval(
            """
            SELECT COUNT(*)::int FROM case_progress_jobs
            WHERE processed_at IS NULL AND NOT cancelled
            """
        )
        return int(v or 0)


async def cryptopay_pending_sessions_count() -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        v = await conn.fetchval(
            """
            SELECT COUNT(*)::int FROM crypto_payment_sessions
            WHERE status NOT IN ('confirmed', 'cancelled', 'expired')
              AND expires_at > NOW()
            """
        )
        return int(v or 0)


async def case_progress_reschedule_or_dlq(
    job_id: int,
    case_no: str,
    kind: str,
    error_text: str,
    *,
    max_failures: int = 3,
    delay_minutes: int = 5,
) -> tuple[str, datetime | None]:
    """
    处理 process_job 异常：未超次则推迟 run_at 重试；否则写入死信并标记 job 已处理。
    返回 ("retry", new_run_at) | ("dlq", None) | ("noop", None)
    """
    from datetime import timedelta, timezone as tz

    cn = (case_no or "").strip().upper()
    k = (kind or "").strip()
    err = (error_text or "")[:2000]
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                SELECT id, processed_at, run_at, meta
                FROM case_progress_jobs
                WHERE id = $1
                FOR UPDATE
                """,
                int(job_id),
            )
            if not row:
                return ("noop", None)
            if row["processed_at"] is not None:
                return ("noop", None)
            meta = row["meta"] or {}
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    meta = {}
            if not isinstance(meta, dict):
                meta = {}
            fc = int(meta.get("process_failures") or 0) + 1
            meta["process_failures"] = fc
            meta["last_process_error"] = err
            blob = json.dumps(_json_safe_for_storage(meta), ensure_ascii=False)
            run_orig = row["run_at"]
            if fc >= int(max_failures):
                await conn.execute(
                    """
                    INSERT INTO case_progress_dlq (
                        original_job_id, case_no, kind, run_at_orig, meta, error_text, failure_count
                    ) VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7)
                    """,
                    int(job_id),
                    cn,
                    k,
                    run_orig,
                    blob,
                    err,
                    fc,
                )
                await conn.execute(
                    """
                    UPDATE case_progress_jobs
                    SET processed_at = NOW(), meta = $2::jsonb
                    WHERE id = $1
                    """,
                    int(job_id),
                    blob,
                )
            else:
                new_run = datetime.now(tz.utc) + timedelta(minutes=int(delay_minutes))
                await conn.execute(
                    """
                    UPDATE case_progress_jobs
                    SET run_at = $2, meta = $3::jsonb
                    WHERE id = $1
                    """,
                    int(job_id),
                    new_run,
                    blob,
                )
                return ("retry", new_run)

    rid = await ops_review_create(
        case_no=cn,
        queue_kind="auto_progress_dead",
        title=f"自动推进失败已达上限: {k}",
        detail=err,
        meta={"original_job_id": job_id, "kind": k},
    )
    if rid:
        logger.warning(
            "[case_progress] job %s case=%s kind=%s moved to DLQ review_id=%s",
            job_id,
            cn,
            k,
            rid,
        )
    return ("dlq", None)


async def case_progress_dlq_list_unresolved(limit: int = 20) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM case_progress_dlq
            WHERE NOT resolved
            ORDER BY created_at DESC
            LIMIT $1
            """,
            int(limit),
        )
        return [dict(r) for r in rows]


async def case_progress_dlq_mark_resolved(dlq_id: int, note: str) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        r = await conn.execute(
            """
            UPDATE case_progress_dlq SET resolved = TRUE, resolved_note = $2
            WHERE id = $1 AND NOT resolved
            """,
            int(dlq_id),
            (note or "")[:500],
        )
        return r != "UPDATE 0"


async def case_progress_cancel_pending(case_no: str) -> None:
    cn = (case_no or "").strip().upper()
    if not cn:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE case_progress_jobs
            SET cancelled = TRUE
            WHERE UPPER(TRIM(case_no)) = $1 AND processed_at IS NULL AND NOT cancelled
            """,
            cn,
        )


async def case_progress_cancel_kind(case_no: str, kind: str) -> None:
    cn = (case_no or "").strip().upper()
    k = (kind or "").strip()
    if not cn or not k:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE case_progress_jobs
            SET cancelled = TRUE
            WHERE UPPER(TRIM(case_no)) = $1 AND kind = $2
              AND processed_at IS NULL AND NOT cancelled
            """,
            cn, k,
        )


async def case_progress_has_pending(case_no: str, kind: str) -> bool:
    """是否存在未取消且未处理的指定 kind 排队任务。"""
    cn = (case_no or "").strip().upper()
    k = (kind or "").strip()
    if not cn or not k:
        return False
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT 1 FROM case_progress_jobs
            WHERE UPPER(TRIM(case_no)) = $1 AND kind = $2
              AND processed_at IS NULL AND NOT cancelled
            LIMIT 1
            """,
            cn,
            k,
        )
        return row is not None


async def case_progress_completed_count(case_no: str, kind: str) -> int:
    """已处理完成的该 kind 任务数量（用于 P4 提醒等是否补排队）。"""
    cn = (case_no or "").strip().upper()
    k = (kind or "").strip()
    if not cn or not k:
        return 0
    pool = await get_pool()
    async with pool.acquire() as conn:
        v = await conn.fetchval(
            """
            SELECT COUNT(*)::int FROM case_progress_jobs
            WHERE UPPER(TRIM(case_no)) = $1 AND kind = $2
              AND processed_at IS NOT NULL
            """,
            cn,
            k,
        )
        return int(v or 0)


async def cryptopay_cancel_active_for_case_kind(case_no: str, payment_kind: str) -> None:
    cn = (case_no or "").strip().upper()
    k = (payment_kind or "").strip()
    if not cn or not k:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE crypto_payment_sessions
            SET status = 'cancelled', updated_at = NOW()
            WHERE UPPER(TRIM(case_no)) = $1 AND payment_kind = $2
              AND status NOT IN ('confirmed', 'cancelled', 'expired')
            """,
            cn, k,
        )


async def cryptopay_create_session(
    *,
    public_id: str,
    case_no: str,
    payment_kind: str,
    tg_user_id: int,
    deposit_address: str,
    amount_expected: float,
    amount_min: float,
    amount_max: float,
    portal_chat_id: int,
    portal_message_id: int,
    expires_at,
    extra: dict | None = None,
) -> int | None:
    cn = (case_no or "").strip().upper()
    pool = await get_pool()
    blob = json.dumps(_json_safe_for_storage(extra or {}), ensure_ascii=False)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO crypto_payment_sessions (
                public_id, case_no, payment_kind, tg_user_id, deposit_address,
                amount_expected, amount_min, amount_max, status,
                portal_chat_id, portal_message_id, expires_at, extra
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,'awaiting_transfer',$9,$10,$11,$12::jsonb)
            RETURNING id
            """,
            public_id[:32],
            cn,
            payment_kind,
            int(tg_user_id),
            deposit_address.strip(),
            amount_expected,
            amount_min,
            amount_max,
            int(portal_chat_id),
            int(portal_message_id),
            expires_at,
            blob,
        )
        return int(row["id"]) if row else None


async def cryptopay_get_by_public_id(public_id: str) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM crypto_payment_sessions WHERE public_id = $1",
            (public_id or "").strip()[:32],
        )
        return dict(row) if row else None


async def cryptopay_list_pollable(limit: int = 80) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM crypto_payment_sessions
            WHERE status IN (
                'awaiting_transfer', 'detected', 'confirming',
                'amount_shortfall', 'wrong_token'
            )
              AND expires_at > NOW()
            ORDER BY id ASC
            LIMIT $1
            """,
            int(limit),
        )
        return [dict(r) for r in rows]


async def cryptopay_update_session(
    public_id: str,
    *,
    status: str | None = None,
    tx_hash: str | None = None,
    confirmations: int | None = None,
    block_number: int | None = None,
    confirmed_at=None,
    extra_patch: dict | None = None,
) -> bool:
    pid = (public_id or "").strip()[:32]
    if not pid:
        return False
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT extra FROM crypto_payment_sessions WHERE public_id = $1",
            pid,
        )
        if not row:
            return False
        ex = row["extra"] or {}
        if isinstance(ex, str):
            try:
                ex = json.loads(ex)
            except Exception:
                ex = {}
        if not isinstance(ex, dict):
            ex = {}
        if extra_patch:
            ex = {**ex, **extra_patch}
        blob = json.dumps(_json_safe_for_storage(ex), ensure_ascii=False)
        await conn.execute(
            """
            UPDATE crypto_payment_sessions SET
                status = COALESCE($2, status),
                tx_hash = COALESCE($3, tx_hash),
                confirmations = COALESCE($4, confirmations),
                block_number = COALESCE($5, block_number),
                confirmed_at = COALESCE($6, confirmed_at),
                extra = $7::jsonb,
                updated_at = NOW()
            WHERE public_id = $1
            """,
            pid,
            status,
            tx_hash,
            confirmations,
            block_number,
            confirmed_at,
            blob,
        )
        return True


async def cryptopay_expire_stale() -> list[str]:
    """将超时会话标为 expired，并返回刚被更新的 public_id（用于刷新支付门户消息）。"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            UPDATE crypto_payment_sessions
            SET status = 'expired', updated_at = NOW()
            WHERE expires_at <= NOW()
              AND status IN (
                'awaiting_transfer', 'detected', 'confirming',
                'amount_shortfall', 'wrong_token'
              )
            RETURNING public_id
            """
        )
        return [str(r["public_id"]) for r in rows]


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


async def get_cases_paginated(
    limit: int = 10,
    offset: int = 0,
    status_filter: str | None = None,
) -> list:
    """分页获取案件，可选按状态筛选。status_filter: 待审核/进行中/已关闭。"""
    pool = await get_pool()
    status_map = {
        "待审核": ("SUBMITTED", "VALIDATING", "Pending Initial Review", "待初步审核"),
        "进行中": ("UNDER REVIEW", "REFERRED"),
        "已关闭": ("CLOSED",),
    }
    async with pool.acquire() as conn:
        if status_filter and status_filter in status_map:
            vals = list(status_map[status_filter])
            rows = await conn.fetch(
                """
                SELECT *, COALESCE(case_no, case_number) AS display_case_no,
                       COALESCE(tg_user_id, user_id) AS display_user_id
                FROM cases
                WHERE status = ANY($1::text[])
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
                """,
                vals, limit, offset,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT *, COALESCE(case_no, case_number) AS display_case_no,
                       COALESCE(tg_user_id, user_id) AS display_user_id
                FROM cases
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2
                """,
                limit, offset,
            )
        return [dict(r) for r in rows]


async def get_case_count_by_status(status_filter: str | None = None) -> int:
    """按状态筛选的案件数量。"""
    pool = await get_pool()
    status_map = {
        "待审核": ("SUBMITTED", "VALIDATING", "Pending Initial Review", "待初步审核"),
        "进行中": ("UNDER REVIEW", "REFERRED"),
        "已关闭": ("CLOSED",),
    }
    async with pool.acquire() as conn:
        if status_filter and status_filter in status_map:
            vals = list(status_map[status_filter])
            return await conn.fetchval(
                "SELECT COUNT(*) FROM cases WHERE status = ANY($1::text[])",
                vals,
            )
        return await conn.fetchval("SELECT COUNT(*) FROM cases")


# ── 证据操作 ───────────────────────────────────────────
async def add_evidence(case_no: str, file_type: str, file_id: str,
                       file_name: str, description: str = "") -> bool:
    key = (case_no or "").strip()
    if not key:
        return False
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM cases WHERE case_no = $1 OR case_number = $1",
            key,
        )
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
    key = (case_no or "").strip()
    if not key:
        return []
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT e.* FROM evidences e
            JOIN cases c ON c.id = e.case_id
            WHERE c.case_no = $1 OR c.case_number = $1
            ORDER BY e.uploaded_at DESC
        """, key)
        return [dict(r) for r in rows]


async def log_user_activity(
    tg_user_id: int,
    case_no: str | None,
    action: str,
    detail: str = "",
) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO user_activity_logs (tg_user_id, case_no, action, detail)
            VALUES ($1, $2, $3, $4)
            """,
            int(tg_user_id),
            ((case_no or "").strip() or None),
            (action or "")[:200],
            (detail or "")[:4000],
        )


async def list_user_activity_peer_uids(limit: int = 25) -> list:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT tg_user_id, MAX(logged_at) AS last_at
            FROM user_activity_logs
            GROUP BY tg_user_id
            ORDER BY last_at DESC
            LIMIT $1
            """,
            limit,
        )
        return [dict(r) for r in rows]


async def get_user_activity_for_uid(tg_user_id: int, limit: int = 80) -> list:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT logged_at, case_no, action, detail
            FROM user_activity_logs
            WHERE tg_user_id = $1
            ORDER BY logged_at DESC
            LIMIT $2
            """,
            int(tg_user_id),
            limit,
        )
        return [dict(r) for r in rows]


async def list_case_nos_with_evidence_counts(limit: int = 20) -> list:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT c.case_no AS case_no, COUNT(e.id)::int AS n
            FROM evidences e
            JOIN cases c ON c.id = e.case_id
            WHERE c.case_no IS NOT NULL AND TRIM(c.case_no) <> ''
            GROUP BY c.case_no
            ORDER BY MAX(e.uploaded_at) DESC
            LIMIT $1
            """,
            limit,
        )
        return [dict(r) for r in rows]


# ── 审计日志 ───────────────────────────────────────────
async def audit_log(conn, actor_type: str, actor_id: str,
                    action: str, target_id: str = "", detail: str = ""):
    try:
        await conn.execute("""
            INSERT INTO audit_logs (actor_type, actor_id, action, target_id, detail)
            VALUES ($1, $2, $3, $4, $5)
        """, actor_type, str(actor_id), action, target_id, detail)
    except Exception as e:
        logger.error(f"审计日志写入失败: {e}")


async def get_cases_by_user_id(tg_user_id: int) -> list:
    """Return all cases for a given Telegram user, newest first."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT case_no, status, risk_score, risk_label, created_at, updated_at,
                   platform, amount, coin
            FROM cases
            WHERE COALESCE(tg_user_id, user_id) = $1
            ORDER BY created_at DESC
            """,
            int(tg_user_id),
        )
        return [dict(r) for r in rows]


async def get_audit_logs(limit: int = 20) -> list:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM audit_logs ORDER BY logged_at DESC LIMIT $1", limit
        )
        return [dict(r) for r in rows]


async def log_audit(
    actor_type: str,
    actor_id: str,
    action: str,
    target_id: str = "",
    detail: str = "",
) -> None:
    """Standalone module-level audit log helper (acquires own connection)."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await audit_log(conn, actor_type, actor_id, action, target_id, detail)
    except Exception as e:
        logger.error(f"log_audit failed: {e}")


# ── 用户管理 (Phase 2) ─────────────────────────────────────────
async def sync_users_from_cases():
    """从 cases 表同步用户到 users 表。"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            await conn.execute("""
                INSERT INTO users (tg_user_id, username, status)
                SELECT DISTINCT COALESCE(c.tg_user_id, c.user_id),
                       COALESCE(c.tg_username, ''),
                       'active'
                FROM cases c
                WHERE COALESCE(c.tg_user_id, c.user_id) IS NOT NULL
                ON CONFLICT (tg_user_id) DO UPDATE SET
                    username = COALESCE(EXCLUDED.username, users.username)
            """)
        except Exception as e:
            logger.warning("sync_users_from_cases: %s", e)


async def get_users_paginated(
    limit: int = 10,
    offset: int = 0,
    status_filter: str | None = None,
) -> list:
    """分页获取用户。status_filter: active / suspended。"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        if status_filter == "suspended":
            rows = await conn.fetch(
                """
                SELECT * FROM users
                WHERE status = 'suspended' OR suspended_until > NOW()
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2
                """,
                limit, offset,
            )
        elif status_filter == "active":
            rows = await conn.fetch(
                """
                SELECT * FROM users
                WHERE (status IS NULL OR status = 'active')
                AND (suspended_until IS NULL OR suspended_until <= NOW())
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2
                """,
                limit, offset,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT * FROM users
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2
                """,
                limit, offset,
            )
        return [dict(r) for r in rows]


async def get_user_count(status_filter: str | None = None) -> int:
    """用户数量。"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        if status_filter == "suspended":
            return await conn.fetchval(
                "SELECT COUNT(*) FROM users WHERE status = 'suspended' OR suspended_until > NOW()"
            )
        if status_filter == "active":
            return await conn.fetchval(
                """
                SELECT COUNT(*) FROM users
                WHERE (status IS NULL OR status = 'active')
                AND (suspended_until IS NULL OR suspended_until <= NOW())
                """
            )
        return await conn.fetchval("SELECT COUNT(*) FROM users")


async def get_user_by_tg_id(tg_user_id: int) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE tg_user_id = $1", int(tg_user_id))
        return dict(row) if row else None


async def get_user_from_cases(tg_user_id: int) -> dict | None:
    """从 cases 聚合用户信息（当 users 表无记录时）。"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT tg_user_id, tg_username
            FROM (SELECT DISTINCT COALESCE(tg_user_id, user_id) AS tg_user_id,
                         MAX(tg_username) AS tg_username
                  FROM cases
                  WHERE COALESCE(tg_user_id, user_id) = $1
                  GROUP BY COALESCE(tg_user_id, user_id)) sub
            """,
            int(tg_user_id),
        )
        return dict(row) if row else None


async def suspend_user(
    tg_user_id: int,
    reason: str,
    until_ts,
    admin_id: str,
) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        username = await conn.fetchval(
            "SELECT tg_username FROM cases WHERE tg_user_id = $1 LIMIT 1",
            int(tg_user_id),
        )
        await conn.execute(
            """
            INSERT INTO users (tg_user_id, username, status, suspended_until)
            VALUES ($1, $2, 'suspended', $3)
            ON CONFLICT (tg_user_id) DO UPDATE SET
                status = 'suspended',
                suspended_until = $3
            """,
            int(tg_user_id), username or "", until_ts,
        )
        await conn.execute(
            """
            INSERT INTO user_suspensions (tg_user_id, reason, until, admin_id)
            VALUES ($1, $2, $3, $4)
            """,
            int(tg_user_id), reason, until_ts, admin_id,
        )
        await audit_log(conn, "ADMIN", admin_id, "USER_SUSPENDED", str(tg_user_id), reason)
        return True


async def resume_user(tg_user_id: int, admin_id: str) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        username = await conn.fetchval(
            "SELECT tg_username FROM cases WHERE tg_user_id = $1 LIMIT 1",
            int(tg_user_id),
        )
        await conn.execute(
            """
            INSERT INTO users (tg_user_id, username, status, suspended_until)
            VALUES ($1, $2, 'active', NULL)
            ON CONFLICT (tg_user_id) DO UPDATE SET
                status = 'active',
                suspended_until = NULL
            """,
            int(tg_user_id), username or "",
        )
        await audit_log(conn, "ADMIN", admin_id, "USER_RESUMED", str(tg_user_id), "")
        return True


async def save_case_signature(
    case_no: str,
    tg_user_id: int,
    signature_hex: str,
    ip_address: str | None = None,
    auth_ref: str | None = None,
    doc_hash: str | None = None,
) -> bool:
    """Store digital signature for a case (after HMAC-SHA256). 兼容有无 signature/doc_hash 列及 ON CONFLICT。"""
    pool = await get_pool()
    sig_val = (signature_hex or "").strip() or ""
    uid = int(tg_user_id)
    ip = ip_address or ""
    ref = auth_ref or ""
    doc_val = (doc_hash or "").strip() or sig_val  # 若表有 doc_hash NOT NULL，用 signature_hex 兜底

    async with pool.acquire() as conn:
        try:
            await conn.execute(
                """
                INSERT INTO case_signatures (case_no, tg_user_id, signature_hex, signature, ip_address, auth_ref, doc_hash)
                VALUES ($1, $2, $3, $3, $4, $5, $6)
                ON CONFLICT (case_no) DO UPDATE SET
                    tg_user_id = EXCLUDED.tg_user_id,
                    signed_at = NOW(),
                    signature_hex = EXCLUDED.signature_hex,
                    signature = EXCLUDED.signature,
                    ip_address = EXCLUDED.ip_address,
                    auth_ref = EXCLUDED.auth_ref,
                    doc_hash = EXCLUDED.doc_hash
                """,
                case_no, uid, sig_val, ip, ref, doc_val,
            )
            return True
        except Exception as e:
            err_s = str(e).lower()
            # 表无 doc_hash 列时重试不含 doc_hash 的 INSERT
            if "doc_hash" in err_s:
                try:
                    await conn.execute(
                        """
                        INSERT INTO case_signatures (case_no, tg_user_id, signature_hex, signature, ip_address, auth_ref)
                        VALUES ($1, $2, $3, $3, $4, $5)
                        ON CONFLICT (case_no) DO UPDATE SET
                            tg_user_id = EXCLUDED.tg_user_id,
                            signed_at = NOW(),
                            signature_hex = EXCLUDED.signature_hex,
                            signature = EXCLUDED.signature,
                            ip_address = EXCLUDED.ip_address,
                            auth_ref = EXCLUDED.auth_ref
                        """,
                        case_no, uid, sig_val, ip, ref,
                    )
                    return True
                except Exception as e_doc:
                    logger.error("save_case_signature (no doc_hash) failed: case_no=%r err=%s", case_no, e_doc)
                    raise
            # 无 UNIQUE/ON CONFLICT 或缺少 signature 列：先尝试 UPDATE 再 INSERT
            if "unique" not in err_s and "duplicate" not in err_s and "on conflict" not in err_s:
                if "column" in err_s or "signature" in err_s:
                    try:
                        await conn.execute(
                            """
                            INSERT INTO case_signatures (case_no, tg_user_id, signature_hex, ip_address, auth_ref)
                            VALUES ($1, $2, $3, $4, $5)
                            ON CONFLICT (case_no) DO UPDATE SET
                                tg_user_id = EXCLUDED.tg_user_id,
                                signed_at = NOW(),
                                signature_hex = EXCLUDED.signature_hex,
                                ip_address = EXCLUDED.ip_address,
                                auth_ref = EXCLUDED.auth_ref
                            """,
                            case_no, uid, sig_val, ip, ref,
                        )
                        return True
                    except Exception as e2:
                        logger.error("save_case_signature fallback failed: case_no=%r err=%s", case_no, e2)
                        raise
                logger.error("save_case_signature failed: case_no=%r err=%s", case_no, e)
                raise
            result = await conn.execute(
                """
                UPDATE case_signatures
                SET tg_user_id = $1, signed_at = NOW(), signature_hex = $2,
                    signature = $2, ip_address = $3, auth_ref = $4, doc_hash = $5
                WHERE case_no = $6
                """,
                uid, sig_val, ip, ref, doc_val, case_no,
            )
            updated = (result or "").strip().split()[-1] if result else "0"
            if updated.isdigit() and int(updated) == 0:
                try:
                    await conn.execute(
                        """
                        INSERT INTO case_signatures (case_no, tg_user_id, signature_hex, signature, ip_address, auth_ref, doc_hash)
                        VALUES ($1, $2, $3, $3, $4, $5, $6)
                        """,
                        case_no, uid, sig_val, ip, ref, doc_val,
                    )
                except Exception as e3:
                    err3 = str(e3).lower()
                    if "doc_hash" in err3:
                        try:
                            await conn.execute(
                                """
                                INSERT INTO case_signatures (case_no, tg_user_id, signature_hex, signature, ip_address, auth_ref)
                                VALUES ($1, $2, $3, $3, $4, $5)
                                """,
                                case_no, uid, sig_val, ip, ref,
                            )
                        except Exception as e4:
                            logger.error("save_case_signature INSERT (no doc_hash) failed: case_no=%r err=%s", case_no, e4)
                            raise
                    elif "column" in err3 or "signature" in err3:
                        await conn.execute(
                            """
                            INSERT INTO case_signatures (case_no, tg_user_id, signature_hex, ip_address, auth_ref)
                            VALUES ($1, $2, $3, $4, $5)
                            """,
                            case_no, uid, sig_val, ip, ref,
                        )
                    else:
                        logger.error("save_case_signature INSERT fallback failed: case_no=%r err=%s", case_no, e3)
                        raise
            return True


async def get_signature_by_hex(signature_hex: str) -> dict | None:
    """Look up signature by hex string (for Verify Signature). 兼容 signature / signature_hex 列。"""
    sig = (signature_hex or "").strip()
    if not sig:
        return None
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            row = await conn.fetchrow(
                """
                SELECT case_no, tg_user_id, signed_at,
                       COALESCE(signature_hex, signature) AS signature_hex,
                       auth_ref
                FROM case_signatures
                WHERE signature_hex = $1 OR signature = $1
                LIMIT 1
                """,
                sig,
            )
            return dict(row) if row else None
        except Exception:
            pass
        for col in ("signature_hex", "signature"):
            try:
                row = await conn.fetchrow(
                    f"SELECT case_no, tg_user_id, signed_at, {col} AS signature_hex, auth_ref "
                    f"FROM case_signatures WHERE {col} = $1 LIMIT 1",
                    sig,
                )
                if row:
                    return dict(row)
            except Exception:
                continue
        return None


async def get_signature_by_case_no(case_no: str) -> dict | None:
    """Return signature record for a case (for 'case already signed' check)."""
    key = (case_no or "").strip()
    if not key:
        return None
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT case_no, tg_user_id, signed_at, signature_hex, auth_ref FROM case_signatures WHERE case_no = $1",
            key,
        )
        return dict(row) if row else None


async def set_case_pin_hash(case_no: str, pin_hash: str) -> bool:
    """为案件设置 / 更新一次性 PIN（与 case_no 绑定）。"""
    key = (case_no or "").strip().upper()
    if not key:
        return False
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO case_pins (case_no, pin_hash)
            VALUES ($1, $2)
            ON CONFLICT (case_no) DO UPDATE SET
                pin_hash = $2,
                updated_at = NOW()
            """,
            key, pin_hash,
        )
        return True


async def get_case_pin_hash(case_no: str) -> str | None:
    """返回案件在 Privacy & Signature 中设置的 PIN 的 SHA-256 哈希（无明文）。"""
    key = (case_no or "").strip().upper()
    if not key:
        return None
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT pin_hash FROM case_pins WHERE UPPER(case_no) = $1",
            key,
        )
        return row["pin_hash"] if row else None


# ── 探员与办公室 (Phase 2) ─────────────────────────────────────
async def get_agents() -> list:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT a.*, o.name_en AS office_name_en, o.name_zh AS office_name_zh
            FROM agents a
            LEFT JOIN offices o ON a.office_id = o.id
            ORDER BY a.agent_code
            """
        )
        return [dict(r) for r in rows]


async def get_agents_from_cases() -> list:
    """从 cases 聚合探员（agents 表为空时备用）。"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT agent_code
            FROM cases
            WHERE agent_code IS NOT NULL AND agent_code != ''
            ORDER BY agent_code
            """
        )
        return [dict(r) for r in rows]


async def get_offices() -> list:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM offices ORDER BY id")
        return [dict(r) for r in rows]


async def upsert_agent(
    agent_code: str,
    tg_user_id: int | None = None,
    office_id: int | None = None,
    is_active: bool = True,
) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO agents (agent_code, tg_user_id, office_id, is_active)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (agent_code) DO UPDATE SET
                tg_user_id = COALESCE(EXCLUDED.tg_user_id, agents.tg_user_id),
                office_id = COALESCE(EXCLUDED.office_id, agents.office_id),
                is_active = EXCLUDED.is_active
            """,
            agent_code, tg_user_id, office_id, is_active,
        )
        return True


async def bump_agent_inbox(
    case_no: str,
    agent_code: str,
    user_tg_id: int | None,
    message_text: str,
    *,
    sender_type: str = "USER",
) -> bool:
    key = (case_no or "").strip()
    agent = (agent_code or "").strip()
    if not key or not agent:
        return False
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO agent_inbox (case_no, agent_code, user_tg_id, unread_count, last_message, last_from, last_message_at)
            VALUES ($1, $2, $3, 1, $4, $5, NOW())
            ON CONFLICT (case_no) DO UPDATE SET
                agent_code = EXCLUDED.agent_code,
                user_tg_id = COALESCE(EXCLUDED.user_tg_id, agent_inbox.user_tg_id),
                unread_count = CASE
                    WHEN $5 = 'USER' THEN agent_inbox.unread_count + 1
                    ELSE agent_inbox.unread_count
                END,
                last_message = EXCLUDED.last_message,
                last_from = EXCLUDED.last_from,
                last_message_at = NOW()
            """,
            key, agent, user_tg_id, (message_text or "")[:500], sender_type,
        )
        return True


async def mark_agent_inbox_read(case_no: str, admin_id: str) -> bool:
    key = (case_no or "").strip()
    if not key:
        return False
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE agent_inbox
            SET unread_count = 0, last_read_at = NOW(), last_admin_id = $2
            WHERE case_no = $1
            """,
            key, str(admin_id),
        )
        return True


async def get_agent_unread_counts() -> dict[str, int]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT agent_code, COALESCE(SUM(unread_count), 0) AS unread_total
            FROM agent_inbox
            GROUP BY agent_code
            """
        )
        return {r["agent_code"]: int(r["unread_total"] or 0) for r in rows}


async def get_cases_for_agent(agent_code: str, limit: int = 20) -> list:
    agent = (agent_code or "").strip()
    if not agent:
        return []
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                c.*,
                COALESCE(ai.unread_count, 0) AS unread_count,
                ai.last_message,
                ai.last_message_at
            FROM cases c
            LEFT JOIN agent_inbox ai ON ai.case_no = COALESCE(c.case_no, c.case_number)
            WHERE c.agent_code = $1
            ORDER BY COALESCE(ai.last_message_at, c.updated_at, c.created_at) DESC
            LIMIT $2
            """,
            agent, int(limit),
        )
        return [dict(r) for r in rows]


async def save_liaison_message(
    case_no: str,
    sender_type: str,
    sender_id: str | None,
    message_text: str,
    coc_hash: str | None = None,
) -> bool:
    key = (case_no or "").strip()
    if not key:
        return False
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO liaison_messages (case_no, sender_type, sender_id, message_text, coc_hash)
            VALUES ($1, $2, $3, $4, $5)
            """,
            key,
            (sender_type or "SYSTEM").upper(),
            str(sender_id) if sender_id is not None else None,
            (message_text or "")[:4000],
            coc_hash,
        )
        return True


async def get_liaison_messages(case_no: str, limit: int = 15) -> list:
    key = (case_no or "").strip()
    if not key:
        return []
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM liaison_messages
            WHERE case_no = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            key, int(limit),
        )
        return [dict(r) for r in rows]


async def get_recent_liaison_messages(limit: int = 30) -> list:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM liaison_messages ORDER BY created_at DESC LIMIT $1",
            int(limit),
        )
        return [dict(r) for r in rows]


async def set_liaison(case_no: str, is_open: bool) -> bool:
    """Open or close the secure liaison channel for a case."""
    key = (case_no or "").strip()
    if not key:
        return False
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE cases SET is_liaison_open = $1 WHERE case_no = $2 OR case_number = $2",
            bool(is_open), key.upper(),
        )
        try:
            _, count_str = result.split()
            return int(count_str) > 0
        except Exception:
            return False


async def close_all_liaison_for_tg_user(tg_user_id: int) -> int:
    """
    将该 Telegram 用户名下所有案件的联络通道标记为关闭。
    解决：同一用户多起案件曾分别开启联络时，只关一案仍会有另一案 is_liaison_open=TRUE，
    get_open_liaison_case 仍会收到用户消息的问题。
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE cases SET is_liaison_open = FALSE
            WHERE COALESCE(tg_user_id, user_id) = $1 AND is_liaison_open IS TRUE
            """,
            int(tg_user_id),
        )
        try:
            _, count_str = result.split()
            return int(count_str)
        except Exception:
            return 0


async def get_open_liaison_case(tg_user_id: int) -> dict | None:
    """Return the case dict for this user that has liaison channel open, or None."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM cases
            WHERE COALESCE(tg_user_id, user_id) = $1 AND is_liaison_open IS TRUE
            ORDER BY updated_at DESC NULLS LAST, created_at DESC
            LIMIT 1
            """,
            int(tg_user_id),
        )
        return dict(row) if row else None


async def liaison_channel_open_for_case(case_no: str) -> bool:
    """案号存在且 is_liaison_open 在数据库中为 TRUE（严格布尔，避免 NULL/歧义）。"""
    row = await get_case_by_no(case_no)
    return row is not None and row.get("is_liaison_open") is True


async def list_open_liaison_case_nos_for_user(tg_user_id: int) -> list[str]:
    """该用户名下当前 is_liaison_open 为真的案件案号列表（用于取消空闲定时任务）。"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT case_no, case_number FROM cases
            WHERE COALESCE(tg_user_id, user_id) = $1 AND is_liaison_open IS TRUE
            """,
            int(tg_user_id),
        )
    out: list[str] = []
    for r in rows:
        cn = (r["case_no"] or r["case_number"] or "").strip()
        if cn:
            out.append(cn)
    return out


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
    key = (case_no or "").strip()
    if not key:
        return False
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT tg_user_id FROM cases WHERE case_no = $1 OR case_number = $1",
            key.upper(),
        )
        if not row:
            return False
        stored = row["tg_user_id"]
        if stored is None:
            return True
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


# ── User Center helpers ────────────────────────────────

async def get_cases_by_tg_user(tg_user_id: int, limit: int = 10) -> list:
    """Return cases for a Telegram user, newest first."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT * FROM cases
               WHERE COALESCE(tg_user_id, user_id) = $1
               ORDER BY created_at DESC LIMIT $2""",
            int(tg_user_id), limit,
        )
    return [dict(r) for r in rows]


async def get_user_settings(tg_user_id: int) -> dict | None:
    """Return user_settings row or None."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM user_settings WHERE tg_user_id = $1",
            int(tg_user_id),
        )
    return dict(row) if row else None


async def save_user_settings(tg_user_id: int, **kwargs) -> None:
    """Upsert user settings. Accepts timezone=, notification_email=, notification_phone=, notify_telegram=, notify_email=, quiet_hour_start=, quiet_hour_end=."""
    allowed = {
        "timezone",
        "notification_email",
        "notification_phone",
        "notify_telegram",
        "notify_email",
        "quiet_hour_start",
        "quiet_hour_end",
    }
    data = {k: v for k, v in kwargs.items() if k in allowed}
    if not data:
        return
    pool = await get_pool()
    placeholders = ", ".join(f"${i + 2}" for i in range(len(data)))
    updates = ", ".join(f"{k} = ${i + 2}" for i, k in enumerate(data.keys()))
    cols = ", ".join(data.keys())
    values = list(data.values())
    async with pool.acquire() as conn:
        await conn.execute(
            f"""INSERT INTO user_settings (tg_user_id, {cols}, updated_at)
                VALUES ($1, {placeholders}, NOW())
                ON CONFLICT (tg_user_id) DO UPDATE SET {updates}, updated_at = NOW()""",
            int(tg_user_id), *values,
        )


async def get_status_history_for_case(case_no: str, limit: int = 20) -> list:
    """Return status change history for a case, oldest first."""
    key = (case_no or "").strip()
    if not key:
        return []
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT sh.* FROM status_history sh
               JOIN cases c ON c.id = sh.case_id
               WHERE c.case_no = $1 OR c.case_number = $1
               ORDER BY sh.changed_at ASC LIMIT $2""",
            key, limit,
        )
    return [dict(r) for r in rows]


async def get_user_pin_hash(tg_user_id: int) -> str | None:
    """Return the stored PIN hash for a user, or None if not set."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT pin_hash FROM user_pins WHERE tg_user_id = $1",
            int(tg_user_id),
        )
    return row["pin_hash"] if row else None


async def reset_user_pin(tg_user_id: int, admin_id: str) -> bool:
    """Delete (reset) a user's PIN hash. Returns True if a row was deleted."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM user_pins WHERE tg_user_id = $1",
            int(tg_user_id),
        )
        # asyncpg returns e.g. "DELETE 1" or "DELETE 0"
        deleted = int((result or "DELETE 0").split()[-1])
        if deleted > 0:
            await audit_log(conn, "ADMIN", str(admin_id), "PIN_RESET", str(tg_user_id), "PIN reset by admin")
            return True
        return False


# ── 运营闭环：通知中心 / 对账 / 人工队列 / SLA ─────────────────


async def notification_rule_get(event_key: str) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM notification_rules WHERE event_key = $1",
            (event_key or "").strip(),
        )
        return dict(row) if row else None


async def notification_rules_list_all() -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM notification_rules ORDER BY event_key ASC"
        )
        return [dict(r) for r in rows]


async def notification_outbox_enqueue(
    *,
    event_key: str,
    channel: str,
    body_html: str | None = None,
    body_text: str | None = None,
    target_tg_id: int | None = None,
    target_email: str | None = None,
    subject: str | None = None,
    case_no: str | None = None,
    meta: dict | None = None,
) -> int | None:
    ek = (event_key or "").strip()
    ch = (channel or "").strip().lower()
    if not ek or ch not in ("telegram", "email"):
        return None
    rule = await notification_rule_get(ek)
    if rule and not rule.get("enabled", True):
        return None
    pool = await get_pool()
    blob = json.dumps(_json_safe_for_storage(meta or {}), ensure_ascii=False)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO notification_outbox (
                event_key, case_no, target_tg_id, target_email, channel,
                subject, body_html, body_text, status, next_attempt_at, meta
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,'pending', NOW(), $9::jsonb)
            RETURNING id
            """,
            ek,
            (case_no or "").strip().upper() or None,
            int(target_tg_id) if target_tg_id is not None else None,
            (target_email or "").strip() or None,
            ch,
            subject,
            body_html,
            body_text,
            blob,
        )
        return int(row["id"]) if row else None


async def notification_outbox_fetch_due(limit: int = 25) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM notification_outbox
            WHERE status = 'pending' AND next_attempt_at <= NOW()
            ORDER BY id ASC
            LIMIT $1
            """,
            int(limit),
        )
        return [dict(r) for r in rows]


async def notification_outbox_mark_sent(outbox_id: int) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE notification_outbox SET status = 'sent', last_error = NULL WHERE id = $1",
            int(outbox_id),
        )


async def notification_outbox_bump_retry(
    outbox_id: int, err: str, next_at, max_retries: int
) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE notification_outbox SET
                attempts = attempts + 1,
                last_error = $2,
                next_attempt_at = $3,
                status = CASE WHEN attempts + 1 >= $4 THEN 'failed' ELSE 'pending' END
            WHERE id = $1
            """,
            int(outbox_id),
            (err or "")[:2000],
            next_at,
            int(max_retries),
        )


async def notification_outbox_mark_skipped(outbox_id: int, reason: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE notification_outbox SET status = 'skipped_quiet', last_error = $2
            WHERE id = $1
            """,
            int(outbox_id),
            (reason or "")[:500],
        )


async def notification_outbox_defer(outbox_id: int, next_attempt_at, reason: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE notification_outbox SET next_attempt_at = $2, last_error = $3
            WHERE id = $1 AND status = 'pending'
            """,
            int(outbox_id),
            next_attempt_at,
            (reason or "")[:200],
        )


async def payment_reconciliation_log(
    *,
    public_id: str | None,
    case_no: str,
    event_type: str,
    detail: dict | None = None,
) -> None:
    cn = (case_no or "").strip().upper()
    et = (event_type or "").strip()
    if not cn or not et:
        return
    pool = await get_pool()
    blob = json.dumps(_json_safe_for_storage(detail or {}), ensure_ascii=False)
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO payment_reconciliation_log (public_id, case_no, event_type, detail)
            VALUES ($1, $2, $3, $4::jsonb)
            """,
            (public_id or "").strip()[:64] or None,
            cn,
            et,
            blob,
        )


async def ops_review_create(
    *,
    case_no: str,
    queue_kind: str,
    title: str,
    detail: str | None = None,
    meta: dict | None = None,
) -> int | None:
    cn = (case_no or "").strip().upper()
    k = (queue_kind or "").strip()
    if not cn or not k:
        return None
    pool = await get_pool()
    blob = json.dumps(_json_safe_for_storage(meta or {}), ensure_ascii=False)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO ops_review_queue (case_no, queue_kind, title, detail, meta)
            VALUES ($1, $2, $3, $4, $5::jsonb)
            RETURNING id
            """,
            cn,
            k,
            (title or "")[:500],
            detail,
            blob,
        )
        return int(row["id"]) if row else None


async def ops_review_list(
    *,
    status: str = "open",
    queue_kind: str | None = None,
    limit: int = 15,
) -> list[dict]:
    pool = await get_pool()
    st = (status or "open").strip()
    async with pool.acquire() as conn:
        if queue_kind:
            rows = await conn.fetch(
                """
                SELECT * FROM ops_review_queue
                WHERE status = $1 AND queue_kind = $2
                ORDER BY created_at DESC
                LIMIT $3
                """,
                st,
                queue_kind.strip(),
                int(limit),
            )
        else:
            rows = await conn.fetch(
                """
                SELECT * FROM ops_review_queue
                WHERE status = $1
                ORDER BY created_at DESC
                LIMIT $2
                """,
                st,
                int(limit),
            )
        return [dict(r) for r in rows]


async def ops_review_resolve(review_id: int, admin_label: str) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        r = await conn.execute(
            """
            UPDATE ops_review_queue SET
                status = 'resolved',
                updated_at = NOW(),
                assigned_to = COALESCE(assigned_to, $2)
            WHERE id = $1 AND status <> 'resolved'
            """,
            int(review_id),
            (admin_label or "")[:120],
        )
        return r != "UPDATE 0"


async def ops_review_assign(review_id: int, admin_label: str) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        r = await conn.execute(
            """
            UPDATE ops_review_queue SET
                status = 'assigned',
                updated_at = NOW(),
                assigned_to = $2
            WHERE id = $1 AND status = 'open'
            """,
            int(review_id),
            (admin_label or "")[:120],
        )
        return r != "UPDATE 0"


async def ops_review_open_count() -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        v = await conn.fetchval(
            "SELECT COUNT(*)::int FROM ops_review_queue WHERE status IN ('open','assigned')"
        )
        return int(v or 0)


async def sla_ticket_upsert_progress_job(
    *,
    case_no: str,
    job_id: int,
    run_at,
    grace_hours: float = 2.0,
) -> None:
    """自动化任务应在 run_at 执行；超过 grace_hours 仍未处理则视为 SLA 风险。"""
    from datetime import timedelta, timezone as tz

    cn = (case_no or "").strip().upper()
    if not cn or not job_id:
        return
    if run_at.tzinfo is None:
        run_at = run_at.replace(tzinfo=tz.utc)
    deadline = run_at + timedelta(hours=float(grace_hours))
    pool = await get_pool()
    ref_id = str(int(job_id))
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO sla_tickets (case_no, ref_type, ref_id, deadline_at, resolved)
            VALUES ($1, 'progress_job', $2, $3, FALSE)
            ON CONFLICT (ref_type, ref_id) DO UPDATE SET
                deadline_at = EXCLUDED.deadline_at,
                case_no = EXCLUDED.case_no,
                resolved = FALSE,
                breach_notified_user = FALSE,
                breach_notified_admin = FALSE
            """,
            cn,
            ref_id,
            deadline,
        )


async def sla_ticket_resolve_ref(ref_type: str, ref_id: str) -> None:
    rt = (ref_type or "").strip()
    rid = (ref_id or "").strip()
    if not rt or not rid:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE sla_tickets SET resolved = TRUE WHERE ref_type = $1 AND ref_id = $2
            """,
            rt,
            rid,
        )


async def sla_fetch_due_admin_unnotified(limit: int = 20) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT t.* FROM sla_tickets t
            WHERE NOT t.resolved
              AND NOT t.breach_notified_admin
              AND t.deadline_at <= NOW()
            ORDER BY t.deadline_at ASC
            LIMIT $1
            """,
            int(limit),
        )
        return [dict(r) for r in rows]


async def sla_fetch_due_user_unnotified(limit: int = 20) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT t.* FROM sla_tickets t
            WHERE NOT t.resolved
              AND NOT t.breach_notified_user
              AND t.deadline_at <= NOW()
            ORDER BY t.deadline_at ASC
            LIMIT $1
            """,
            int(limit),
        )
        return [dict(r) for r in rows]


async def sla_mark_admin_notified(sla_id: int) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE sla_tickets SET breach_notified_admin = TRUE WHERE id = $1",
            int(sla_id),
        )


async def sla_mark_user_notified(sla_id: int) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE sla_tickets SET breach_notified_user = TRUE WHERE id = $1",
            int(sla_id),
        )


async def sla_progress_job_still_pending(job_id: int) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT 1 FROM case_progress_jobs
            WHERE id = $1 AND processed_at IS NULL AND NOT cancelled
            """,
            int(job_id),
        )
        return row is not None


# ── Push delivery tracking ─────────────────────────────

async def push_log_record(
    case_no: str,
    tg_user_id: int,
    phase: int | None,
    event_kind: str,
) -> int | None:
    """Insert a new push_log row before sending. Returns the row id."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO push_log (case_no, tg_user_id, phase, event_kind)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            """,
            (case_no or "").strip().upper(),
            int(tg_user_id),
            phase,
            (event_kind or "unknown")[:64],
        )
        return int(row["id"]) if row else None


async def push_log_mark_delivered(push_id: int, tg_message_id: int | None) -> None:
    """Mark a push_log row as delivered (send_message succeeded)."""
    if not push_id:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE push_log
            SET delivered_at = NOW(), tg_message_id = $2
            WHERE id = $1
            """,
            int(push_id),
            int(tg_message_id) if tg_message_id else None,
        )


async def push_log_update_error(push_id: int, error: str) -> None:
    """Record delivery failure on a push_log row."""
    if not push_id:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE push_log
            SET retry_count = retry_count + 1, last_error = $2
            WHERE id = $1
            """,
            int(push_id),
            (error or "")[:500],
        )


async def push_log_mark_interacted(tg_user_id: int, case_no: str | None = None) -> None:
    """
    When a user opens any case-related section, mark their recent unacknowledged
    push_log rows as interacted (first_interaction_at = NOW()).
    Targets rows from the last 7 days.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        if case_no:
            await conn.execute(
                """
                UPDATE push_log
                SET first_interaction_at = NOW()
                WHERE tg_user_id = $1
                  AND UPPER(TRIM(case_no)) = UPPER($2)
                  AND first_interaction_at IS NULL
                  AND created_at >= NOW() - INTERVAL '7 days'
                """,
                int(tg_user_id),
                (case_no or "").strip().upper(),
            )
        else:
            await conn.execute(
                """
                UPDATE push_log
                SET first_interaction_at = NOW()
                WHERE tg_user_id = $1
                  AND first_interaction_at IS NULL
                  AND created_at >= NOW() - INTERVAL '7 days'
                """,
                int(tg_user_id),
            )


async def push_log_fetch_for_user(tg_user_id: int, limit: int = 20) -> list[dict]:
    """Return recent push_log rows for a user, newest first."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, created_at, case_no, phase, event_kind,
                   delivered_at, first_interaction_at, nudge_sent_at, last_error
            FROM push_log
            WHERE tg_user_id = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            int(tg_user_id),
            int(limit),
        )
        return [dict(r) for r in rows]


async def push_log_fetch_pending_nudge(min_hours: int = 24, limit: int = 50) -> list[dict]:
    """
    Return push_log rows that were delivered but never interacted with,
    and for which no nudge has been sent yet, older than min_hours.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, case_no, tg_user_id, phase, event_kind, created_at
            FROM push_log
            WHERE delivered_at IS NOT NULL
              AND first_interaction_at IS NULL
              AND nudge_sent_at IS NULL
              AND event_kind != 'nudge'
              AND created_at < NOW() - ($1 * INTERVAL '1 hour')
            ORDER BY created_at ASC
            LIMIT $2
            """,
            int(min_hours),
            int(limit),
        )
        return [dict(r) for r in rows]


async def push_log_mark_nudged(push_id: int) -> None:
    """Record that a nudge reminder was sent for this push_log entry."""
    if not push_id:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE push_log SET nudge_sent_at = NOW() WHERE id = $1",
            int(push_id),
        )


async def get_all_cases(limit: int = 500) -> list[dict]:
    """Return all cases ordered by created_at DESC (used by broadcast worker)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM cases ORDER BY created_at DESC LIMIT $1",
            int(limit),
        )
        return [dict(r) for r in rows]


# ── Scheduled broadcasts ───────────────────────────────────────────────────

async def broadcast_create(
    *,
    created_by: str,
    scheduled_at,
    target_kind: str = "all",
    target_case_no: str | None = None,
    target_phase: int | None = None,
    template_kind: str = "custom",
    custom_body: str | None = None,
) -> int | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO scheduled_broadcasts
                (created_by, scheduled_at, target_kind, target_case_no,
                 target_phase, template_kind, custom_body)
            VALUES ($1,$2,$3,$4,$5,$6,$7)
            RETURNING id
            """,
            (created_by or "admin")[:64],
            scheduled_at,
            (target_kind or "all")[:20],
            (target_case_no or "").strip().upper() or None,
            target_phase,
            (template_kind or "custom")[:20],
            custom_body,
        )
        return int(row["id"]) if row else None


async def broadcast_list(status: str = "pending", limit: int = 20) -> list[dict]:
    """status: 'pending'|'executed'|'cancelled'"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        if status == "pending":
            rows = await conn.fetch(
                "SELECT * FROM scheduled_broadcasts WHERE executed_at IS NULL AND NOT cancelled ORDER BY scheduled_at ASC LIMIT $1",
                int(limit),
            )
        elif status == "executed":
            rows = await conn.fetch(
                "SELECT * FROM scheduled_broadcasts WHERE executed_at IS NOT NULL ORDER BY executed_at DESC LIMIT $1",
                int(limit),
            )
        else:  # cancelled
            rows = await conn.fetch(
                "SELECT * FROM scheduled_broadcasts WHERE cancelled ORDER BY created_at DESC LIMIT $1",
                int(limit),
            )
        return [dict(r) for r in rows]


async def broadcast_cancel(broadcast_id: int, cancelled_by: str) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        r = await conn.execute(
            "UPDATE scheduled_broadcasts SET cancelled=TRUE, cancelled_by=$2 WHERE id=$1 AND executed_at IS NULL AND NOT cancelled",
            int(broadcast_id),
            (cancelled_by or "admin")[:64],
        )
        return r != "UPDATE 0"


async def broadcast_fetch_due(limit: int = 10) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM scheduled_broadcasts WHERE executed_at IS NULL AND NOT cancelled AND scheduled_at <= NOW() ORDER BY scheduled_at ASC LIMIT $1",
            int(limit),
        )
        return [dict(r) for r in rows]


async def broadcast_mark_executed(broadcast_id: int, sent_count: int, error_count: int) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE scheduled_broadcasts SET executed_at=NOW(), sent_count=$2, error_count=$3 WHERE id=$1",
            int(broadcast_id),
            int(sent_count),
            int(error_count),
        )


# ── Blacklist ──────────────────────────────────────────────────────────────

async def blacklist_add(tg_user_id: int, reason: str, banned_by: str) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            await conn.execute(
                "INSERT INTO blacklist (tg_user_id, reason, banned_by) VALUES ($1,$2,$3)",
                int(tg_user_id),
                (reason or "")[:500],
                (banned_by or "admin")[:64],
            )
            await audit_log(conn, "ADMIN", banned_by, "BLACKLIST_ADD", str(tg_user_id), reason or "")
            return True
        except Exception:
            return False


async def blacklist_remove(tg_user_id: int, unbanned_by: str) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        r = await conn.execute(
            "UPDATE blacklist SET is_active=FALSE, unbanned_at=NOW(), unbanned_by=$2 WHERE tg_user_id=$1 AND is_active",
            int(tg_user_id),
            (unbanned_by or "admin")[:64],
        )
        if r != "UPDATE 0":
            await audit_log(conn, "ADMIN", unbanned_by, "BLACKLIST_REMOVE", str(tg_user_id), "")
            return True
        return False


async def blacklist_is_active(tg_user_id: int) -> bool:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT 1 FROM blacklist WHERE tg_user_id=$1 AND is_active LIMIT 1",
                int(tg_user_id),
            )
            return row is not None
    except Exception:
        return False  # fail-open: if table missing or DB error, don't block anyone


async def blacklist_list(limit: int = 30) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM blacklist ORDER BY banned_at DESC LIMIT $1",
            int(limit),
        )
        return [dict(r) for r in rows]


# ── Fee config ─────────────────────────────────────────────────────────────

async def fee_config_get(key: str, default: float = 0.0) -> float:
    """Get global fee amount by key. Falls back to default if not in DB."""
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            val = await conn.fetchval(
                "SELECT amount FROM fee_config WHERE key=$1",
                key,
            )
            return float(val) if val is not None else default
    except Exception:
        return default


async def fee_config_set(key: str, amount: float, updated_by: str) -> None:
    """Upsert a fee config entry and write to audit_log."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO fee_config (key, amount, updated_by, updated_at)
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (key) DO UPDATE
              SET amount=$2, updated_by=$3, updated_at=NOW()
            """,
            key,
            float(amount),
            (updated_by or "admin")[:64],
        )
        await audit_log(
            conn, "ADMIN", updated_by, "FEE_UPDATED", key,
            f"amount={amount:.2f}",
        )


async def fee_config_list() -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM fee_config ORDER BY key")
        return [dict(r) for r in rows]

