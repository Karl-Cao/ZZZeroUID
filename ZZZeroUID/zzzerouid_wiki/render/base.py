"""wiki 卡片渲染底座：pytakumi 页面、背景、通用积木。

版式约定（面向手机端竖屏）：
- 页面宽 :data:`PAGE_W` CSS px，高度随内容增长，整体偏窄偏长
- 标题一律 ``font-style:italic`` 的 ``[ 名称 ]``
- 数值统一走 ``.num``（橙黄），增益走 ``.good``（绿）
- 面板内容按 2/3 列平铺，避免竖向拉长和留白
- 页首右侧可挂一条数值竖栏（:func:`hero` 的 ``rail``），常用在角色/邦布面板

pytakumi 的三个坑（踩过就别再踩）：
- ``<div>`` 上的 inline ``style`` 完全无效，宽度/配色一律要生成 class 规则
- 后代选择器（``.父 .子``）除 ``.good .num`` 外都不生效，
  宽度类必须直接挂在元素上，靠源顺序覆盖默认值
- ``flex:1`` 会用 ``flex-basis:0%`` 盖掉显式 ``width``，
  要锁列宽得加 ``.lane{{flex:0 0 auto}}``
"""

import base64
from io import BytesIO
from html import escape
from typing import Final
from pathlib import Path

import httpx
from PIL import Image
from PIL.Image import Resampling

from gsuid_core.utils.html_render import render_html_to_bytes

from ...utils.nanoka import element as el
from ...utils.nanoka.cache import load_asset
from ...utils.nanoka.source import get_source
from ...utils.nanoka.material import Material
from ...utils.resource.RESOURCE_PATH import TEXT2D_PATH

#: 设备像素倍率
SCALE: Final[int] = 3
#: 逻辑页宽（CSS px）。比手机屏宽略窄，保证竖屏阅读不横拉
PAGE_W: Final[int] = 760
#: 页首立绘的目标比例（CSS px），2:1 竖屏观感
HERO_RW: Final[int] = 1240
HERO_RH: Final[int] = 620
PAD: Final[int] = 10
GAP: Final[int] = 7
#: 页首右侧数值竖栏宽度（CSS px）
HERO_RAIL_W: Final[int] = 176
#: 图标式页首里方形 ICON 的画布边长（CSS px）
ICON_BOX: Final[int] = 200

BG_PATH: Final[Path] = TEXT2D_PATH / "bg.jpg"
INK: Final[str] = "#f2f5fb"
INK_2: Final[str] = "#c3cbdb"
GOLD: Final[str] = "#ffcf4d"
HAIR: Final[str] = "rgba(255,255,255,0.10)"
#: 局内货币 id -> 名称
CURRENCY_COLOR: Final[str] = "#FFD24A"

#: 拉不到官方图标时的兜底色徽章：档位 -> (文字, 色)
TIER_STYLE: Final[dict[int, tuple[str, str]]] = {
    1: ("初级", "#8FA3C0"),
    2: ("中级", "#5FA8FF"),
    3: ("高级", "#C77DFF"),
    4: ("顶级", "#FFB454"),
}

_URI: dict[str, str] = {}
#: 格子宽度 -> 动态生成的 class 名，由 :func:`page` 追加成 CSS 规则
_W_CLS: dict[int, str] = {}


def _width_class(width: int) -> str:
    if width not in _W_CLS:
        _W_CLS[width] = f"cw{len(_W_CLS)}"
    return _W_CLS[width]


def _width_rules() -> str:
    return "".join(f".{cls}{{width:{w}px;}}" for w, cls in _W_CLS.items())


def _tier_rules() -> str:
    """材料档位配色。pytakumi 不认 inline style，只能生成 class 规则。"""
    rules = [f".mtc{{background:{CURRENCY_COLOR};}}"]
    rules.extend(f".mt{tier}{{background:{color};}}" for tier, (_, color) in sorted(TIER_STYLE.items()))
    return "".join(rules)


# ---------------------------------------------------------------- 素材编码
def esc(text: str) -> str:
    return escape(text, quote=True)


def _mime(path: Path) -> str:
    if path.suffix.lower() in (".jpg", ".jpeg"):
        return "image/jpeg"
    return "image/png"


def file_uri(path: Path) -> str:
    """把本地文件编码成 data URI，按路径记忆。"""
    key = f"f:{path}"
    if key in _URI:
        return _URI[key]
    if not path.exists():
        return ""
    suffix = path.suffix.lower()
    mime = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/webp" if suffix == ".webp" else "image/png"
    uri = f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"
    _URI[key] = uri
    return uri


def _resized_uri(path: Path, size: int) -> str:
    """缩放后再编码，避免大图撑爆页面。"""
    key = f"r:{path}:{size}"
    if key in _URI:
        return _URI[key]
    if not path.is_file():
        return ""
    with Image.open(path) as img:
        img = img.convert("RGBA")
        img.thumbnail((size, size), Resampling.LANCZOS)
        buf = BytesIO()
        img.save(buf, "PNG")
    uri = f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('ascii')}"
    _URI[key] = uri
    return uri


