"""式舆防卫战 / 危局强袭战 / 临界推演 / 拟境湮灭战 四张 endgame 卡片。

排版约定（面向手机端竖屏）：
- 一期只出一期：危局按 ``zone_type`` 过滤后再按时间窗口选期
- 一条防线一张卡；卡内房间并排，房间内怪物一行三个平铺
- **只有一层卡**：房间不再套卡，只用一条小标题分隔；怪物图按这张卡真正分到的
  宽度算格子（见 :func:`base.stage_lane_width`），否则会被根节点缩放糊掉

各模式上游的关卡结构并不一致，这里各自做一次归一化：

============  ===================================================
模式          上游路径 → :class:`StageView`
============  ===================================================
式舆          ``zone[]``，``防线*`` 开头的是新防线，随后的
              ``房间一/二/三`` 并列 zone 收进同一条防线
危局          ``modes[].zone[]``，只留 ``zone_type`` 为强袭战的那种
临界          ``node[].battle[]``，房间挂在 ``battle.layer_room``
              （``battle.layer.layer_room`` 恒为空，只当兜底）
拟境          ``boss[].mode[].zone[].layer_room``
============  ===================================================
"""

from typing import Final
from datetime import datetime
from dataclasses import dataclass

from . import base, common
from ...utils.nanoka import element as el
from ...utils.nanoka.data import Monster, decorate, monsters_of_room
from ...utils.nanoka.source import get_source
from ...utils.nanoka.json_node import JsonNode

M_PER_ROW: Final[int] = 3
ROOMS_PER_ROW: Final[int] = 2
#: 危局每期固定三只怪，横排一行正好
HAEDAL_PER_ROW: Final[int] = 3
#: 怪物格子边长上限（CSS px），房间只有一只怪时别把图撑爆
M_CELL_MAX: Final[int] = 138

_CN_NUM: Final[tuple[str, ...]] = ("一", "二", "三", "四", "五", "六", "七", "八", "九", "十")


@dataclass(slots=True)
class RoomView:
    """一个房间（可选队伍）的怪物集合。

    ``title`` 为空表示无名（危局那种一关一房），此时只留波数徽章；
    ``wave`` 单独存，避免「房间 1 · 4 波」这种标题把单房间的卡片撑出无意义的一行。
    """

    title: str
    wave: int
    monsters: list[Monster]


@dataclass(slots=True)
class StageView:
    """一条关卡。"""

    title: str
    note: str
    rooms: list[RoomView]


@dataclass(slots=True)
class ModeView:
    """一个期次。"""

    kicker: str
    title: str
    subtitle: str
    period: str
    stages: list[StageView]
    records: list[tuple[str, str]]
    hero_art: str = ""
    #: 一行放几个关卡卡（危局每期三只怪，横排才不浪费竖屏空间）
    stage_columns: int = 1


# ---------------------------------------------------------------- 房间
def _rooms_of(lane_rooms: JsonNode, name_hint: str = "") -> list[RoomView]:
    """展开一条防线的房间。

    标题只在「有名字」或「多房间需要编号」时才给：危局每关只有一个房间，
    再挂一个「阵容 · 1波」纯属噪音，留空让弱点/抗性条直接起头。
    """
    out: list[RoomView] = []
    multi = lane_rooms.size() > 1
    for idx, (_, room) in enumerate(lane_rooms.items(), start=1):
        monsters = monsters_of_room(room)
        if not monsters:
            continue
        decorate(room, monsters)
        title = name_hint
        if not title and multi:
            title = f"房间 {idx}"
        out.append(RoomView(title=title, wave=room.at("waves_num").as_int(), monsters=monsters))
    return out


def _rooms_of_battle(battle: JsonNode) -> JsonNode | None:
    """临界推演的房间挂在 ``battle`` 顶层，``battle.layer.layer_room`` 恒为空。"""
    direct = battle.maybe("layer_room")
    if direct is not None and not direct.is_empty():
        return direct
    layer = battle.maybe("layer")
    if layer is None:
        return None
    return layer.maybe("layer_room")


