"""绝区零 WIKI：角色 / 音擎 / 驱动盘 / 邦布 / 怪物 / 四类 endgame 资料卡。

取数走 ``utils/nanoka``（可替换数据源），绘图走 ``render``，
这里只做命令分发与 AI 侧文本注入。

命令一览（均带 ``to_ai``，AI 可直接调用）：

======================  ===========================================
命令                    内容
======================  ===========================================
角色介绍                 立绘 + 面板 + 技能倍率/说明 + 影画 + 天赋 + 故事 + 突破
音擎介绍                 立绘 + 基础/精炼效果 + 词条刷新消耗 + 突破材料
驱动盘介绍               套装立绘 + 二件套/四件套效果
邦布介绍                 立绘 + 面板 + 主动技倍率 + 升级材料
怪物介绍                 立绘 + 族群 + 背景设定 + 抗性表 + 形态面板
深渊信息 / 式舆信息       式舆防卫战全局阵容
危局信息                 危局强袭战当期三只怪
临界信息                 临界推演各 STAGE 房间阵容
拟境信息 / 拟境湮灭战     拟境湮灭战异构首领阵容
======================  ===========================================

与个人战绩模块的分工：``zzzerouid_challenge`` / ``zzzerouid_mem`` /
``zzzerouid_void`` 出的是某个 UID 的通关记录，本模块出的是版本本身的资料与阵容。
"""

from typing import Final
from collections.abc import Callable, Awaitable

from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.utils.image.convert import convert_img
from gsuid_core.ai_core.trigger_bridge import ai_return

from .render import (
    drive as drive_card,
    weapon as weapon_card,
    bangboo as bangboo_card,
    endgame as endgame_card,
    monster as monster_card,
    character as character_card,
)
from ..utils.nanoka import data as wiki_data, text as tx, get_source
from ..utils.nanoka.json_node import JsonNode

sv_zzz_wiki = SV("绝区零WIKI")
sv_zzz_guide = SV("绝区零攻略")

_Render = Callable[[str], Awaitable[bytes]]
_Periods = Callable[[], Awaitable[list[wiki_data.Period]]]

#: endgame 模式注册表：别名 -> (渲染函数, 中文名, 期次来源)
_MODES: Final[dict[str, tuple[_Render, str, _Periods]]] = {
    "shiyu": (endgame_card.shiyu, "式舆防卫战", wiki_data.shiyu_periods),
    "haedal": (endgame_card.haedal, "危局强袭战", wiki_data.haedal_periods),
    "simul": (endgame_card.simul, "临界推演", wiki_data.simul_periods),
    "hard": (endgame_card.hard, "拟境湮灭战", wiki_data.hard_periods),
}

#: 期次选择词的统一说明
_PERIOD_HINT: Final[str] = "留空=本期，「上期」「下期」取相邻期次，也可写日期，如 2026.9.1"

_PERIOD_TOKENS: Final[tuple[str, ...]] = ("上期", "下期", "本期")


def _split_period(text: str) -> str:
    """把「上期式舆防卫战」这类前缀期次词从命令里摘出来。"""
    for token in _PERIOD_TOKENS:
        if text.startswith(token):
            return token
    return ""


def _ai_note(text: str) -> None:
    """把纯文本结论注入给 AI。"""
    try:
        ai_return(text)
    except Exception as exc:  # noqa: BLE001 # AI 侧失败不应影响出图
        logger.warning(f"[绝区零][wiki] ai_return 注入失败: {exc}")


async def _fail(bot: Bot, message: str) -> None:
    await bot.send(f"[绝区零] {message}")


async def _resolve(
    bot: Bot,
    finder: Callable[[str], Awaitable[tuple[str, str]]],
    kind: str,
    query: str,
    example: str,
) -> str | None:
    """统一处理「没给参数 / 没查到」两种情况，返回查到的 id。"""
    query = query.strip()
    if not query:
        await _fail(bot, f"请在命令后带上{kind}名，例如{example}")
        return None
    try:
        found_id, _ = await finder(query)
    except LookupError:
        await _fail(bot, f"没有找到{kind}「{query}」")
        return None
    return found_id