def texture(name: str, size: int = 40) -> str:
    """texture2d 下的通用小图标。``name`` 为空表示没有对应素材。"""
    if not name:
        return ""
    return _resized_uri(TEXT2D_PATH / name, size * SCALE)


def element_uri(element_id: int, size: int = 40) -> str:
    return texture(el.element_icon(element_id), size)


def role_uri(role_id: int, size: int = 40) -> str:
    name = el.role_icon(role_id)
    if not name:
        return ""
    return _resized_uri(TEXT2D_PATH / "pro" / f"{name}.png", size * SCALE)


def prop_uri(name: str, size: int = 40) -> str:
    if not name:
        return ""
    return _resized_uri(TEXT2D_PATH / "prop" / f"{name}.png", size * SCALE)


def skill_uri(name: str, size: int = 40) -> str:
    """技能分类 ICON：按 ``分类：技能名`` 的前缀取 ``texture2d/skill_icon``。"""
    code = el.skill_icon(name)
    if not code:
        return ""
    return _resized_uri(TEXT2D_PATH / "skill_icon" / f"{code}.webp", size * SCALE)


def local_canvas(path: Path, size: int) -> str:
    """把本地素材等比放进 ``size`` 见方的透明画布，保留原图不裁切。

    ``thumbnail`` 只缩不放，152×152 的驱动盘套装图要摆进 200 见方的画布
    得自己开一张新图；等比 + 居中留白才不会把图标拉变形。
    """
    key = f"cv:{path}:{size}"
    if key in _URI:
        return _URI[key]
    if not path.is_file():
        return ""
    with Image.open(path) as img:
        img = img.convert("RGBA")
        img.thumbnail((size, size), Resampling.LANCZOS)
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        canvas.paste(img, ((size - img.width) // 2, (size - img.height) // 2), img)
        buf = BytesIO()
        canvas.save(buf, "PNG")
    uri = f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('ascii')}"
    _URI[key] = uri
    return uri


async def remote_icon(code_name: str, out_w: int, out_h: int, bias: float = 0.2) -> str:
    """取上游静态素材（怪物图等），落盘缓存后按 ``out_w``×``out_h`` 裁剪编码。

    ``bias`` 越小越靠上取。上游是竖版立绘，怪物图取 0.12 只留上半身。
    """
    if not code_name:
        return ""
    key = f"n:{code_name}:{out_w}x{out_h}:{bias}"
    if key in _URI:
        return _URI[key]
    source = get_source()
    url = source.asset(code_name)

    async def _fetch() -> bytes:
        async with httpx.AsyncClient(timeout=40, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return b""
            return resp.content

    data = await load_asset(code_name, _fetch)
    if not data:
        return ""
    with Image.open(BytesIO(data)) as img:
        img = img.convert("RGBA")
        img = _crop(img, out_w, out_h, bias)
        img = img.resize((out_w, out_h), Resampling.LANCZOS)
        buf = BytesIO()
        img.save(buf, "PNG", optimize=True)
    uri = f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('ascii')}"
    _URI[key] = uri
    return uri


def _crop(img: Image.Image, ratio_w: int, ratio_h: int, bias: float) -> Image.Image:
    """按目标比例裁剪，``bias`` 越小越靠上取。"""
    src_w, src_h = img.size
    target = ratio_w / ratio_h
    current = src_w / src_h
    if current > target:
        crop_w = int(src_h * target)
        x0 = (src_w - crop_w) // 2
        return img.crop((x0, 0, x0 + crop_w, src_h))
    crop_h = int(src_w / target)
    y0 = int((src_h - crop_h) * bias)
    return img.crop((0, y0, src_w, y0 + crop_h))


async def icons(
    codes: list[str],
    out_w: int,
    out_h: int,
    bias: float = 0.2,
) -> dict[str, str]:
    """批量取上游素材，键为原始代号。"""
    uniq = [c for c in dict.fromkeys(codes) if c]
    out: dict[str, str] = {}
    for code in uniq:
        out[code] = await remote_icon(code, out_w, out_h, bias)
    return out


def local_icon(path: Path, size: int = 200) -> str:
    """本地素材（角色立绘、音擎、驱动盘等）。"""
    return _resized_uri(path, size * SCALE)


def local_big_enough(path: Path, min_side: int) -> bool:
    """本地素材够不够撑起页首；太小就宁可走 CDN 拿原图。

    邦布头像只有 152×186，硬拉到页首宽会糊成马赛克。
    """
    if not path.is_file():
        return False
    with Image.open(path) as img:
        return min(img.size) >= min_side


def crop_uri(path: Path, ratio_w: int, ratio_h: int, size: int = 400, bias: float = 0.35) -> str:
    """按目标比例预裁剪后再编码。

    pytakumi 会忽略 ``<img>`` 的 ``height`` / ``object-fit``，所以形状必须在这里
    裁好；``bias`` 越小越靠上取（立绘的脸通常在上半部）。
    """
    key = f"c:{path}:{ratio_w}x{ratio_h}:{size}:{bias}"
    if key in _URI:
        return _URI[key]
    if not path.exists():
        return ""
    with Image.open(path) as img:
        img = img.convert("RGBA")
        img = _crop(img, ratio_w, ratio_h, bias)
        img = img.resize((ratio_w * 2, ratio_h * 2), Resampling.LANCZOS)
        buf = BytesIO()
        img.save(buf, "PNG")
    uri = f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('ascii')}"
    _URI[key] = uri
    return uri


