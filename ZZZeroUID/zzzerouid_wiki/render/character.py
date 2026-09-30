"""``角色介绍`` / ``角色信息`` 卡片。

数据取自上游 ``zh/character/{id}.json``，各区块的取数位置：

- 页首 ``partner_info`` + ``element_type`` / ``weapon_type`` / ``hit_type`` / ``camp``
- 面板数值 ``level`` 最后一个 band（Lv50→60），额外属性在 ``extra_level``
- 技能 ``skill.{group}.description[]``：同一条目要么带 ``param``（倍率）要么带
  ``desc``（说明），按技能名合并成一张卡；``main`` 是 1 级值、``growth`` 是每级
  增量（线性），等级列取 Lv1 / Lv12
- 影画 ``potential_detail``、天赋 ``talent``、故事 ``partner_info``、突破 ``level.*.materials``

版式上，Lv50-60 面板数值竖排进页首右侧（见 :func:`base.hero` 的 ``rail`` 槽），
条目超过 :data:`_RAIL_MAX` 行才退回独立小节。
"""

from typing import Final

from . import base, common
from ...utils.nanoka import data, ratio as rt, element as el, material as mat
from ...utils.nanoka.source import get_source
from ...utils.nanoka.json_node import JsonNode
from ...utils.resource.RESOURCE_PATH import MIND_PATH, ROLE_PATH

ACCENT: Final[str] = "#ffcf4d"
#: 页首竖栏最多放几行（生命/攻击/防御 + 额外属性）
_RAIL_MAX: Final[int] = 8
#: 三栏卡片正文每行约多少字（.txt.td 11.5px、栏内宽 ~224px）。估高度用
_LINE_3: Final[int] = 18


def _first_value(node: JsonNode) -> str:
    """取 ``{"203": "电属性"}`` 这类单值字典里的第一个值。"""
    for _, item in node.items():
        return item.as_str()
    return ""


def _one_id(node: JsonNode) -> int:
    for key, _ in node.items():
        return int(key) if key.lstrip("-").isdigit() else 0
    return 0


async def _hero_art(char_id: str) -> str:
    """立绘走本地 resource，缺失时回退到 CDN；统一裁成页首比例。"""
    from ...utils.name_convert import char_id_to_sprite

    sprite = char_id_to_sprite(char_id).zfill(2)
    path = ROLE_PATH / f"IconRole{sprite}.png"
    if path.exists():
        return base.crop_uri(path, base.HERO_RW, base.HERO_RH, bias=0.16)
    return await base.remote_icon(f"IconRole{sprite}", base.HERO_RW, base.HERO_RH, 0.16)


async def build(char_id: str) -> bytes:
    """渲染角色卡片。"""
    await data.items()
    detail = await get_source().detail("character", char_id)

    name = detail.at("name").as_str()
    code_name = detail.at("code_name").as_str()
    rarity = detail.at("rarity").as_int()
    element_id = _one_id(detail.at("element_type"))
    role_id = _one_id(detail.at("weapon_type"))
    hit_id = _one_id(detail.at("hit_type"))
    camp = _first_value(detail.at("camp"))

    info = detail.at("partner_info")
    full_name = info.at("full_name").as_str()
    birthday = info.at("birthday").as_str()
    stature = info.at("stature").as_str()

    accent = el.element_color(element_id) if element_id else ACCENT
    art = await _hero_art(char_id)

    chips: list[str] = []
    chips.append(common.element_chips([element_id]))
    role_icon = base.role_uri(role_id, 40)
    if role_icon:
        chips.append(base.chip_img(role_icon, el.role_name(role_id)))
    chips.append(base.chip_text(f"命破·{el.hit_name(hit_id) or '—'}"))
    if camp:
        chips.append(base.chip_text(camp))
    if rarity:
        chips.append(base.chip_text("S" if rarity >= 4 else "A"))
    meta_bits = [f"生日 {birthday}" if birthday else "", f"身高 {stature}cm" if stature else ""]
    meta_bits = [b for b in meta_bits if b]
    if meta_bits:
        chips.append(base.chip_text(" · ".join(meta_bits)))

    rail = _rail(detail)
    parts: list[str] = [
        base.hero(
            "CHARACTER / AGENT",
            name,
            full_name,
            art,
            "".join(chips),
            rail,
            _band_note(detail),
        )
    ]
    if not rail:
        # 额外属性太多时竖栏塞不下，退回独立小节
        block = _panel_block(detail)
        if block:
            parts.append(block)

    parts.append(_skills(detail))
    parts.append(await _mindscape(detail, char_id))
    parts.append(_talent(detail))
    parts.append(_story(detail))
    parts.append(await _growth(detail))
    parts.append(base.footer(f"数据源 nanoka.cc · {code_name}"))

    return await base.render(accent, "".join(parts))