# ---------------------------------------------------------------- 实体资料
@sv_zzz_wiki.on_prefix(
    ("角色介绍", "角色信息", "角色图鉴", "查角色"),
    to_ai="""查询绝区零角色图鉴卡片，返回一张完整角色资料图。

    当用户问某个角色的属性、定位、技能倍率、影画、天赋、背景故事、突破材料时调用。
    典型说法："猫又的属性是啥"、"安比强攻还是击破"、"比利的终结技倍率多少"、
    "查角色 帕姆"、"妮可的影画效果"、"角色介绍 莱特"。
    图中含：属性/特性/命破 ICON 胶囊、Lv50-60 面板数值竖栏、全技能倍率表
    （Lv1 与 Lv12 的伤害/失衡倍率）、技能说明、六条影画、核心天赋、角色故事、分档突破材料。
    调用后会附带该角色的属性与背景纯文本，AI 可据此直接回答，不必再猜数值。
    本命令查的是图鉴资料，与"角色面板 猫又"（需要绑定 UID 的实战数据）不同。

    Args:
        text: 角色正式名、简称或常见错字，可省略"绝区零"前缀。
              例如 "猫又"、"安比"、"帕姆"、"莱特"、"11号"、"比利"。
              支持错字与拼音近似；查不到时返回"没有找到角色 xxx"。
    """,
    covers=[
        "绝区零角色属性",
        "绝区零角色技能倍率",
        "绝区零影画",
        "绝区零角色故事",
        "绝区零角色定位",
        "绝区零终结技倍率",
    ],
    aliases=["绝区零·角色图鉴", "绝区零·角色资料", "绝区零·角色技能倍率", "绝区零·影画效果"],
)
async def send_role_wiki_pic(bot: Bot, ev: Event) -> None:
    """图鉴侧的角色资料卡。与 ``zzzerouid_roleinfo`` 的实战面板互不冲突。"""
    char_id = await _resolve(bot, wiki_data.find_character, "角色", ev.text, "「角色介绍 猫又」")
    if char_id is None:
        return
    detail = await get_source().detail("character", char_id)
    _ai_note(_char_ai_text(detail, char_id))
    await bot.send(await convert_img(await character_card.build(char_id)))


@sv_zzz_wiki.on_prefix(
    ("音擎介绍", "音擎资料", "查音擎", "武器介绍", "武器资料"),
    to_ai="""查询绝区零音擎（音擎/武器）图鉴卡片，返回一张完整音擎资料图。

    当用户问某把音擎的基础属性、基础效果、精炼效果、突破材料时调用。
    典型说法："加农转子加多少攻击"、"淬锋的精炼效果"、"查音擎 街头巨星"、
    "音擎介绍 相声"、"音擎武器资料"。
    图中含：立绘、稀有度、武器类型、基础/附加属性、基础效果、各阶段精炼效果、
    各精炼等级的词条刷新与精炼经验消耗、突破材料（带官方材料图标）。
    调用后会附带简介、基础效果与首条精炼的纯文本。
    注意：nanoka 上游没有音擎背景故事字段，本卡不含故事文本。

    Args:
        text: 音擎正式名或简称，可省略"绝区零"前缀。
              例如 "加农转子"、"淬锋"、"街头巨星"、"冷锋"、"「相」"。
              同一音擎的不同叫法都收录；查不到时返回"没有找到音擎 xxx"。
    """,
    covers=[
        "绝区零音擎属性",
        "绝区零音擎精炼",
        "绝区零音擎突破材料",
        "绝区零武器基础效果",
        "绝区零音擎词条",
    ],
    aliases=["绝区零·音擎查询", "绝区零·音擎图鉴", "绝区零·音擎精炼", "绝区零·武器图鉴"],
)
async def send_weapon_wiki_pic(bot: Bot, ev: Event) -> None:
    """图鉴侧的音擎资料卡。"""
    weapon_id = await _resolve(bot, wiki_data.find_weapon, "音擎", ev.text, "「音擎介绍 加农转子」")
    if weapon_id is None:
        return
    detail = await get_source().detail("weapon", weapon_id)
    _ai_note(_weapon_ai_text(detail, weapon_id))
    await bot.send(await convert_img(await weapon_card.build(weapon_id)))