# ---------------------------------------------------------------- 样式
def _css(accent: str) -> str:
    return f"""
*{{box-sizing:border-box;}}
.pytakumi-root{{
  width:{PAGE_W}px; min-height:120px; padding:{PAD}px;
  background-image:url({file_uri(BG_PATH)});
  background-size:100% auto; background-repeat:repeat-y; background-position:top center;
  font-family:'MiSans',sans-serif; color:{INK}; font-size:13px; line-height:1.6;
}}
.bd{{display:flex; flex-direction:column; gap:{GAP}px;}}

.hero{{position:relative; border-radius:14px; overflow:hidden; background:#0e1118; min-height:118px;}}
/* 比例已在 Python 侧裁好，这里只给宽度，避免 pytakumi 忽略 height 时溢出 */
.heroimg{{width:100%; display:block;}}
.veil{{position:absolute; left:0; right:0; top:0; bottom:0;
  background:linear-gradient(180deg, rgba(0,0,0,0.10) 0%, rgba(0,0,0,0.62) 46%, rgba(6,8,12,0.96) 78%);}}
.heroin{{position:absolute; left:0; right:0; bottom:0; padding:12px 12px 10px;}}
/* 带右栏时左侧文案让位，别压在数值面板上 */
.hero.railed .heroin{{right:{HERO_RAIL_W + 16}px;}}
/* 立绘缺失时 hero 会塌到 min-height，竖栏顶出容器被 overflow:hidden 裁掉，这里兜住 */
.hero.railed{{min-height:196px;}}
/* 数值竖栏：贴右缘、贴底边，和左侧标题块视觉对齐 */
.herorail{{position:absolute; right:8px; bottom:8px; width:{HERO_RAIL_W}px;
  padding:7px 9px 8px; border-radius:10px; background:rgba(6,8,12,0.66);
  border:1px solid {HAIR};}}
.railnote{{font-size:9px; letter-spacing:1.4px; color:rgba(255,255,255,0.34);
  font-weight:600; padding:0 0 3px 2px;}}
.rail .kv{{font-size:11.5px; line-height:1.62;}}
.rail .kv img{{width:17px; height:17px;}}
.rail .kvsp{{width:17px; flex:0 0 17px;}}
.rail .kvk{{min-width:46px;}}
.kick{{font-size:10px; letter-spacing:2.4px; color:{accent}; font-weight:600;}}
/* 图标式页首：小素材（驱动盘套装图只有 152×152）做满宽立绘只会糊，
   改成方形 ICON 在左、文字块在右。宽度必须显式给，pytakumi 不认 img 的 height */
.iconhero{{display:flex; align-items:center; gap:14px; padding:12px 14px;}}
.ihimg{{flex:0 0 auto;}}
.iheroin{{flex:1 1 auto; min-width:0;}}
.tname{{font-size:30px; font-weight:700; font-style:italic; letter-spacing:1px; line-height:1.15;}}
.tsub{{font-size:12px; color:{INK_2}; margin-top:2px;}}
.chips{{display:flex; flex-wrap:wrap; gap:5px; margin-top:7px;}}
.chip{{display:flex; align-items:center; gap:4px; padding:2px 7px 2px 3px; border-radius:11px;
  background:rgba(8,10,15,0.72); border:1px solid {HAIR}; font-size:11px;}}
.chip img{{width:19px; height:19px;}}
.chipno{{padding:2px 8px; border-radius:11px; background:rgba(8,10,15,0.72);
  border:1px solid {HAIR}; font-size:11px; color:{INK_2}; white-space:nowrap;}}

.sec{{display:flex; align-items:baseline; gap:8px; padding:2px 2px 0;}}
.sec i{{font-style:italic; font-size:16px; font-weight:700; color:{accent}; letter-spacing:0.6px;}}
.sec em{{font-size:10px; letter-spacing:1.8px; color:rgba(255,255,255,0.34); font-weight:600;}}
.sec .note{{margin-left:auto; font-size:10px; color:{INK_2};}}

.card{{background:rgba(16,19,27,0.80); border:1px solid {HAIR}; border-radius:12px; padding:9px 10px;}}
.card.tight{{padding:7px 8px;}}

/* 正文密度：760px 页宽上的 12px 约等于手机上 1.6% 屏宽，比普通网页密得多，
   再往下调就看不清了，行距也跟着一起收，别让字挤成一坨 */
.txt{{font-size:12px; line-height:1.55; color:{INK_2}; white-space:pre-wrap; word-break:break-word;}}
.txt strong{{color:{INK}; font-weight:600;}}
/* 三栏并排的技能正文：按窄栏把字号行距再收一档 */
.txt.td{{font-size:11.5px; line-height:1.5;}}
/* .num 必须排在增益色之前：同名 class 时后者生效 */
.num{{color:{GOLD}; font-weight:700;}}
.good{{color:#5fe08a; font-weight:600;}}
.warn{{color:#ffb454; font-weight:600;}}
.bad{{color:#ff7a6b; font-weight:600;}}
.cold{{color:#8fd0ff; font-weight:600;}}
.dim{{color:rgba(255,255,255,0.40);}}
.cols{{display:flex; gap:{GAP}px;}}
/* .col 不能带 flex:1：纵向列里的卡都套着这层 div，给了默认拉伸就会
   在卡与卡之间凭空撑出空白。真要吃剩余高度得显式加 .cg。 */
.col{{min-width:0; display:flex; flex-direction:column;}}
.cg{{flex:1 1 auto;}}
/* .col 的 flex:1 会用 flex-basis:0% 盖掉 width，锁定列宽必须先放开 flex */
.lane{{flex:0 0 auto;}}
.cols2 .col{{width:{_col_w(2)}px;}}
.cols3 .col{{width:{_col_w(3)}px;}}
.cols4 .col{{width:{_col_w(4)}px;}}
.cols5 .col{{width:{_col_w(5)}px;}}
/* 一行多卡时让卡片等高，末块（怪物图）贴同一水平线 */
.card.fill{{flex:1 1 auto; display:flex; flex-direction:column; justify-content:space-between;}}

.kv{{display:flex; align-items:center; gap:6px; font-size:12px; line-height:1.75;}}
.kv img{{width:20px; height:20px;}}
/* 没有对应 ICON 的属性用等宽占位，否则整列的数值会左右错开 */
.kvsp{{width:20px; flex:0 0 20px;}}
.kvk{{color:{INK_2}; min-width:52px;}}
.kvv{{color:{INK}; font-weight:600;}}
/* 技能卡头：分类 ICON 在左，技能名在右，标签最右 */
.skhead{{display:flex; flex-wrap:wrap; align-items:center; gap:4px; padding:0 1px 4px;}}
.skhead img{{width:16px; height:16px; flex:0 0 16px;}}
.skhead .kvv{{font-size:12px; line-height:1.4; flex:1 1 auto; min-width:0;}}

.grid{{display:flex; flex-wrap:wrap; justify-content:center; gap:6px 5px;}}
.sname{{font-size:14px; font-weight:700; font-style:italic; color:{accent}; letter-spacing:0.5px;}}
.snote{{font-size:11px; color:{INK_2};}}
/* 关卡头右侧的等级/波数：顶到卡片右缘，和怪物图右缘对齐 */
.snote.head{{margin-left:auto; font-size:10px; color:rgba(255,255,255,0.40); white-space:nowrap;}}
.tl{{font-size:10px; color:rgba(255,255,255,0.34); margin-right:2px; align-self:center;}}

.cell{{width:{_cell_w()}px; display:flex; flex-direction:column; align-items:center;}}
.cell img{{width:100%; border-radius:9px; background:rgba(0,0,0,0.45); display:block;}}
.ph{{width:100%; height:56px; border-radius:9px; background:rgba(255,255,255,0.05);}}
.cn{{font-size:10.5px; line-height:1.3; text-align:center; margin-top:3px; color:{INK};}}
.chp{{font-size:9.5px; line-height:1.25; text-align:center; color:{GOLD};}}

.row{{display:flex; align-items:center; gap:7px;}}
.row .grow{{flex:1; min-width:0;}}
.slot{{width:60px; flex:0 0 60px; border-radius:9px; overflow:hidden;
  background:rgba(0,0,0,0.42); border:1px solid {HAIR}; align-self:flex-start;}}
.slot img{{width:100%; display:block;}}
.bar{{height:4px; border-radius:2px; background:rgba(255,255,255,0.10); overflow:hidden;}}
.bar i{{display:block; height:4px; background:{accent};}}

.tbl{{display:flex; flex-direction:column; gap:3px;}}
.tr{{display:flex; gap:6px; align-items:baseline; font-size:12px;}}
.tr .tn{{flex:1 1 auto; min-width:58px; color:{INK_2};}}
.tr .tv{{color:{GOLD}; font-weight:700; font-size:13px;}}
.tr .tvw{{flex:0 0 auto; min-width:104px; text-align:right;}}
.tr .tvd{{flex:0 0 auto; min-width:58px; max-width:82px; text-align:right;}}
.tr.hd{{color:rgba(255,255,255,0.34); font-size:10px; letter-spacing:1px;}}
/* 倍率表：段位为行、伤害/失衡为列，单元格里写 Lv1→Lv12。
   格子必须 flex:0 0 auto —— flex:1 会用 flex-basis:0% 把列压得比文字还窄，
   数字直接压在邻格上；.rtr 两端对齐，短列各贴一边。 */
.kr{{flex:0 0 auto; color:{INK_2}; font-size:11.5px; line-height:1.5; white-space:nowrap;}}
.krc{{flex:0 0 auto; white-space:nowrap; text-align:right; color:{GOLD}; font-weight:700;
  font-size:11px; line-height:1.5;}}
/* .khd 必须排在 .kr/.krc 之后：同名 class 靠源顺序覆盖 */
.khd{{color:rgba(255,255,255,0.36); font-size:9.5px; font-weight:400; letter-spacing:0.3px;}}
.rtr{{justify-content:space-between;}}
.rtbl{{display:flex; flex-direction:column; gap:2px; padding:0 0 5px;}}

.mat{{display:flex; flex-wrap:wrap; gap:4px;}}
/* 五档突破材料一行时每张卡只有 ~142px，字号与图标都得收一收才不换行 */
.mitem{{display:flex; align-items:center; gap:4px; padding:2px 6px 2px 3px; border-radius:8px;
  background:rgba(255,255,255,0.05); border:1px solid {HAIR}; font-size:10px; line-height:1.35;}}
.mitem img{{width:20px; height:20px;}}
.mtier{{width:16px; height:16px; border-radius:5px; display:flex; align-items:center; justify-content:center;
  font-size:8.5px; font-weight:700; color:#0c0e13;}}

.wrow{{display:flex; flex-wrap:wrap; gap:3px; margin-bottom:6px; align-items:center;}}
.wchip{{display:flex; align-items:center; gap:2px; padding:1px 5px 1px 2px; border-radius:8px;
  background:rgba(255,110,90,0.13); border:1px solid rgba(255,110,90,0.35); font-size:9.5px; line-height:1.35;}}
.wchip img{{width:15px; height:15px;}}
.rchip{{display:flex; align-items:center; gap:2px; padding:1px 5px 1px 2px; border-radius:8px;
  background:rgba(90,160,255,0.13); border:1px solid rgba(90,160,255,0.35); font-size:9.5px; line-height:1.35;}}
.rchip img{{width:15px; height:15px;}}
/* 波数：中性灰，不跟弱点/抗性抢注意力 */
.wchip.wc{{background:rgba(255,255,255,0.07); border-color:{HAIR}; color:{INK_2};
  padding:1px 7px 1px 6px;}}
/* 房间标题：外面已经有卡时降级成一行小标，不再套一层卡 */
.rblk{{padding-top:2px;}}
.rhead{{display:flex; align-items:baseline; gap:6px; padding:0 2px 4px;}}
.rhead b{{font-size:11.5px; font-weight:600; color:{INK};}}
.rhead em{{font-size:10px; color:rgba(255,255,255,0.36);}}
/* 卡片头：关卡名在左，Lv/波数等标签靠右 */
.shead{{display:flex; align-items:baseline; gap:6px; padding:0 2px 5px;}}

.foot{{text-align:center; font-size:9.5px; letter-spacing:1.4px; color:rgba(255,255,255,0.26); padding:2px 0 0;}}
"""


