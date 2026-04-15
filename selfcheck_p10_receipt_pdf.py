"""生成服务授权 PDF 样例到当前目录，便于本地打开检查（不启动 Bot）。"""
from __future__ import annotations

import os
import sys

# 保证能 import bot_modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot_modules.receipt_pdf import generate_p10_service_agreement_pdf


def main() -> None:
    case = {
        "case_no": "IC3-2026-REF-0000-CHK",
        "case_pdf_snapshot": {
            "fullname": "Jane Q. Public",
            "address": "123 Main Street, New York, NY 10001",
        },
        "case_cmp_overrides": None,
    }
    pdf = generate_p10_service_agreement_pdf(
        case,
        deposit_address=os.getenv(
            "SELFTEST_TRC20_ADDR",
            "TN8vYfqhBHLx4fhX2J8HvXxXxXxXxXxXx",
        ),
        memo="BOND-CB-2026-IC3-ABCDE",
        service_order="SO-2026-IC3-ABCDE",
        contract_no=os.getenv(
            "CASE_P10_CHAINALYSIS_CONTRACT_NO", "DOJ-2024-BC-7829"
        ),
    )
    out = os.path.join(os.path.dirname(__file__), "ServiceAuthorization_SELFTEST.pdf")
    with open(out, "wb") as f:
        f.write(pdf)
    print("Wrote:", out)


if __name__ == "__main__":
    main()
