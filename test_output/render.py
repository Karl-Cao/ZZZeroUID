"""全量回归渲染：把每类 wiki 卡片各渲若干张，用来肉眼查版式。

不是给用户看的成品图集，是自己 / CI 用的回归产物。
要看「每条功能一张代表图」请跑 ``preview.py``。

    F:\\gsuid_core\\.venv\\Scripts\\python.exe test_output\\render.py [过滤词...]
"""

import sys
import asyncio
import traceback
from pathlib import Path
from collections.abc import Callable, Awaitable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = Path(__file__).resolve().parent / "output"
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

CASES: list[tuple[str, _Run]] = [
    ("char_1021_猫又", lambda: character.build("1021")),
    ("char_1031_妮可", lambda: character.build("1031")),
    ("char_1041_11号", lambda: character.build("1041")),
    ("char_1301_安比", lambda: character.build("1301")),
    ("char_1191_妮可", lambda: character.build("1191")),
    ("weapon_12001", lambda: weapon.build("12001")),
    ("weapon_13001", lambda: weapon.build("13001")),
    ("weapon_14001", lambda: weapon.build("14001")),
    ("drive_31000", lambda: drive.build("31000")),
    ("drive_31400", lambda: drive.build("31400")),
    ("drive_31800", lambda: drive.build("31800")),
    ("bangboo_53001", lambda: bangboo.build("53001")),
    ("bangboo_53006", lambda: bangboo.build("53006")),
    ("monster_10000", lambda: monster.build("10000")),
    ("monster_100004", lambda: monster.build("100004")),
    ("endgame_shiyu", lambda: endgame.shiyu("")),
    ("endgame_haedal", lambda: endgame.haedal("")),
    ("endgame_simul", lambda: endgame.simul("")),
    ("endgame_hard", lambda: endgame.hard("")),
]


async def main() -> None:
    filters = sys.argv[1:]
    ok = 0
    bad = 0
    for name, run in CASES:
        if filters and not any(f in name for f in filters):
            continue
        try:
            png = await run()
        except Exception:
            bad += 1
            print(f"FAIL {name}\n{traceback.format_exc()}", flush=True)
            continue
        (OUT / f"{name}.png").write_bytes(png)
        ok += 1
        print(f"OK   {name}  {len(png)} bytes", flush=True)
    print(f"\ndone: {ok} ok / {bad} fail -> {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
