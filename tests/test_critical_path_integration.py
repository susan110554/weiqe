"""
关键路径集成测试（测试库）：建案 → PDF 快照 → 签名 → 状态推进 → 排队任务 → 加密支付会话确认 → CMP 解锁字段。

需：PostgreSQL + WEIQUAN_TEST_DB_NAME；安装 requirements-dev.txt。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

import database as db

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_critical_path_create_sign_pdf_status_progress_payment_unlock(db_ready):
    case_no = f"IT-{uuid.uuid4().hex[:12].upper()}"
    tg_uid = 900_000_001

    assert await db.create_case(
        {
            "case_no": case_no,
            "tg_user_id": tg_uid,
            "tg_username": "it_user",
            "platform": "integration_test",
            "amount": "100",
            "coin": "USDT",
            "incident_time": "2026-01-01",
            "wallet_addr": "TTest",
            "chain_type": "TRON",
            "tx_hash": "none",
            "contact": "it@example.com",
        }
    ) == case_no

    assert await db.merge_case_pdf_snapshot(
        case_no, {"integration_pdf_marker": True, "title": "IT PDF"}
    )

    assert await db.save_case_signature(
        case_no, tg_uid, signature_hex="a" * 64, ip_address="127.0.0.1", auth_ref="it-ref"
    )
    sig = await db.get_signature_by_case_no(case_no)
    assert sig and sig["case_no"] == case_no

    assert await db.update_case_status(case_no, "UNDER REVIEW", "it_admin", "integration")

    pool = await db.get_pool()
    async with pool.acquire() as conn:
        hist = await conn.fetch(
            """
            SELECT new_status FROM status_history sh
            JOIN cases c ON c.id = sh.case_id
            WHERE c.case_no = $1 ORDER BY sh.changed_at DESC LIMIT 1
            """,
            case_no,
        )
    assert hist and hist[0]["new_status"] == "UNDER REVIEW"

    run_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    job_id = await db.case_progress_enqueue(case_no, "integration_kind", run_at, {"test": True})
    assert job_id is not None

    due = await db.case_progress_fetch_due(limit=50)
    ours = [j for j in due if j["case_no"] == case_no.upper() and j["kind"] == "integration_kind"]
    assert ours, "应有已到期的 case_progress job"
    await db.case_progress_mark_processed(ours[0]["id"])

    exp = datetime.now(timezone.utc) + timedelta(hours=1)
    pid = f"it{uuid.uuid4().hex[:28]}"
    sid = await db.cryptopay_create_session(
        public_id=pid,
        case_no=case_no,
        payment_kind="p10_pay",
        tg_user_id=tg_uid,
        deposit_address="TDeposit",
        amount_expected=10.0,
        amount_min=9.0,
        amount_max=11.0,
        portal_chat_id=1,
        portal_message_id=1,
        expires_at=exp,
        extra={"integration": True},
    )
    assert sid is not None

    ok = await db.cryptopay_update_session(
        pid,
        status="confirmed",
        tx_hash="0x" + "ab" * 32,
        confirmed_at=datetime.now(timezone.utc),
    )
    assert ok
    row = await db.cryptopay_get_by_public_id(pid)
    assert row and row["status"] == "confirmed"

    assert await db.merge_case_cmp_overrides(
        case_no,
        {
            "p10_payment_confirmed": True,
            "p10_payment_tx": row["tx_hash"],
        },
    )

    pool = await db.get_pool()
    async with pool.acquire() as conn:
        r = await conn.fetchrow(
            "SELECT status, case_cmp_overrides FROM cases WHERE case_no = $1",
            case_no,
        )
    assert r["status"] == "UNDER REVIEW"
    co = r["case_cmp_overrides"] or {}
    if isinstance(co, str):
        import json
        co = json.loads(co)
    assert co.get("p10_payment_confirmed") is True
