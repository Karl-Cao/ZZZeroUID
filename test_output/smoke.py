"""命令层冒烟：只跑取数 + AI 文本构造，不出图。

    F:\\gsuid_core\\.venv\\Scripts\\python.exe test_output\\smoke.py

为什么单独一个脚本：``preview.py`` 直接调 ``render.*.build()``，绕过了
``zzzerouid_wiki/__init__.py``。命令层里的字段名写错（比如明细页误用索引页的
``zh``）在出图路径上完全看不出来，只会在群里表现为「没反应」。

历史踩坑：character / weapon / bangboo 的**明细页**没有 ``zh`` 键（那是索引页的），
一律用 ``name``；``weapon`` 明细页也没有 ``story`` 键。
"""

import sys
import asyncio
import traceback
from pathlib import Path
from collections.abc import Callable, Awaitable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ZZZeroUID.utils.nanoka import data, text as tx, get_source  # noqa: E402
from ZZZeroUID.zzzerouid_wiki import _char_ai_text, _weapon_ai_text  # noqa: E402

_Run = Callable[[], Awaitable[str]]


async def _char(kind: str, ident: str) -> str:
    return _char_ai_text(await get_source().detail(kind, ident), ident)


async def _weapon(kind: str, ident: str) -> str:
    return _weapon_ai_text(await get_source().detail(kind, ident), ident)


#: 覆盖每个实体的取数 + AI 文本拼装
CASES: list[tuple[str, _Run]] = [
    ("角色 猫又", lambda: _char("character", "1021")),
    ("角色 安比", lambda: _char("character", "1301")),
    ("音擎 望", lambda: _weapon("weapon", "12001")),
    ("音擎 加农转子", lambda: _weapon("weapon", "14001")),
]


async def main() -> None:
    ok = 0
    bad = 0

    for name, make in CASES:
        try:
            text = await make()
        except Exception:
            bad += 1
            print(f"FAIL {name}\n{traceback.format_exc()}", flush=True)
            continue
        ok += 1
        print(f"OK   {name}  {len(text)} 字\n     {text[:150]}", flush=True)

    # 其余实体的 AI 文本是内联 f-string，单独跑一遍取数 + 拼装
    others = [
        ("驱动盘", "equipment", "31000", lambda d: f"{d.at('name').as_str()} {tx.plain(d.at('desc2').as_str())}"),
        ("邦布", "bangboo", "53001", lambda d: f"{d.at('name').as_str()} {tx.plain(d.at('desc').as_str())}"),
    ]
    for name, kind, ident, fmt in others:
        try:
            node = await get_source().detail(kind, ident)
            text = fmt(node)
        except Exception:
            bad += 1
            print(f"FAIL {name}\n{traceback.format_exc()}", flush=True)
            continue
        ok += 1
        print(f"OK   {name}  {len(text)} 字\n     {text[:150]}", flush=True)

    # 怪物走明细页：索引页的 desc 是英文，中文设定在明细页
    try:
        node = await get_source().detail("monster", "100004")
        name = node.at("name").as_str()
        group = node.at("group_desc").as_str()
        text = f"{name}（族群 {group}）{tx.plain(node.at('desc').as_str())}"
        ok += 1
        print(f"OK   怪物  {len(text)} 字\n     {text[:150]}", flush=True)
    except Exception:
        bad += 1
        print(f"FAIL 怪物\n{traceback.format_exc()}", flush=True)

    # 名字查找
    for finder, query in (
        (data.find_character, "猫又"),
        (data.find_weapon, "加农转子"),
        (data.find_bangboo, "鲨牙布"),
        (data.find_equipment, "啄木鸟电音"),
        (data.find_monster, "提尔锋"),
    ):
        try:
            found = await finder(query)
            ok += 1
            print(f"OK   查找 {query} -> {found[0]}", flush=True)
        except Exception:
            bad += 1
            print(f"FAIL 查找 {query}\n{traceback.format_exc()}", flush=True)

    print(f"\ndone: {ok} ok / {bad} fail")
    if bad:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
