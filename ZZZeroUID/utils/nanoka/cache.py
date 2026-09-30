"""wiki 数据的 JSON 与绘图缓存。

JSON 与渲染结果都落盘，并带进程内 single-flight，避免并发重复下载/重复渲染。
"""

import json
import asyncio
import hashlib
from pathlib import Path
from collections.abc import Callable, Awaitable

from gsuid_core.pool import to_thread
from gsuid_core.logger import logger

from .json_node import JsonNode
from ..resource.RESOURCE_PATH import WIKI_PATH

JSON_CACHE_DIR = WIKI_PATH / "nanoka"
IMAGE_CACHE_DIR = WIKI_PATH / "img"
ASSET_CACHE_DIR = WIKI_PATH / "asset"

_json_memo: dict[str, JsonNode] = {}
_image_memo: dict[str, bytes] = {}
_json_locks: dict[str, asyncio.Lock] = {}
_image_locks: dict[str, asyncio.Lock] = {}


def _slug(raw: str) -> str:
    """把任意入参压成安全的文件名。"""
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    tail = "".join(c if (c.isalnum() or c in "-_") else "_" for c in raw)[:48]
    return f"{tail}_{digest}" if tail else digest


def _lock(registry: dict[str, asyncio.Lock], key: str) -> asyncio.Lock:
    lock = registry.get(key)
    if lock is None:
        lock = asyncio.Lock()
        registry[key] = lock
    return lock


def _read(path: Path) -> bytes | None:
    if not path.exists():
        return None
    return path.read_bytes()


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _decode(data: bytes) -> object:
    return json.loads(data.decode("utf-8"))


_read_bg = to_thread(_read)
_write_bg = to_thread(_write)
_decode_bg = to_thread(_decode)


async def load_json(key: str, fetch: Callable[[], Awaitable[str]]) -> JsonNode:
    """取 JSON 文本：内存 -> 磁盘 -> 网络，命中任一层即返回。"""
    memo = _json_memo.get(key)
    if memo is not None:
        return memo

    async with _lock(_json_locks, key):
        memo = _json_memo.get(key)
        if memo is not None:
            return memo

        path = JSON_CACHE_DIR / f"{_slug(key)}.json"
        raw = await _read_bg(path)
        if raw is not None:
            node = JsonNode(await _decode_bg(raw))
            _json_memo[key] = node
            return node

        text = await fetch()
        data = text.encode("utf-8")
        await _write_bg(path, data)
        node = JsonNode(await _decode_bg(data))
        _json_memo[key] = node
        logger.info(f"[绝区零][wiki] 缓存上游数据: {key}")
        return node


async def load_image(key: str, build: Callable[[], Awaitable[bytes]]) -> bytes:
    """取渲染结果：内存 -> 磁盘 -> 重新渲染。"""
    memo = _image_memo.get(key)
    if memo is not None:
        return memo

    async with _lock(_image_locks, key):
        memo = _image_memo.get(key)
        if memo is not None:
            return memo

        path = IMAGE_CACHE_DIR / f"{_slug(key)}.png"
        raw = await _read_bg(path)
        if raw is not None:
            _image_memo[key] = raw
            return raw

        data = await build()
        await _write_bg(path, data)
        _image_memo[key] = data
        return data


def warm_up() -> None:
    """确保缓存目录存在。"""
    JSON_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    ASSET_CACHE_DIR.mkdir(parents=True, exist_ok=True)


async def load_asset(code_name: str, fetch: Callable[[], Awaitable[bytes]]) -> bytes | None:
    """取上游静态素材（怪物图等），只下载一次。"""
    if not code_name:
        return None
    path = ASSET_CACHE_DIR / f"{code_name}.webp"
    raw = await _read_bg(path)
    if raw is not None:
        return raw
    data = await fetch()
    if not data:
        return None
    await _write_bg(path, data)
    logger.info(f"[绝区零][wiki] 缓存上游素材: {code_name}")
    return data
