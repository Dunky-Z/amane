"""ResourceStore.ingest_file."""

from pathlib import Path

import pytest

from amane.media import ResourceStore
from amane.media.pipeline import RESOURCE_URL_PREFIX


@pytest.mark.asyncio
async def test_ingest_file_returns_internal_url(resource_store: ResourceStore, tmp_path: Path):
    src = tmp_path / "poster.jpg"
    src.write_bytes(b"image-bytes")

    url = await resource_store.ingest_file(src)
    assert url is not None
    assert url.startswith(f"{RESOURCE_URL_PREFIX}/")

    # 再次 ingest 同路径命中缓存
    url2 = await resource_store.ingest_file(src)
    assert url2 == url

    locator = f"localfile:{src.resolve().as_posix()}"
    resolved = await resource_store.resolve(locator)
    assert resolved is not None
    assert resolved.read_bytes() == b"image-bytes"


@pytest.mark.asyncio
async def test_ingest_file_missing_returns_none(resource_store: ResourceStore, tmp_path: Path):
    assert await resource_store.ingest_file(tmp_path / "nope.jpg") is None
