"""本地 sidecar 收集与 LocalProbe."""

from pathlib import Path

import pytest

from amane.crawlers.local_source import (
    ProbeKind,
    collect_sidecar,
    find_in_roots,
    probe,
    probe_directory,
)


def _write_movie_nfo(path: Path, number: str, title: str = "Title") -> None:
    path.write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<movie>
  <num>{number}</num>
  <title>{number} {title}</title>
  <plot>Plot</plot>
  <studio>Studio</studio>
</movie>
""",
        encoding="utf-8",
    )


def _touch_image(path: Path) -> None:
    path.write_bytes(b"\xff\xd8\xff")  # minimal jpeg-ish


@pytest.mark.asyncio
async def test_parent_full_hit(tmp_path: Path):
    video_dir = tmp_path / "MIDV-123"
    video_dir.mkdir()
    video = video_dir / "MIDV-123.mp4"
    video.write_bytes(b"x")
    _write_movie_nfo(video_dir / "MIDV-123.nfo", "MIDV-123")
    _touch_image(video_dir / "MIDV-123-poster.jpg")

    result = await probe("MIDV-123", file_path=str(video))
    assert result.kind == ProbeKind.FULL_HIT
    assert result.metadata is not None
    assert result.metadata.title == "Title"
    assert result.metadata.poster_urls


@pytest.mark.asyncio
async def test_nfo_only_is_partial(tmp_path: Path):
    video_dir = tmp_path / "MIDV-123"
    video_dir.mkdir()
    video = video_dir / "MIDV-123.mp4"
    video.write_bytes(b"x")
    _write_movie_nfo(video_dir / "MIDV-123.nfo", "MIDV-123")

    result = await probe("MIDV-123", file_path=str(video))
    assert result.kind == ProbeKind.PARTIAL


@pytest.mark.asyncio
async def test_images_only_is_partial(tmp_path: Path):
    video_dir = tmp_path / "MIDV-123"
    video_dir.mkdir()
    video = video_dir / "MIDV-123.mp4"
    video.write_bytes(b"x")
    _touch_image(video_dir / "MIDV-123-poster.jpg")

    result = await probe("MIDV-123", file_path=str(video))
    assert result.kind == ProbeKind.PARTIAL


@pytest.mark.asyncio
async def test_parent_partial_root_full_hit(tmp_path: Path):
    # 父目录仅有图
    video_dir = tmp_path / "library" / "MIDV-123"
    video_dir.mkdir(parents=True)
    video = video_dir / "MIDV-123.mp4"
    video.write_bytes(b"x")
    _touch_image(video_dir / "MIDV-123-poster.jpg")

    # 根目录完整
    root = tmp_path / "JAV_output"
    hit = root / "studio" / "MIDV-123"
    hit.mkdir(parents=True)
    _write_movie_nfo(hit / "MIDV-123.nfo", "MIDV-123")
    _touch_image(hit / "MIDV-123-thumb.jpg")

    result = await probe("MIDV-123", file_path=str(video), roots=[str(root)])
    assert result.kind == ProbeKind.FULL_HIT
    assert result.sidecar is not None
    assert result.sidecar.directory == hit.resolve()


@pytest.mark.asyncio
async def test_parent_full_hit_skips_roots(tmp_path: Path):
    video_dir = tmp_path / "beside"
    video_dir.mkdir()
    video = video_dir / "MIDV-123.mp4"
    video.write_bytes(b"x")
    _write_movie_nfo(video_dir / "MIDV-123.nfo", "MIDV-123")
    _touch_image(video_dir / "MIDV-123-poster.jpg")

    root = tmp_path / "JAV_output" / "MIDV-123"
    root.mkdir(parents=True)
    _write_movie_nfo(root / "MIDV-123.nfo", "MIDV-123", title="FromRoot")
    _touch_image(root / "MIDV-123-poster.jpg")

    result = await probe("MIDV-123", file_path=str(video), roots=[str(tmp_path / "JAV_output")])
    assert result.kind == ProbeKind.FULL_HIT
    assert result.metadata is not None
    assert result.metadata.title == "Title"
    assert result.sidecar is not None
    assert result.sidecar.directory == video_dir.resolve()


@pytest.mark.asyncio
async def test_by_number_only_searches_roots(tmp_path: Path):
    root = tmp_path / "out"
    hit = root / "MIDV123"
    hit.mkdir(parents=True)
    _write_movie_nfo(hit / "x.nfo", "MIDV-123")
    _touch_image(hit / "x-poster.jpg")

    result = await probe("MIDV-123", file_path=None, roots=[str(root)])
    assert result.kind == ProbeKind.FULL_HIT


def test_collect_sidecar_extrafanart(tmp_path: Path):
    d = tmp_path / "MIDV-123"
    ef = d / "extrafanart"
    ef.mkdir(parents=True)
    _touch_image(ef / "1.jpg")
    _touch_image(ef / "2.jpg")
    sc = collect_sidecar(d, "MIDV-123")
    assert len(sc.extrafanart) == 2


def test_find_in_roots_depth_limit(tmp_path: Path):
    # depth 5 from root — beyond max 4 from root children counting
    deep = tmp_path / "a" / "b" / "c" / "d" / "e" / "MIDV-123"
    deep.mkdir(parents=True)
    _write_movie_nfo(deep / "MIDV-123.nfo", "MIDV-123")
    found = find_in_roots("MIDV-123", [tmp_path], max_depth=4)
    assert deep.resolve() not in found

    shallow = tmp_path / "a" / "b" / "MIDV-456"
    shallow.mkdir(parents=True)
    found2 = find_in_roots("MIDV-456", [tmp_path], max_depth=4)
    assert shallow.resolve() in found2
