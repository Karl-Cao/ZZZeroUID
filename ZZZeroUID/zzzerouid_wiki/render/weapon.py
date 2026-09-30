"""``音擎介绍`` 卡片。"""

from typing import Final

from . import base, common
from ...utils.nanoka import data, material as mat
from ...utils.nanoka.source import get_source
from ...utils.nanoka.json_node import JsonNode
from ...utils.resource.RESOURCE_PATH import WEAPON_PATH

ACCENT: Final[str] = "#7fd4ff"
#: 精炼等级
REFINE: Final[int] = 1
#: 主词条区间只展示这些等级，其余 0~21 全列会把页面撑成两倍长
_REFINE_STEPS: Final[frozenset[int]] = frozenset({0, 5, 10, 15, 20})


def _role(detail: JsonNode) -> str:
    for _, item in detail.at("weapon_type").items():
        return item.as_str()
    return ""


async def _art(code_name: str) -> str:
    """音擎图优先用本地 resource，其次 CDN。"""
    for name in (f"{code_name}_High.png", f"{code_name}.png"):
        path = WEAPON_PATH / name
        if path.exists():
            return base.crop_uri(path, base.HERO_RW, base.HERO_RH, bias=0.5)
    return await base.remote_icon(f"{code_name}Big", base.HERO_RW, base.HERO_RH, 0.5)


def _stats(detail: JsonNode) -> str:
    """1 级面板 + 精炼词条区间。

    上游只给 1 级基础攻击力，等级成长系数没有下发，这里不编造满级数值。
    """
    base_prop = detail.at("base_property")
    rand_prop = detail.at("rand_property")
    level = detail.maybe("level")
    fmt = base_prop.at("format").as_str("{0:0.#}")
    rfmt = rand_prop.at("format").as_str("{0:0.#%}")

    out = base.rows(
        [
            ("基础攻击力 · Lv1", common.format_prop("", base_prop.at("value").as_float(), fmt)),
            (rand_prop.at("name").as_str(), common.format_prop("", rand_prop.at("value").as_float(), rfmt)),
        ],
        "面板数值",
    )
    if level is None:
        return out
    # 上游给了 0~21 全部等级，全列会撑爆页面，只取关键档
    spans: list[tuple[str, str]] = []
    for key, item in level.items():
        if not key.isdigit() or int(key) not in _REFINE_STEPS or not item.has("rate2"):
            continue
        spans.append((f"Lv{key}", f"{item.at('rate2').as_int() / 100:.2f}%"))
    if spans:
        out += base.rows(spans, "主词条区间")
    return out


def _talents(detail: JsonNode) -> str:
    node = detail.maybe("talents")
    if node is None:
        return ""
    blocks: list[str] = []
    for key, item in node.items():
        if not key.isdigit() or not 1 <= int(key) <= 5:
            continue
        name = item.at("name").as_str()
        body = item.at("desc").as_str()
        inner = base.chip_text(f"精炼 {key}")
        inner += f'<div class="kvv">{base.esc(name)}</div>'
        inner += f'<div class="txt">{common.markup(body)}</div>'
        blocks.append(f'<div class="col">{base.card(inner, tight=True)}</div>')
    if not blocks:
        return ""
    return base.section("精炼特效", "REFINE") + base.columns(blocks, 2)


async def _materials(detail: JsonNode) -> str:
    raw = detail.at("materials").as_str()
    stages = mat.parse_stages(raw)
    if not stages:
        return ""
    blocks: list[str] = []
    for idx, items in enumerate(stages, start=1):
        head = base.chip_text(f"精炼 +{idx}")
        blocks.append(f'<div class="col">{base.card(head + await base.materials(items), tight=True)}</div>')
    return base.section("突破材料", "ASCENSION") + base.columns(blocks, 3)


def _stars(detail: JsonNode) -> str:
    """精炼消耗。上游字段是 ``star_rate``（精炼经验）/ ``rand_rate``（词条刷新）。"""
    node = detail.maybe("stars")
    if node is None:
        return ""
    body: list[list[str]] = []
    for key, item in node.items():
        if not key.isdigit() or not 1 <= int(key) <= 5:
            continue
        body.append([f"精炼 {key}", f"{item.at('star_rate').as_int():,}", f"{item.at('rand_rate').as_int():,}"])
    return base.rows_n(["阶段", "精炼经验", "词条刷新"], body) if body else ""


async def build(weapon_id: str) -> bytes:
    """渲染音擎卡片。"""
    await data.items()
    detail = await get_source().detail("weapon", weapon_id)
    name = detail.at("name").as_str()
    code_name = detail.at("code_name").as_str()
    rarity = detail.at("rarity").as_int()
    role = _role(detail)

    art = await _art(code_name)
    chips = [base.chip_text(role)] if role else []
    chips.append(base.chip_text("S" if rarity >= 4 else "A"))

    parts = [base.hero("W-ENGINE / 音擎", name, detail.at("desc3").as_str(), art, "".join(chips))]
    parts.append(base.section("简介", "INTRO"))
    parts.append(base.card(f'<div class="txt">{common.para(detail.at("desc").as_str())}</div>'))

    effect = detail.at("desc2").as_str()
    if effect:
        parts.append(base.section("基础效果", "BASE EFFECT"))
        parts.append(base.card(f'<div class="txt">{common.markup(effect)}</div>'))

    parts.append(base.section("面板数值", "STATS"))
    parts.append(base.card(_stats(detail)))

    talents = _talents(detail)
    if talents:
        parts.append(talents)

    stars = detail.maybe("stars")
    if stars is not None and stars.size():
        parts.append(base.section("精炼消耗", "COST"))
        parts.append(base.card(_stars(detail)))

    mats = await _materials(detail)
    if mats:
        parts.append(mats)

    parts.append(base.footer(f"数据源 nanoka.cc · {code_name}"))
    return await base.render(ACCENT, "".join(parts))