# ---------------------------------------------------------------- 面板
def _top_band(detail: JsonNode) -> tuple[JsonNode | None, JsonNode | None]:
    """取顶等级段与其额外属性。``level`` 的最后一个 band 即 Lv50→60。"""
    level = detail.maybe("level")
    if level is None:
        return None, None
    band_keys = [k for k, _ in level.items()]
    if not band_keys:
        return None, None
    top_key = band_keys[-1]
    extra_node = detail.maybe("extra_level")
    extra = extra_node.maybe(top_key) if extra_node is not None else None
    return level.at(top_key), extra


def _band_note(detail: JsonNode) -> str:
    band, _ = _top_band(detail)
    if band is None:
        return ""
    return f"Lv{band.at('level_min').as_int()}-{band.at('level_max').as_int()}"


def _extra_lines(extra: JsonNode | None) -> list[str]:
    if extra is None:
        return []
    holder = extra.maybe("extra")
    if holder is None:
        return []
    lines: list[str] = []
    for _, prop in holder.items():
        name = prop.at("name").as_str()
        value = common.format_prop("", prop.at("value").as_float(), prop.at("format").as_str())
        lines.append(base.kv(name, base.esc(value), _prop_icon(name)))
    return lines


def _rail(detail: JsonNode) -> str:
    """Lv.60 面板数值，竖排一列塞进页首右侧。

    顶档取 ``level`` 最后一个 band（Lv50→60），额外属性读 ``extra_level``。
    返回空串表示放不下（无数据，或条目数超 :data:`_RAIL_MAX`）。
    """
    band, extra = _top_band(detail)
    if band is None:
        return ""
    lines = [
        base.kv("生命", base.esc(f"{band.at('hp_max').as_int():,}"), base.prop_uri("IconHpMax", 40)),
        base.kv("攻击", base.esc(f"{band.at('attack').as_int():,}"), base.prop_uri("IconAttack", 40)),
        base.kv("防御", base.esc(f"{band.at('defence').as_int():,}"), base.prop_uri("IconDef", 40)),
    ]
    lines.extend(_extra_lines(extra))
    if not lines[3:] or len(lines) > _RAIL_MAX:
        return ""
    return "".join(lines)


def _panel_block(detail: JsonNode) -> str:
    """竖栏放不下时的兜底：退回独立小节。"""
    band, extra = _top_band(detail)
    if band is None:
        return ""
    lines = _extra_lines(extra)
    left = base.kv("生命", base.esc(f"{band.at('hp_max').as_int():,}"), base.prop_uri("IconHpMax", 40))
    left += base.kv("攻击", base.esc(f"{band.at('attack').as_int():,}"), base.prop_uri("IconAttack", 40))
    left += base.kv("防御", base.esc(f"{band.at('defence').as_int():,}"), base.prop_uri("IconDef", 40))
    right = "".join(lines) if lines else base.chip_text("无额外属性")
    return base.section("面板数值", "STATS", _band_note(detail)) + base.card(base.columns([left, right], 2))