@sv_zzz_wiki.on_prefix(
    ("驱动盘介绍", "驱动盘资料", "查驱动盘", "驱动盘"),
    to_ai="""查询绝区零驱动盘套装图鉴卡片，返回一张完整套装资料图。

    当用户问某个驱动盘套装的二件套/四件套效果时调用。
    典型说法："啄木鸟电音四件套效果"、"极地重金属二件套加什么"、
    "查驱动盘 羽衣"、"驱动盘介绍 混沌爵士"、"驱动盘套装效果"。
    图中含：套装立绘、稀有度、驱动盘类型、套装简介、完整二件套效果与四件套效果。
    调用后会附带二件套与四件套效果的纯文本，AI 可直接复述数值。

    Args:
        text: 驱动盘套装名或简称，可省略"绝区零"前缀。
              例如 "啄木鸟电音"、"极地重金属"、"羽衣"、"混沌爵士"、" Freedom "。
              套装按 2 件 / 4 件两种效果分别给出；查不到时返回"没有找到驱动盘 xxx"。
    """,
    covers=[
        "绝区零驱动盘套装",
        "绝区零驱动盘效果",
        "绝区零四件套",
        "绝区零二件套",
    ],
    aliases=["绝区零·驱动盘查询", "绝区零·驱动盘图鉴", "绝区零·驱动盘套装效果"],
)
async def send_relic_wiki_pic(bot: Bot, ev: Event) -> None:
    """图鉴侧的驱动盘套装资料卡。"""
    suit_id = await _resolve(bot, wiki_data.find_equipment, "驱动盘", ev.text, "「驱动盘介绍 啄木鸟电音」")
    if suit_id is None:
        return
    detail = await get_source().detail("equipment", suit_id)
    _ai_note(
        f"驱动盘套装 {detail.at('name').as_str()}："
        f"二件套 {tx.plain(detail.at('desc2').as_str())}；"
        f"四件套 {tx.plain(detail.at('desc4').as_str())}"
    )
    await bot.send(await convert_img(await drive_card.build(suit_id)))


@sv_zzz_wiki.on_prefix(
    ("邦布介绍", "邦布资料", "查邦布", "邦布"),
    to_ai="""查询绝区零邦布图鉴卡片，返回一张完整邦布资料图。

    当用户问某个邦布的定位、面板数值、技能效果或升级材料时调用。
    典型说法："鲨牙布的技能是什么"、"企鹅布面板多少"、"阿全的攻击力"、
    "查邦布 搬砖王"、"邦布介绍 恶魔布"、"邦布升级材料"。
    图中含：立绘、稀有度、简介、Lv 面板数值、每个主动技的说明与倍率表、分档升级材料
    （带官方材料图标）。调用后会附带邦布简介的纯文本。

    Args:
        text: 邦布名称或常用简称，可省略"绝区零"前缀。
              例如 "鲨牙布"、"企鹅布"、"阿全"、"搬砖王"、"恶魔布"、"电锯鲨"。
              同一邦布的多个叫法都收录；查不到时返回"没有找到邦布 xxx"。
    """,
    covers=["绝区零邦布属性", "绝区零邦布技能", "绝区零邦布升级材料"],
    aliases=["绝区零·邦布查询", "绝区零·邦布图鉴", "绝区零·邦布技能"],
)
async def send_bang_boo_wiki_pic(bot: Bot, ev: Event) -> None:
    """图鉴侧的邦布资料卡。"""
    bangboo_id = await _resolve(bot, wiki_data.find_bangboo, "邦布", ev.text, "「邦布介绍 鲨牙布」")
    if bangboo_id is None:
        return
    detail = await get_source().detail("bangboo", bangboo_id)
    _ai_note(f"邦布 {detail.at('name').as_str()}：{tx.plain(detail.at('desc').as_str())}")
    await bot.send(await convert_img(await bangboo_card.build(bangboo_id)))


