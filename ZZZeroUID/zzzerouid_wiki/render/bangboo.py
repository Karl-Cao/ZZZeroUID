"""``邦布介绍`` 卡片。

数据取自上游 ``zh/bangboo/{id}.json``：

- 面板数值 ``stats``（定长字典，值为 0 的属性不显示；``crit`` / ``crit_dmg`` /
  ``pen_ratio`` 上游按万分比存，显示时除 100）
- 技能 ``skill.{group}.level.{n}``，``param`` 是 ``|`` 分隔的字符串，倍率项写成
  ``{Skill:5300101, Prop:1001}``，真实数值（``main`` / ``growth``）在顶层 ``skill_prop``
- 升级材料 ``level.*.materials``

立绘优先用本地头像，但本地只有 152×186，放到页首宽会糊，所以小于
:data:`_LOCAL_MIN` 改走 CDN 原图。面板数值同样竖排进页首右侧。
"""

from typing import Final

from . import base, common
from ...utils.nanoka import data, ratio as rt, material as mat
from ...utils.nanoka.source import get_source
from ...utils.nanoka.json_node import JsonNode
from ...utils.resource.RESOURCE_PATH import SQUARE_BANGBOO

ACCENT: Final[str] = "#ffb454"
#: 邦布技能名不带「分类：」前缀，统一用主动技图标
SKILL_ICON: Final[str] = "Icon_CoreSkill"
#: 页首竖栏最多放几行
_RAIL_MAX: Final[int] = 8
#: 本地头像小于这个边长就改走 CDN 原图
_LOCAL_MIN: Final[int] = 512

#: ``bangboo.stats`` 键 -> 显示名
_STAT_LABEL: Final[dict[str, str]] = {
    "hp_max": "生命",
    "attack": "攻击",
    "defence": "防御",
    "break_stun": "失衡值",
    "element_abnormal_power": "异常精通",
    "crit": "暴击率",
    "pen_ratio": "贯穿值",
    "crit_dmg": "暴击伤害",
    "endurance": "耐力",
}
#: ``bangboo.stats`` 键 -> texture2d/prop 图标（缺失就没有图标）
_STAT_ICON: Final[dict[str, str]] = {
    "hp_max": "IconHpMax",
    "attack": "IconAttack",
    "defence": "IconDef",
    "crit": "IconCrit",
    "crit_dmg": "IconCritDam",
    "element_abnormal_power": "IconElementAbnormalPower",
    "pen_ratio": "IconPenValue",
    "break_stun": "IconBreakStun",
}
#: 上游按万分比存，显示时除 100
_PCT_STAT: Final[frozenset[str]] = frozenset({"crit", "crit_dmg", "pen_ratio"})


def _stat_lines(detail: JsonNode) -> list[str]:
    """面板数值逐行。``stats`` 是定长字典，值为 0 的属性不显示。"""
    stats = detail.maybe("stats")
    if stats is None:
        return []
    lines: list[str] = []
    for key, item in stats.items():
        if key not in _STAT_LABEL:
            continue
        value = item.as_int()
        if value == 0:
            continue
        shown = f"{value / 100:.1f}%" if key in _PCT_STAT else f"{value:,}"
        uri = base.prop_uri(_STAT_ICON[key], 40) if key in _STAT_ICON else ""
        lines.append(base.kv(_STAT_LABEL[key], base.esc(shown), uri))
    return lines


def _stat_block(detail: JsonNode) -> str:
    """竖栏放不下时的兜底：两列平铺。"""
    lines = _stat_lines(detail)
    if not lines:
        return ""
    half = (len(lines) + 1) // 2
    left = "".join(lines[:half])
    right = "".join(lines[half:])
    return base.section("面板数值", "STATS") + base.card(base.columns([left, right], 2))


def _skill_ratio(top: JsonNode, table: JsonNode, level: int) -> str:
    """技能倍率表。

    ``level.{n}.param`` 是 ``|`` 分隔的字符串，倍率项写成
    ``{Skill:5300101, Prop:1001}``，真实数值在顶层 ``skill_prop`` 里。
    非倍率项（冷却时间、60% 这类）原样显示。
    """
    props = top.maybe("property")
    if props is None or not props.size():
        return ""
    parts = rt.split_params(top.at("param").as_str())
    rows: list[list[str]] = []
    for idx, one in enumerate(props.values()):
        label = one.as_str()
        raw = parts[idx] if idx < len(parts) else ""
        if not raw:
            continue
        found = rt.resolve(table, raw)
        if found is None:
            rows.append([label, common.markup(raw)])
            continue
        main, growth, fmt = found
        rows.append(
            [
                label,
                base.esc(common.format_prop(label, main, fmt)),
                base.esc(common.format_prop(label, rt.at_level(main, growth, level), fmt)),
            ]
        )
    if not rows:
        return ""
    return base.rows_dense(["属性", "Lv1", f"Lv{level}"], rows)


