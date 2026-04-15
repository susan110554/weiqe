"""
validation/val_transaction.py
验证：金额格式、银行账号、路由号码、交易风险评分
风险评分 0–100
前端返回英文、后端返回中文
"""
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional


@dataclass
class ValResult:
    valid: bool
    msg_en: str
    msg_zh: str
    value: Optional[str] = None
    risk_score: int = 0


MSG_AMOUNT_OK_EN = "Amount format is valid."
MSG_AMOUNT_INVALID_EN = "Invalid amount format. Use numbers and optional decimal."
MSG_ACCT_OK_EN = "Bank account format is valid."
MSG_ACCT_INVALID_EN = "Invalid bank account format."
MSG_ROUTING_OK_EN = "Routing number is valid."
MSG_ROUTING_INVALID_EN = "Invalid routing number (9 digits for US)."
MSG_RISK_LOW_EN = "Low transaction risk."
MSG_RISK_MED_EN = "Medium transaction risk."
MSG_RISK_HIGH_EN = "High transaction risk."

MSG_AMOUNT_OK_ZH = "金额格式正确。"
MSG_AMOUNT_INVALID_ZH = "金额格式无效，请使用数字及可选小数。"
MSG_ACCT_OK_ZH = "银行账号格式正确。"
MSG_ACCT_INVALID_ZH = "银行账号格式无效。"
MSG_ROUTING_OK_ZH = "路由号码正确。"
MSG_ROUTING_INVALID_ZH = "路由号码无效（美国为9位数字）。"
MSG_RISK_LOW_ZH = "交易风险较低。"
MSG_RISK_MED_ZH = "交易风险中等。"
MSG_RISK_HIGH_ZH = "交易风险较高。"


def validate_amount(amount: str, max_decimals: int = 2) -> ValResult:
    """验证金额格式"""
    if not amount or not isinstance(amount, str):
        return ValResult(False, MSG_AMOUNT_INVALID_EN, MSG_AMOUNT_INVALID_ZH, risk_score=100)

    s = amount.strip().replace(",", "")
    try:
        d = Decimal(s)
        if d < 0:
            return ValResult(False, MSG_AMOUNT_INVALID_EN, MSG_AMOUNT_INVALID_ZH, risk_score=100)
        if d.as_tuple().exponent and abs(d.as_tuple().exponent) > max_decimals:
            return ValResult(False, MSG_AMOUNT_INVALID_EN, MSG_AMOUNT_INVALID_ZH, risk_score=50)
    except (InvalidOperation, ValueError):
        return ValResult(False, MSG_AMOUNT_INVALID_EN, MSG_AMOUNT_INVALID_ZH, risk_score=100)

    return ValResult(True, MSG_AMOUNT_OK_EN, MSG_AMOUNT_OK_ZH, value=s, risk_score=0)


def validate_bank_account(account: str, min_len: int = 4, max_len: int = 17) -> ValResult:
    """验证银行账号格式（美国通常 4–17 位数字）"""
    if not account or not isinstance(account, str):
        return ValResult(False, MSG_ACCT_INVALID_EN, MSG_ACCT_INVALID_ZH, risk_score=100)

    digits = re.sub(r"\D", "", account)
    if len(digits) < min_len or len(digits) > max_len:
        return ValResult(False, MSG_ACCT_INVALID_EN, MSG_ACCT_INVALID_ZH, risk_score=80)
    if not digits.isdigit():
        return ValResult(False, MSG_ACCT_INVALID_EN, MSG_ACCT_INVALID_ZH, risk_score=100)

    return ValResult(True, MSG_ACCT_OK_EN, MSG_ACCT_OK_ZH, value=digits, risk_score=0)


def validate_routing_number(routing: str) -> ValResult:
    """验证美国路由号码（9 位数字）"""
    if not routing or not isinstance(routing, str):
        return ValResult(False, MSG_ROUTING_INVALID_EN, MSG_ROUTING_INVALID_ZH, risk_score=100)

    digits = re.sub(r"\D", "", routing)
    if len(digits) != 9:
        return ValResult(False, MSG_ROUTING_INVALID_EN, MSG_ROUTING_INVALID_ZH, risk_score=90)
    if not digits.isdigit():
        return ValResult(False, MSG_ROUTING_INVALID_EN, MSG_ROUTING_INVALID_ZH, risk_score=100)

    return ValResult(True, MSG_ROUTING_OK_EN, MSG_ROUTING_OK_ZH, value=digits, risk_score=0)


def compute_transaction_risk_score(
    amount_valid: bool,
    account_valid: bool,
    routing_valid: bool,
    amount_value: Optional[str] = None,
) -> int:
    """
    计算交易风险评分 0–100
    基于各项验证结果及金额大小
    """
    score = 0
    if not amount_valid:
        score += 40
    if not account_valid:
        score += 30
    if not routing_valid:
        score += 20

    if amount_value and amount_valid:
        try:
            d = Decimal(str(amount_value).replace(",", ""))
            if d > 100000:
                score += 15
            elif d > 50000:
                score += 10
            elif d > 10000:
                score += 5
        except (InvalidOperation, ValueError):
            pass

    return min(100, score)


def validate_transaction(
    amount: str = "",
    account: str = "",
    routing: str = "",
) -> dict:
    """汇总交易验证结果及风险评分"""
    results = {}
    amount_res = validate_amount(amount) if amount else None
    account_res = validate_bank_account(account) if account else None
    routing_res = validate_routing_number(routing) if routing else None

    if amount_res:
        results["amount"] = amount_res
    if account_res:
        results["account"] = account_res
    if routing_res:
        results["routing"] = routing_res

    risk = compute_transaction_risk_score(
        amount_res.valid if amount_res else True,
        account_res.valid if account_res else True,
        routing_res.valid if routing_res else True,
        amount_res.value if amount_res else None,
    )
    results["risk_score"] = risk

    return results