@sv_zzz_wiki.on_prefix(
    ("怪物介绍", "怪物资料", "查怪物", "原魔介绍"),
    to_ai="""查询绝区零怪物（敌人）图鉴卡片，返回一张完整怪物资料图。

    当用户问某个敌人的设定、族群、属性、弱点抗性或战斗特征时调用。
    典型说法："提尔锋是什么属性的怪"、"赫由托的属性和抗性"、"库萨里库的资料"、
    "查怪物 铁道地精"、"怪物介绍 泰拉斯特"。
    图中含：立绘、主属性 ICON 胶囊、族群、中文背景设定、战斗名言、战斗特征、
    抗性表，以及按等级变体去重后的形态面板。
    调用后会附带怪物名、族群与背景设定的纯文本。
    注意：这里查的是怪物图鉴，式舆/危局等关卡里出现哪些怪请用"深渊信息"/"危局信息"。

    Args:
        text: 怪物名称或简称，可省略"绝区零"前缀。
              例如 "提尔锋"、"赫由托"、"库萨里库"、"泰拉斯特"、"铁道地精"。
              同名不同形态会自动合并；查不到时返回"没有找到怪物 xxx"。
    """,
    covers=["绝区零怪物档案", "绝区零敌人资料", "绝区零怪物属性", "绝区零怪物抗性"],
    aliases=["绝区零·怪物查询", "绝区零·敌人图鉴", "绝区零·怪物属性"],
)
async def send_enemy_wiki_pic(bot: Bot, ev: Event) -> None:
    """图鉴侧的怪物资料卡。"""
    monster_id = await _resolve(bot, wiki_data.find_monster, "怪物", ev.text, "「怪物介绍 提尔锋」")
    if monster_id is None:
        return
    detail = await get_source().detail("monster", monster_id)
    _ai_note(
        f"怪物 {detail.at('name').as_str()}（族群 {detail.at('group_desc').as_str()}）："
        f"{tx.plain(detail.at('desc').as_str())}"
    )
    await bot.send(await convert_img(await monster_card.build(monster_id)))


# ---------------------------------------------------------------- endgame
@sv_zzz_wiki.on_prefix(
    ("深渊信息", "式舆信息"),
    to_ai=f"""查看绝区零式舆防卫战（式舆）某一期的全局阵容图。

    当用户问式舆防卫战某一期有几条防线、每条防线几只怪、怪物属性和血量时调用。
    典型说法："式舆信息"、"深渊信息"、"上期式舆"、"式舆 2026.9.1"、"本周式舆怪物"。
    图中按节点逐条防线列出：防线名与等级 -> 房间 -> 房间内怪物（带属性 ICON、
    弱点与抗性胶囊、压缩血量）。第五防线的三个房间会合并成一条整行显示。
    调用后会附带当前展示的期次范围。
    注意：这是版本阵容，不是某个 UID 的通关战绩（个人战绩请用"式舆防卫战"）。{_PERIOD_HINT}

    Args:
        text: 期次选择词，留空取本期。可写：
              - "上期" / "下期" / "本期"，例如 "上期式舆信息"
              - 日期，例如 "2026.9.1"、"9月1日式舆"
              认不出的期次会返回"没有找到式舆防卫战 xxx 对应的期次"并附上可选写法。
    """,
    covers=["绝区零式舆防卫战阵容", "绝区零式舆节点", "绝区零式舆怪物", "绝区零深渊信息"],
    aliases=["绝区零·式舆防卫战阵容", "绝区零·式舆节点阵容", "绝区零·式舆怪物阵容"],
)
async def send_shiyu_wiki_pic(bot: Bot, ev: Event) -> None:
    """式舆防卫战（别名「深渊信息」）的版本阵容卡。"""
    await _endgame(bot, ev, "shiyu")


