# 八、nanoka 图鉴卡（`zzzerouid_wiki`）

九条命令，全部带 `to_ai` + `ai_return`。取数与绘图严格分层：

```
zzzerouid_wiki/__init__.py      命令分发 + AI 文本注入（不知道任何字段名以外的东西）
  └── utils/nanoka/             可替换数据源，唯一取数入口
        urls / cache / source   URL 拼装、落盘缓存、WikiSource Protocol（换源只动这里）
        json_node               类型化 JSON 访问（.at/.maybe/.items/.values）
        data                    索引查找 + 四类 endgame 的期次枚举
        element / material      id -> 名称、ICON、配色
        ratio / text            倍率解析、上游富文本 -> HTML
  └── zzzerouid_wiki/render/    pytakumi 绘图，只认 WikiSource
        base                    页面底座、通用积木、CSS
        common                  富文本 / 数字上色 / 属性胶囊
        character weapon drive bangboo monster endgame
```

| 命令（别名） | render 函数 | 上游 kind |
|---|---|---|
| `角色介绍` `角色信息` `角色图鉴` `查角色` | `character.build` | `character` |
| `音擎介绍` `音擎资料` `查音擎` `武器介绍` `武器资料` | `weapon.build` | `weapon` |
| `驱动盘介绍` `驱动盘资料` `查驱动盘` `驱动盘` | `drive.build` | `equipment` |
| `邦布介绍` `邦布资料` `查邦布` `邦布` | `bangboo.build` | `bangboo` |
| `怪物介绍` `怪物资料` `查怪物` `原魔介绍` | `monster.build` | `monster` |
| `深渊信息` `式舆信息` | `endgame.shiyu` | `shiyu` |
| `危局信息` | `endgame.haedal` | `boss` |
| `临界信息` | `endgame.simul` | `simul` |
| `拟境信息` `拟境湮灭战` | `endgame.hard` | `hard` |

endgame 四条都支持期次选择词：`上期` / `下期` / `本期` / 期次 id / 日期，
由 `data.pick()` 统一挑期，卡片本身与期次无关。

## 数据源版本

`utils/nanoka/urls.py::WIKI_DATA_VERSION` 单独锁版本，**不要**动
`version.py` 的 `NANOKA_DATA_VERSION`（`hakush_api` / `hakush_resource` 共用）。
换数据源只改 `source.set_source()`，render 层无感。

## ICON 来源

| 用途 | 路径 | 来源 |
|---|---|---|
| 属性 物理/火/冰/电/风/以太/玄墨 | `texture2d/{名}属性.png` | 本地 |
| 角色特性 强攻/击破/异常/支援/防御/命破 | `texture2d/pro/Icon*.png` | 本地 |
| 道具（生命/攻击/暴击率/贯穿值…） | `texture2d/prop/Icon*.png` | 本地 |
| 技能分类 普通攻击/闪避/连携/终结… | `texture2d/skill_icon/*.webp` | nanoka CDN |
| 材料 / 怪物立绘 / 角色缺失立绘 | `assets/zzz/{basename}.webp` | nanoka CDN，落盘 `data/ZZZeroUID/wiki/asset` |

技能分类映射见 `utils/nanoka/element.py::SKILL_TYPES`，键是技能名
`分类：技能名` 的前缀。两处上游数据的小出入按「以用户实际看到的图形为准」处理：
冲刺攻击与闪避反击官方共用一张图；支援突击上游误标成 `Icon_Normal`。

**CDN 会对无 UA 的请求返 403**，抓素材要带 `User-Agent` + `Referer`。

## pytakumi 坑（都踩过）

- inline `style` **完全无效** → 宽度/配色一律生成 class 规则，由 `page()` 追加
- 后代选择器除 `.good .num` 外都可能被同特异度规则盖掉 → 宽度类直接挂元素上
- `flex:1` 会用 `flex-basis:0%` 盖掉显式 `width` → 锁列宽要加 `.lane{flex:0 0 auto}`
- `.col` **绝不能带 `flex:1`**：卡都套在这层 div 里，给了默认拉伸就会在卡与卡
  之间凭空撑出空白（技能/天赋/影画/故事全中招）。真要吃剩余高度得显式
  `.cg`（外层）+ `.card.fill`（里层），见 `base._fill_card`
- 倍率格同理：`flex:1 1 auto` 会把列压得比文字还窄，数字直接压在邻格上 →
  `.krc` 用 `flex:0 0 auto` + `.rtr{justify-content:space-between}`
