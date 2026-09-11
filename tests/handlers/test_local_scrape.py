"""本地刮削源短路与聚合接入."""

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from amane.config import HotSettings, ScrapingConfig
from amane.crawlers.models import MediaMetadata
from amane.db.models import MediaFileStatus
from amane.enums import SiteName
from amane.handlers import ScrapeHandler, ScrapePayload
from amane.parsing import ContentType

if TYPE_CHECKING:
    from collections.abc import Iterable

    from amane.db.repository import Repository
    from amane.media import ResourceStore


class TrackingFactory:
    def __init__(self, crawlers: dict | None = None):
        self._crawlers = crawlers or {}
        self.get_crawlers_calls: list[list[str]] = []

    async def get(self, name: str):
        return self._crawlers.get(name)

    async def get_crawlers(self, names: Iterable[str]) -> dict:
        names_list = [str(n) for n in names]
        self.get_crawlers_calls.append(names_list)
        result = {}
        for name in names_list:
            crawler = await self.get(name)
            if crawler is not None:
                result[name] = crawler
        return result


class OnlineCrawler:
    name = SiteName.JAVDB

    def __init__(self):
        self.called = False

    async def fetch(self, query, options=None) -> MediaMetadata | None:
        self.called = True
        return MediaMetadata(number=query.number, title="Online Title", actors=["A"])


def _write_full_sidecar(directory: Path, number: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    video = directory / f"{number}.mp4"
    video.write_bytes(b"video")
    (directory / f"{number}.nfo").write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<movie>
  <num>{number}</num>
  <title>{number} Local Title</title>
  <plot>Local plot</plot>
  <studio>LocalStudio</studio>
  <actor><name>Local Actor</name></actor>
</movie>
""",
        encoding="utf-8",
    )
    (directory / f"{number}-poster.jpg").write_bytes(b"\xff\xd8\xffposter")
    return video


def _settings_with_local(tmp_path: Path | None = None) -> HotSettings:
    roots = [str(tmp_path)] if tmp_path else []
    scraping = ScrapingConfig(
        content_routes={
            ContentType.CENSORED: [str(SiteName.LOCAL), str(SiteName.JAVDB)],
        },
        local_roots=roots,
    )
    return HotSettings(scraping=scraping)


@pytest.mark.asyncio
async def test_parent_full_hit_skips_online_crawlers(
    repo: Repository, resource_store: ResourceStore, tmp_path: Path
):
    video = _write_full_sidecar(tmp_path / "MIDV-123", "MIDV-123")
    media = await repo.create_media_file(library_id=1, path=str(video))

    online = OnlineCrawler()
    factory = TrackingFactory({"javdb": online, "local": None})
    handler = ScrapeHandler(
        repo=repo,
        factory=factory,
        resource_store=resource_store,
        pipeline_config=_settings_with_local(),
    )

    result = await handler.handle(
        ScrapePayload(media_file_id=media.id, number="MIDV-123", content_type=ContentType.CENSORED)
    )
    assert result.success is True
    assert factory.get_crawlers_calls == []
    assert online.called is False

    meta = await repo.get_metadata_by_number("MIDV-123")
    assert meta is not None
    assert meta.title == "Local Title"
    assert meta.studio == "LocalStudio"
    assert meta.poster_urls
    assert all(u.startswith("/api/resources/") for u in meta.poster_urls)

    media2 = await repo.get_media_file(media_id=media.id)
    assert media2 is not None
    assert media2.status == MediaFileStatus.SCRAPED


@pytest.mark.asyncio
async def test_nfo_only_falls_through_to_aggregate(
    repo: Repository, resource_store: ResourceStore, tmp_path: Path
):
    d = tmp_path / "MIDV-200"
    d.mkdir()
    video = d / "MIDV-200.mp4"
    video.write_bytes(b"v")
    (d / "MIDV-200.nfo").write_text(
        """<?xml version="1.0"?><movie><num>MIDV-200</num><title>MIDV-200 Only Nfo</title></movie>""",
        encoding="utf-8",
    )
    media = await repo.create_media_file(library_id=1, path=str(video))

    online = OnlineCrawler()
    factory = TrackingFactory({"javdb": online})
    handler = ScrapeHandler(
        repo=repo,
        factory=factory,
        resource_store=resource_store,
        pipeline_config=_settings_with_local(),
    )
    result = await handler.handle(
        ScrapePayload(media_file_id=media.id, number="MIDV-200", content_type=ContentType.CENSORED)
    )
    assert result.success is True
    assert factory.get_crawlers_calls
    assert online.called is True
    meta = await repo.get_metadata_by_number("MIDV-200")
    assert meta is not None
    assert meta.title == "Online Title"


@pytest.mark.asyncio
async def test_root_full_hit_without_media_path(
    repo: Repository, resource_store: ResourceStore, tmp_path: Path
):
    hit = tmp_path / "out" / "MIDV-300"
    _write_full_sidecar(hit, "MIDV-300")

    online = OnlineCrawler()
    factory = TrackingFactory({"javdb": online})
    handler = ScrapeHandler(
        repo=repo,
        factory=factory,
        resource_store=resource_store,
        pipeline_config=_settings_with_local(tmp_path / "out"),
    )
    result = await handler.handle(
        ScrapePayload(number="MIDV-300", content_type=ContentType.CENSORED)
    )
    assert result.success is True
    assert factory.get_crawlers_calls == []
    meta = await repo.get_metadata_by_number("MIDV-300")
    assert meta is not None
    assert meta.title == "Local Title"
