"""TRC-20 / 任意钱包地址 → PNG 二维码（供 Telegram send_photo / reply_photo）。"""

from __future__ import annotations

import io
import logging

logger = logging.getLogger(__name__)


def wallet_address_to_qr_png(
    address: str,
    *,
    box_size: int = 8,
    border: int = 2,
) -> bytes | None:
    """
    将地址字符串编码为 QR（原始文本，无 URI 前缀）。
    失败时返回 None（调用方回退为纯文本）。
    """
    raw = (address or "").strip()
    if not raw:
        return None
    try:
        import qrcode
        from qrcode.constants import ERROR_CORRECT_M

        qr = qrcode.QRCode(
            version=None,
            error_correction=ERROR_CORRECT_M,
            box_size=box_size,
            border=border,
        )
        qr.add_data(raw)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        logger.exception("wallet_address_to_qr_png failed")
        return None
