"""SCRAPE ``subtitle_only``: 清空配对外挂字幕后只调用字幕来源插件."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from ..library.rules import DEFAULT_SUBTITLE_EXTENSIONS
from ..organize.subtitles import discover_subtitles
from ..parsing import parse_file_info
from ..utils.threads import in_thread

if TYPE_CHECKING:
    from ..db.models import Library, MediaFile, Metadata
    from ..db.repository import Repository

# 主机仅在此路径调用字幕副作用插件; 与 content_routes 是否含该 ID 无关.
SUBTITLE_SOURCE_ID = "nas.javsubs"


@in_thread
def remove_paired_subtitles(video_path: Path, extensions: Sequence[str]) -> list[Path]:
    """删除与视频配对的同目录字幕; 返回已删除路径."""
    video = parse_file_info(video_path)
    found = discover_subtitles.sync(video_path, extensions, video)
    removed: list[Path] = []
    for path in found:
        try:
            path.unlink()
        except OSError:
            continue
        removed.append(path)
    return removed


@in_thread
def paired_subtitles_exist(video_path: Path, extensions: Sequence[str]) -> bool:
    video = parse_file_info(video_path)
    return bool(discover_subtitles.sync(video_path, extensions, video))


def subtitle_extensions_for(library: Library | None) -> list[str]:
    if library is None:
        return list(DEFAULT_SUBTITLE_EXTENSIONS)
    return list(library.subtitle_extensions or DEFAULT_SUBTITLE_EXTENSIONS)


async def resolve_subtitle_targets(
    repo: Repository,
    *,
    number: str,
    media_file_id: int | None,
) -> tuple[Metadata | None, list[MediaFile]]:
    """解析字幕任务目标文件."""
    meta = await repo.get_metadata_by_number(number)
    if media_file_id is not None:
        media = await repo.get_media_file(media_file_id)
        if media is None:
            return meta, []
        return meta, [media]
    if meta is None or meta.id is None:
        return meta, []
    files = await repo.list_media_files(metadata_ids=[meta.id], limit=None)
    return meta, files
