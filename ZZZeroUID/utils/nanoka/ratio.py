"""技能倍率。

上游有两种写法，都是「文本里放占位符，真实数值放在别处」：

- 角色：``description[].param[] = {name, desc, param}``，``param`` 直接内联了
  ``{main, growth, format}``，占位符只在 ``desc`` 里
- 邦布：``level.{n}.param`` 是 ``|`` 分隔的字符串，形如
  ``{Skill:5300101, Prop:1001}``，要回 ``skill_prop`` 查

``main`` 是 1 级数值，``growth`` 是每级增量，曲线线性。
"""

import re
from typing import Final

from .json_node import JsonNode

#: ``{Skill:5300101, Prop:1001}``
REF: Final[re.Pattern[str]] = re.compile(r"\{Skill:(\d+),\s*Prop:(\d+)\}")

#: 倍率表默认展示的等级。12 来自上游 ``material`` 的档位数（各技能组一致）。
STEPS: Final[tuple[int, ...]] = (1, 5, 10, 12)


def at_level(main: int, growth: int, level: int) -> int:
    """1 级 ``main``、每级 ``growth``，线性外推到 ``level``。"""
    return main + growth * (level - 1)


def from_node(node: JsonNode) -> tuple[int, int, str]:
    """从内联的 ``{main, growth, format}`` 节点取值。"""
    return node.at("main").as_int(), node.at("growth").as_int(), node.at("format").as_str()


def resolve(table: JsonNode, ref: str) -> tuple[int, int, str] | None:
    """把 ``{Skill:x, Prop:y}`` 解析成 ``skill_prop`` 里的三元组。"""
    matched = REF.fullmatch(ref.strip())
    if matched is None:
        return None
    prop = table.at(matched.group(1)).maybe(matched.group(2))
    if prop is None:
        return None
    return from_node(prop)


def split_params(raw: str) -> list[str]:
    """``|`` 分隔的参数列表，去掉空段。"""
    return [part.strip() for part in raw.split("|") if part.strip()]
