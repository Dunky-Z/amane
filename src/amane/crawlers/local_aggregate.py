"""本地 full_hit 短路用的 AggregateResult 构造."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..aggregate.models import AggregatedMetadata, AggregateResult, SourcedScore
from ..enums import MetadataField, SiteName
from .local_source import ProbeResult, sidecar_raw_snapshot

if TYPE_CHECKING:
    from .models import MediaMetadata

_SITE = str(SiteName.LOCAL)

_SCALAR_ATTRS: tuple[tuple[MetadataField, str], ...] = (
    (MetadataField.TITLE, "title"),
    (MetadataField.PLOT, "plot"),
    (MetadataField.STUDIO, "studio"),
    (MetadataField.PUBLISHER, "publisher"),
    (MetadataField.RELEASE, "release"),
    (MetadataField.RUNTIME, "runtime"),
    (MetadataField.SERIES, "series"),
)


def build_local_aggregate(number: str, meta: MediaMetadata, probe: ProbeResult) -> AggregateResult:
    field_sources: dict[str, str] = {}
    agg = AggregatedMetadata(number=number)

    for field, attr in _SCALAR_ATTRS:
        value = getattr(meta, attr)
        if value is not None and value != "":
            setattr(agg, attr, value)
            field_sources[field] = _SITE

    if meta.actors:
        agg.actors = list(meta.actors)
        field_sources[MetadataField.ACTORS] = _SITE
    if meta.tags:
        agg.tags = list(meta.tags)
        field_sources[MetadataField.TAGS] = _SITE
    if meta.directors:
        agg.directors = list(meta.directors)
        field_sources[MetadataField.DIRECTORS] = _SITE

    if meta.poster_urls:
        agg.poster_urls = list(meta.poster_urls)
        field_sources[MetadataField.POSTER_URLS] = _SITE
    if meta.thumb_urls:
        agg.thumb_urls = list(meta.thumb_urls)
        field_sources[MetadataField.THUMB_URLS] = _SITE
    if meta.trailer_urls:
        agg.trailer_urls = list(meta.trailer_urls)
        field_sources[MetadataField.TRAILER_URLS] = _SITE
    if meta.extrafanart:
        agg.extrafanart_urls = {_SITE: list(meta.extrafanart)}
        field_sources[MetadataField.EXTRAFANART] = _SITE

    if meta.score is not None:
        agg.scores = [SourcedScore(site=_SITE, score=meta.score)]
        field_sources[MetadataField.SCORE] = _SITE

    if meta.source_url:
        agg.source_urls[_SITE] = meta.source_url
    if meta.external_id:
        agg.external_ids[_SITE] = meta.external_id

    agg.field_sources = dict(field_sources)

    raw: dict = {}
    if probe.sidecar is not None:
        raw[_SITE] = sidecar_raw_snapshot(probe.sidecar, probe.parsed)
    else:
        raw[_SITE] = meta.model_dump()

    return AggregateResult(
        metadata=agg,
        field_sources=field_sources,
        failed_sites=[],
        sites_queried=[_SITE],
        raw=raw,
        log="",
    )
