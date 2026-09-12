"""影片 SCRAPE 写库前相对已有 Metadata 填空 / 并集. 无 I/O."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..crawlers.models import FilmActor
from .models import AggregatedMetadata

if TYPE_CHECKING:
    from ..db.models import Metadata


@dataclass
class MergedFilmFields:
    """供 ``upsert_metadata`` 使用的合并结果."""

    title: str | None = None
    actors: list[str] = field(default_factory=list)
    actor_items: list[FilmActor] = field(default_factory=list)
    studio: str | None = None
    publisher: str | None = None
    release: str | None = None
    runtime: int | None = None
    tags: list[str] = field(default_factory=list)
    series: str | None = None
    plot: str | None = None
    directors: list[str] = field(default_factory=list)
    poster_urls: list[str] = field(default_factory=list)
    thumb_urls: list[str] = field(default_factory=list)
    trailer_urls: list[str] = field(default_factory=list)
    extrafanart_urls: dict[str, list[str]] = field(default_factory=dict)
    scores: dict[str, float] = field(default_factory=dict)
    external_ids: dict[str, str] = field(default_factory=dict)
    source_urls: dict[str, str] = field(default_factory=dict)
    field_sources: dict[str, str] = field(default_factory=dict)
    raw: dict[str, dict] = field(default_factory=dict)


def _text_empty(value: object) -> bool:
    return value in (None, "")


def _list_empty(value: object) -> bool:
    return not value


def _url_union(old: list[str], new: list[str]) -> list[str]:
    if old and not new:
        return list(old)
    if not old:
        return list(new)
    seen = set(old)
    out = list(old)
    for url in new:
        if not url or url in seen:
            continue
        seen.add(url)
        out.append(url)
    return out


def _merge_extrafanart(old: dict[str, list[str]], new: dict[str, list[str]]) -> dict[str, list[str]]:
    out = {site: list(urls) for site, urls in old.items() if urls}
    for site, urls in new.items():
        if urls:
            out[site] = list(urls)
    return out


def _merge_str_dict(old: dict[str, str], new: dict[str, str]) -> dict[str, str]:
    out = dict(old)
    for key, value in new.items():
        out.setdefault(key, value)
    return out


def _merge_scores(old: dict[str, float], new_scores: dict[str, float]) -> dict[str, float]:
    out = dict(old)
    for site, score in new_scores.items():
        out.setdefault(site, score)
    return out


def merge_film_rows_fill_empty(
    existing: Metadata,
    incoming: AggregatedMetadata,
    *,
    poster_urls: list[str],
    thumb_urls: list[str],
    trailer_urls: list[str],
    raw: dict[str, dict],
    field_sources: dict[str, str],
) -> MergedFilmFields:
    """相对已有行填空 / 并集. ``incoming`` 的 URL 字段以显式参数为准 (物化后)."""
    new_scores = {s.site: s.score for s in incoming.scores}
    new_actor_names = [item.name for item in incoming.actors]

    title = existing.title if not _text_empty(existing.title) else incoming.title
    studio = existing.studio if not _text_empty(existing.studio) else incoming.studio
    publisher = existing.publisher if not _text_empty(existing.publisher) else incoming.publisher
    release = existing.release if not _text_empty(existing.release) else incoming.release
    series = existing.series if not _text_empty(existing.series) else incoming.series
    plot = existing.plot if not _text_empty(existing.plot) else incoming.plot
    runtime = existing.runtime if existing.runtime is not None else incoming.runtime

    actors = list(existing.actors) if not _list_empty(existing.actors) else list(new_actor_names)
    tags = list(existing.tags) if not _list_empty(existing.tags) else list(incoming.tags)
    directors = list(existing.directors) if not _list_empty(existing.directors) else list(incoming.directors)

    # 保留已有演员名单时, 仍用本次 FilmActor 补性别 (仅匹配名).
    if not _list_empty(existing.actors):
        by_name = {item.name: item for item in incoming.actors}
        actor_items = [by_name.get(name) or FilmActor(name=name) for name in existing.actors if name]
    else:
        actor_items = list(incoming.actors)

    merged_raw = dict(existing.raw or {})
    merged_raw.update(raw)

    merged_sources = dict(existing.field_sources or {})

    def _adopt_source(field: str, used_incoming: bool) -> None:
        if not used_incoming or field in merged_sources:
            return
        site = field_sources.get(field)
        if site:
            merged_sources[field] = site

    _adopt_source("title", _text_empty(existing.title) and not _text_empty(incoming.title))
    _adopt_source("studio", _text_empty(existing.studio) and not _text_empty(incoming.studio))
    _adopt_source("publisher", _text_empty(existing.publisher) and not _text_empty(incoming.publisher))
    _adopt_source("release", _text_empty(existing.release) and not _text_empty(incoming.release))
    _adopt_source("series", _text_empty(existing.series) and not _text_empty(incoming.series))
    _adopt_source("plot", _text_empty(existing.plot) and not _text_empty(incoming.plot))
    _adopt_source("runtime", existing.runtime is None and incoming.runtime is not None)
    _adopt_source("actors", _list_empty(existing.actors) and not _list_empty(incoming.actors))
    _adopt_source("tags", _list_empty(existing.tags) and not _list_empty(incoming.tags))
    _adopt_source("directors", _list_empty(existing.directors) and not _list_empty(incoming.directors))

    return MergedFilmFields(
        title=title,
        actors=actors,
        actor_items=actor_items,
        studio=studio,
        publisher=publisher,
        release=release,
        runtime=runtime,
        tags=tags,
        series=series,
        plot=plot,
        directors=directors,
        poster_urls=_url_union(list(existing.poster_urls or []), list(poster_urls)),
        thumb_urls=_url_union(list(existing.thumb_urls or []), list(thumb_urls)),
        trailer_urls=_url_union(list(existing.trailer_urls or []), list(trailer_urls)),
        extrafanart_urls=_merge_extrafanart(
            dict(existing.extrafanart_urls or {}), dict(incoming.extrafanart_urls or {})
        ),
        scores=_merge_scores(dict(existing.scores or {}), new_scores),
        external_ids=_merge_str_dict(dict(existing.external_ids or {}), dict(incoming.external_ids or {})),
        source_urls=_merge_str_dict(dict(existing.source_urls or {}), dict(incoming.source_urls or {})),
        field_sources=merged_sources,
        raw=merged_raw,
    )


def film_fields_from_aggregate(
    incoming: AggregatedMetadata,
    *,
    poster_urls: list[str],
    thumb_urls: list[str],
    trailer_urls: list[str],
    raw: dict[str, dict],
    field_sources: dict[str, str],
) -> MergedFilmFields:
    """无已有行时直通本次聚合 (含物化 URL)."""
    return MergedFilmFields(
        title=incoming.title,
        actors=[item.name for item in incoming.actors],
        actor_items=list(incoming.actors),
        studio=incoming.studio,
        publisher=incoming.publisher,
        release=incoming.release,
        runtime=incoming.runtime,
        tags=list(incoming.tags),
        series=incoming.series,
        plot=incoming.plot,
        directors=list(incoming.directors),
        poster_urls=list(poster_urls),
        thumb_urls=list(thumb_urls),
        trailer_urls=list(trailer_urls),
        extrafanart_urls={k: list(v) for k, v in (incoming.extrafanart_urls or {}).items()},
        scores={s.site: s.score for s in incoming.scores},
        external_ids=dict(incoming.external_ids),
        source_urls=dict(incoming.source_urls),
        field_sources=dict(field_sources),
        raw=dict(raw),
    )