- 宽度必须在 Python 侧算死，百分比不可靠
- `<img>` 的 `height` / `object-fit` 被忽略 → 形状要在 `crop_uri` / `remote_icon` 里裁好
- 参数固定 `max_width=PAGE_W*SCALE, dpi=96*SCALE, root_max_width=PAGE_W`

## 版式约定

- 页宽 `PAGE_W=760`，面向手机竖屏
- 标题一律斜体 `[ 名称 ]`；数值 `.num`（橙黄）、增益 `.good`（绿）
- **Lv50-60 面板数值竖排进页首右侧**（`base.hero(..., rail=...)`），
  条目超过 `_RAIL_MAX`（8）行才退回独立小节
- 缺 ICON 的属性行用 `.kvsp` 等宽占位，否则整列数值左右错开
- endgame **只有一层卡**：房间不再套卡，怪物图按这张卡真正分到的宽度算格子
  （`base.stage_lane_width`），否则会被根节点缩放糊掉
- 紧凑控件一律「ICON 在左、文字在右」横向
- **天生小的素材别拉满宽**：驱动盘套装图只有 152×152，裁成 2:1 立绘就是一块糊，
  改走 `base.hero_icon()` + `base.local_canvas()`（等比留白、不放大），
  顺带省一百多像素页高
- `3d_suit/` **不要用**：33 张里有 5 张（ChaosJazz / HormonePunk / PufferElectro /
  SoulRock / WoodpeckerElectro）是 512×512 但 alpha 峰值只有 4/255 的空壳，
  只判文件存在会让页首渲染成一整块黑

### 角色卡的小节与分栏数

角色卡一屏放不下，靠「合并 + 三栏 + 按行高配平」压长度，顺序是
页首 → 技能 → 影画 → 天赋 → 角色故事 → 突破材料 → 页脚。

- **技能合成一节**：上游把同一个技能的数值和文本拆成两条 entry
  （一条只带 `param`、一条只带 `desc`），拆成「技能倍率 + 技能说明」两节
  会让同一个技能在图上出现两次；按技能名合并后 30 张卡变 14 张
- **倍率表转置**：段位为行、伤害/失衡为列，格内写 `Lv1→Lv12`。
  「每个等级一列」要 5 列，三栏卡片（内宽 ~224px）放不下，
  转置后 2 列 185px 就够；三种及以上属性（轻招架/重招架/连续招架失衡）
  再退化成每属性一行
- **技能节固定三栏**：四栏内宽只有 161px，`42062%→420620%` 这种六位倍率
  一定撑破卡片
- 分栏权重用 `base.est_lines()`（**折行后的行数**）而不是字数，并且
  **正文行数、倍率行数、固定开销（+3）必须同一单位**——混算会让 LPT 排歪。
  正文里作者刻意写的换行是硬换行，按字数算会低估高度
- 技能/天赋之间没有先后语义，开 `columns_by_height(..., reorder=True)`；
  影画有 Lv1→Lv6、故事有「印象」语序，只能 `False`
- 正文密度：`.txt` 12px/1.55，窄栏用 `.txt.td` 11.5px/1.5。
  760px 页宽上的 12px 约合手机上 1.6% 屏宽，已比普通网页密得多

实测（SCALE=3，出图 2280px 宽，长宽比 = 高/宽）：猫又 10171→7661（4.46→3.36）、
妮可 6623（2.90）、奥菲丝 8156（3.58）、艾莲 9518（4.17）。艾莲最长的原因是
数据量本身——她有 19 个技能、4461 字说明，是猫又的 2.4 倍。

## 本地预览

```sh
# 全量回归（19 张，自己/CI 看）
F:\gsuid_core\.venv\Scripts\python.exe test_output\render.py [过滤词...]

# 精选集（9 张，给用户看）
F:\gsuid_core\.venv\Scripts\python.exe test_output\preview.py

# 命令层冒烟（12 项，专抓字段名写错——render/preview 直接调 build() 绕过了命令层）
F:\gsuid_core\.venv\Scripts\python.exe test_output\smoke.py
```

`smoke.py` 不是冗余：字段名打错在 `render.py` 的出图路径上常常看不出来，
只有走命令层 + `ai_return` 实参求值才会暴露。

## 已知缺口

- **音擎没有故事**：上游 `weapon` 明细页与索引页都没有故事字段，别再找了
- **怪物卡走明细页**：索引页 `desc` 是英文，中文设定在 `zh/monster/{id}.json`
