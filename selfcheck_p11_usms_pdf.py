"""生成 P11 USMS 相关 PDF 样例到项目根目录，便于本地打开检查印章水印与版式（不启动 Bot）。"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot_modules.p11_usms_pdf import generate_p11_usms_payment_receipt_pdf
from bot_modules.receipt_pdf import (
    generate_p11_marshals_service_agreement_pdf,
    generate_p11_withdrawal_certificate_pdf,
)


def main() -> None:
    root = os.path.dirname(os.path.abspath(__file__))
    case_no = os.getenv("SELFTEST_CASE_NO", "IC3-2026-REF-84729-B")
    addr = os.getenv(
        "SELFTEST_TRC20_ADDR",
        "TN8vYfqhBHLx4fhX2J8HvXxXxXxXxXxXxXx",
    )
    tx = os.getenv(
        "SELFTEST_TX_HASH",
        "9b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3",
    )
    case = {
        "case_no": case_no,
        "case_pdf_snapshot": {
            "fullname": os.getenv("SELFTEST_RECIPIENT_NAME", "Jane Q. Public"),
            "address": os.getenv(
                "SELFTEST_RECIPIENT_ADDR",
                "123 Main Street, New York, NY 10001",
            ),
        },
        "case_cmp_overrides": {
            "p10_locked_amount_usdt": float(os.getenv("SELFTEST_WAC_LOCKED_USDT", "27475")),
            "p8_submitted_wallet": addr,
            "p11_items": [
                ["Custody Wallet Activation", 400.0],
                ["Withdrawal Authorization Fee", 200.0],
            ],
        },
    }
    now = datetime(2026, 3, 30, 14, 35, tzinfo=timezone.utc)
    pay = {
        "case_no": case_no,
        "amount_expected": 600.0,
        "tx_hash": tx,
        "block_number": 58393102,
        "confirmations": 6,
        "confirmed_at": now,
    }

    # 1) 支付收据（含水印）
    receipt_pdf = generate_p11_usms_payment_receipt_pdf(case, pay)
    out1 = os.path.join(root, "P11_USMS_PaymentReceipt_SELFTEST.pdf")
    with open(out1, "wb") as f:
        f.write(receipt_pdf)
    print("Wrote:", out1)

    # 2) 提款授权证书 WAC（含水印）
    wac_pdf = generate_p11_withdrawal_certificate_pdf(case, pay)
    out2 = os.path.join(root, "P11_USMS_WAC_SELFTEST.pdf")
    with open(out2, "wb") as f:
        f.write(wac_pdf)
    print("Wrote:", out2)

    # 3) 付款前服务协议（含水印）
    from bot_modules.case_management_push import p11_withdrawal_reference_ids

    ids = p11_withdrawal_reference_ids(case_no)
    suffix = ids["suffix"]
    escrow = os.getenv(
        "CASE_P11_ESCROW_DISPLAY",
        f"Federal Escrow Account #USMS-{suffix}",
    )
    contractor = os.getenv("CASE_P11_USMS_CONTRACTOR_ID", "FC-2024-VAL-8821")
    agree_pdf = generate_p11_marshals_service_agreement_pdf(
        case,
        deposit_address=addr,
        memo=ids["memo"],
        escrow_display=escrow,
        contractor_id=contractor,
    )
    out3 = os.path.join(root, "P11_USMS_ServiceAgreement_SELFTEST.pdf")
    with open(out3, "wb") as f:
        f.write(agree_pdf)
    print("Wrote:", out3)


if __name__ == "__main__":
    main()
