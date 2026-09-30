"""nanoka CDN 的路由模板。

所有上游 URL 都收敛在这一处：换数据源时只需替换本模块与 ``source.py``。
"""

from typing import Final, Literal

#: wiki 专用的数据版本，与 ``version.NANOKA_DATA_VERSION`` 解耦，便于单独升级
WIKI_DATA_VERSION = "3.3.4+19304006"

CDN_ROOT = f"https://static.nanoka.cc/zzz/{WIKI_DATA_VERSION}"
ZH_ROOT = f"{CDN_ROOT}/zh"
ASSET_ROOT = "https://static.nanoka.cc/assets/zzz"

#: 有索引页 + 明细页的实体
DetailKind = Literal["character", "weapon", "equipment", "bangboo", "monster", "boss", "simul", "hard", "shiyu"]

#: 只有索引页的实体
IndexKind = Literal["character", "weapon", "equipment", "bangboo", "monster", "boss", "simul", "hard", "shiyu", "item"]

DETAIL_KINDS: tuple[DetailKind, ...] = (
    "character",
    "weapon",
    "equipment",
    "bangboo",
    "monster",
    "boss",
    "simul",
    "hard",
    "shiyu",
)

INDEX_KINDS: tuple[IndexKind, ...] = (*DETAIL_KINDS, "item")

#: 少数实体的索引页不在 ``{CDN_ROOT}/{kind}.json`` 上，需要显式指定
_INDEX_OVERRIDE: Final[dict[str, str]] = {"item": f"{ZH_ROOT}/item.json"}


def index_url(kind: IndexKind) -> str:
    """实体索引页 URL。"""
    if kind in _INDEX_OVERRIDE:
        return _INDEX_OVERRIDE[kind]
    return f"{CDN_ROOT}/{kind}.json"


def detail_url(kind: DetailKind, key: str) -> str:
    """实体明细页 URL，``key`` 为上游主键。"""
    return f"{ZH_ROOT}/{kind}/{key}.json"


def asset_url(code_name: str) -> str:
    """静态素材地址，``code_name`` 不带扩展名。

    上游 ``icon`` 字段是游戏内路径（``Assets/NapResources/.../IconCoin.png``），
    但 CDN 上只按**文件名**存 ``.webp``，所以调用方要先取 basename。
    """
    return f"{ASSET_ROOT}/{code_name}.webp"
