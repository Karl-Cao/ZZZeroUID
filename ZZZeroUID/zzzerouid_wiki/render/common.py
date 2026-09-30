"""wiki 卡片共用的小积木与标记转换。"""

from typing import Final

from . import base
from ...utils.nanoka import text as tx, element as el

#: 上游 ``<IconMap:Name>`` -> 本地 ICON
ICON_MAP: Final[dict[str, tuple[str, str]]] = {
    # (目录, 文件名)
    "Icon_AvatarClass_Attack": ("pro", "IconAttack"),
    "Icon_AvatarClass_Anomaly": ("pro", "IconAnomaly"),
    "Icon_AvatarClass_Defense": ("pro", "IconDefense"),
    "Icon_AvatarClass_Armorer": ("pro", "IconDefense"),
    "Icon_AvatarClass_Rupture": ("pro", "IconRupture"),
    "Icon_AvatarClass_Stun": ("pro", "IconStun"),
    "Icon_AvatarClass_Support": ("pro", "IconSupport"),
    "Icon_GeneralBuff_Thunder": ("", "电属性.png"),
    "Icon_GeneralBuff_Fire": ("", "火属性.png"),
    "Icon_GeneralBuff_Ice": ("", "冰属性.png"),
    "Icon_GeneralBuff_Physical": ("", "物理属性.png"),
    "Icon_GeneralBuff_Ether": ("", "以太属性.png"),
}

#: 未收录的 IconMap 直接丢弃，避免正文露出原始标记
_DROP = (
    "Icon_Normal",
    "Icon_Special",
    "Icon_SpecialReady",
    "Icon_Evade",
    "Icon_QTE",
    "Icon_UltimateReady",
    "Icon_Switch",
)


def icon_repl(name: str) -> str:
    """``<IconMap:>`` 的替换函数：命中本地素材就出图，否则抹掉。"""
    if name in ICON_MAP:
        folder, filename = ICON_MAP[name]
        uri = base.texture(filename, 22)
        return f'<img src="{uri}" style="height:13px"/>' if uri else ""
    if name in _DROP:
        return ""
    return ""


def markup(text: str) -> str:
    """单行正文：去标记 + 上色 + 数字高亮。"""
    return tx.markup(text, icon_repl)


def para(text: str) -> str:
    """多行正文，保留作者换行。"""
    return tx.multiline(text, icon_repl)


def plain(text: str) -> str:
    return tx.plain(text)


def element_chips(element_ids: list[int], with_text: bool = True) -> str:
    """属性胶囊：ICON 在左，文字在右。"""
    out: list[str] = []
    for eid in element_ids:
        uri = base.element_uri(eid, 40)
        if uri:
            out.append(base.chip_img(uri, el.element_name(eid) if with_text else ""))
        elif with_text:
            out.append(base.chip_text(el.element_name(eid)))
    return "".join(out)


def format_prop(name: str, raw: float, fmt: str) -> str:
    """按上游的 format 串还原显示值。

    形如 ``{0:0.#%}``：百分号在花括号内，不能用 endswith 判断。
    """
    if "%" in fmt:
        value = raw / 100
        digits = 1 if "#.#" in fmt else 0
        return f"{value:.{digits}f}%"
    if "#.##" in fmt:
        return f"{raw:.2f}".rstrip("0").rstrip(".")
    if "#.#" in fmt:
        return f"{raw:.1f}".rstrip("0").rstrip(".")
    if float(raw).is_integer():
        return str(int(raw))
    return f"{raw:g}"


def ratio_at(main: int, growth: int, level: int) -> float:
    """技能倍率：``main`` 为 1 级，``growth`` 为每级增量。"""
    return (main + growth * (level - 1)) / 100


def human_int(raw: int) -> str:
    """血量这类大数字压缩显示。"""
    if raw >= 100_000_000:
        return f"{raw / 100_000_000:.2f}亿"
    if raw >= 10_000:
        return f"{raw / 10_000:.1f}万"
    return f"{raw:,}"
