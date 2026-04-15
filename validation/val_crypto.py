"""
validation/val_crypto.py
验证：钱包地址格式、自动识别网络(ERC-20/TRC-20/BTC)
交易哈希验证、地址风险评分
前端返回英文、后端返回中文
"""
import re
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class ValResult:
    valid: bool
    msg_en: str
    msg_zh: str
    value: Optional[str] = None
    network: Optional[str] = None
    risk_score: int = 0


MSG_WALLET_OK_EN = "Wallet address format is valid."
MSG_WALLET_INVALID_EN = "Invalid wallet address format."
MSG_TXID_OK_EN = "Transaction hash format is valid."
MSG_TXID_INVALID_EN = "Invalid transaction hash (64 hex chars for ETH/TRX, 64 for BTC)."
MSG_NET_ERC_EN = "Detected: ERC-20 / BSC (Ethereum)."
MSG_NET_TRC_EN = "Detected: TRC-20 (TRON)."
MSG_NET_BTC_EN = "Detected: Bitcoin Network."
MSG_NET_UNKNOWN_EN = "Network could not be determined."

MSG_WALLET_OK_ZH = "钱包地址格式正确。"
MSG_WALLET_INVALID_ZH = "钱包地址格式无效。"
MSG_TXID_OK_ZH = "交易哈希格式正确。"
MSG_TXID_INVALID_ZH = "交易哈希无效（ETH/TRX 为 64 位十六进制，BTC 为 64 位）。"
MSG_NET_ERC_ZH = "已识别：ERC-20 / BSC（以太坊）。"
MSG_NET_TRC_ZH = "已识别：TRC-20（波场）。"
MSG_NET_BTC_ZH = "已识别：比特币网络。"
MSG_NET_UNKNOWN_ZH = "无法识别网络。"


def detect_network(address: str) -> Tuple[Optional[str], str, str]:
    """
    根据地址格式自动识别网络
    返回 (network_key, msg_en, msg_zh)
    """
    if not address or not isinstance(address, str):
        return None, MSG_NET_UNKNOWN_EN, MSG_NET_UNKNOWN_ZH

    s = address.strip()

    if re.match(r"^0x[0-9a-fA-F]{40}$", s):
        return "ERC-20", MSG_NET_ERC_EN, MSG_NET_ERC_ZH
    if re.match(r"^T[A-Za-z0-9]{33}$", s):
        return "TRC-20", MSG_NET_TRC_EN, MSG_NET_TRC_ZH
    if re.match(r"^(1|3|bc1)[A-Za-z0-9]{25,62}$", s):
        return "BTC", MSG_NET_BTC_EN, MSG_NET_BTC_ZH

    return None, MSG_NET_UNKNOWN_EN, MSG_NET_UNKNOWN_ZH


def validate_wallet_address(address: str) -> ValResult:
    """验证钱包地址格式并自动识别网络"""
    if not address or not isinstance(address, str):
        return ValResult(False, MSG_WALLET_INVALID_EN, MSG_WALLET_INVALID_ZH, risk_score=100)

    s = address.strip()
    network, net_en, net_zh = detect_network(s)

    if not network:
        return ValResult(False, MSG_WALLET_INVALID_EN, MSG_WALLET_INVALID_ZH, risk_score=100)

    risk = compute_address_risk_score(s, network)
    return ValResult(
        True,
        f"{MSG_WALLET_OK_EN} {net_en}",
        f"{MSG_WALLET_OK_ZH} {net_zh}",
        value=s,
        network=network,
        risk_score=risk,
    )


def validate_tx_hash(txid: str, network: Optional[str] = None) -> ValResult:
    """
    验证交易哈希
    ETH/TRX: 64 位十六进制 (0x 可选)
    BTC: 64 位十六进制
    """
    if not txid or not isinstance(txid, str):
        return ValResult(False, MSG_TXID_INVALID_EN, MSG_TXID_INVALID_ZH, risk_score=100)

    s = txid.strip()
    if s.lower().startswith("0x"):
        s = s[2:]

    if len(s) != 64:
        return ValResult(False, MSG_TXID_INVALID_EN, MSG_TXID_INVALID_ZH, risk_score=90)
    if not re.match(r"^[0-9a-fA-F]{64}$", s):
        return ValResult(False, MSG_TXID_INVALID_EN, MSG_TXID_INVALID_ZH, risk_score=100)

    return ValResult(True, MSG_TXID_OK_EN, MSG_TXID_OK_ZH, value=txid.strip(), risk_score=0)


def compute_address_risk_score(address: str, network: Optional[str] = None) -> int:
    """
    地址风险评分 0–100
    基于格式、网络类型及简单启发式
    """
    score = 0
    if not network:
        return 80

    if network == "TRC-20":
        score += 5
    elif network == "ERC-20":
        score += 3

    if address and len(address) < 20:
        score += 10

    return min(100, score)


def validate_crypto(
    wallet: str = "",
    tx_hash: str = "",
) -> dict:
    """汇总加密货币验证结果"""
    results = {}
    if wallet:
        wr = validate_wallet_address(wallet)
        results["wallet"] = wr
        results["network"] = wr.network
    if tx_hash:
        results["tx_hash"] = validate_tx_hash(tx_hash, results.get("network"))

    if "wallet" in results:
        results["address_risk_score"] = results["wallet"].risk_score

    return results
