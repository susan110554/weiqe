"""
集中读取环境变量（费率、重试、功能开关、文案版本等），避免业务模块各自 os.getenv 分散。
业务代码可逐步改为从此处引用；未迁移的变量仍以各模块为准。
"""

from __future__ import annotations

import os


def _truthy(v: str | None) -> bool:
    return (v or "").strip().lower() in ("1", "true", "yes", "on")


class RuntimeConfig:
    """单例式配置命名空间（进程内只读）。"""

    STRUCTURED_LOG: bool = _truthy(os.getenv("STRUCTURED_LOG", "0"))
    METRICS_EMIT_INTERVAL_SEC: int = int(os.getenv("METRICS_EMIT_INTERVAL_SEC", "120"))
    LOG_CORRELATION_PREFIX: str = os.getenv("LOG_CORRELATION_PREFIX", "ic3")

    CASE_PROGRESS_MAX_PROCESS_FAILURES: int = int(
        os.getenv("CASE_PROGRESS_MAX_PROCESS_FAILURES", "3")
    )
    CASE_PROGRESS_RETRY_DELAY_MIN: int = int(
        os.getenv("CASE_PROGRESS_RETRY_DELAY_MIN", "5")
    )

    IC3_COPY_VERSION: str = os.getenv("IC3_COPY_VERSION", "3.4.0")

    FEATURE_METRICS_EMIT: bool = _truthy(os.getenv("FEATURE_METRICS_EMIT", "1"))
    FEATURE_DLQ_ADMIN: bool = _truthy(os.getenv("FEATURE_DLQ_ADMIN", "1"))

    CRYPTOPAY_TRC20_POOL: str = os.getenv("CRYPTOPAY_TRC20_POOL", "").strip()
    CRYPTOPAY_P5_AMOUNT_USD: float = float(os.getenv("CRYPTOPAY_P5_AMOUNT_USD", "50"))
    CRYPTOPAY_SESSION_MINUTES: int = int(os.getenv("CRYPTOPAY_SESSION_MINUTES", "30"))
    CRYPTOPAY_CONFIRMATIONS: int = int(os.getenv("CRYPTOPAY_CONFIRMATIONS", "3"))


rt = RuntimeConfig()
