"""
结构化日志上下文 + 进程内指标（单进程 polling 场景）。
- 通过 ContextVar 在日志中串联 corr_id / tg_user_id / case_no / job_id
- 指标定期以单条 INFO 日志输出，便于外部采集（grep METRICS_SNAPSHOT）
"""

from __future__ import annotations

import contextvars
import json
import logging
import threading
import uuid
from collections import Counter
from typing import Any

from .runtime_config import rt

logger = logging.getLogger(__name__)

corr_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("corr_id", default=None)
tg_user_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "tg_user_id", default=None
)
case_no_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("case_no", default=None)
job_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("job_id", default=None)


class _Metrics:
    def __init__(self) -> None:
        self._c: Counter[str] = Counter()
        self._lock = threading.Lock()

    def inc(self, key: str, n: int = 1) -> None:
        with self._lock:
            self._c[key] += n

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(self._c)


metrics = _Metrics()


class ContextFilter(logging.Filter):
    """为每条 LogRecord 注入上下文字段（供 Formatter 使用）。"""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "corr_id"):
            record.corr_id = corr_id_var.get() or "-"
        if not hasattr(record, "tg_user_id"):
            record.tg_user_id = tg_user_id_var.get() or "-"
        if not hasattr(record, "case_no"):
            record.case_no = case_no_var.get() or "-"
        if not hasattr(record, "job_id"):
            record.job_id = job_id_var.get() or "-"
        return True


STRUCTURED_FORMAT = (
    "%(asctime)s [%(levelname)s] %(name)s "
    "corr=%(corr_id)s tg=%(tg_user_id)s case=%(case_no)s job=%(job_id)s | %(message)s"
)


def setup_logging() -> None:
    """在已有 basicConfig 基础上挂载 Filter；STRUCTURED_LOG=1 时切换 Formatter。"""
    root = logging.getLogger()
    if getattr(root, "_ic3_obs_configured", False):
        return
    root._ic3_obs_configured = True  # type: ignore[attr-defined]
    flt = ContextFilter()
    for h in root.handlers:
        h.addFilter(flt)
        if rt.STRUCTURED_LOG:
            h.setFormatter(logging.Formatter(STRUCTURED_FORMAT))


def new_correlation_id() -> str:
    return f"{rt.LOG_CORRELATION_PREFIX}-{uuid.uuid4().hex[:10]}"


def bind_update(update: Any) -> None:
    """从 Telegram Update 提取用户 ID，并生成本次处理 corr_id。"""
    corr_id_var.set(new_correlation_id())
    tg_user_id_var.set("-")
    try:
        u = getattr(update, "effective_user", None)
        if u is not None and getattr(u, "id", None) is not None:
            tg_user_id_var.set(str(u.id))
    except Exception:
        pass


def set_case_no(case_no: str | None) -> None:
    if case_no:
        case_no_var.set((case_no or "").strip().upper()[:64])
    else:
        case_no_var.set("-")


def set_job_id(job_id: int | str | None) -> None:
    if job_id is None:
        job_id_var.set("-")
    else:
        job_id_var.set(str(job_id))


def bind_case_progress(case_no: str, job_id: int) -> None:
    set_case_no(case_no)
    set_job_id(job_id)


def clear_case_job() -> None:
    case_no_var.set("-")
    job_id_var.set("-")


def clear_correlation() -> None:
    corr_id_var.set(None)
    tg_user_id_var.set(None)
    case_no_var.set(None)
    job_id_var.set(None)


async def metrics_emit_loop(app: Any) -> None:
    import asyncio

    import database as db

    await asyncio.sleep(30)
    while True:
        try:
            if not rt.FEATURE_METRICS_EMIT:
                await asyncio.sleep(rt.METRICS_EMIT_INTERVAL_SEC)
                continue
            snap = metrics.snapshot()
            pending_cp = 0
            pending_pay = 0
            pool_size = idle = -1
            try:
                pending_cp = await db.case_progress_pending_count()
            except Exception:
                pass
            try:
                pending_pay = await db.cryptopay_pending_sessions_count()
            except Exception:
                pass
            try:
                pool = await db.get_pool()
                pool_size = pool.get_size()
                idle = pool.get_idle_size()
            except Exception:
                pass
            payload = {
                "counters": snap,
                "case_progress_pending": pending_cp,
                "cryptopay_sessions_pending": pending_pay,
                "db_pool_size": pool_size,
                "db_pool_idle": idle,
                "copy_version": rt.IC3_COPY_VERSION,
            }
            logging.getLogger("ic3.metrics").info("METRICS_SNAPSHOT %s", json.dumps(payload))
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("[metrics] emit loop")
        await asyncio.sleep(rt.METRICS_EMIT_INTERVAL_SEC)
