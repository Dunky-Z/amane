"""将 localfile: locator 物化为内部 Resource URL."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from .local_source import is_localfile_locator, localfile_path
from .models import MediaMetadata

if TYPE_CHECKING:
    from ..aggregate.models import AggregatedMetadata
    from ..media import ResourceStore

logger = structlog.get_logger()


async def _ingest_url(store: ResourceStore, url: str) -> str:
    if not is_localfile_locator(url):
        return url
    path = localfile_path(url)
    if path is None:
        return url
    internal = await store.ingest_file(path, locator=url)
    if internal is None:
        logger.warning("local ingest failed", locator=url)
        return url
    return internal


async def materialize_local_metadata(meta: MediaMetadata, store: ResourceStore) -> MediaMetadata:
    """就地替换 localfile: URL 为 ``/api/resources/...``; 非本地 URL 原样保留."""
    meta.poster_urls = [await _ingest_url(store, u) for u in meta.poster_urls]
    meta.thumb_urls = [await _ingest_url(store, u) for u in meta.thumb_urls]
    meta.trailer_urls = [await _ingest_url(store, u) for u in meta.trailer_urls]
    meta.extrafanart = [await _ingest_url(store, u) for u in meta.extrafanart]
    return meta


async def materialize_local_aggregate(agg: AggregatedMetadata, store: ResourceStore) -> None:
    """聚合结果中的 localfile: 先入库, 再交给 HTTP materialize / 写库."""
    agg.poster_urls = [await _ingest_url(store, u) for u in agg.poster_urls]
    agg.thumb_urls = [await _ingest_url(store, u) for u in agg.thumb_urls]
    agg.trailer_urls = [await _ingest_url(store, u) for u in agg.trailer_urls]
    agg.extrafanart_urls = {
        site: [await _ingest_url(store, u) for u in urls] for site, urls in agg.extrafanart_urls.items()
    }
