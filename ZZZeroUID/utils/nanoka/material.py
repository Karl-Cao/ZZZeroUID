"""突破材料的 id -> 官方名称 / 图标。

上游只给材料 id，名称和图标都在 ``zh/item.json``（5980 条）里：
``{"10": {"name": "丁尼", "icon": "Assets/.../IconCoin.png", ...}}``。
``:func:`load_index` 载入后，:func:`make` 就能给出真名与图标代号。

别再按 id 前缀猜名字 —— 实测前缀猜测基本全错：
``101010`` 是「强攻组件」不是音擎突破材料，``102010`` 是「以太电解液」
不是邦布升级材料，``10`` 是「丁尼」不是贝拉币。
"""

from typing import Final

from .json_node import JsonNode

#: item id -> (官方名称, 图标代号)
_INDEX: dict[str, tuple[str, str]] = {}


def _icon_code(path: str) -> str:
    """``Assets/.../IconCoin.png`` -> ``IconCoin``（CDN 上是 ``<code>.webp``）。"""
    tail = path.rsplit("/", 1)[-1]
    return tail.rsplit(".", 1)[0]


def load_index(node: JsonNode) -> None:
    """载入 ``item.json``。重复调用是幂等的。"""
    for key, item in node.items():
        if not key.isdigit():
            continue
        _INDEX[key] = (item.at("name").as_str(), _icon_code(item.at("icon").as_str()))


class Material:
    """一条材料。"""

    __slots__ = ("icon", "item_id", "name", "number", "tier")

    def __init__(self, item_id: str, number: int, name: str, icon: str) -> None:
        self.item_id = item_id
        self.number = number
        self.name = name
        self.icon = icon
        self.tier = _tier_of(item_id)


def _tier_of(item_id: str) -> int:
    """档位编码在倒数第二位：X1 初级 / X2 中级 / X3 高级 / X4+ 顶级。

    只用于「拉不到官方图标」时的兜底色徽章，恒在 ``1..4``。
    """
    if len(item_id) < 2 or not item_id.isdigit():
        return 4
    tens = int(item_id[-2])
    if tens <= 1:
        return 1
    if tens == 2:
        return 2
    if tens == 3:
        return 3
    return 4


def make(item_id: str, number: int) -> Material:
    """构造一条材料；``item.json`` 里没有的 id 退化成纯数字名。"""
    clean = item_id.strip()
    if not clean.isdigit():
        raise ValueError(f"非法的材料 id: {item_id!r}")
    found = _INDEX.get(clean)
    if found is None:
        return Material(item_id=clean, number=number, name=f"材料 {clean}", icon="")
    return Material(item_id=clean, number=number, name=found[0], icon=found[1])


def parse_pair(block: str) -> list[Material]:
    """解析上游的 ``"10:12000,101010:4"`` 材料块，数量为 0 的丢弃。"""
    out: list[Material] = []
    for pair in block.split(","):
        if ":" not in pair:
            continue
        item_id, _, raw = pair.partition(":")
        if not item_id.strip().isdigit() or not raw.strip().isdigit():
            continue
        count = int(raw)
        if count == 0:
            continue
        out.append(make(item_id.strip(), count))
    return out


def parse_stages(raw: str) -> list[list[Material]]:
    """音擎的 5 阶精炼材料，``|`` 分隔。"""
    if not raw:
        return []
    return [parse_pair(block) for block in raw.split("|") if block.strip()]


#: 局内货币。``item.json`` 里同样有图标（丁尼 = ``IconCoin``），
#: 只在没有图标时代价才不同，保留下来给「确实取不到素材」的场合兜底。
CURRENCY: Final[frozenset[str]] = frozenset({"10"})
