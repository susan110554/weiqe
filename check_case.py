"""临时脚本：查询案号 IC3-2026-REF-9842-3WG 是否存在于数据库。"""
import asyncio
from database import get_pool, close_pool, get_case_by_no, get_signature_by_case_no

async def main():
    await get_pool()
    case_no = "IC3-2026-REF-9842-3WG"
    case = await get_case_by_no(case_no)
    sig = await get_signature_by_case_no(case_no)
    print("案号:", case_no)
    print("案件记录(cases):", "存在" if case else "不存在")
    if case:
        print("  id:", case.get("id"), "| tg_user_id:", case.get("tg_user_id"), "| created_at:", case.get("created_at"))
    print("签名记录(case_signatures):", "存在" if sig else "不存在")
    if sig:
        print("  signed_at:", sig.get("signed_at"))
    await close_pool()

if __name__ == "__main__":
    asyncio.run(main())
