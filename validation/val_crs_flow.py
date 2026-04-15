"""
CRS 多步表单：字段级校验，供 bot / crs 模块复用。
返回 (是否通过, 错误提示英文 HTML 文本)；通过时第三项为规范化后的字符串。
"""
from __future__ import annotations

import re
from typing import Optional, Tuple

from .val_profile import check_name, validate_email, validate_phone, ValResult

# ── CRS-01 Age ─────────────────────────────────────────────

_MSG_AGE_INVALID = (
    "❌ <b>Invalid age.</b>\n\n"
    "Please enter a number (e.g. <code>35</code>), a range "
    "(e.g. <code>45-50</code>), or <code>Unknown</code>.\n\n"
    "Example: <code>42</code>"
)


def validate_crs01_age(text: str) -> Tuple[bool, str, Optional[str]]:
    s = (text or "").strip()
    if not s:
        return False, _MSG_AGE_INVALID, None
    sl = s.lower()
    if sl in ("unknown", "prefer not to say", "n/a", "na"):
        return True, "", s
    if re.match(r"^\d{1,3}$", s):
        n = int(s)
        if 1 <= n <= 120:
            return True, "", s
        return False, _MSG_AGE_INVALID, None
    if re.match(r"^\d{1,3}\s*[-–]\s*\d{1,3}$", s):
        a, b = re.split(r"\s*[-–]\s*", s, maxsplit=1)
        ia, ib = int(a), int(b)
        if 1 <= ia <= 120 and 1 <= ib <= 120 and ia <= ib:
            return True, "", s
    return False, _MSG_AGE_INVALID, None


# ── CRS-03 Subject contact ─────────────────────────────────

def _looks_like_garbage(s: str) -> bool:
    t = s.strip()
    if len(t) < 2:
        return True
    if len(set(t.lower())) <= 1:
        return True
    if re.fullmatch(r"(.)\1{7,}", t):
        return True
    return False


def validate_crs03_subject_name(text: str) -> Tuple[bool, str, Optional[str]]:
    s = (text or "").strip()
    if not s:
        return False, (
            "❌ <b>Invalid name.</b>\n\n"
            "Please enter the subject name.\n\n"
            "Example: <code>John Smith</code> or <code>ABC Company Ltd</code>"
        ), None
    if _looks_like_garbage(s):
        return False, (
            "❌ <b>Invalid name.</b>\n\n"
            "Please enter a realistic name or organization.\n\n"
            "Example: <code>John Smith</code>"
        ), None
    r: ValResult = check_name(s)
    if r.valid:
        return True, "", r.value or s
    # 机构名：允许无空格的长字母串（略宽于 complainant 姓名）
    if re.match(r"^[a-zA-Z0-9\s&\.,'\-]{3,80}$", s) and len(s.split()) >= 1 and len(s) >= 4:
        return True, "", s
    return False, (
        "❌ <b>Invalid name.</b>\n\n"
        "Please enter the subject name as shown.\n\n"
        "Example: <code>John Smith</code> or <code>Acme Corp</code>"
    ), None


def validate_crs03_subject_phone(text: str) -> Tuple[bool, str, Optional[str]]:
    s = (text or "").strip()
    if not s:
        return False, (
            "❌ <b>Invalid phone number.</b>\n\n"
            "Include country code.\n\n"
            "Example: <code>+1-305-555-0100</code>"
        ), None
    r = validate_phone(s)
    if r.valid:
        return True, "", r.value or s
    # 允许常见分隔符
    if re.match(r"^\+?[\d\s\-()]{8,22}$", s) and sum(c.isdigit() for c in s) >= 8:
        return True, "", s
    return False, (
        "❌ <b>Invalid phone number.</b>\n\n"
        "Use international format with country code.\n\n"
        "Example: <code>+1 305-555-0100</code>"
    ), None


def validate_crs03_subject_email(text: str) -> Tuple[bool, str, Optional[str]]:
    s = (text or "").strip()
    if not s:
        return False, (
            "❌ <b>Invalid email.</b>\n\n"
            "Example: <code>subject@email.com</code>"
        ), None
    r = validate_email(s)
    if r.valid:
        return True, "", r.value or s
    return False, (
        "❌ <b>Invalid email.</b>\n\n"
        "Example: <code>subject@email.com</code>"
    ), None


def _validate_crs03_line(text: str, field_label: str, example: str, min_len: int = 3) -> Tuple[bool, str, Optional[str]]:
    s = (text or "").strip()
    if len(s) < min_len:
        return False, (
            f"❌ <b>Invalid {field_label}.</b>\n\n"
            f"Please enter at least {min_len} characters.\n\n"
            f"Example: <code>{example}</code>"
        ), None
    if _looks_like_garbage(s):
        return False, (
            f"❌ <b>Invalid {field_label}.</b>\n\n"
            "Please enter a realistic value.\n\n"
            f"Example: <code>{example}</code>"
        ), None
    if not re.match(r"^[\w\s\-\.,'#/&()áéíóúÁÉÍÓÚàèìòùÀÈÌÒÙâêîôûÂÊÎÔÛäëïöüÄËÏÖÜñÑ]{2,200}$", s):
        return False, (
            f"❌ <b>Invalid {field_label}.</b>\n\n"
            f"Example: <code>{example}</code>"
        ), None
    return True, "", s


def validate_crs03_subject_address(text: str) -> Tuple[bool, str, Optional[str]]:
    return _validate_crs03_line(text, "address", "123 Main Street", min_len=5)


def validate_crs03_subject_city(text: str) -> Tuple[bool, str, Optional[str]]:
    return _validate_crs03_line(text, "city", "New York", min_len=2)


def validate_crs03_subject_country(text: str) -> Tuple[bool, str, Optional[str]]:
    return _validate_crs03_line(text, "country", "United States", min_len=2)


CRS03_VALIDATORS = {
    "CRS03_STATE_C_NAME": validate_crs03_subject_name,
    "CRS03_STATE_C_PHONE": validate_crs03_subject_phone,
    "CRS03_STATE_C_EMAIL": validate_crs03_subject_email,
    "CRS03_STATE_C_ADDRESS": validate_crs03_subject_address,
    "CRS03_STATE_C_CITY": validate_crs03_subject_city,
    "CRS03_STATE_C_COUNTRY": validate_crs03_subject_country,
}
