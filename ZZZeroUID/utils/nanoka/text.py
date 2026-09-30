"""上游游戏标记与数字高亮。

上游文本混用 ``<color=#RRGGBB>`` / ``<IconMap:Name>`` / ``<Term:id>`` 等游戏内标记，
pytakumi 不认这些标签。处理顺序：

1. 把 color 段与 IconMap 图标换成私用区占位符（不进 HTML 转义）
2. 丢掉 Term 与零散残标签
3. HTML 转义 -> 数字高亮 -> 空白压缩
4. 占位符还原成 span / img

这样生成的标签不会被自己的转义步骤破坏。
"""

import re
from html import escape
from typing import Final
from collections.abc import Callable

#: 上游调色板 -> 渲染用 class。绿=增益、橙黄=警告、红=减益、蓝=属性
COLOR_CLASS: Final[dict[str, str]] = {
    "2bad00": "good",
    "ffaf2c": "warn",
    "f0d12b": "warn",
    "ffef00": "warn",
    "ffb454": "warn",
    "ff5521": "bad",
    "ff4e00": "bad",
    "fe437e": "bad",
    "ff437e": "bad",
    "ff3b30": "bad",
    "a6c5fd": "cold",
    "2eb6ff": "cold",
    "069eff": "cold",
    "4a9eff": "cold",
    "98eff0": "cold",
    "959595": "dim",
}

#: 数字：整数/小数，带可选正负号与百分号
_NUM: Final[re.Pattern[str]] = re.compile(r"[+-]?\d+(?:\.\d+)?%?")
_COLOR_SPLIT: Final[re.Pattern[str]] = re.compile(r"(<color=#[0-9A-Fa-f]{6,8}>|</color>)")
_ICON_MAP: Final[re.Pattern[str]] = re.compile(r"<IconMap:([^>]+)>")
_TERM: Final[re.Pattern[str]] = re.compile(r"<Term:\d+>")
_STRAY: Final[re.Pattern[str]] = re.compile(r"</?(?:color|IconMap|Term)[^>]*>")
#: 邦布技能里的原始参数占位：``{Skill:5300101, Prop:1001}``
_BRACE: Final[re.Pattern[str]] = re.compile(r"\{[^{}<>]{1,80}\}")
#: 连续空白压成单个空格
_WS: Final[re.Pattern[str]] = re.compile(r"[ \t\u3000]+")

#: 占位符：私用区码位，避开数字正则
_OPEN_BASE: Final[int] = 0xE000
_CLOSE_BASE: Final[int] = 0xF000
_MAX_GUARDS: Final[int] = 0x27F


def _css_of(token: str) -> str:
    """``<color=#2BAD00>`` -> class 名；未知颜色走默认色。"""
    code = token[8:-1].lower()
    if code in COLOR_CLASS:
        return COLOR_CLASS[code]
    return ""


def _open(idx: int) -> str:
    return chr(_OPEN_BASE + idx)


def _close(idx: int) -> str:
    return chr(_CLOSE_BASE + idx)


def _colorize(text: str, guards: list[tuple[str, str]]) -> str:
    """把 color 段换成占位符，正确处理嵌套。默认色（class 为空）不产出 span。"""
    out: list[str] = []
    stack: list[int] = []
    for token in _COLOR_SPLIT.split(text):
        if token.startswith("<color="):
            css = _css_of(token)
            guards.append((f'<span class="{css}">' if css else "", "</span>" if css else ""))
            stack.append(len(guards) - 1)
            out.append(_open(len(guards) - 1))
        elif token == "</color>":
            if stack:
                out.append(_close(stack.pop()))
        else:
            out.append(token)
    while stack:
        out.append(_close(stack.pop()))
    return "".join(out)


def _restore(text: str, guards: list[tuple[str, str]]) -> str:
    for idx, (open_html, close_html) in enumerate(guards):
        text = text.replace(_open(idx), open_html).replace(_close(idx), close_html)
    return _flatten(text)


#: 颜色段里只包着数字时，把两个 class 合并到一个元素上
#: （不依赖 CSS 层叠顺序，pytakumi 的层叠行为不明确）
_WRAP_NUM: Final[re.Pattern[str]] = re.compile(
    r'<span class="([a-z]*)"><span class="num">(.*?)</span></span>',
    re.S,
)


def _flatten(text: str) -> str:
    out = text
    for _ in range(4):
        new = _WRAP_NUM.sub(lambda m: f'<span class="num {m.group(1)}">{m.group(2)}</span>', out)
        if new == out:
            break
        out = new
    return out


def _strip_markup(text: str) -> str:
    """去掉全部游戏标记。

    上游存在没有开标签的孤立 ``</color>``（临界推演的 ``tag`` 字段就是），
    所以不能只匹配 ``</?color=...>``，必须用不带 ``=`` 的宽松规则。
    """
    out = _ICON_MAP.sub("", text)
    out = _TERM.sub("", out)
    out = _STRAY.sub("", out)
    return _BRACE.sub("", out)


def plain(text: str) -> str:
    """剥掉全部游戏标记，只留可读文本。"""
    return _WS.sub(" ", _strip_markup(text)).strip()


def plain_keep_lines(text: str) -> str:
    """去标记但保留换行。"""
    return _strip_markup(text).strip()


def mark_numbers(text: str) -> str:
    """把数字包进 ``.num``，已生成的标签内部不处理。"""
    parts = re.split(r"(<[^>]+>)", text)
    out: list[str] = []
    for part in parts:
        if part.startswith("<") and part.endswith(">"):
            out.append(part)
            continue
        out.append(_NUM.sub(lambda m: f'<span class="num">{m.group(0)}</span>', part))
    return "".join(out)


def markup(text: str, icon_repl: Callable[[str], str] | None = None) -> str:
    """把上游文本转成可渲染的 HTML 片段（单行）。"""
    if not text:
        return ""
    guards: list[tuple[str, str]] = []

    text = _colorize(text, guards)
    if icon_repl is not None:
        text = _ICON_MAP.sub(lambda m: _push(guards, icon_repl(m.group(1)), ""), text)
    else:
        text = _ICON_MAP.sub("", text)
    text = _TERM.sub("", text)
    text = _STRAY.sub("", text)
    text = _BRACE.sub("", text)

    text = escape(text, quote=False)
    text = mark_numbers(text)
    text = _WS.sub(" ", text).strip()
    return _restore(text, guards)


def _push(guards: list[tuple[str, str]], fragment: str, closing: str = "") -> str:
    if len(guards) > _MAX_GUARDS:
        raise RuntimeError("单段文本的标记数量超出占位符容量")
    guards.append((fragment, closing))
    return _open(len(guards) - 1)


def multiline(text: str, icon_repl: Callable[[str], str] | None = None) -> str:
    """多行正文，保留作者刻意写的换行。"""
    if not text:
        return ""
    out = markup(plain_keep_lines(text), icon_repl)
    return re.sub(r"[ ]*\n[ ]*", "<br/>", out)
