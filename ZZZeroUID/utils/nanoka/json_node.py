"""对上游 JSON 的类型安全包装。

渲染层不允许出现 ``dict.get`` / ``getattr`` 兜底，因此统一走本包装：
必填字段用 :meth:`JsonNode.at` 取（缺失即报错），可选字段用
:meth:`JsonNode.maybe` 取并由调用方显式判空。
"""

from typing import Final


class JsonNode:
    """包裹一个已解析的 JSON 值，提供显式的类型化访问。"""

    __slots__ = ("_raw",)

    def __init__(self, raw: object) -> None:
        self._raw = raw

    def raw(self) -> object:
        """返回底层值，仅用于调试输出。"""
        return self._raw

    # ---------- 存在性 ----------
    def has(self, key: str) -> bool:
        if not isinstance(self._raw, dict):
            return False
        return key in self._raw

    def maybe(self, key: str) -> "JsonNode | None":
        """取子节点，不存在时返回 None，由调用方显式处理。"""
        if not isinstance(self._raw, dict):
            return None
        if key not in self._raw:
            return None
        return JsonNode(self._raw[key])

    def at(self, key: str) -> "JsonNode":
        """取必填子节点，缺失即抛错。"""
        node = self.maybe(key)
        if node is None:
            raise KeyError(f"nanoka json 缺少字段: {key}")
        return node

    # ---------- 容器 ----------
    def is_obj(self) -> bool:
        return isinstance(self._raw, dict)

    def is_list(self) -> bool:
        return isinstance(self._raw, list)

    def is_str(self) -> bool:
        return isinstance(self._raw, str)

    def keys(self) -> "list[str]":
        if not isinstance(self._raw, dict):
            return []
        return list(self._raw.keys())

    def values(self) -> "list[JsonNode]":
        """子节点值，按上游顺序。

        上游同一语义时而用对象时而用数组（危局 ``modes`` 是数组，
        拟境 ``mode`` 是对象），所以这里两种都支持。
        """
        if isinstance(self._raw, list):
            return [JsonNode(v) for v in self._raw]
        if isinstance(self._raw, dict):
            return [JsonNode(v) for v in self._raw.values()]
        return []

    def items(self) -> "list[tuple[str, JsonNode]]":
        """按上游顺序返回键值对，索引页与明细页都依赖这个顺序。"""
        if isinstance(self._raw, dict):
            return [(k, JsonNode(v)) for k, v in self._raw.items()]
        if isinstance(self._raw, list):
            return [(str(i), JsonNode(v)) for i, v in enumerate(self._raw)]
        return []

    def size(self) -> int:
        if isinstance(self._raw, (dict, list, str)):
            return len(self._raw)
        return 0

    def is_empty(self) -> bool:
        return self.size() == 0

    # ---------- 标量 ----------
    def as_str(self, default: str = "") -> str:
        if isinstance(self._raw, str):
            return self._raw
        if isinstance(self._raw, (int, float)) and not isinstance(self._raw, bool):
            return str(self._raw)
        return default

    def as_int(self, default: int = 0) -> int:
        if isinstance(self._raw, bool):
            return default
        if isinstance(self._raw, int):
            return self._raw
        if isinstance(self._raw, float):
            return int(self._raw)
        if isinstance(self._raw, str) and self._raw.strip().lstrip("-").isdigit():
            return int(self._raw)
        return default

    def as_float(self, default: float = 0.0) -> float:
        if isinstance(self._raw, bool):
            return default
        if isinstance(self._raw, (int, float)):
            return float(self._raw)
        return default

    def as_bool(self, default: bool = False) -> bool:
        if isinstance(self._raw, bool):
            return self._raw
        return default

    # ---------- 文本清洗 ----------
    def str_list(self, sep: str = "") -> str:
        """拼接字符串型子节点，用于 ``layer_buff`` 这类纯文本列表。"""
        out: list[str] = []
        for node in self.values():
            text = node.as_str()
            if text:
                out.append(text)
        return sep.join(out)


def wrap(raw: object) -> JsonNode:
    """便捷入口。"""
    return JsonNode(raw)


EMPTY: Final[JsonNode] = JsonNode({})