async def _room_block(room: RoomView, lane: int, cap: int) -> str:
    """房间块：小标题 + 弱点/抗性条 + 怪物平铺。

    ``lane`` 是这条房间卡的实际宽度，``cap`` 是一行最多放几只。
    怪物数不足一行时按实际数量摊开，不会把格子留在那儿空着。
    外面已经有一层关卡卡，这里不再套卡，只用一条小标题分隔。
    """
    count = len(room.monsters)
    per_row = max(1, min(count, cap))
    cell_w = min((lane - 5 * (per_row - 1)) // per_row, M_CELL_MAX)
    icon = cell_w * base.SCALE
    arts = await base.icons([m.image_code for m in room.monsters], icon, icon, 0.12)
    cells = [base.cell(arts.get(mon.image_code, ""), mon.name, common.human_int(mon.hp)) for mon in room.monsters]
    weak: list[int] = room.monsters[0].weakness if room.monsters else []
    res: list[int] = room.monsters[0].resistance if room.monsters else []
    tags: list[str] = []
    if weak:
        tags.append('<span class="tl">弱点</span>' + "".join(_elt(weak, "wchip")))
    if res:
        tags.append('<span class="tl">抗性</span>' + "".join(_elt(res, "rchip")))
    head = f'<div class="rhead"><b>{base.esc(room.title)}</b></div>' if room.title else ""
    if tags:
        head += f'<div class="wrow">{"".join(tags)}</div>'
    return head + base.grid(cells, cell_w)


def _elt(ids: list[int], cls: str) -> str:
    """属性胶囊。``uri`` 必须包在 ``<img src>`` 里，否则 pytakumi 会当正文渲染。"""
    out: list[str] = []
    for eid in ids:
        uri = base.element_uri(eid, 40)
        if uri:
            out.append(f'<div class="{cls}"><img src="{uri}"/><span>{el.element_name(eid)}</span></div>')
    return "".join(out)


# ---------------------------------------------------------------- 关卡
async def _stage_block(stage: StageView, outer: int, fill: bool) -> str:
    """一条防线一张卡，卡内房间并排，房间内怪物一行三个。

    ``outer`` 是这张卡真正分到的宽度（危局三关并排时只有 1/3 页宽）。
    不按整页宽算格子，怪物图会按满宽排版再被根节点缩放，越小越糊。
    ``fill`` 让同一行的卡片等高，怪物图落在同一条水平线上。
    """
    count = len(stage.rooms)
    per_row = max(1, min(count, ROOMS_PER_ROW))
    # 三个房间并排时格子会偏窄，怪物改成一行两个才看得清
    cap = 2 if per_row >= 3 else M_PER_ROW
    inner = outer - 20
    lane = (inner - base.GAP * (per_row - 1)) // per_row
    blocks = [await _room_block(room, lane, cap) for room in stage.rooms]
    body = base.columns(blocks, per_row) if per_row > 1 else f'<div class="rblk">{"".join(blocks)}</div>'
    return base.card(_stage_head(stage) + body, fill=fill)


def _stage_head(stage: StageView) -> str:
    """关卡头：名称 + 等级/波数标签靠右。

    波数放在这里而不是徽章行，徽章行就能压在一行内。
    """
    monsters = sum(len(r.monsters) for r in stage.rooms)
    bits = [stage.note] if stage.note else []
    waves = [r.wave for r in stage.rooms if r.wave]
    if waves:
        bits.append(f"{max(waves)} 波" if len(waves) == 1 else f"{min(waves)}~{max(waves)} 波")
    if not bits:
        bits.append(f"{len(stage.rooms)} 个房间 · {monsters} 只怪")
    return (
        f'<div class="shead"><span class="sname">{base.esc(stage.title)}</span>'
        f'<span class="snote head">{base.esc(" · ".join(bits))}</span></div>'
    )


# ---------------------------------------------------------------- 各模式
async def shiyu(selector: str) -> bytes:
    """式舆防卫战：节点 -> 防线 -> 房间。

    上游把第五防线的三个房间拆成三个并列 ``zone``（``房间一/二/三``），
    前面还夹一个没有房间的空 ``zone`` 当分隔，这里要重新拼回一条防线。
    """
    from ...utils.nanoka import data

    periods = await data.shiyu_periods()
    period = data.pick(periods, selector)
    detail = await get_source().detail("shiyu", period.key)

    stages: list[StageView] = []
    current: StageView | None = None
    group_open = False
    for _, zone in detail.at("zone").items():
        name = zone.at("name").as_str()
        rooms_node = zone.maybe("layer_room")
        # 「房间一/二/三」用 zone 自己的名字，其余按「房间 N」编
        hint = name if name.startswith("房间") else ""
        rooms = _rooms_of(rooms_node, hint) if rooms_node is not None else []
        level = f"Lv{zone.at('monster_level').as_int()}" if zone.has("monster_level") else ""

        if "防线" in name:
            current = StageView(title=name, note=level, rooms=rooms)
            stages.append(current)
            group_open = False
            continue
        if group_open and current is not None:
            current.rooms.extend(rooms)
            continue
        # 空 zone 是占位；随后的「房间一/二/三」要收成同一条防线
        current = StageView(title=f"第{_cn_num(len(stages))}防线", note=level, rooms=rooms)
        stages.append(current)
        group_open = True

    stages = [s for s in stages if s.rooms]
    view = ModeView(
        kicker="SHIYU DEFENCE / 式舆防卫战",
        title=detail.at("name").as_str(),
        subtitle="",
        period=f"节点 {period.key} · {_span(period.begin, period.end)}",
        stages=stages,
        records=[],
    )
    return await _render(view, "#5fe08a")


async def haedal(selector: str) -> bytes:
    """危局强袭战：每期三只怪（按 ``zone_type`` 过滤，异构挑战不算）。"""
    from ...utils.nanoka import data

    periods = await data.haedal_periods()
    period = data.pick(periods, selector)
    detail = await get_source().detail("boss", period.key)

    stages: list[StageView] = []
    art_code = ""
    for mode in detail.at("modes").values():
        if mode.at("zone_type").as_int() != data.HAEDAL_ZONE:
            continue
        for _, zone in mode.at("zone").items():
            rooms_node = zone.maybe("layer_room")
            if rooms_node is None:
                continue
            rooms = _rooms_of(rooms_node)
            if not rooms:
                continue
            if not art_code and rooms[0].monsters:
                art_code = rooms[0].monsters[0].image_code
            note = f"Lv{zone.at('monster_level').as_int()}" if zone.has("monster_level") else ""
            stages.append(StageView(title=zone.at("name").as_str(), note=note, rooms=rooms))

    view = ModeView(
        kicker="RUTHLESS ASSAULT / 危局强袭战",
        title=f"第 {period.key} 期",
        subtitle=detail.at("name").as_str(),
        period=_span(period.begin, period.end),
        stages=stages,
        records=[],
        hero_art=art_code,
        stage_columns=HAEDAL_PER_ROW,
    )
    return await _render(view, "#ff7a6b")


async def simul(selector: str) -> bytes:
    """临界推演：``node`` 逐行，``battle`` 逐房间；空的 PLOT 节点自动跳过。"""
    from ...utils.nanoka import data

    periods = await data.simul_periods()
    period = data.pick(periods, selector)
    detail = await get_source().detail("simul", period.key)

    stages: list[StageView] = []
    for _, node in detail.at("node").items():
        battles = node.maybe("battle")
        if battles is None or battles.is_empty():
            continue
        rooms: list[RoomView] = []
        for bidx, (_, battle) in enumerate(battles.items(), start=1):
            # 房间挂在 battle 顶层；layer.layer_room 恒为空，只当兜底
            lane_rooms = _rooms_of_battle(battle)
            if lane_rooms is None:
                continue
            tag = _tag_text(battle.at("tag").as_str())
            name = battle.at("name").as_str() or f"房间 {bidx}"
            title = name + (f" · {tag}" if tag else "")
            found = _rooms_of(lane_rooms, title)
            if found:
                rooms.extend(found)
        if rooms:
            stages.append(StageView(title=node.at("name").as_str(), note="", rooms=rooms))

    records: list[tuple[str, str]] = []
    record = detail.maybe("record")
    if record is not None:
        for _, item in record.items():
            records.append((item.at("name").as_str(), item.at("desc").as_str()))

    view = ModeView(
        kicker="SIMULACRUM / 临界推演",
        title=f"第 {period.key} 期",
        subtitle="",
        period=_span(period.begin, period.end),
        stages=stages,
        records=records,
    )
    return await _render(view, "#7fd4ff")


async def hard(selector: str) -> bytes:
    """拟境湮灭战：每期若干异构首领，首领立绘走页首。"""
    from ...utils.nanoka import data

    periods = await data.hard_periods()
    period = data.pick(periods, selector)
    detail = await get_source().detail("hard", period.key)

    stages: list[StageView] = []
    art_code = ""
    for _, boss in detail.at("boss").items():
        rooms: list[RoomView] = []
        for mode in boss.at("mode").values():
            zone_node = mode.maybe("zone")
            if zone_node is None:
                continue
            title = f"难度 {mode.at('difficulty').as_int()}"
            for _, zone in zone_node.items():
                lane_rooms = zone.maybe("layer_room")
                if lane_rooms is None:
                    continue
                rooms.extend(_rooms_of(lane_rooms, title))
        if not rooms:
            continue
        if not art_code:
            art_code = _code(boss.at("image").as_str())
        note = f"Lv{boss.at('avatar_level').as_int()}" if boss.has("avatar_level") else ""
        stages.append(StageView(title=boss.at("name").as_str(), note=note, rooms=rooms))

    view = ModeView(
        kicker="ANNIHILATION SIMULACRUM / 拟境湮灭战",
        title=period.label,
        subtitle=detail.at("version").as_str(),
        period=_span(period.begin, period.end),
        stages=stages,
        records=[],
        hero_art=art_code,
    )
    return await _render(view, "#c77dff")


# ---------------------------------------------------------------- 组装
def _cn_num(idx: int) -> str:
    if idx < len(_CN_NUM):
        return _CN_NUM[idx]
    return str(idx + 1)


def _tag_text(tag: str) -> str:
    return common.plain(tag)


def _code(path: str) -> str:
    tail = path.rsplit("/", 1)[-1]
    return tail.rsplit(".", 1)[0]


def _span(begin: datetime | None, end: datetime | None) -> str:
    if begin is None or end is None:
        return ""
    return f"{begin:%Y-%m-%d} ~ {end:%Y-%m-%d}"


async def _render(view: ModeView, accent: str) -> bytes:
    art = ""
    if view.hero_art:
        art = await base.remote_icon(view.hero_art, base.HERO_RW, base.HERO_RH, 0.25)

    chips: list[str] = [base.chip_text(view.period)] if view.period else []
    parts = [base.hero(view.kicker, view.title, view.subtitle, art, "".join(chips))]

    lanes: list[str] = []
    outer = base.stage_lane_width(view.stage_columns)
    fill = view.stage_columns > 1
    for stage in view.stages:
        block = await _stage_block(stage, outer, fill)
        if block:
            lanes.append(block)

    if lanes:
        parts.append(base.section("关卡阵容", "STAGES", f"{len(lanes)} 关"))
        parts.extend(base.row_of(lanes, view.stage_columns))
    else:
        parts.append(base.card('<div class="txt dim">该期次没有怪物数据</div>'))

    if view.records:
        blocks = [_record_block(name, body) for name, body in view.records]
        parts.append(base.section("结局", "RECORDS"))
        parts.append(base.columns(blocks, 2))

    parts.append(base.footer("数据源 nanoka.cc"))
    return await base.render(accent, "".join(parts))


def _record_block(name: str, body: str) -> str:
    head = f'<div class="row"><span class="kvv">{base.esc(name)}</span></div>'
    return f'<div class="col">{base.card(head + f"""<div class="txt">{common.markup(body)}</div>""", tight=True)}</div>'