def _skills(detail: JsonNode) -> str:
    skill = detail.maybe("skill")
    if skill is None:
        return ""
    table = detail.maybe("skill_prop")
    blocks: list[str] = []
    for _, group in skill.items():
        levels = group.maybe("level")
        if levels is None:
            continue
        level_keys = [k for k, _ in levels.items()]
        if not level_keys:
            continue
        top_key = level_keys[-1]
        top = levels.at(top_key)
        level = int(top_key) if top_key.isdigit() else 0
        name = top.at("name").as_str()
        desc = top.at("desc").as_str()
        tag = base.chip_text(f"Lv{top_key}") if top_key.isdigit() else ""
        head_html = base.skill_head(name, extra=tag, fallback=SKILL_ICON)
        body = f'<div class="txt">{common.para(desc)}</div>'
        if table is not None:
            body += _skill_ratio(top, table, level)
        blocks.append(f'<div class="col">{base.card(head_html + body, tight=True)}</div>')
    if not blocks:
        return ""
    return base.section("技能", "SKILL") + base.columns(blocks, 2)


async def _growth(detail: JsonNode) -> str:
    level = detail.maybe("level")
    if level is None:
        return ""
    blocks: list[str] = []
    for key, band in level.items():
        holder = band.maybe("materials")
        items: list[mat.Material] = []
        if holder is not None:
            for item_id, count in holder.items():
                if count.as_int() > 0:
                    items.append(mat.make(item_id, count.as_int()))
        if not items:
            continue
        lo = band.at("level_min").as_int() if band.has("level_min") else 0
        hi = band.at("level_max").as_int() if band.has("level_max") else 0
        head = base.chip_text(f"Lv{lo}→{hi}")
        blocks.append(f'<div class="col">{base.card(head + await base.materials(items), tight=True)}</div>')
    if not blocks:
        return ""
    per_row = min(len(blocks), 4)
    return base.section("升级材料", "ASCENSION") + "".join(base.row_of(blocks, per_row))


async def _hero_art(bangboo_id: str, icon_path: str) -> str:
    """立绘：本地头像够大就用本地的，否则拉 CDN 原图。

    ``code_name`` 在 CDN 上没有对应素材，必须用 ``icon`` 字段的游戏内路径取扁平 basename。
    """
    local = SQUARE_BANGBOO / f"bangboo_rectangle_avatar_{bangboo_id}.png"
    if base.local_big_enough(local, _LOCAL_MIN):
        return base.crop_uri(local, base.HERO_RW, base.HERO_RH, bias=0.3)
    tail = icon_path.rsplit("/", 1)[-1]
    return await base.remote_icon(tail.rsplit(".", 1)[0], base.HERO_RW, base.HERO_RH, 0.3)


async def build(bangboo_id: str) -> bytes:
    """渲染邦布卡片。"""
    await data.items()
    detail = await get_source().detail("bangboo", bangboo_id)
    name = detail.at("name").as_str()
    code_name = detail.at("code_name").as_str()
    rarity = detail.at("rarity").as_int()

    art = await _hero_art(bangboo_id, detail.at("icon").as_str())
    chips = [base.chip_text("邦布"), base.chip_text("S" if rarity >= 4 else "A")]

    lines = _stat_lines(detail)
    rail = "".join(lines) if 0 < len(lines) <= _RAIL_MAX else ""

    parts = [base.hero("BANGBOO / 邦布", name, code_name, art, "".join(chips), rail)]
    if not rail:
        block = _stat_block(detail)
        if block:
            parts.append(block)
    parts.append(base.section("简介", "INTRO"))
    parts.append(base.card(f'<div class="txt">{common.para(detail.at("desc").as_str())}</div>'))

    parts.append(_skills(detail))
    growth = await _growth(detail)
    if growth:
        parts.append(growth)
    parts.append(base.footer(f"数据源 nanoka.cc · {code_name}"))
    return await base.render(ACCENT, "".join(parts))