_PROP_ICON: Final[dict[str, str]] = {
    "暴击率": "IconCrit",
    "暴击伤害": "IconCritDam",
    "异常精通": "IconElementAbnormalPower",
    "贯穿值": "IconPenValue",
    "能量回复": "IconSpRecover",
    "基础能量自动回复": "IconSpRecover",
    "能量获取效率": "IconSpGetRatio",
    "最大能量": "IconSpMax",
    "冲击力": "IconBreakStun",
    "基础攻击力": "IconAttack",
}


def _prop_icon(name: str) -> str:
    if name in _PROP_ICON:
        return base.prop_uri(_PROP_ICON[name], 40)
    return ""


# ---------------------------------------------------------------- 技能
#: 倍率属性名后缀 -> 表格列的短名
_RATIO_KINDS: Final[tuple[tuple[str, str], ...]] = (("伤害倍率", "伤害"), ("失衡倍率", "失衡"))


def _split_ratio(name: str) -> tuple[str, str]:
    """``一段伤害倍率`` -> ``("一段", "伤害")``；不认识的后缀原样返回。"""
    for suffix, kind in _RATIO_KINDS:
        if name.endswith(suffix):
            return name[: -len(suffix)], kind
    return "", ""


def _is_enhanced(entry: JsonNode) -> bool:
    """这条技能是不是「影画强化」版本。

    上游 ``potential`` 有三种：``[0]`` 基础版、``[影画id...]`` 强化版、
    ``[]`` 只有倍率没有说明。只看「非空」会把基础版也标成强化版。
    """
    node = entry.maybe("potential")
    if node is None:
        return False
    return any(key.lstrip("-").isdigit() and int(key) != 0 for key, _ in node.items())


def _kind_head(kinds: list[str]) -> tuple[str, list[str]]:
    """两种属性并排时的行标签与列名。

    共用后缀提到行标签上（``段位·失衡`` + ``轻招架/重招架``），列名才放得下。
    """
    for suffix in ("失衡", "伤害"):
        if all(k.endswith(suffix) for k in kinds):
            return f"段位·{suffix}", [k[: -len(suffix)] for k in kinds]
    return "段位", list(kinds)


def _ratio_html(entry: JsonNode, steps: tuple[int, ...]) -> tuple[str, int]:
    """一个技能条目的倍率表，返回 (HTML, 段数)。段数用于估算卡片高度。"""
    props = entry.maybe("param")
    if props is None:
        return "", 0
    segs: dict[str, dict[str, tuple[int, int, str]]] = {}
    order: list[str] = []
    extras: list[str] = []
    for prop in props.values():
        label = prop.at("name").as_str()
        holder = prop.maybe("param")
        if holder is None or not holder.size():
            extras.append(base.kv(label, common.markup(prop.at("desc").as_str())))
            continue
        seg, kind = _split_ratio(label)
        if seg not in segs:
            segs[seg] = {}
            order.append(seg)
        for _, one in holder.items():
            segs[seg][kind] = rt.from_node(one)
    if not segs:
        return "", 0

    kinds = sorted({kind for seg in segs.values() for kind in seg})

    def cell(found: tuple[int, int, str] | None) -> str:
        if found is None:
            return "—"
        main, growth, fmt = found
        lo = common.format_prop("", rt.at_level(main, growth, steps[0]), fmt)
        hi = common.format_prop("", rt.at_level(main, growth, steps[-1]), fmt)
        return f'{base.esc(lo)}<span class="dim">→</span>{base.esc(hi)}'

    if len(kinds) == 1:
        # 单一属性直接铺成行，段位多时靠行标签区分
        single = len(order) == 1
        head = ["倍率" if single else "段位"]
        body = [["" if single else seg, cell(segs[seg][kinds[0]])] for seg in order if kinds[0] in segs[seg]]
    elif len(kinds) == 2:
        # 只有一段时行标签是空的，表头就别写"段位"了
        single = len(order) == 1
        if single:
            head = ["倍率", *kinds]
        else:
            head0, kind_head = _kind_head(kinds)
            head = [head0, *kind_head]
        body = [[""] + [cell(segs[seg].get(kind)) for kind in kinds] for seg in order]
    else:
        # 三种及以上（如轻招架/重招架/连续招架失衡）横排放不下，竖着堆成行
        head = ["段位", "倍率"]
        body = [
            [f"{seg}·{kind}", cell(found)]
            for seg in order
            for kind in kinds
            if (found := segs[seg].get(kind)) is not None
        ]
    return base.ratio_table(head, body) + "".join(extras), len(order)


