"""内置本地 sidecar 影片源. 无 HTTP."""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from ...enums import SiteName
from ..base import Crawler, CrawlerProfile
from ..local_source import probe
from ..models import FetchOptions, MediaMetadata, SearchQuery

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ...config import SiteConfig
    from ..http import HttpClient


class LocalCrawler(Crawler):
    @classmethod
    def profile(cls) -> CrawlerProfile:
        return CrawlerProfile(name=SiteName.LOCAL, base_url="local://sidecar")

    def __init__(
        self,
        client: HttpClient,
        config: SiteConfig | None = None,
        *,
        roots: Sequence[str] | None = None,
    ):
        super().__init__(client, config=config)
        self._roots = list(roots or [])

    @override
    async def fetch(self, query: SearchQuery, options: FetchOptions | None = None) -> MediaMetadata | None:
        result = await probe(query.number, file_path=query.file_path, roots=self._roots)
        for w in result.warnings:
            self.logger.warning("local probe warning", detail=w)
        if result.metadata is None:
            self.logger.info("miss")
            return None
        self.logger.info("hit", kind=str(result.kind), title=result.metadata.title)
        return result.metadata

    async def _search(self, query: SearchQuery, options: FetchOptions | None = None) -> str | None:
        return None

    async def _scrape(self, url: str, options: FetchOptions | None = None) -> MediaMetadata | None:
        return None