def _col_w(n: int) -> int:
    return (PAGE_W - PAD * 2 - GAP * (n - 1)) // n


def _cell_w() -> int:
    return (PAGE_W - PAD * 2 - GAP * 4) // 5


def stage_lane_width(per_row: int) -> int:
    """一行放 ``per_row`` 张关卡卡时，每张卡真正分到的宽度。

    ``_lay_out`` 用 :func:`columns` 排布，这里必须和它同一口径，
    否则卡内按整页宽算出来的格子会溢出被根节点缩放。
    """
    if per_row <= 1:
        return PAGE_W - PAD * 2
    return _col_w(per_row)


# ---------------------------------------------------------------- 积木
def hero(
    kicker: str,
    title: str,
    sub: str,
    art: str,
    chips: str = "",
    rail: str = "",
    rail_note: str = "",
) -> str:
    """页首：立绘/图 + 斜体标题 + 属性胶囊，可选右侧数值竖栏。

    ``rail`` 传一列 ``.kv`` 就贴右缘竖排（角色面板用），传空串则整幅留给标题。
    """
    inner = f'<div class="heroin"><div class="kick">{esc(kicker)}</div>'
    inner += f'<div class="tname">{esc(title)}</div>'
    if sub:
        inner += f'<div class="tsub">{esc(sub)}</div>'
    if chips:
        inner += f'<div class="chips">{chips}</div>'
    inner += "</div>"
    art_html = f'<img class="heroimg" src="{art}"/>' if art else ""
    if rail:
        note = f'<div class="railnote">{esc(rail_note)}</div>' if rail_note else ""
        rail_html = f'<div class="herorail">{note}<div class="rail">{rail}</div></div>'
        cls = "hero railed"
    else:
        rail_html = ""
        cls = "hero"
    return f'<div class="{cls}">{art_html}<div class="veil"></div>{inner}{rail_html}</div>'


