"""由已注册爬虫的 ``profile()`` 推导站点角色, 供配置 schema 与运行时校验共用.

不写入 HotSettings. 双料站 = 同一 ``SiteName`` 同时出现在影片 / 演员注册表, 不允许手写名单.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, cast, overload

from pydantic.config import JsonDict

from ..enums import SiteName
from ..plugins.models import SourceCapability, is_external_source_id
from . import actor_registry, registry

_ACTOR_PROFILE = SourceCapability.ACTOR_PROFILE
_ACTOR_IMAGE = SourceCapability.ACTOR_IMAGE


def _actor_sites(capability: SourceCapability) -> tuple[SiteName, ...]:
    sites: list[SiteName] = []
    for cls in actor_registry.classes():
        profile = cls.profile()
        if capability not in profile.capabilities:
            continue
        name = profile.name
        sites.append(name if isinstance(name, SiteName) else SiteName(str(name)))
    return tuple(sites)


# 列表顺序 = actor_registry.register 顺序, 即默认 profile_sites / image_sites 优先级.
ACTOR_PROFILE_SITES: tuple[SiteName, ...] = _actor_sites(_ACTOR_PROFILE)
ACTOR_IMAGE_SITES: tuple[SiteName, ...] = _actor_sites(_ACTOR_IMAGE)

_ACTOR_SITE_SET = frozenset({*ACTOR_PROFILE_SITES, *ACTOR_IMAGE_SITES})

# 影片站集合在 registry.register 完成后由 refresh_film_sites() 刷新.
# 使用可变 list / set 就地更新, 以便 ``from site_roles import FILM_METADATA_SITES`` 的持有者看到新值.
_FILM_SITE_SET: set[SiteName] = set()
ACTOR_ONLY_SITES: set[SiteName] = set()
FILM_METADATA_SITES: list[SiteName] = []
MULTI_LANGUAGE_SITES: set[SiteName] = set()
MULTI_LANGUAGE_SOURCE_IDS: set[str] = set()


def refresh_film_sites() -> None:
    """按当前 ``registry`` 重算影片站资格. ``crawlers`` 注册完毕后必须调用."""
    film = {SiteName(s) for s in registry.sites()}
    _FILM_SITE_SET.clear()
    _FILM_SITE_SET.update(film)

    ACTOR_ONLY_SITES.clear()
    ACTOR_ONLY_SITES.update(_ACTOR_SITE_SET - film)

    FILM_METADATA_SITES.clear()
    FILM_METADATA_SITES.extend(s for s in SiteName if s in film)

    MULTI_LANGUAGE_SITES.clear()
    MULTI_LANGUAGE_SITES.update(
        s for s in FILM_METADATA_SITES if (cls := registry.get(s)) is not None and cls.profile().multi_language
    )
    MULTI_LANGUAGE_SOURCE_IDS.clear()
    MULTI_LANGUAGE_SOURCE_IDS.update(str(s) for s in MULTI_LANGUAGE_SITES)


refresh_film_sites()

_ACTOR_PROFILE_SET = frozenset(ACTOR_PROFILE_SITES)
_ACTOR_IMAGE_SET = frozenset(ACTOR_IMAGE_SITES)


def is_actor_profile_site(site: SiteName) -> bool:
    return site in _ACTOR_PROFILE_SET


def is_actor_image_site(site: SiteName) -> bool:
    return site in _ACTOR_IMAGE_SET


def site_list_schema(sites: Sequence[SiteName], *, ordered: bool = True) -> Callable[[JsonDict], None]:
    enum_vals = list(sites)

    def extra(schema: JsonDict) -> None:
        schema["items"] = cast("JsonDict", {"type": "string", "enum": enum_vals})
        if ordered:
            schema["x-ordered"] = True

    return extra


def site_list_value_schema(sites: Sequence[SiteName], *, ordered: bool = True) -> dict[str, Any]:
    items: dict[str, Any] = {"type": "string", "enum": list(sites)}
    out: dict[str, Any] = {"items": items}
    if ordered:
        out["x-ordered"] = True
    return out


@overload
def assert_sites_allowed(
    sites: list[str],
    allowed: frozenset[SiteName] | frozenset[str],
    *,
    field: str,
    allow_external: bool = False,
) -> list[str]: ...


@overload
def assert_sites_allowed(
    sites: list[SiteName],
    allowed: frozenset[SiteName] | frozenset[str],
    *,
    field: str,
    allow_external: bool = False,
) -> list[SiteName]: ...


def assert_sites_allowed(
    sites: list[str] | list[SiteName],
    allowed: frozenset[SiteName] | frozenset[str],
    *,
    field: str,
    allow_external: bool = False,
) -> list[str] | list[SiteName]:
    """站点列表必须 ⊆ allowed; 可选放行外部 source ID. 不合法时抛 ValueError."""
    allowed_values = set(allowed)
    values = list(sites)
    bad = [
        value
        for value in values
        if value not in allowed_values and not (allow_external and is_external_source_id(value))
    ]
    if bad:
        allowed_vals = sorted(allowed_values)
        suffix = " or namespaced source ids" if allow_external else ""
        raise ValueError(f"{field} contains sites outside allowed set {allowed_vals}{suffix}: {bad}")
    return sites