def _skills(detail: JsonNode) -> str:
    """技能：倍率与说明合成一张卡。

    上游把同一个技能的数值和文本拆成两条 entry（一条只带 ``param``、
    一条只带 ``desc``），拆成两节会让同一个技能在图上出现两次；
    按技能名合并后 30 张卡变 14 张，四栏排下来比原来矮一大截。
    """
    skill = detail.maybe("skill")
    if skill is None:
        return ""
    order: list[str] = []
    tables: dict[str, tuple[str, int]] = {}
    texts: dict[str, list[tuple[bool, str]]] = {}
    for _, group in skill.items():
        descs = group.maybe("description")
        if descs is None:
            continue
        for _, entry in descs.items():
            name = entry.at("name").as_str()
            if not name:
                continue
            if name not in texts:
                order.append(name)
                texts[name] = []
                tables[name] = ("", 0)
            body = entry.maybe("desc")
            if body is not None and body.as_str():
                texts[name].append((_is_enhanced(entry), body.as_str()))
            ratio, segs = _ratio_html(entry, rt.STEPS)
            if ratio:
                tables[name] = (ratio, segs)

    blocks: list[tuple[int, str]] = []
    for name in order:
        lines = texts[name]
        ratio, segs = tables[name]
        if not lines and not ratio:
            continue
        enhanced = any(tag for tag, _ in lines)
        tag = base.chip_text("强化") if enhanced else ""
        inner = base.skill_head(common.markup(name), raw=True, extra=tag) + ratio
        for is_enhanced, text in lines:
            # 强化版是影画叠上去的，压成次级色，基础版保持正文色
            cls = "txt td dim" if is_enhanced else "txt td"
            inner += f'<div class="{cls}">{common.para(text)}</div>'
        # 权重单位统一是「行」：正文行数 + 倍率行数 + 卡头/内边距的固定开销
        weight = sum(base.est_lines(t, _LINE_3) for _, t in lines) + segs + 3
        blocks.append((weight, f'<div class="col">{base.card(inner, tight=True)}</div>'))
    if not blocks:
        return ""
    note = f"倍率 Lv{rt.STEPS[0]}→Lv{rt.STEPS[-1]}"
    # 技能之间没有先后语义，可以为压高度重排；影画/故事有 Lv 顺序，不能开
    return base.section("技能", "SKILLS", note) + base.columns_by_height(blocks, 3, reorder=True)


# ---------------------------------------------------------------- 影画
async def _mindscape(detail: JsonNode, char_id: str) -> str:
    holder = detail.maybe("potential_detail")
    if holder is None:
        return ""
    items = holder.items()
    if not items:
        return ""

    blocks: list[tuple[int, str]] = []
    for key, node in items:
        title = node.at("level_show_name").as_str(f"影画 {key}")
        body = node.at("desc").as_str()
        name = node.at("name").as_str()
        level = node.at("level").as_int()
        head = f'<div class="row"><span class="kvv">{base.esc(title)}</span>'
        if level:
            head += base.chip_text(f"Lv{level}")
        head += "</div>"
        if name:
            head += f'<div class="txt dim">{base.esc(name)}</div>'
        mats = node.maybe("potential_materials")
        mat_html = ""
        if mats is not None:
            items_m: list[mat.Material] = []
            for entry in mats.values():
                count = entry.at("number").as_int()
                if count > 0:
                    items_m.append(mat.make(str(entry.at("item_id").as_int()), count))
            mat_html = await base.materials(items_m)
        pic = ""
        if level <= 3:
            art = MIND_PATH / f"Mindscape_{char_id}_{level}.png"
            if art.exists():
                pic = f'<div class="slot"><img src="{base.local_icon(art, 240)}"/></div>'
        body_html = common.para(body) if body else '<span class="dim">无附加文本</span>'
        inner = f'<div class="row">{pic}<div class="grow">{head}{body_html}{mat_html}</div></div>'
        # 缩略图占掉一截宽度，有图时每行能装的字更少
        weight = base.est_lines(body, _LINE_3 - 5 if pic else _LINE_3) + 3 + (1 if name else 0)
        blocks.append((weight, base.card(inner, tight=True)))

    return base.section("影画", "MINDSCAPE") + base.columns_by_height(blocks, 3)


