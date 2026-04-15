"""
validation/val_address.py
验证：接入 LocationIQ API
功能：地址验证、建议修正、国家验证
前端返回英文、后端返回中文
回传比对：仅比对城市与邮编是否一致；不校验门牌、标点、换行等书写格式。
"""
import os
import re as _re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from dotenv import load_dotenv
load_dotenv()

# LocationIQ Forward Geocoding API
LOCATIONIQ_SEARCH = "https://us1.locationiq.com/v1/search"
MIN_IMPORTANCE = 0.12


@dataclass
class ValResult:
    valid: bool
    msg_en: str
    msg_zh: str
    value: Optional[str] = None
    suggestions: list = field(default_factory=list)
    country_code: Optional[str] = None
    country_name: Optional[str] = None


MSG_ADDR_OK_EN = "Address validated successfully."
MSG_ADDR_INVALID_EN = "Address could not be validated."
MSG_ADDR_SUGGEST_EN = "Address validated with suggestions."
MSG_ADDR_API_ERR_EN = "Address validation service unavailable."
MSG_ADDR_NO_RESULT_EN = "No matching address found."
MSG_COUNTRY_OK_EN = "Country verified."
MSG_COUNTRY_INVALID_EN = "Country could not be verified."
MSG_FMT_STREET_EN = "Address must start with a street number (digits). Example: 123 Main St."
MSG_CITY_MISMATCH_EN = "City does not match. Please re-enter your address."
MSG_POSTCODE_MISMATCH_EN = "Postal code does not match. Please re-enter your address."

MSG_ADDR_OK_ZH = "地址验证成功。"
MSG_ADDR_INVALID_ZH = "地址无法验证。"
MSG_ADDR_SUGGEST_ZH = "地址已验证，有修正建议。"
MSG_ADDR_API_ERR_ZH = "地址验证服务不可用。"
MSG_ADDR_NO_RESULT_ZH = "未找到匹配的地址。"
MSG_COUNTRY_OK_ZH = "国家验证通过。"
MSG_COUNTRY_INVALID_ZH = "国家无法验证。"
MSG_FMT_STREET_ZH = "地址须以门牌号（数字）开头。示例：123 Main St。"
MSG_CITY_MISMATCH_ZH = "城市不匹配，请重新输入地址。"
MSG_POSTCODE_MISMATCH_ZH = "邮编不匹配，请重新输入地址。"


def _get_api_key() -> str:
    """从 .env 读取 LOCATIONIQ_API_KEY"""
    return os.getenv("LOCATIONIQ_API_KEY", "")


def _extract_city_from_api(place: dict) -> str:
    """从 LocationIQ 单条结果中提取城市名（多字段兜底，不强制书写格式）。"""
    addr = place.get("address") or {}
    for key in (
        "city",
        "town",
        "village",
        "municipality",
        "hamlet",
        "suburb",
        "county",
    ):
        v = (addr.get(key) or "").strip()
        if v:
            return v
    return ""


def _extract_postcode_from_api(place: dict) -> str:
    """从 LocationIQ 单条结果中提取邮编。"""
    addr = place.get("address") or {}
    return (addr.get("postcode") or "").strip()


def _city_matches_user(user_input: str, api_city: str) -> bool:
    """
    城市是否一致：仅看用户原文中是否出现 API 城市名的合理片段（不校验整句格式）。
    - 整段包含，或按词/连字符拆分后任一段（≥2 字符）出现在用户输入中即通过。
    """
    if not api_city:
        return True
    u = (user_input or "").lower()
    ac = api_city.strip().lower()
    if not ac:
        return True
    if ac in u:
        return True
    for part in _re.split(r"[\s,\-]+", ac):
        t = part.strip()
        if len(t) >= 3 and t in u:
            return True
    return False


def _postcode_first3(postcode: str) -> str:
    """取邮编前 3 位（前 3 位匹配即视为同区域）。"""
    s = (postcode or "").strip()
    digits = _re.sub(r"\D", "", s)
    return digits[:3] if len(digits) >= 3 else digits


def _postcode_match_first3(user_input: str, api_postcode: str) -> bool:
    """邮编比对：前 3 位一致即通过；API 有邮编时用户须能解析出美国 5 位邮编。"""
    if not api_postcode:
        return True
    user_pc = _postcode_from_user_input(user_input)
    if not user_pc:
        return False
    return _postcode_first3(user_pc) == _postcode_first3(api_postcode)


def _postcode_from_user_input(text: str) -> Optional[str]:
    """从用户输入中解析美国邮编（5 位或 5+4）；不限制前后标点、空格等书写格式。"""
    if not text:
        return None
    m = _re.search(r"\b\d{5}(?:-\d{4})?\b", text)
    if m:
        return m.group(0)
    matches = _re.findall(r"\d{5}", text)
    if matches:
        return matches[-1]
    return None


