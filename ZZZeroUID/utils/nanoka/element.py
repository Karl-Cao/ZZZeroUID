"""属性 / 特性 / 命破属性的 id -> 名称、ICON、配色映射。

id 取值来自上游：属性 200-205 + 300，特性 1-6，命破属性 101-103。
"""

from typing import Final

#: 属性 id -> (简称, texture2d 文件名, 强调色)
ELEMENTS: Final[dict[int, tuple[str, str, str]]] = {
    200: ("物理", "物理属性.png", "#F5C542"),
    201: ("火", "火属性.png", "#FF5B4A"),
    202: ("冰", "冰属性.png", "#7FD4FF"),
    203: ("电", "电属性.png", "#C08BFF"),
    204: ("风", "风属性.png", "#8FE3C4"),
    205: ("以太", "以太属性.png", "#FF9BD0"),
    300: ("玄墨", "玄墨属性.png", "#B9A6FF"),
}

#: 特性 id -> (名称, texture2d/pro 文件名)
ROLES: Final[dict[int, tuple[str, str]]] = {
    1: ("强攻", "IconAttack"),
    2: ("击破", "IconStun"),
    3: ("异常", "IconAnomaly"),
    4: ("支援", "IconSupport"),
    5: ("防御", "IconDefense"),
    6: ("命破", "IconRupture"),
}

#: 命破属性 id -> 名称
HIT_TYPES: Final[dict[int, str]] = {
    101: "斩击",
    102: "贯穿",
    103: "冲击",
}

#: 技能分类（技能名 ``分类：技能名`` 的前缀）-> texture2d/skill_icon 文件名
#:
#: 素材取自 nanoka 站点自己的资源表（``static.nanoka.cc/assets/zzz/<名>.webp``），
#: 已逐个 HTTP 200 验证。分类与图形的对应同时用两条证据交叉确认过：
#: 一是上游角色 JSON 里内联的 ``<IconMap:>`` 标签，二是与 nanoka 页面截图的像素比对。
#: 两处上游数据的小出入按「以用户实际看到的图形为准」处理：
#: 冲刺攻击官方没有独立图标，与闪避反击共用 ``Icon_Evade``；
#: 支援突击上游误标成 ``Icon_Normal``，这里归到支援类的 ``Icon_Switch``。
SKILL_TYPES: Final[dict[str, str]] = {
    "普通攻击": "Icon_Normal",
    "冲刺攻击": "Icon_Evade",
    "闪避反击": "Icon_Evade",
    "闪避": "Icon_Evade",
    "连携技": "Icon_QTE",
    "终结技": "Icon_UltimateReady",
    "强化特殊技": "Icon_SpecialReady",
    "特殊技": "IconRoleSkillKeySpecial",
    "支援突击": "Icon_Switch",
    "招架支援": "Icon_Switch",
    "快速支援": "Icon_Switch",
    "支援技": "Icon_Switch",
    "核心技": "Icon_CoreSkill",
}

#: 星级 1-5 -> 稀有度贴图
RARITY: Final[dict[int, str]] = {
    1: "Rarity_C.png",
    2: "Rarity_B.png",
    3: "Rarity_A.png",
    4: "Rarity_S.png",
    5: "Rarity_S.png",
}

#: 局内货币 id -> 名称
CURRENCY_NAMES: Final[dict[str, str]] = {
    "10": "贝拉币",
}


def element_icon(element_id: int) -> str:
    """属性 ICON 文件名，未知属性返回空串。"""
    if element_id in ELEMENTS:
        return ELEMENTS[element_id][1]
    return ""


def element_name(element_id: int) -> str:
    if element_id in ELEMENTS:
        return ELEMENTS[element_id][0]
    return ""


def element_color(element_id: int) -> str:
    if element_id in ELEMENTS:
        return ELEMENTS[element_id][2]
    return "#E8EDF7"


def role_icon(role_id: int) -> str:
    if role_id in ROLES:
        return ROLES[role_id][1]
    return ""


def role_name(role_id: int) -> str:
    if role_id in ROLES:
        return ROLES[role_id][0]
    return ""


def hit_name(hit_id: int) -> str:
    if hit_id in HIT_TYPES:
        return HIT_TYPES[hit_id]
    return ""


def skill_kind(name: str) -> str:
    """从 ``普通攻击：猫猫爪刺`` 里取出分类 ``普通攻击``；认不出返回空串。"""
    head = name.split("：", 1)[0].strip()
    if head in SKILL_TYPES:
        return head
    return ""


def skill_icon(name: str) -> str:
    """技能分类 ICON 文件名，认不出分类返回空串。"""
    kind = skill_kind(name)
    if kind in SKILL_TYPES:
        return SKILL_TYPES[kind]
    return ""


def element_by_word(word: str) -> int:
    """``monster.element`` 用英文键，反查属性 id。"""
    table = {
        "physical": 200,
        "fire": 201,
        "ice": 202,
        "electric": 203,
        "wind": 204,
        "ether": 205,
        "mystery": 300,
    }
    if word in table:
        return table[word]
    return 0


def dominant_element(element: dict[str, int]) -> int:
    """从 ``{ice: 0, fire: 1, ...}`` 里取唯一的非零属性。"""
    for word, value in element.items():
        if value != 0:
            return element_by_word(word)
    return 0