def hero_icon(kicker: str, title: str, sub: str, icon: str, chips: str = "", box: int = ICON_BOX) -> str:
    """页首的紧凑版：方形 ICON 在左，文字块在右。

    给天生就小的素材用（驱动盘套装图 152×152）：塞进满宽立绘只会糊成马赛克，
    保持原尺寸当 ICON 反而清楚，顺带省下一百多像素页高。
    """
    art = ""
    if icon:
        cls = f" {_width_class(box)}" if box else ""
        art = f'<img class="ihimg{cls}" src="{icon}"/>'
    inner = f'<div class="iheroin"><div class="kick">{esc(kicker)}</div>'
    inner += f'<div class="tname">{esc(title)}</div>'
    if sub:
        inner += f'<div class="tsub">{esc(sub)}</div>'
    if chips:
        inner += f'<div class="chips">{chips}</div>'
    inner += "</div>"
    return f'<div class="hero iconhero">{art}{inner}</div>'


def section(title: str, en: str = "", note: str = "") -> str:
    """``[ 标题 ]`` 斜体小节头。"""
    label = esc(f"[ {title} ]")
    tail = f'<span class="note">{esc(note)}</span>' if note else ""
    en_html = f"<em>{esc(en)}</em>" if en else ""
    return f'<div class="sec"><i>{label}</i>{en_html}{tail}</div>'


