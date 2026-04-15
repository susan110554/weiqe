"""
validation/val_report.py
功能：汇总以上4个模块验证结果
生成验证报告、标记问题项
前端返回英文、后端返回中文
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# 导入各验证模块（仅在此文件内使用，不修改 __init__.py）
from .val_profile import validate_profile
from .val_transaction import validate_transaction
from .val_crypto import validate_crypto


@dataclass
class ReportItem:
    field: str
    valid: bool
    msg_en: str
    msg_zh: str
    value: Optional[str] = None
    risk_score: Optional[int] = None
    is_problem: bool = False


@dataclass
class ValidationReport:
    valid: bool
    msg_en: str
    msg_zh: str
    items: List[ReportItem] = field(default_factory=list)
    problem_fields: List[str] = field(default_factory=list)
    risk_scores: Dict[str, int] = field(default_factory=dict)


MSG_REPORT_OK_EN = "All validations passed."
MSG_REPORT_ISSUES_EN = "Validation completed with issues. Please review."
MSG_REPORT_FAIL_EN = "Validation failed."

MSG_REPORT_OK_ZH = "全部验证通过。"
MSG_REPORT_ISSUES_ZH = "验证完成，存在待处理问题，请核查。"
MSG_REPORT_FAIL_ZH = "验证未通过。"


def _collect_items_from_profile(data: dict) -> List[ReportItem]:
    items = []
    results = validate_profile(
        fullname=data.get("fullname", ""),
        email=data.get("email", ""),
        phone=data.get("phone", ""),
        id_doc=data.get("id_document", ""),
    )
    for k, v in results.items():
        if hasattr(v, "valid"):
            items.append(ReportItem(
                field=k,
                valid=v.valid,
                msg_en=v.msg_en,
                msg_zh=v.msg_zh,
                value=getattr(v, "value", None),
                is_problem=not v.valid,
            ))
    return items


def _collect_items_from_transaction(data: dict) -> List[ReportItem]:
    items = []
    results = validate_transaction(
        amount=data.get("amount", ""),
        account=data.get("account", ""),
        routing=data.get("routing", ""),
    )
    for k, v in results.items():
        if k == "risk_score":
            continue
        if hasattr(v, "valid"):
            items.append(ReportItem(
                field=k,
                valid=v.valid,
                msg_en=v.msg_en,
                msg_zh=v.msg_zh,
                value=getattr(v, "value", None),
                risk_score=getattr(v, "risk_score", None),
                is_problem=not v.valid,
            ))
    if "risk_score" in results:
        items.append(ReportItem(
            field="transaction_risk",
            valid=results["risk_score"] < 70,
            msg_en=f"Transaction risk score: {results['risk_score']}/100",
            msg_zh=f"交易风险评分：{results['risk_score']}/100",
            risk_score=results["risk_score"],
            is_problem=results["risk_score"] >= 70,
        ))
    return items


def _collect_items_from_crypto(data: dict) -> List[ReportItem]:
    items = []
    results = validate_crypto(
        wallet=data.get("wallet", ""),
        tx_hash=data.get("tx_hash", ""),
    )
    for k, v in results.items():
        if k in ("network", "address_risk_score"):
            continue
        if hasattr(v, "valid"):
            items.append(ReportItem(
                field=k,
                valid=v.valid,
                msg_en=v.msg_en,
                msg_zh=v.msg_zh,
                value=getattr(v, "value", None),
                risk_score=getattr(v, "risk_score", None),
                is_problem=not v.valid,
            ))
    if "address_risk_score" in results:
        items.append(ReportItem(
            field="address_risk",
            valid=results["address_risk_score"] < 70,
            msg_en=f"Address risk score: {results['address_risk_score']}/100",
            msg_zh=f"地址风险评分：{results['address_risk_score']}/100",
            risk_score=results["address_risk_score"],
            is_problem=results["address_risk_score"] >= 70,
        ))
    return items


def generate_report(
    profile_data: Optional[dict] = None,
    transaction_data: Optional[dict] = None,
    crypto_data: Optional[dict] = None,
    address_results: Optional[list] = None,
) -> ValidationReport:
    """
    汇总各模块验证结果，生成验证报告
    address_results: 由 val_address.validate_address 异步调用后传入的结果列表
    """
    items: List[ReportItem] = []
    problem_fields: List[str] = []
    risk_scores: Dict[str, int] = {}

    if profile_data:
        for it in _collect_items_from_profile(profile_data):
            items.append(it)
            if it.is_problem:
                problem_fields.append(it.field)

    if transaction_data:
        for it in _collect_items_from_transaction(transaction_data):
            items.append(it)
            if it.is_problem:
                problem_fields.append(it.field)
            if it.risk_score is not None:
                risk_scores[it.field] = it.risk_score

    if crypto_data:
        for it in _collect_items_from_crypto(crypto_data):
            items.append(it)
            if it.is_problem:
                problem_fields.append(it.field)
            if it.risk_score is not None:
                risk_scores[it.field] = it.risk_score

    if address_results:
        for r in address_results:
            if hasattr(r, "valid"):
                it = ReportItem(
                    field="address",
                    valid=r.valid,
                    msg_en=r.msg_en,
                    msg_zh=r.msg_zh,
                    value=getattr(r, "value", None),
                    is_problem=not r.valid,
                )
                items.append(it)
                if it.is_problem:
                    problem_fields.append(it.field)

    has_problems = len(problem_fields) > 0
    all_valid = not has_problems

    if all_valid:
        msg_en, msg_zh = MSG_REPORT_OK_EN, MSG_REPORT_OK_ZH
    elif has_problems:
        msg_en = f"{MSG_REPORT_ISSUES_EN} Problems: {', '.join(problem_fields)}"
        msg_zh = f"{MSG_REPORT_ISSUES_ZH} 问题项：{', '.join(problem_fields)}"
    else:
        msg_en, msg_zh = MSG_REPORT_FAIL_EN, MSG_REPORT_FAIL_ZH

    return ValidationReport(
        valid=all_valid,
        msg_en=msg_en,
        msg_zh=msg_zh,
        items=items,
        problem_fields=problem_fields,
        risk_scores=risk_scores,
    )


def format_report_en(report: ValidationReport) -> str:
    """生成英文验证报告文本"""
    lines = [f"Validation Report: {'PASSED' if report.valid else 'ISSUES FOUND'}", "─" * 40]
    for it in report.items:
        status = "✓" if it.valid else "✗"
        lines.append(f"  {status} {it.field}: {it.msg_en}")
        if it.risk_score is not None:
            lines.append(f"    Risk score: {it.risk_score}/100")
    if report.problem_fields:
        lines.append("")
        lines.append(f"Problem fields: {', '.join(report.problem_fields)}")
    return "\n".join(lines)


def format_report_zh(report: ValidationReport) -> str:
    """生成中文验证报告文本"""
    lines = [f"验证报告：{'通过' if report.valid else '存在问题'}", "─" * 40]
    for it in report.items:
        status = "✓" if it.valid else "✗"
        lines.append(f"  {status} {it.field}: {it.msg_zh}")
        if it.risk_score is not None:
            lines.append(f"    风险评分：{it.risk_score}/100")
    if report.problem_fields:
        lines.append("")
        lines.append(f"问题项：{', '.join(report.problem_fields)}")
    return "\n".join(lines)
