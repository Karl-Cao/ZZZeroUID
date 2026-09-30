"""``怪物介绍`` 卡片。

怪物索引页的 ``desc`` 是英文，中文设定在明细页 ``zh/monster/{id}.json``，
所以这里取明细页；索引页只用来兜底（上游偶尔会先放索引再补明细）。
"""

from typing import Final

from . import base, common
from ...utils.nanoka import element as el
from ...utils.nanoka.source import get_source
from ...utils.nanoka.json_node import JsonNode

ACCENT: Final[str] = "#ff7a6b"

#: 形态面板字段 -> (中文名, texture2d/prop 图标)
_STATS: Final[dict[str, tuple[str, str]]] = {
    "hp": ("生命值", "IconHpMax"),
    "attack": ("攻击力", "IconAttack"),
    "defence": ("防御力", "IconDef"),
    "stun": ("失衡值", "IconBreakStun"),
    "crit": ("暴击率", "IconCrit"),
    "crit_damage": ("暴击伤害", "IconCritDam"),
    "pen_rate": ("穿透率", "IconPenRatio"),
}
#: 上游按万分比存，显示时除 100
_PCT: Final[frozenset[str]] = frozenset({"crit", "crit_damage", "pen_rate"})


def _code_of(path: str) -> str:
    tail = path.rsplit("/", 1)[-1]
    return tail.rsplit(".", 1)[0]


def _flat(node: JsonNode) -> dict[str, int]:
    out: dict[str, int] = {}
    for key, value in node.items():
        out[key] = value.as_int()
    return out


def _chips(detail: JsonNode) -> str:
    """族群 / 稀有度 / 主属性 ICON 胶囊。

    ``monster_info.*.element`` 是完整抗性表（六个属性常同时非零），
    直接铺开会刷出十几个重复胶囊；只取每个形态的主属性并去重。
    """
    out: list[str] = []
    group = detail.at("group_desc").as_str()
    if group:
        out.append(base.chip_text(group))
    rarity = detail.at("rarity").as_int()
    if rarity:
        out.append(base.chip_text("S" if rarity >= 4 else "A"))
    seen: set[int] = set()
    for _, info in detail.at("monster_info").items():
        eid = el.dominant_element(_flat(info.at("element")))
        if eid == 0 or eid in seen:
            continue
        seen.add(eid)
        uri = base.element_uri(eid, 40)
        if uri:
            out.append(f'<div class="chip"><img src="{uri}"/><span>{el.element_name(eid)}</span></div>')
    return "".join(out)


def _stats(info: JsonNode) -> str:
    """形态面板。

    ``monster_info`` 里同一 ``code_name`` 会出现多条，那是不同等级的曲线变体
    （``curves``），不是不同形态；按 code_name 去重，只留基础值。
    """
    blocks: list[tuple[int, str]] = []
    seen: set[str] = set()
    for _, one in info.at("monster_info").items():
        code = one.at("code_name").as_str()
        if code in seen:
            continue
        seen.add(code)
        rows: list[str] = []
        for key, (label, icon) in _STATS.items():
            node = one.at("stats").maybe(key)
            if node is None:
                continue
            value = node.as_int()
            if value == 0:
                continue
            shown = f"{value / 100:.1f}%" if key in _PCT else f"{value:,}"
            rows.append(base.kv(label, base.esc(shown), base.prop_uri(icon, 40)))
        if not rows:
            continue
        head = base.chip_text(code) if code and len(seen) > 1 else ""
        inner = "".join(rows)
        blocks.append((len(inner), f'<div class="col">{base.card(head + inner, tight=True)}</div>'))
    if not blocks:
        return ""
    # 一个形态就占满整行，两个才并排
    return base.section("形态面板", "STATS") + base.columns_by_height(blocks, 2, fill=True)


def _text_section(title: str, en: str, text: str) -> str:
    if not text:
        return ""
    body = f'<div class="txt">{common.para(text)}</div>'
    return base.section(title, en) + base.card(body)


async def build(monster_id: str) -> bytes:
    """渲染怪物卡片。"""
    detail = await get_source().detail("monster", monster_id)

    name = detail.at("name").as_str()
    art_code = _code_of(detail.at("image_path").as_str())
    art = await base.remote_icon(art_code, base.HERO_RW, base.HERO_RH, 0.2)

    parts = [base.hero("MONSTER / 怪物", name, art_code, art, _chips(detail))]
    parts.append(_text_section("简介", "INTRO", detail.at("desc").as_str()))

    quote = detail.at("card_quote").as_str()
    if quote:
        parts.append(base.section("档案记录", "QUOTE") + base.card(f'<div class="txt dim">{common.para(quote)}</div>'))

    obtain = detail.at("card_obtain").as_str()
    skill = detail.at("card_skill_desc").as_str()
    parts.append(_text_section("战斗特征", "SKILL", skill))

    info: list[str] = []
    group = detail.at("group_desc").as_str()
    if group:
        info.append(base.kv("族群", base.esc(group)))
    info.append(base.kv("编号", base.esc(monster_id)))
    if obtain:
        info.append(base.kv("数据获取", common.para(obtain)))
    parts.append(base.section("档案", "RECORD") + base.card("".join(info)))

    parts.append(_stats(detail))

    parts.append(base.footer(f"数据源 nanoka.cc · {art_code}"))
    return await base.render(ACCENT, "".join(parts))
