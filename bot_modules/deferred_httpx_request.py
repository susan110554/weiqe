"""
PTB 的 HTTPXRequest 在 __init__ 里同步创建 httpx.AsyncClient；在部分环境（新版 httpcore + Linux）
会触发 sniffio.AsyncLibraryNotFoundError。此类把 AsyncClient 推迟到 initialize()（已在 asyncio 循环内）再创建。
行为与 telegram.request.HTTPXRequest（20.7）一致，逻辑同步自其 __init__。
"""
from __future__ import annotations

from collections.abc import Collection
from typing import Optional, Tuple, Union

import httpx
from telegram._utils.types import HTTPVersion, ODVInput, SocketOpt
from telegram._utils.warnings import warn
from telegram.request import BaseRequest, HTTPXRequest, RequestData
from telegram.warnings import PTBDeprecationWarning


class DeferredHTTPXRequest(HTTPXRequest):
    """与 HTTPXRequest 相同参数；仅在 await initialize() 时创建底层 AsyncClient。"""

    def __init__(
        self,
        connection_pool_size: int = 1,
        proxy_url: Optional[Union[str, httpx.Proxy, httpx.URL]] = None,
        read_timeout: Optional[float] = 5.0,
        write_timeout: Optional[float] = 5.0,
        connect_timeout: Optional[float] = 5.0,
        pool_timeout: Optional[float] = 1.0,
        http_version: HTTPVersion = "1.1",
        socket_options: Optional[Collection[SocketOpt]] = None,
        proxy: Optional[Union[str, httpx.Proxy, httpx.URL]] = None,
    ):
        if proxy_url is not None and proxy is not None:
            raise ValueError("The parameters `proxy_url` and `proxy` are mutually exclusive.")

        if proxy_url is not None:
            proxy = proxy_url
            warn(
                "The parameter `proxy_url` is deprecated since version 20.7. Use `proxy` "
                "instead.",
                PTBDeprecationWarning,
                stacklevel=2,
            )

        self._http_version = http_version
        timeout = httpx.Timeout(
            connect=connect_timeout,
            read=read_timeout,
            write=write_timeout,
            pool=pool_timeout,
        )
        limits = httpx.Limits(
            max_connections=connection_pool_size,
            max_keepalive_connections=connection_pool_size,
        )

        if http_version not in ("1.1", "2", "2.0"):
            raise ValueError("`http_version` must be either '1.1', '2.0' or '2'.")

        http1 = http_version == "1.1"
        http_kwargs = {"http1": http1, "http2": not http1}
        transport = (
            httpx.AsyncHTTPTransport(
                socket_options=socket_options,
            )
            if socket_options
            else None
        )
        self._client_kwargs = {
            "timeout": timeout,
            "proxies": proxy,
            "limits": limits,
            "transport": transport,
            **http_kwargs,
        }
        self._client = None

    @property
    def read_timeout(self) -> Optional[float]:
        if self._client is None:
            return self._client_kwargs["timeout"].read
        return self._client.timeout.read

    async def initialize(self) -> None:
        if self._client is None:
            try:
                self._client = self._build_client()
            except ImportError as exc:
                if "httpx[http2]" not in str(exc) and "httpx[socks]" not in str(exc):
                    raise exc
                if "httpx[socks]" in str(exc):
                    raise RuntimeError(
                        "To use Socks5 proxies, PTB must be installed via `pip install "
                        '"python-telegram-bot[socks]"`.'
                    ) from exc
                raise RuntimeError(
                    "To use HTTP/2, PTB must be installed via `pip install "
                    '"python-telegram-bot[http2]"`.'
                ) from exc
        await super().initialize()

    async def shutdown(self) -> None:
        if self._client is None:
            return
        await super().shutdown()

    async def do_request(
        self,
        url: str,
        method: str,
        request_data: Optional[RequestData] = None,
        read_timeout: ODVInput[float] = BaseRequest.DEFAULT_NONE,
        write_timeout: ODVInput[float] = BaseRequest.DEFAULT_NONE,
        connect_timeout: ODVInput[float] = BaseRequest.DEFAULT_NONE,
        pool_timeout: ODVInput[float] = BaseRequest.DEFAULT_NONE,
    ) -> Tuple[int, bytes]:
        if self._client is None:
            raise RuntimeError("This HTTPXRequest is not initialized!")
        return await super().do_request(
            url,
            method,
            request_data=request_data,
            read_timeout=read_timeout,
            write_timeout=write_timeout,
            connect_timeout=connect_timeout,
            pool_timeout=pool_timeout,
        )
