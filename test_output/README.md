# test_output

本地预渲染目录，产物全部在 `.gitignore` 里，只提交脚本。

| 文件 | 用途 |
|------|------|
| `render.py` | **全量回归**：每类卡片各渲若干张，给自己 / CI 查版式。产物在 `output/` |
| `preview.py` | **精选集**：每条功能命令一张代表图，给人看版式。产物在 `preview/` |
| `smoke.py` | **命令层冒烟**：只跑取数 + AI 文本构造，不出图。产物在 stdout |

三个脚本刻意分开：回归全集动辄十几张几十张，堆给用户没有意义；
「给我看看版式」只要每条功能各一张代表样本就够了；而 `smoke.py` 补的是前两个
脚本都覆盖不到的盲区（见下）。

## 跑法

```sh
# 用宿主 Core 的 venv，不要用 uv run（跑脚本会触发环境同步）
F:\gsuid_core\.venv\Scripts\python.exe test_output\render.py            # 全量
F:\gsuid_core\.venv\Scripts\python.exe test_output\render.py endgame shiyu  # 只跑名字含关键词的
F:\gsuid_core\.venv\Scripts\python.exe test_output\preview.py          # 精选集
F:\gsuid_core\.venv\Scripts\python.exe test_output\smoke.py            # 冒烟
```

三个脚本都依赖 `sys.path` 指向插件根 `F:\gsuid_core\gsuid_core\plugins\ZZZeroUID`
（不是 `plugins`），否则 `import ZZZeroUID` 会失败。

## 为什么要有 smoke.py

`render.py` / `preview.py` 直接调 `render.*.build()`，**绕过了**
`zzzerouid_wiki/__init__.py` 的命令层。命令层里的字段名写错，在出图路径上
完全看不出来。

踩过的坑：character / weapon / bangboo 的**明细页**没有 `zh` 键（那是索引页才有的），
一律要用 `name`；`weapon` 明细页也没有 `story` 键。这 4 处都在 `_ai_note(...)`
的实参求值阶段，`try` 接不住，线上表现是**群里完全没反应**，而 19 张图全绿。

所以凡是「取数 + 拼文本」的路径，都要在 `smoke.py` 里过一遍。

## 注意

- `preview.py` 开跑前会清空 `preview/`。目录里如果按尺寸命名，改版式后会攒一堆
  旧尺寸孤儿图，所以必须先清。
- JSON / 图片缓存落在 `F:\gsuid_core\data\ZZZeroUID\wiki\` 下（`nanoka/` / `img/` / `asset/`），
  不在本目录，也不需要清。
- PowerShell 控制台是 GBK，中文输出要 `$env:PYTHONIOENCODING="utf-8"`。
