"""SCRAPE subtitle_only: 只调字幕插件、清空后重下."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from amane.config import HotSettings
from amane.crawlers.models import MediaMetadata
from amane.handlers import ScrapeHandler, ScrapePayload
from amane.handlers.subtitle_scrape import SUBTITLE_SOURCE_ID
from amane.parsing import ContentType

if TYPE_CHECKING:
    from collections.abc import Iterable

    from amane.db.repository import Repository
    from amane.media import ResourceStore


class TrackingFactory:
    def __init__(self, crawlers: dict | None = None) -> None:
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


class SubtitlePlugin:
    def __init__(self, *, write: bool = True, raise_error: Exception | None = None) -> None:
        self.write = write
        self.raise_error = raise_error
        self.calls: list[str | None] = []

    async def fetch(self, query, options=None) -> MediaMetadata | None:
        self.calls.append(query.file_path)
        if self.raise_error is not None:
            raise self.raise_error
        if self.write and query.file_path:
            path = Path(query.file_path)
            (path.parent / f"{path.stem}.zh.srt").write_text("new-sub", encoding="utf-8")
        return None


async def _seed_video(repo: Repository, tmp_path: Path, number: str, *, with_sidecar: bool) -> tuple[Path, int]:
    lib = await repo.create_library(name="lib", path=str(tmp_path))
    assert lib.id is not None
    video = tmp_path / f"{number}.mp4"
    video.write_bytes(b"video")
    if with_sidecar:
        (tmp_path / f"{number}.zh.srt").write_text("old-wrong", encoding="utf-8")
    media = await repo.create_media_file(library_id=lib.id, path=str(video))
    meta = await repo.upsert_metadata(number=number, content_type=ContentType.CENSORED, title=number)
    assert media.id is not None and meta.id is not None
    await repo.update_media_file(media.id, metadata_id=meta.id, has_external_subtitle=with_sidecar)
    return video, media.id


@pytest.mark.asyncio
async def test_subtitle_only_writes_new_sidecar(
    repo: Repository, resource_store: ResourceStore, tmp_path: Path
) -> None:
    video, media_id = await _seed_video(repo, tmp_path, "SSNI-497", with_sidecar=True)
    plugin = SubtitlePlugin(write=True)
    factory = TrackingFactory({SUBTITLE_SOURCE_ID: plugin})
    handler = ScrapeHandler(repo, factory, resource_store, HotSettings())

    result = await handler.handle(
        ScrapePayload(
            number="SSNI-497",
            media_file_id=media_id,
            content_type=ContentType.CENSORED,
            subtitle_only=True,
        )
    )

    assert result.success is True
    assert factory.get_crawlers_calls == [[SUBTITLE_SOURCE_ID]]
    assert plugin.calls == [str(video)]
    assert (tmp_path / "SSNI-497.zh.srt").read_text(encoding="utf-8") == "new-sub"
    media = await repo.get_media_file(media_id)
    assert media is not None
    assert media.has_external_subtitle is True
    assert media.status.name != "failed"


@pytest.mark.asyncio
async def test_subtitle_only_clears_when_no_match(
    repo: Repository, resource_store: ResourceStore, tmp_path: Path
) -> None:
    _video, media_id = await _seed_video(repo, tmp_path, "SSNI-497", with_sidecar=True)
    plugin = SubtitlePlugin(write=False)
    factory = TrackingFactory({SUBTITLE_SOURCE_ID: plugin})
    handler = ScrapeHandler(repo, factory, resource_store, HotSettings())

    result = await handler.handle(ScrapePayload(number="SSNI-497", media_file_id=media_id, subtitle_only=True))

    assert result.success is False
    assert result.error is not None
    assert not (tmp_path / "SSNI-497.zh.srt").exists()
    media = await repo.get_media_file(media_id)
    assert media is not None
    assert media.has_external_subtitle is False
    assert media.status.name != "failed"


@pytest.mark.asyncio
async def test_subtitle_only_fails_when_plugin_missing(
    repo: Repository, resource_store: ResourceStore, tmp_path: Path
) -> None:
    _video, media_id = await _seed_video(repo, tmp_path, "SSNI-497", with_sidecar=True)
    factory = TrackingFactory({})
    handler = ScrapeHandler(repo, factory, resource_store, HotSettings())

    result = await handler.handle(ScrapePayload(number="SSNI-497", media_file_id=media_id, subtitle_only=True))

    assert result.success is False
    assert result.error is not None
    assert SUBTITLE_SOURCE_ID in result.error
    assert (tmp_path / "SSNI-497.zh.srt").exists()
    assert factory.get_crawlers_calls == [[SUBTITLE_SOURCE_ID]]


@pytest.mark.asyncio
async def test_subtitle_only_by_number_resolves_linked_files(
    repo: Repository, resource_store: ResourceStore, tmp_path: Path
) -> None:
    video, _media_id = await _seed_video(repo, tmp_path, "SSNI-497", with_sidecar=False)
    plugin = SubtitlePlugin(write=True)
    factory = TrackingFactory({SUBTITLE_SOURCE_ID: plugin})
    handler = ScrapeHandler(repo, factory, resource_store, HotSettings())

    result = await handler.handle(ScrapePayload(number="SSNI-497", subtitle_only=True))

    assert result.success is True
    assert plugin.calls == [str(video)]
    assert (tmp_path / "SSNI-497.zh.srt").exists()