def _city_postcode_match(
    user_input: str,
    api_city: str,
    api_postcode: str,
) -> Optional[Tuple[str, str]]:
    """
    仅比对城市名与邮编是否一致（不校验门牌、标点等书写格式）。
    返回 None 表示通过；(msg_en, msg_zh) 表示不通过及原因。
    """
    u = (user_input or "").strip()
    if not u:
        return (MSG_ADDR_NO_RESULT_EN, MSG_ADDR_NO_RESULT_ZH)
    if api_city and not _city_matches_user(u, api_city):
        return (MSG_CITY_MISMATCH_EN, MSG_CITY_MISMATCH_ZH)
    if not _postcode_match_first3(u, api_postcode):
        return (MSG_POSTCODE_MISMATCH_EN, MSG_POSTCODE_MISMATCH_ZH)
    return None


async def _fetch_geocode(address: str) -> Tuple[Optional[list], Optional[str]]:
    """
    调用 LocationIQ Forward Geocoding API
    返回 (results_list, error_msg_en) 或 (None, error_msg) 表示失败
    """
    if not address or not isinstance(address, str):
        return None, MSG_ADDR_INVALID_EN

    api_key = _get_api_key()
    if not api_key:
        return None, "Address validation requires LOCATIONIQ_API_KEY."

    try:
        import aiohttp
        params = {"q": address.strip(), "format": "json", "key": api_key, "limit": 5}
        async with aiohttp.ClientSession() as session:
            async with session.get(LOCATIONIQ_SEARCH, params=params) as resp:
                if resp.status != 200:
                    return None, MSG_ADDR_API_ERR_EN
                data = await resp.json()
    except Exception:
        return None, MSG_ADDR_API_ERR_EN

    if not data or not isinstance(data, list):
        return None, MSG_ADDR_NO_RESULT_EN
    data = [d for d in data if (d.get("importance") or 0) >= MIN_IMPORTANCE]
    if not data:
        return None, MSG_ADDR_NO_RESULT_EN
    return data, None


def _display_has_postcode_match(user_postcode: str, display: str) -> bool:
    """display 中是否出现与用户邮编前 3 位一致的区域（仅用于 API 未拆出 city/postcode 时的兜底）。"""
    if not user_postcode or not display:
        return False
    if user_postcode in display:
        return True
    pc3 = _postcode_first3(user_postcode)
    if not pc3:
        return False
    disp_digits = _re.sub(r"\D", "", display)
    return pc3 in disp_digits


async def check_address(address: str) -> ValResult:
    """
    1. check_address(address: str)
    只验证 城市与邮编是否一致；不校验书写格式。
    调用 LocationIQ 后比对：城市、邮编一致即通过。
    ✅ 完全匹配 → Address verified
    ⚠️ 部分匹配 → Did you mean? + 建议地址
    ❌ 不匹配   → Address not found / 城市不匹配 / 邮编不匹配
    """
    addr_stripped = (address or "").strip()
    if len(addr_stripped) < 3:
        return ValResult(False, MSG_ADDR_INVALID_EN, MSG_ADDR_INVALID_ZH)

    data, err = await _fetch_geocode(address)
    if err:
        msg_zh = {
            MSG_ADDR_INVALID_EN: MSG_ADDR_INVALID_ZH,
            MSG_ADDR_API_ERR_EN: MSG_ADDR_API_ERR_ZH,
            MSG_ADDR_NO_RESULT_EN: MSG_ADDR_NO_RESULT_ZH,
        }.get(err, MSG_ADDR_INVALID_ZH)
        if "LOCATIONIQ_API_KEY" in err:
            msg_zh = "地址验证需要配置 LOCATIONIQ_API_KEY。"
        return ValResult(False, err, msg_zh)

    best = data[0]
    display = best.get("display_name", address)
    addr_obj = best.get("address") or {}
    country_code = (addr_obj.get("country_code") or "").upper()
    country_name = addr_obj.get("country", "")

    # 回传比对：首条结果含城市与邮编时，必须与用户输入一致；若 API 未返回 city/postcode，则用 display 与用户邮编做备用校验（兼容如 New York, NY 10017 等仅 display 完整的情况）
    api_city = _extract_city_from_api(best)
    api_postcode = _extract_postcode_from_api(best)
    if not api_city or not api_postcode:
        user_postcode = _postcode_from_user_input(addr_stripped)
        if user_postcode and _display_has_postcode_match(user_postcode, display or ""):
            return ValResult(
                True,
                MSG_ADDR_OK_EN,
                MSG_ADDR_OK_ZH,
                value=display,
                suggestions=[],
                country_code=country_code or None,
                country_name=country_name or None,
            )
        return ValResult(False, MSG_ADDR_NO_RESULT_EN, MSG_ADDR_NO_RESULT_ZH)
    mismatch = _city_postcode_match(addr_stripped, api_city, api_postcode)
    if mismatch is not None:
        msg_en, msg_zh = mismatch
        return ValResult(False, msg_en, msg_zh)

    # 建议列表仅保留城市、邮编与用户输入一致的结果；API 未返回 city/postcode 的条目不纳入，避免出现「Did you mean? Miami Lakes 33014」当用户输入 Miami 33101
    suggestions = []
    for item in data[1:5]:
        dn = item.get("display_name", "")
        if not dn:
            continue
        c = _extract_city_from_api(item)
        p = _extract_postcode_from_api(item)
        if not c and not p:
            continue
        if _city_postcode_match(addr_stripped, c, p) is None:
            suggestions.append(dn)

    # ✅ 完全匹配：仅 1 条结果 或 无符合城市/邮编的其它建议
    # ⚠️ 部分匹配：有多条结果且存在城市/邮编一致的建议
    if not suggestions:
        return ValResult(
            True,
            MSG_ADDR_OK_EN,
            MSG_ADDR_OK_ZH,
            value=display,
            suggestions=[],
            country_code=country_code or None,
            country_name=country_name or None,
        )
    # 多条结果：城市与邮编已与首条一致，保留建议列表
    return ValResult(
        True,
        MSG_ADDR_SUGGEST_EN,
        MSG_ADDR_SUGGEST_ZH,
        value=display,
        suggestions=suggestions,
        country_code=country_code or None,
        country_name=country_name or None,
    )


