"""
blockchain.py — 链上风险地址实时查询模块
支持：ETH/BSC（Etherscan）、TRC20（Tronscan）、BTC（Blockchain.info）
"""

import aiohttp
import asyncio
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

ETHERSCAN_KEY = os.getenv("ETHERSCAN_KEY", "")
TIMEOUT = aiohttp.ClientTimeout(total=12)


async def _get(session: aiohttp.ClientSession, url: str) -> dict:
    try:
        async with session.get(url, timeout=TIMEOUT) as resp:
            return await resp.json(content_type=None)
    except asyncio.TimeoutError:
        return {"error": "timeout"}
    except Exception as e:
        logger.error(f"HTTP请求失败: {e}")
        return {"error": str(e)}


async def query_eth_address(address: str) -> dict:
    """查询 ETH/BSC 地址"""
    result = {"chain": "ETH/ERC20/BSC", "lines": [], "risk": 0}
    async with aiohttp.ClientSession() as session:
        # 交易记录
        tx_data = await _get(session,
            f"https://api.etherscan.io/api?module=account&action=txlist"
            f"&address={address}&startblock=0&endblock=99999999"
            f"&page=1&offset=20&sort=desc&apikey={ETHERSCAN_KEY}"
        )
        if tx_data.get("status") == "1":
            txs = tx_data.get("result", [])
            result["lines"].append(f"📊 近期交易记录：{len(txs)} 条")
            if len(txs) >= 20:
                result["risk"] = max(result["risk"], 2)
                result["lines"].append("🔴 交易次数异常频繁，疑似高风险地址")
            elif len(txs) >= 5:
                result["risk"] = max(result["risk"], 1)
        elif "No transactions" in str(tx_data.get("result", "")):
            result["lines"].append("📊 链上暂无交易记录（全新地址）")
        else:
            result["lines"].append("📊 ETH链查询完成")

        # 检查是否为合约
        contract_data = await _get(session,
            f"https://api.etherscan.io/api?module=contract&action=getabi"
            f"&address={address}&apikey={ETHERSCAN_KEY}"
        )
        if contract_data.get("status") == "1":
            result["lines"].append("⚠️ 该地址为智能合约地址，请勿直接转账")
            result["risk"] = max(result["risk"], 2)

        # ETH 余额
        bal_data = await _get(session,
            f"https://api.etherscan.io/api?module=account&action=balance"
            f"&address={address}&tag=latest&apikey={ETHERSCAN_KEY}"
        )
        if bal_data.get("status") == "1":
            eth_bal = int(bal_data.get("result", 0)) / 1e18
            result["lines"].append(f"💰 当前ETH余额：{eth_bal:.6f} ETH")

    return result


async def query_trc20_address(address: str) -> dict:
    """查询 TRC20/TRON 地址"""
    result = {"chain": "TRON/TRC20", "lines": [], "risk": 0}
    async with aiohttp.ClientSession() as session:
        data = await _get(session,
            f"https://apilist.tronscanapi.com/api/accountv2?address={address}"
        )
        if "error" in data:
            result["lines"].append("⚠️ Tronscan查询超时，请稍后重试")
            return result

        tx_out = data.get("transactions_out", 0)
        tx_in = data.get("transactions_in", 0)
        total_tx = tx_out + tx_in
        result["lines"].append(f"📊 TRC20链上数据：")
        result["lines"].append(f"   转出交易：{tx_out} 笔 | 转入交易：{tx_in} 笔 | 合计：{total_tx} 笔")

        # USDT 余额
        for b in data.get("balances", []):
            if b.get("tokenAbbr") == "USDT":
                usdt = float(b.get("quantity", 0)) / 1e6
                result["lines"].append(f"💰 当前USDT余额：{usdt:,.2f}")

        if total_tx > 200:
            result["risk"] = 3
            result["lines"].append("🚨 交易次数极高，高度疑似诈骗收款地址！")
        elif total_tx > 50:
            result["risk"] = 2
            result["lines"].append("🔴 交易频繁，疑似诈骗相关地址")
        elif total_tx > 10:
            result["risk"] = 1
            result["lines"].append("⚠️ 存在一定交易记录，请谨慎核实")
        else:
            result["lines"].append("✅ 交易记录较少")

    return result


async def query_btc_address(address: str) -> dict:
    """查询 Bitcoin 地址"""
    result = {"chain": "Bitcoin", "lines": [], "risk": 0}
    async with aiohttp.ClientSession() as session:
        data = await _get(session,
            f"https://blockchain.info/rawaddr/{address}?limit=5"
        )
        if "error" in data:
            result["lines"].append("⚠️ BTC链查询超时")
            return result

        tx_count = data.get("n_tx", 0)
        total_recv = data.get("total_received", 0) / 1e8
        total_sent = data.get("total_sent", 0) / 1e8
        final_bal = data.get("final_balance", 0) / 1e8

        result["lines"].append(f"📊 BTC链上数据：")
        result["lines"].append(f"   总交易次数：{tx_count} 笔")
        result["lines"].append(f"   累计收款：{total_recv:.8f} BTC")
        result["lines"].append(f"   累计转出：{total_sent:.8f} BTC")
        result["lines"].append(f"   当前余额：{final_bal:.8f} BTC")

        if tx_count > 100:
            result["risk"] = 2
            result["lines"].append("🔴 交易次数较高，存在风险")
        elif tx_count > 20:
            result["risk"] = 1

    return result


async def query_risk_address(address: str, chain: str) -> str:
    """统一风险查询入口，返回格式化报告文本"""
    if chain == "ETH/ERC20/BSC":
        data = await query_eth_address(address)
    elif chain == "TRON/TRC20":
        data = await query_trc20_address(address)
    elif "Bitcoin" in chain:
        data = await query_btc_address(address)
    else:
        return "❌ 暂不支持该链类型的查询"

    risk = data.get("risk", 0)
    risk_labels = {
        0: "🟢 低风险（暂无异常记录）",
        1: "🟡 中风险（存在可疑特征，请谨慎）",
        2: "🔴 高风险（强烈建议停止转账）",
        3: "🚨 极高风险（高度疑似诈骗地址）",
    }

    short_addr = address[:10] + "..." + address[-6:]
    lines = [
        "🗂 *链上风险查询报告*",
        "━━━━━━━━━━━━━━━━━━━━",
        f"📍 地址：`{short_addr}`",
        f"⛓ 链类型：{chain}",
        f"🕒 查询时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
    ]
    lines.extend(data.get("lines", []))
    lines += [
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        f"*风险评级：{risk_labels[risk]}*",
        "",
        "💡 如该地址涉及诈骗，请点「📑 提交案件信息」登记维权",
    ]
    return "\n".join(lines)
