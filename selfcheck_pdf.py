import asyncio
from datetime import datetime


async def main():
    from bot_modules.pdf_gen import generate_case_pdf

    case_id = "IC3-2026-REF-0000-CHK"
    attest_ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    auth_id = "IC3-2026-REF-9928-X82"

    # Crypto sample
    pdf_data = {
        "case_no": case_id,
        "registered": attest_ts,
        "uid": "USR-12345",
        "status": "PENDING REVIEW",
        "last_updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "fullname": "John Michael Smith",
        "address": "937, South E Street, Broken Bow, Nebraska, 68822, USA",
        "phone": "+1 555 0100",
        "email": "john.smith@gmail.com",
        "amount": "2500.00",
        "coin": "USDT",
        "incident_time": "2026-03-16 11:04:22 UTC",
        "tx_hash": "0x" + "a" * 64,
        "victim_wallet": "0x" + "b" * 40,
        "wallet_addr": "0x" + "c" * 40,
        "chain_type": "Ethereum (ERC-20)",
        "platform": "Binance",
        "scammer_id": "@faketrader",
        "crime_type": "Crypto / Mining Fraud",
        "incident_story": "Test narrative.",
        "transaction_type": "crypto",
        "evidence_files": [],
    }

    pdf_bytes = await generate_case_pdf(pdf_data, attest_ts, auth_id)
    out_path = f"{case_id}_Case_Report_SELFTEST.pdf"
    with open(out_path, "wb") as f:
        f.write(pdf_bytes)
    print("Wrote:", out_path, "bytes=", len(pdf_bytes))


if __name__ == "__main__":
    asyncio.run(main())