# ---------------------------------------------------------------- 天赋
def _talent(detail: JsonNode) -> str:
    node = detail.maybe("talent")
    if node is None:
        return ""
    blocks: list[tuple[int, str]] = []
    for _, item in node.items():
        name = item.at("name").as_str()
        body = item.at("desc").as_str()
        lore = item.at("desc2").as_str()
        head = f'<span class="kvv">{base.esc(name)}</span>'
        head += base.chip_text("Lv" + item.at("level").as_str())
        inner = f'<div class="row">{head}</div>'
        inner += f'<div class="txt">{common.markup(body)}</div>'
        if lore:
            inner += f'<div class="txt dim">{common.markup(lore)}</div>'
        # +3 是卡头与内边距的固定开销
        weight = base.est_lines(body, _LINE_3) + base.est_lines(lore, _LINE_3) + 3
        blocks.append((weight, f'<div class="col">{base.card(inner, tight=True)}</div>'))
    if not blocks:
        return ""
    return base.section("天赋", "TALENT") + base.columns_by_height(blocks, 3, reorder=True)


# ---------------------------------------------------------------- 故事
def _story(detail: JsonNode) -> str:
    info = detail.maybe("partner_info")
    if info is None:
        return ""
    profile = info.at("profile_desc").as_str()
    out = base.section("角色故事", "STORY")
    if profile:
        out += base.card(f'<div class="txt">{common.para(profile)}</div>')

    side: list[tuple[int, str]] = []
    for key in ("impression_f", "impression_m"):
        text = info.at(key).as_str()
        if text:
            inner = f'<div class="txt">{common.para(text)}</div>'
            side.append((base.est_lines(text, _LINE_3), f'<div class="col">{base.card(inner, tight=True)}</div>'))
    impressions = info.at("impressions")
    if impressions.size():
        joined = "\n".join(n.as_str() for n in impressions.values())
        inner = f'<div class="txt">{common.para(joined)}</div>'
        side.append((base.est_lines(joined, _LINE_3), f'<div class="col">{base.card(inner, tight=True)}</div>'))
    if side:
        out += base.columns_by_height(side, 3, fill=True)
    return out if profile or side else ""


# ---------------------------------------------------------------- 突破
async def _growth(detail: JsonNode) -> str:
    level = detail.maybe("level")
    if level is None:
        return ""
    blocks: list[str] = []
    for _, band in level.items():
        name = f"Lv{band.at('level_min').as_int()}→{band.at('level_max').as_int()}"
        holder = band.maybe("materials")
        items: list[mat.Material] = []
        if holder is not None:
            for item_id, count in holder.items():
                if count.as_int() > 0:
                    items.append(mat.make(item_id, count.as_int()))
        if not items:
            continue
        head = base.chip_text(name)
        blocks.append(f'<div class="col">{base.card(head + await base.materials(items), tight=True)}</div>')
    if not blocks:
        return ""
    # 五档正好一行；档位不是 5 个时按行铺，不留孤儿块
    per_row = min(len(blocks), 5)
    rows = base.row_of(blocks, per_row)
    return base.section("突破材料", "ASCENSION") + "".join(rows)
