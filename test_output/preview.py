"""精选集预渲染：每条功能命令出一张代表图，给人看版式用。

不是回归全集 —— 全集跑 ``render.py``。这个脚本开跑前会清空 ``preview/``，
否则改版式后目录里会攒一堆旧尺寸孤儿图。

    F:\\gsuid_core\\.venv\\Scripts\\python.exe test_output\\preview.py
"""

import sys
import shutil
import asyncio
import traceback
from typing import Final
from pathlib import Path
from collections.abc import Callable, Awaitable

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = Path(__file__).resolve().parent / "preview"
if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir(parents=True, exist_ok=True)

from ZZZeroUID.zzzerouid_wiki.render import (  # noqa: E402
    drive,
    weapon,
    bangboo,
    endgame,
    monster,
    character,
)

_Run = Callable[[], Awaitable[bytes]]

#: 超过这个宽度就缩到 :data:`_MAX_W`。原图 760*3=2280px，式舆/临界能到 12MB，
#: 聊天窗口根本渲染不出来；缩到 1400 仍约等于 1.8 倍 CSS 尺度，正文依然可读。
_MAX_W: Final[int] = 1400

#: (输出名, 说明, 协程) —— 一条功能一张
CASES: list[tuple[str, str, _Run]] = [
    ("1_角色介绍_猫又", "大立绘 + 面板 + 技能倍率 + 影画 + 故事", lambda: character.build("1021")),
    ("2_音擎介绍", "简介 + 精炼特效 + 突破材料(官方ICON)", lambda: weapon.build("14001")),
    ("3_驱动盘介绍", "简介 + 二件套/四件套", lambda: drive.build("31000")),
    ("4_邦布介绍", "简介 + 面板 + 技能倍率", lambda: bangboo.build("53001")),
    ("5_怪物介绍", "中文设定 + 属性 ICON + 档案 + 形态面板", lambda: monster.build("100004")),
    ("6_深渊信息_式舆", "五条防线，第五防线三房间", lambda: endgame.shiyu("")),
    ("7_危局信息", "当期三只怪，高清图", lambda: endgame.haedal("")),
    ("8_临界信息", "STAGE 逐行，stage02 不丢", lambda: endgame.simul("")),
    ("9_拟境信息", "首领 + 各难度", lambda: endgame.hard("")),
]


async def main() -> None:
    ok = 0
    bad = 0
    for name, note, run in CASES:
        try:
            png = await run()
        except Exception:
            bad += 1
            print(f"FAIL {name}\n{traceback.format_exc()}", flush=True)
            continue
        path = OUT / f"{name}.png"
        path.write_bytes(_fit(png))
        ok += 1
        print(f"OK   {name}  {path.stat().st_size:>9,} B  {note}", flush=True)
    print(f"\ndone: {ok} ok / {bad} fail -> {OUT}")


def _fit(png: bytes) -> bytes:
    """超宽的按 :data:`_MAX_W` 等比缩一遍再落盘。"""
    from io import BytesIO

    with Image.open(BytesIO(png)) as im:
        if im.width <= _MAX_W:
            return png
        buf = BytesIO()
        im.convert("RGB").resize((_MAX_W, round(im.height * _MAX_W / im.width)), Image.LANCZOS).save(
            buf, "PNG", optimize=True
        )
        return buf.getvalue()


if __name__ == "__main__":
    asyncio.run(main())
