"""
validation/val_profile.py
验证：姓名格式、邮箱格式、电话格式、证件格式
前端返回英文、后端返回中文
"""
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ValResult:
    valid: bool
    msg_en: str
    msg_zh: str
    value: Optional[str] = None


# ── 前端英文消息 ─────────────────────────────────────
MSG_NAME_OK_EN = "Full legal name recorded."
MSG_NAME_INVALID_EN = (
    "Invalid name format.\n"
    "Enter your full legal name as shown on your government-issued identification.\n"
    "Example: John Michael Smith"
)
MSG_EMAIL_OK_EN = "Email format is valid."
MSG_EMAIL_INVALID_EN = "Invalid email format."
MSG_PHONE_OK_EN = "Phone format is valid."
MSG_PHONE_INVALID_EN = "Invalid phone format. Use +CountryCode-Number."
MSG_ID_OK_EN = "ID format is valid."
MSG_ID_INVALID_EN = "Invalid ID document format."

# ── 后端中文消息 ─────────────────────────────────────
MSG_NAME_OK_ZH = "姓名格式正确。"
MSG_NAME_INVALID_ZH = "姓名格式无效，仅允许字母、空格、连字符。"
MSG_EMAIL_OK_ZH = "邮箱格式正确。"
MSG_EMAIL_INVALID_ZH = "邮箱格式无效。"
MSG_PHONE_OK_ZH = "电话格式正确。"
MSG_PHONE_INVALID_ZH = "电话格式无效，请使用 +国家码-号码 格式。"
MSG_ID_OK_ZH = "证件格式正确。"
MSG_ID_INVALID_ZH = "证件格式无效。"


def check_name(name: str) -> ValResult:
    """
    Full Legal Name 验证规则：
    1. 至少包含两个单词 (名 + 姓)
    2. 每个单词至少 2 个字符
    3. 只允许字母、空格、连字符(-)、点(.)
    4. 不接受纯单字输入如 "Smith"
    5. 不接受乱码如 "jkshfkshf"（每词至少含一元音）
    6. 不接受数字或特殊符号
    """
    if not name or not isinstance(name, str):
        return ValResult(False, MSG_NAME_INVALID_EN, MSG_NAME_INVALID_ZH)
    s = name.strip()
    if not s:
        return ValResult(False, MSG_NAME_INVALID_EN, MSG_NAME_INVALID_ZH)
    # 3. 只允许字母、空格、连字符(-)、点(.)
    if not re.match(r"^[a-zA-Z\s\-\.]+$", s):
        return ValResult(False, MSG_NAME_INVALID_EN, MSG_NAME_INVALID_ZH)
    # 1. 至少两个单词；2. 每个单词至少 2 字符；4. 不接受纯单字
    words = [w for w in s.split() if w]
    if len(words) < 2:
        return ValResult(False, MSG_NAME_INVALID_EN, MSG_NAME_INVALID_ZH)
    vowels = set("aeiouAEIOU")
    for w in words:
        letters = re.sub(r"[\-\.]", "", w)
        if len(letters) < 2:
            return ValResult(False, MSG_NAME_INVALID_EN, MSG_NAME_INVALID_ZH)
        # 5. 不接受乱码：每个单词至少包含一个元音
        if not any(c in vowels for c in letters):
            return ValResult(False, MSG_NAME_INVALID_EN, MSG_NAME_INVALID_ZH)
    return ValResult(True, MSG_NAME_OK_EN, MSG_NAME_OK_ZH, s)


def validate_name(name: str) -> ValResult:
    """兼容：等同于 check_name"""
    return check_name(name)


def validate_email(email: str) -> ValResult:
    """验证邮箱格式"""
    if not email or not isinstance(email, str):
        return ValResult(False, MSG_EMAIL_INVALID_EN, MSG_EMAIL_INVALID_ZH)
    s = email.strip().lower()
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(pattern, s):
        return ValResult(False, MSG_EMAIL_INVALID_EN, MSG_EMAIL_INVALID_ZH)
    return ValResult(True, MSG_EMAIL_OK_EN, MSG_EMAIL_OK_ZH, s)


def validate_phone(phone: str) -> ValResult:
    """验证电话格式：+CountryCode-Number 或纯数字"""
    if not phone or not isinstance(phone, str):
        return ValResult(False, MSG_PHONE_INVALID_EN, MSG_PHONE_INVALID_ZH)
    s = phone.strip().replace(" ", "").replace("-", "")
    digits = re.sub(r"\D", "", s)
    if len(digits) < 7 or len(digits) > 15:
        return ValResult(False, MSG_PHONE_INVALID_EN, MSG_PHONE_INVALID_ZH)
    if not s.startswith("+") and not digits:
        return ValResult(False, MSG_PHONE_INVALID_EN, MSG_PHONE_INVALID_ZH)
    return ValResult(True, MSG_PHONE_OK_EN, MSG_PHONE_OK_ZH, s)


def validate_id_document(doc: str) -> ValResult:
    """验证证件格式：护照/身份证等，字母数字组合"""
    if not doc or not isinstance(doc, str):
        return ValResult(False, MSG_ID_INVALID_EN, MSG_ID_INVALID_ZH)
    s = doc.strip().upper()
    if len(s) < 5 or len(s) > 30:
        return ValResult(False, MSG_ID_INVALID_EN, MSG_ID_INVALID_ZH)
    if not re.match(r"^[A-Z0-9\-]+$", s):
        return ValResult(False, MSG_ID_INVALID_EN, MSG_ID_INVALID_ZH)
    return ValResult(True, MSG_ID_OK_EN, MSG_ID_OK_ZH, s)


def validate_profile(fullname: str = "", email: str = "", phone: str = "", id_doc: str = "") -> dict:
    """汇总个人资料验证结果"""
    results = {}
    if fullname:
        results["fullname"] = validate_name(fullname)
    if email:
        results["email"] = validate_email(email)
    if phone:
        results["phone"] = validate_phone(phone)
    if id_doc:
        results["id_document"] = validate_id_document(id_doc)
    return results