def card(body: str, tight: bool = False, fill: bool = False) -> str:
    """一张卡。``fill`` 用于一行多卡的场景，让卡片等高、内部内容上下撑开。"""
    cls = "card" + (" tight" if tight else "") + (" fill" if fill else "")
    return f'<div class="{cls}">{body}</div>'


def chip_img(uri: str, label: str) -> str:
    img = f'<img src="{uri}"/>' if uri else ""
    return f'<div class="chip">{img}<span>{esc(label)}</span></div>'


def chip_text(label: str) -> str:
    return f'<div class="chipno">{esc(label)}</div>'


def skill_head(title: str, raw: bool = False, extra: str = "", fallback: str = "") -> str:
    """技能卡头：分类 ICON 在左、技能名在右。

    ``raw=True`` 表示 ``title`` 已经是 HTML（要保留 :func:`common.markup` 的上色）；
    标题里认不出分类时（如邦布技能不带「分类：」前缀）退回 ``fallback`` 指定的图标。
    """
    code = el.skill_icon(title) or fallback
    uri = _resized_uri(TEXT2D_PATH / "skill_icon" / f"{code}.webp", 40 * SCALE) if code else ""
    img = f'<img src="{uri}"/>' if uri else ""
    label = title if raw else esc(title)
    return f'<div class="skhead">{img}<span class="kvv">{label}</span>{extra}</div>'


def kv(key: str, value: str, icon: str = "") -> str:
    """一行「属性 + 数值」。``icon`` 为空时留等宽占位，保证整列数值对齐。"""
    img = f'<img src="{icon}"/>' if icon else '<span class="kvsp"></span>'
    return f'<div class="kv">{img}<span class="kvk">{esc(key)}</span><span class="kvv">{value}</span></div>'


def grid(cells: list[str], width: int = 0) -> str:
    """图标平铺。

    ``width`` 不能写成 inline style —— pytakumi 不吃 ``style`` 属性；
    宽度类也必须直接挂在 cell 上，后代选择器 ``.父 .cell`` 同样不生效。
    规则由 :func:`page` 动态追加在 ``.cell`` 之后，靠源顺序覆盖默认值。
    """
    if not cells:
        return ""
    cls = f" {_width_class(width)}" if width else ""
    body = "".join(f'<div class="cell{cls}">{c}</div>' for c in cells)
    return f'<div class="grid">{body}</div>'


def cell(art: str, name: str, note: str = "") -> str:
    img = f'<img src="{art}"/>' if art else '<div class="ph"></div>'
    tail = f'<div class="chp">{esc(note)}</div>' if note else ""
    return f"{img}<div class='cn'>{esc(name)}</div>{tail}"