async def suggest_address(address: str) -> ValResult:
    """
    2. suggest_address(address: str)
    当地址部分匹配时，返回 LocationIQ 建议的标准格式地址
    前端返回英文、后端返回中文
    """
    data, err = await _fetch_geocode(address)
    if err:
        msg_zh = {
            MSG_ADDR_INVALID_EN: MSG_ADDR_INVALID_ZH,
            MSG_ADDR_API_ERR_EN: MSG_ADDR_API_ERR_ZH,
            MSG_ADDR_NO_RESULT_EN: MSG_ADDR_NO_RESULT_ZH,
        }.get(err, MSG_ADDR_INVALID_ZH)
        if "LOCATIONIQ_API_KEY" in err:
            msg_zh = "地址验证需要配置 LOCATIONIQ_API_KEY。"
        return ValResult(False, err, msg_zh, suggestions=[])

    suggestions: List[str] = [item.get("display_name", "") for item in data if item.get("display_name")]
    if not suggestions:
        return ValResult(False, MSG_ADDR_NO_RESULT_EN, MSG_ADDR_NO_RESULT_ZH, suggestions=[])

    return ValResult(
        True,
        "Suggested addresses retrieved.",
        "已获取建议地址。",
        value=suggestions[0] if suggestions else None,
        suggestions=suggestions,
    )


async def verify_country(address: str) -> ValResult:
    """
    3. verify_country(address: str)
    从 LocationIQ 返回结果提取国家代码
    前端返回英文、后端返回中文
    """
    data, err = await _fetch_geocode(address)
    if err:
        msg_zh = {
            MSG_ADDR_INVALID_EN: MSG_ADDR_INVALID_ZH,
            MSG_ADDR_API_ERR_EN: MSG_ADDR_API_ERR_ZH,
            MSG_ADDR_NO_RESULT_EN: MSG_ADDR_NO_RESULT_ZH,
        }.get(err, MSG_ADDR_INVALID_ZH)
        if "LOCATIONIQ_API_KEY" in err:
            msg_zh = "地址验证需要配置 LOCATIONIQ_API_KEY。"
        return ValResult(False, err, msg_zh)

    best = data[0]
    addr_obj = best.get("address") or {}
    country_code = (addr_obj.get("country_code") or "").upper()
    country_name = addr_obj.get("country", "")

    if not country_code:
        return ValResult(False, MSG_COUNTRY_INVALID_EN, MSG_COUNTRY_INVALID_ZH)

    return ValResult(
        True,
        MSG_COUNTRY_OK_EN,
        MSG_COUNTRY_OK_ZH,
        country_code=country_code,
        country_name=country_name or None,
    )


async def validate_address(address: str) -> ValResult:
    """兼容旧接口：等同于 check_address"""
    return await check_address(address)


async def validate_country(address: str, expected_country: Optional[str] = None) -> ValResult:
    """
    国家验证：验证地址所属国家，可选与期望国家比对
    expected_country: ISO 3166-1 两位国家码，如 US, CN
    """
    result = await validate_address(address)
    if not result.valid:
        return result

    if not result.country_code:
        return ValResult(False, MSG_COUNTRY_INVALID_EN, MSG_COUNTRY_INVALID_ZH)

    if expected_country:
        exp = str(expected_country).strip().upper()[:2]
        if result.country_code != exp:
            return ValResult(
                False,
                f"Country mismatch. Expected {exp}, got {result.country_code}.",
                f"国家不匹配。期望 {exp}，实际 {result.country_code}。",
                country_code=result.country_code,
                country_name=result.country_name,
            )

    return ValResult(
        True,
        MSG_COUNTRY_OK_EN,
        MSG_COUNTRY_OK_ZH,
        country_code=result.country_code,
        country_name=result.country_name,
    )
