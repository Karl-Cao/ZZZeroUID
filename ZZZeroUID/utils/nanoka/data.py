"""高层取数：名称解析、期次选择、实体装配。

渲染层只调用这里的方法，不直接碰 :mod:`~.source` 与 URL。
"""

from typing import Final
from datetime import datetime
from dataclasses import field, dataclass

from . import element as el, material
from .urls import IndexKind
from .source import get_source
from .json_node import JsonNode
from ..name_convert import alias_to_char_name

#: 危局强袭战在 boss 索引里的 zone_type；1001 是式舆试炼，1002 是异构挑战
HAEDAL_ZONE = 1001
_HARD_ZONE = 1002

#: 式舆索引里 sort=1 的是按周轮换的剧变节点，2/3/4 是常驻的稳定/纷争/奇袭节点
SHIYU_ROTATE_SORT = 1

_PERIOD_EMPTY: Final[str] = ""


@dataclass(frozen=True, slots=True)
class Period:
    """一个可查询的期次。"""

    key: str
    label: str
    begin: datetime | None
    end: datetime | None


@dataclass(slots=True)
class Monster:
    """怪物条目。"""

    key: str
    name: str
    image_code: str
    element: int
    hp: int
    weakness: list[int] = field(default_factory=list)
    resistance: list[int] = field(default_factory=list)
    rarity: int = 1
    desc: str = ""


# ---------------------------------------------------------------- 索引解析
async def _index(kind: IndexKind) -> JsonNode:
    return await get_source().index(kind)


#: item 索引只载入一次
_ITEMS: JsonNode | None = None


async def items() -> JsonNode:
    """``zh/item.json``，材料名与图标的唯一来源。"""
    global _ITEMS
    if _ITEMS is None:
        _ITEMS = await _index("item")
        material.load_index(_ITEMS)
    return _ITEMS


async def find_character(query: str) -> tuple[str, str]:
    """按名称/简称/错字找角色 id，返回 ``(id, 名称)``。"""
    name = alias_to_char_name(query.strip())
    node = await _index("character")
    for key, item in node.items():
        if item.at("zh").as_str() == name:
            return key, name
    for key, item in node.items():
        if item.at("code").as_str().lower() == name.lower():
            return key, item.at("zh").as_str()
    for key, item in node.items():
        if name in item.at("zh").as_str():
            return key, item.at("zh").as_str()
    raise LookupError(query)


async def find_weapon(query: str) -> tuple[str, str]:
    """按名称找音擎 id。"""
    name = query.strip()
    node = await _index("weapon")
    for key, item in node.items():
        if item.at("zh").as_str() == name:
            return key, name
    for key, item in node.items():
        if name in item.at("zh").as_str():
            return key, item.at("zh").as_str()
    raise LookupError(query)


async def find_equipment(query: str) -> tuple[str, str]:
    """按名称找驱动盘套装 id。"""
    name = query.strip()
    node = await _index("equipment")
    for key, item in node.items():
        zh = item.at("zh")
        if zh.has("name") and zh.at("name").as_str() == name:
            return key, name
    for key, item in node.items():
        zh = item.at("zh")
        if zh.has("name") and name in zh.at("name").as_str():
            return key, zh.at("name").as_str()
    raise LookupError(query)


async def find_bangboo(query: str) -> tuple[str, str]:
    """按名称找邦布 id。"""
    name = query.strip()
    node = await _index("bangboo")
    for key, item in node.items():
        if item.at("zh").as_str() == name:
            return key, name
    for key, item in node.items():
        if name in item.at("zh").as_str():
            return key, item.at("zh").as_str()
    raise LookupError(query)


async def find_monster(query: str) -> tuple[str, str]:
    """按名称找怪物 id。"""
    name = query.strip()
    node = await _index("monster")
    for key, item in node.items():
        if item.at("zh").as_str() == name:
            return key, name
    for key, item in node.items():
        if name in item.at("zh").as_str():
            return key, item.at("zh").as_str()
    raise LookupError(query)


