"""wiki 上游数据源。

渲染层只认 :class:`WikiSource` 协议，不接触任何 URL。nanoka 失效时，
新增一个实现同样协议的类并 :func:`set_source` 即可整体切换。
"""

from typing import Protocol

import httpx

from gsuid_core.logger import logger

from . import urls
from .urls import IndexKind, DetailKind
from .cache import load_json
from .json_node import JsonNode

_TIMEOUT = 40.0
_HEADERS = {"user-agent": "gsuid-core/ZZZeroUID"}


class WikiSource(Protocol):
    """wiki 数据源协议。"""

    name: str

    async def index(self, kind: IndexKind) -> JsonNode:
        """取实体索引页。"""
        ...

    async def detail(self, kind: DetailKind, key: str) -> JsonNode:
        """取实体明细页。"""
        ...

    def asset(self, code_name: str) -> str:
        """把上游的素材代号解析为可直接下载的地址。"""
        ...


class NanokaSource:
    """https://zzz.nanoka.cc/ 的数据源实现。"""

    name = "nanoka"

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True, headers=_HEADERS)

    async def _get(self, url: str) -> str:
        resp = await self._client.get(url)
        if resp.status_code != 200:
            raise RuntimeError(f"nanoka 返回 {resp.status_code}: {url}")
        return resp.text

    async def index(self, kind: IndexKind) -> JsonNode:
        url = urls.index_url(kind)
        return await load_json(f"index:{kind}", lambda: self._get(url))

    async def detail(self, kind: DetailKind, key: str) -> JsonNode:
        url = urls.detail_url(kind, key)
        return await load_json(f"{kind}:{key}", lambda: self._get(url))

    def asset(self, code_name: str) -> str:
        return urls.asset_url(code_name)


_source: WikiSource = NanokaSource()


def get_source() -> WikiSource:
    """当前生效的数据源。"""
    return _source


def set_source(source: WikiSource) -> None:
    """替换数据源，同时清掉已缓存的上游数据。"""
    global _source
    _source = source
    logger.info(f"[绝区零][wiki] wiki 数据源已切换为: {source.name}")