@sv_zzz_wiki.on_prefix(
    ("危局信息",),
    to_ai=f"""查看绝区零危局强袭战某一期的三只怪阵容图。

    当用户问危局强袭战本期打哪三只怪、每只怪的属性与血量时调用。
    典型说法："危局信息"、"本期危局"、"上期危局"、"危局 69041"、"危局强袭战怪物"。
    图中一期只出一期（三关横排），每关一张卡：怪物名与等级 -> 弱点/抗性胶囊 -> 怪物立绘与血量。
    调用后会附带当前展示的期次与时间范围。
    注意：这是版本阵容，不是某个 UID 的战绩（个人战绩请用"危局强袭战"）。{_PERIOD_HINT}

    Args:
        text: 期次选择词，留空取本期。可写：
              - "上期" / "下期" / "本期"，例如 "上期危局信息"
              - 期次 id 或日期，例如 "69041"、"2026.9.1"
              认不出的期次会返回"没有找到危局强袭战 xxx 对应的期次"并附上可选写法。
    """,
    covers=["绝区零危局强袭战阵容", "绝区零强袭战怪物", "绝区零危局怪物"],
    aliases=["绝区零·危局强袭战阵容", "绝区零·强袭战怪物阵容", "绝区零·危局阵容"],
)
async def send_haedal_wiki_pic(bot: Bot, ev: Event) -> None:
    """危局强袭战的版本阵容卡。"""
    await _endgame(bot, ev, "haedal")


@sv_zzz_wiki.on_prefix(
    ("临界信息",),
    to_ai=f"""查看绝区零临界推演某一期的关卡与房间阵容图。

    当用户问临界推演某一期有几个 STAGE、每层每间房有哪些怪时调用。
    典型说法："临界信息"、"上期临界"、"临界推演阵容"、"临界 102"、"本期临界怪物"。
    图中按 STAGE 逐行展开：STAGE 名 -> 房间名与标签 -> 房间内怪物（带属性 ICON、
    弱点/抗性胶囊、压缩血量）；末尾附上该期的结局记录。
    调用后会附带当前展示的期次。
    注意：这是版本阵容，不是某个 UID 的战绩（个人战绩请用"临界推演"）。{_PERIOD_HINT}

    Args:
        text: 期次选择词，留空取本期。可写：
              - "上期" / "下期" / "本期"，例如 "上期临界信息"
              - 期次 id 或日期，例如 "102"、"2026.9.1"
              认不出的期次会返回"没有找到临界推演 xxx 对应的期次"并附上可选写法。
    """,
    covers=["绝区零临界推演阵容", "绝区零临界推演关卡", "绝区零临界怪物"],
    aliases=["绝区零·临界推演阵容", "绝区零·临界推演关卡", "绝区零·临界怪物阵容"],
)
async def send_simul_wiki_pic(bot: Bot, ev: Event) -> None:
    """临界推演的版本阵容卡。"""
    await _endgame(bot, ev, "simul")


@sv_zzz_wiki.on_prefix(
    ("拟境信息", "拟境湮灭战"),
    to_ai=f"""查看绝区零拟境湮灭战某一期的首领阵容图。

    当用户问拟境湮灭战某期有几个异构首领、每个首领各难度出什么怪时调用。
    典型说法："拟境信息"、"拟境湮灭战"、"上期拟境"、"本期拟境首领"、"拟境怪物"。
    图中按异构首领分组：首领名与等级 -> 难度 -> 房间内怪物（带属性 ICON、
    弱点/抗性胶囊、压缩血量）；首领立绘走页首。
    调用后会附带当前展示的期次与时间范围。
    注意：这是版本阵容，不是某个 UID 的战绩（个人战绩请用"拟境湮灭战"）。{_PERIOD_HINT}

    Args:
        text: 期次选择词，留空取本期。可写：
              - "上期" / "下期" / "本期"，例如 "上期拟境信息"
              - 日期，例如 "2026.9.1"
              认不出的期次会返回"没有找到拟境湮灭战 xxx 对应的期次"并附上可选写法。
    """,
    covers=["绝区零拟境湮灭战阵容", "绝区零拟境首领", "绝区零拟境怪物"],
    aliases=["绝区零·拟境湮灭战阵容", "绝区零·拟境首领阵容", "绝区零·拟境怪物阵容"],
)
async def send_hard_wiki_pic(bot: Bot, ev: Event) -> None:
    """拟境湮灭战的版本阵容卡。"""
    await _endgame(bot, ev, "hard")