# ---------------------------------------------------------------- 期次选择
def _parse_dt(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def _sort_key(key: str) -> tuple[int, int]:
    """按 (主段, 次段) 排序，让 620621 排在 62060 之后。"""
    head = key[:5]
    tail = key[5:]
    if head.isdigit() and tail.isdigit():
        return int(head), int(tail)
    if key.isdigit():
        return int(key), 0
    return 0, 0


def _dt_of(node: JsonNode, key: str) -> datetime | None:
    """时间窗字段在上游时有时无，缺失一律当空。"""
    child = node.maybe(key)
    if child is None:
        return None
    return _parse_dt(child.as_str(_PERIOD_EMPTY))


def _period_key(period: Period) -> tuple[int, int]:
    return _sort_key(period.key)


async def haedal_periods() -> list[Period]:
    """危局强袭战期次，按时间排；无时间的排在最后。"""
    node = await _index("boss")
    out: list[Period] = []
    for key, item in node.items():
        if item.at("zone_type").as_int() != HAEDAL_ZONE:
            continue
        out.append(
            Period(
                key=key,
                label=f"第 {key} 期",
                begin=_dt_of(item, "live_begin"),
                end=_dt_of(item, "live_end"),
            )
        )
    out.sort(key=lambda p: (p.begin is None, p.begin or datetime.max, p.key))
    return out


async def simul_periods() -> list[Period]:
    """临界推演期次。"""
    node = await _index("simul")
    out: list[Period] = []
    for key, item in node.items():
        out.append(Period(key=key, label=f"第 {key} 期", begin=None, end=_dt_of(item, "end")))
    out.sort(key=_period_key)
    return out


async def hard_periods() -> list[Period]:
    """拟境湮灭战期次。"""
    node = await _index("hard")
    out: list[Period] = []
    for key, item in node.items():
        out.append(
            Period(
                key=key,
                label=item.at("zh").as_str("拟境湮灭战"),
                begin=_dt_of(item, "start_time"),
                end=_dt_of(item, "end_time"),
            )
        )
    out.sort(key=_period_key)
    return out


async def shiyu_periods() -> list[Period]:
    """式舆防卫战期次：``sort=1`` 的剧变节点按周轮换，其余是常驻节点。"""
    node = await _index("shiyu")
    out: list[Period] = []
    for key, item in node.items():
        if item.at("sort").as_int() != SHIYU_ROTATE_SORT:
            continue
        out.append(
            Period(
                key=key,
                label=item.at("zh").as_str("剧变节点"),
                begin=_dt_of(item, "live_begin"),
                end=_dt_of(item, "live_end"),
            )
        )
    out.sort(key=_period_key)
    return out


def pick(periods: list[Period], selector: str) -> Period:
    """按 ``上期``/``下期``/``2026.9.1``/``id`` 选期。"""
    if not periods:
        raise LookupError("没有可用期次")

    text = selector.strip()
    if text in ("", "本期", "当前", "现在"):
        for period in reversed(periods):
            if _live(period):
                return period
        return periods[-1]
    if text in ("上期", "上一期", "历史"):
        return _step(periods, -1)
    if text in ("下期", "下一期", "未来"):
        return _step(periods, 1)

    stamp = _parse_selector_date(text)
    if stamp is not None:
        for period in periods:
            if period.begin is None or period.end is None:
                continue
            if period.begin <= stamp <= period.end:
                return period
        raise LookupError(f"没有覆盖 {text} 的期次")

    for period in periods:
        if period.key == text:
            return period
    raise LookupError(text)


def _step(periods: list[Period], offset: int) -> Period:
    if offset < 0:
        live = [p for p in periods if _live(p)]
        anchor = live[0] if live else periods[0]
        idx = periods.index(anchor)
        return periods[max(0, idx + offset)]
    if offset > 0:
        live = [p for p in periods if _live(p)]
        anchor = live[-1] if live else periods[-1]
        idx = periods.index(anchor)
        return periods[min(len(periods) - 1, idx + offset)]
    return periods[-1]


def _live(period: Period) -> bool:
    if period.begin is None or period.end is None:
        return False
    now = datetime.now()
    return period.begin <= now <= period.end


def _parse_selector_date(text: str) -> datetime | None:
    for sep in (".", "-", "/", "年"):
        cleaned = text.replace(sep, "-")
        cleaned = cleaned.replace("月", "-").replace("日", "")
        parts = cleaned.split("-")
        if len(parts) < 3:
            continue
        try:
            return datetime(int(parts[0]), int(parts[1]), int(parts[2]))
        except (ValueError, IndexError):
            continue
    return None


# ---------------------------------------------------------------- 怪物装配
def _flat(node: JsonNode) -> dict[str, int]:
    out: dict[str, int] = {}
    for key, value in node.items():
        out[key] = value.as_int()
    return out


def _code_of(path: str) -> str:
    """``UI/.../Monster_X_HC.png`` -> ``Monster_X_HC``。"""
    tail = path.rsplit("/", 1)[-1]
    return tail.rsplit(".", 1)[0]


def _element_ids_from_keys(node: JsonNode) -> list[int]:
    """``monster_weakness`` / ``monster_resistance`` 以属性 id 为键。"""
    out: list[int] = []
    for key, _ in node.items():
        if key.lstrip("-").isdigit():
            out.append(int(key))
    return out


def monsters_of_room(room: JsonNode) -> list[Monster]:
    """从一个 ``layer_room`` 节点里取出全部怪物。"""
    out: list[Monster] = []
    listing = room.maybe("monster_list")
    if listing is None:
        return out
    for key, item in listing.items():
        out.append(
            Monster(
                key=key,
                name=item.at("name").as_str(),
                image_code=_code_of(item.at("image").as_str()),
                element=el.dominant_element(_flat(item.at("element"))),
                hp=item.at("stats").at("hp").as_int(),
            )
        )
    return out


def decorate(room: JsonNode, monsters: list[Monster]) -> None:
    """给怪物补上弱点 / 抗性（房间级信息，逐个下发）。"""
    weak_node = room.maybe("monster_weakness")
    res_node = room.maybe("monster_resistance")
    weak = _element_ids_from_keys(weak_node) if weak_node is not None else []
    res = _element_ids_from_keys(res_node) if res_node is not None else []
    for monster in monsters:
        monster.weakness = weak
        monster.resistance = res


async def monster_index_entry(monster_id: str) -> JsonNode | None:
    node = await _index("monster")
    if monster_id in node.keys():
        return node.at(monster_id)
    return None
