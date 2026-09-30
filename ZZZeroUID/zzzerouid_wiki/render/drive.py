"""``驱动盘介绍`` 卡片。"""

from typing import Final

from . import base, common
from ...utils.nanoka.source import get_source
from ...utils.nanoka.json_node import JsonNode
from ...utils.resource.RESOURCE_PATH import SUIT_PATH

ACCENT: Final[str] = "#c77dff"


def _code_of(path: str) -> str:
    tail = path.rsplit("/", 1)[-1]
    return tail.rsplit(".", 1)[0]


async def _art(code_name: str) -> str:
    """驱动盘套装图标：只按原尺寸摆，不放大。

    ``suit/`` 下的套装图只有 152×152，拉成满宽立绘就是一块糊，所以走
    :func:`base.local_canvas` 等比留白，不做裁剪也不做放大。本地没有就退回
    CDN 的方图。**别去动** ``3d_suit/``：那 33 张里有 5 张是 512×512 但
    alpha 峰值只有 4/255 的空壳（ChaosJazz / HormonePunk / PufferElectro /
    SoulRock / WoodpeckerElectro），只判文件存在会渲染成一整块黑。
    """
    path = SUIT_PATH / f"{code_name}.png"
    if path.is_file():
        return base.local_canvas(path, base.ICON_BOX)
    return await base.remote_icon(code_name, base.ICON_BOX, base.ICON_BOX, 0.5)


def _set_effect(detail: JsonNode) -> str:
    out = ""
    two = detail.at("desc2").as_str()
    four = detail.at("desc4").as_str()
    if two:
        out += base.section("二件套", "2 PIECE")
        out += base.card(f'<div class="txt">{common.markup(two)}</div>')
    if four:
        out += base.section("四件套", "4 PIECE")
        out += base.card(f'<div class="txt">{common.markup(four)}</div>')
    return out


async def build(suit_id: str) -> bytes:
    """渲染驱动盘卡片。

    驱动盘明细页是扁平的 ``{id, name, desc2, desc4, story, icon, icon2}``，
    没有角色/音擎那种 ``zh`` 子对象。
    """
    detail = await get_source().detail("equipment", suit_id)
    name = detail.at("name").as_str()
    code_name = _code_of(detail.at("icon").as_str())

    art = await _art(code_name)
    chips = [base.chip_text("驱动盘套装")]

    parts = [base.hero_icon("DRIVE DISC / 驱动盘", name, "", art, "".join(chips))]

    parts.append(base.section("简介", "INTRO"))
    story = detail.at("story").as_str() if detail.has("story") else ""
    body = f'<div class="txt">{common.para(story)}</div>' if story else '<div class="txt dim">暂无简介文本</div>'
    parts.append(base.card(body))

    parts.append(_set_effect(detail))
    parts.append(base.footer(f"数据源 nanoka.cc · {code_name}"))
    return await base.render(ACCENT, "".join(parts))