async def _endgame(bot: Bot, ev: Event, mode: str) -> None:
    """endgame 四个模式的公共入口。

    期次选择词只认前缀（``上期``/``下期``/``本期``），其余内容当作期次 id 或日期。
    """
    render, label, periods_of = _MODES[mode]
    selector = _split_period(ev.text.strip())
    try:
        period = wiki_data.pick(await periods_of(), selector)
    except LookupError:
        await _fail(bot, f"没有找到{label}「{selector}」对应的期次，{_PERIOD_HINT}")
        return
    _ai_note(f"{label}：当前展示{period.label}。{_PERIOD_HINT}")
    await bot.send(await convert_img(await render(selector)))


# ---------------------------------------------------------------- AI 文本
def _char_ai_text(detail: JsonNode, char_id: str) -> str:
    """角色的纯文本结论，方便 AI 直接回答。"""
    bits = [f"角色 {detail.at('name').as_str()}（id {char_id}）"]
    info = detail.maybe("partner_info")
    if info is not None:
        profile = info.at("profile_desc").as_str()
        if profile:
            bits.append(profile)
    for key in ("element_type", "weapon_type", "camp", "hit_type"):
        node = detail.maybe(key)
        if node is None or not node.size():
            continue
        for _, item in node.items():
            bits.append(f"{key}={item.as_str()}")
            break
    bits.append(f"rarity={detail.at('rarity').as_int()}")
    return " ".join(bits)


def _weapon_ai_text(detail: JsonNode, weapon_id: str) -> str:
    """音擎的纯文本结论。nanoka 没有音擎故事字段，只能给简介 / 基础效果 / 精炼。"""
    bits = [f"音擎 {detail.at('name').as_str()}（id {weapon_id}）"]
    for label, key in (("简介", "desc"), ("基础效果", "desc2")):
        raw = detail.at(key).as_str()
        if raw:
            bits.append(f"{label}：{tx.plain(raw)}")
    talents = detail.maybe("talents")
    if talents is not None:
        for key, item in talents.items():
            bits.append(f"精炼 {key} {item.at('name').as_str()}：{tx.plain(item.at('desc').as_str())}")
            break
    return " ".join(bits)


# ---------------------------------------------------------------- 攻略
@sv_zzz_guide.on_prefix("角色攻略")
@sv_zzz_guide.on_suffix("攻略")
async def send_role_guide_pic(bot: Bot, ev: Event) -> None:
    from ..utils.name_convert import alias_to_char_name
    from ..utils.resource.RESOURCE_PATH import CAT_GUIDE_PATH, FLOWER_GUIDE_PATH
    from ..zzzerouid_config.zzzero_config import ZZZ_CONFIG

    name = alias_to_char_name(ev.text.strip())
    logger.info(f"[绝区零] 角色攻略: {name}")
    gp = ZZZ_CONFIG.get_config("ZZZGuideProvide").data
    logger.info(f"[绝区零] 攻略提供方: {gp}")
    if gp == "猫冬":
        path = CAT_GUIDE_PATH / f"{name}.jpg"
    else:
        path1 = FLOWER_GUIDE_PATH / f"{name}.jpg"
        path2 = FLOWER_GUIDE_PATH / f"{name}.png"
        path = path1 if path1.exists() else path2

    if path.exists():
        await bot.send(await convert_img(path))
    else:
        await bot.send("[绝区零] 该角色攻略不存在, 请检查输入角色是否正确！")