def columns(items: list[str], n: int, round_robin: bool = True) -> str:
    """按列数排布。

    ``round_robin`` 把第 1、3、5 项丢第一列，长度不均时更平衡；
    关掉则按顺序先填满第一列，关卡这种有先后语义的用后者。
    列宽写成显式的宽度类而不是靠 ``.colsN .col`` —— 后代选择器不生效，
    只剩 ``flex:1`` 均分，实际列宽会飘几像素，把格子挤到换行。
    """
    if not items:
        return ""
    buckets: list[list[str]] = [[] for _ in range(n)]
    if round_robin:
        for idx, item in enumerate(items):
            buckets[idx % n].append(item)
    else:
        for idx, item in enumerate(items):
            buckets[idx // n].append(item)
    cls = _width_class(_col_w(n))
    inner = "".join(f'<div class="col lane {cls}">{"".join(buckets[i])}</div>' for i in range(n))
    return f'<div class="cols cols{n}">{inner}</div>'


def row_of(blocks: list[str], per_row: int) -> list[str]:
    """每 ``per_row`` 张卡横排一行，返回多段 HTML 供 ``.bd`` 依次拼。

    与 :func:`columns` 的区别：``columns`` 是 n 根**纵向**长列，条目数除不尽时
    最后几列会出现孤块；这里按行切，每行都从左往左填满，短行靠左不靠中。
    末尾只剩一张时仍按 ``per_row`` 分栏，否则那张卡会撑满整页、和上一行的
    卡片宽度对不上。
    """
    if per_row <= 1:
        return blocks
    out: list[str] = []
    for i in range(0, len(blocks), per_row):
        group = blocks[i : i + per_row]
        out.append(columns(group, per_row) if len(group) == 1 else columns(group, len(group)))
    return out


def columns_by_height(items: list[tuple[int, str]], n: int, fill: bool = False, reorder: bool = False) -> str:
    """按预估高度分栏，列与列的高度差最小。

    ``items`` 是 ``(权重, HTML)``，权重用 :func:`est_lines` 折出的行数
    （同宽卡片下高度 ∝ 行数）。先降序排，再逐个丢进当前最轻的一栏（LPT 装箱）
    ——比按个数平均分匀得多，影画 / 天赋 / 技能这类长度悬殊的内容用它才
    不会出现半列空白。``reorder`` 再补一轮局部搜索把最长那栏压下来。
    ``fill`` 给每张卡加等高类，只在「每列恰好一张卡」时用（一行三张印象卡那种）。
    """
    if not items:
        return ""
    n = min(n, len(items))
    buckets: list[list[tuple[int, str]]] = [[] for _ in range(n)]
    loads: list[int] = [0] * n
    for weight, html in sorted(items, key=lambda pair: -pair[0]):
        target = loads.index(min(loads))
        buckets[target].append((weight, html))
        loads[target] += max(weight, 1)
    if reorder:
        _level_buckets(buckets, loads, n)
    cls = _width_class(_col_w(n))
    inner = "".join(
        f'<div class="col lane {cls}">{"".join(_fill_card(h) if fill else h for _, h in buckets[i])}</div>'
        for i in range(n)
    )
    return f'<div class="cols cols{n}">{inner}</div>'


def _level_buckets(buckets: list[list[tuple[int, str]]], loads: list[int], n: int) -> None:
    """局部搜索：把最重栏的末卡挪到最轻栏，只在总高真的降了才留下。

    LPT 分完仍可能差一整张卡的高度（14 张卡分 3 栏最常见），挪一张尾卡就能
    压掉一大截。尾卡是这段里最容易被挪走的，所以只动它。
    """
    for _ in range(n):
        top = max(range(n), key=lambda idx: loads[idx])
        low = min(range(n), key=lambda idx: loads[idx])
        if top == low or not buckets[top]:
            return
        weight, html = buckets[top][-1]
        rest = [loads[idx] for idx in range(n) if idx not in (top, low)]
        after = [*rest, loads[top] - weight, loads[low] + weight]
        # 挪过去要么更匀、要么总高更低，否则这一轮就此收手
        if loads[top] - weight < loads[low] + weight and max(after) >= max(loads):
            return
        buckets[top].pop()
        buckets[low].append((weight, html))
        loads[top] -= weight
        loads[low] += weight


def est_lines(text: str, per_line: int) -> int:
    """按折行后的行数估高度，给 :func:`columns_by_height` 当权重。

    直接用字数会低估：技能/天赋正文里作者刻意写的换行是硬换行，
    同样字数折出来的行数差一大截，按字数配平就会把长列排到短列后面。
    """
    return sum(max(1, -(-len(seg) // per_line)) for seg in text.split("\n"))


def _fill_card(html: str) -> str:
    """让一张卡在纵向列里吃掉剩余高度。

    外层 div 要显式补 ``cg`` 才会被拉伸，里面的卡要 ``fill`` 才撑得满外层，
    两者缺一个等高就失效（见 :func:`columns_by_height` 的 ``fill``）。
    """
    out = html.replace('<div class="col">', '<div class="col cg">', 1)
    if 'class="card' in out and " fill" not in out:
        out = out.replace('class="card', 'class="card fill', 1)
    return out


def rows(pairs: list[tuple[str, str]], head: str = "") -> str:
    """两列小表。"""
    out: list[str] = []
    if head:
        title = esc(head)
        out.append(f'<div class="tr hd"><span class="tn">{title}</span><span class="tvw">数值</span></div>')
    for name, value in pairs:
        out.append(f'<div class="tr"><span class="tn">{name}</span><span class="tv">{value}</span></div>')
    return f'<div class="tbl">{"".join(out)}</div>'


def rows_n(head: list[str], body: list[list[str]]) -> str:
    """多列小表，列数由 ``head`` 决定。

    表头与首列按纯文本转义，**数值列是原始 HTML**（和 :func:`rows` 一个约定），
    方便直接塞 ``common.markup`` 的结果。
    """
    out: list[str] = []
    cells = "".join(f'<span class="tvw">{esc(title)}</span>' for title in head[1:])
    out.append(f'<div class="tr hd"><span class="tn">{esc(head[0])}</span>{cells}</div>')
    for line in body:
        cells = "".join(f'<span class="tv tvw">{cell}</span>' for cell in line[1:])
        out.append(f'<div class="tr"><span class="tn">{esc(line[0])}</span>{cells}</div>')
    return f'<div class="tbl">{"".join(out)}</div>'


def rows_dense(head: list[str], body: list[list[str]]) -> str:
    """多列小表的紧凑版，数值列更窄，给倍率表这种 5 列的用。

    转义约定同 :func:`rows_n`：数值列是原始 HTML。
    """
    out: list[str] = []
    cells = "".join(f'<span class="tvd">{esc(title)}</span>' for title in head[1:])
    out.append(f'<div class="tr hd"><span class="tn">{esc(head[0])}</span>{cells}</div>')
    for line in body:
        cells = "".join(f'<span class="tv tvd">{cell}</span>' for cell in line[1:])
        out.append(f'<div class="tr"><span class="tn">{esc(line[0])}</span>{cells}</div>')
    return f'<div class="tbl">{"".join(out)}</div>'


def ratio_table(head: list[str], body: list[list[str]]) -> str:
    """技能倍率表：段位为行、伤害/失衡为列。

    同一格写 ``Lv1→Lv12``，比"每个等级一列"窄一半，三栏并排也塞得下；
    ``head`` 首列是行标签（``段位`` / ``倍率``），其余是各属性的列名。
    表头与首列按纯文本转义，数值列是原始 HTML（与 :func:`rows` 一个约定）。
    """
    out: list[str] = []
    cells = "".join(f'<span class="krc khd">{esc(title)}</span>' for title in head[1:])
    out.append(f'<div class="tr rtr"><span class="kr khd">{esc(head[0])}</span>{cells}</div>')
    for line in body:
        cells = "".join(f'<span class="krc">{cell}</span>' for cell in line[1:])
        out.append(f'<div class="tr rtr"><span class="kr">{esc(line[0])}</span>{cells}</div>')
    return f'<div class="rtbl">{"".join(out)}</div>'


async def material_chip(item: Material) -> str:
    """材料徽章：官方图标 + 名称 + 数量。

    图标走 ``item.json`` 的 ``icon`` 字段 basename，在 CDN 上是
    ``assets/zzz/<code>.webp``（丁尼是 ``IconCoin``，也有图）；
    真拉不到时退回档位色徽章，但名称始终用官方名。
    """
    img = ""
    if item.icon:
        side = 20 * SCALE
        uri = await remote_icon(item.icon, side, side, 0.5)
        if uri:
            img = f'<img src="{uri}"/>'
    if img:
        return f'<div class="mitem">{img}<span>{esc(item.name)} ×{item.number:,}</span></div>'
    label, color = TIER_STYLE.get(item.tier, ("素材", "#8FA3C0"))
    badge = f'<span class="mtier mt{item.tier}">{esc(label[0])}</span>'
    return f'<div class="mitem">{badge}<span>{esc(item.name)} ×{item.number:,}</span></div>'


async def materials(items: list[Material]) -> str:
    if not items:
        return ""
    chips = [await material_chip(i) for i in items]
    return f'<div class="mat">{"".join(chips)}</div>'


def footer(text: str) -> str:
    return f'<div class="foot">{esc(text)}</div>'


# ---------------------------------------------------------------- 出图
def page(accent: str, inner: str) -> str:
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'/>"
        f"<style>{_css(accent)}{_width_rules()}{_tier_rules()}</style></head><body>"
        f'<div class="bd">{inner}</div></body></html>'
    )


async def render(accent: str, inner: str) -> bytes:
    """把页面交给 pytakumi 出图。"""
    return await render_html_to_bytes(
        page(accent, inner),
        max_width=PAGE_W * SCALE,
        dpi=96 * SCALE,
        default_font_size=13,
        font_name="sans-serif",
        allow_refit=True,
        image_format="png",
        lang="zh",
        root_max_width=PAGE_W,
    )
