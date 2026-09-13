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


@pytest.mark.asyncio
async def test_ingest_file_concurrent_same_locator(resource_store: ResourceStore, tmp_path: Path):
    """同 locator 并发入库不得因 resources.url UNIQUE 失败; 只保留一行.

    在 resolve 缓存未命中后短暂让出事件循环, 放大 TOCTOU 窗口以稳定复现竞态.
    """
    import asyncio

    from sqlmodel import col, select

    from amane.db.models import Resource

    src = tmp_path / "shared-poster.jpg"
    src.write_bytes(b"shared-image")
    locator = f"localfile:{src.resolve().as_posix()}"

    orig_resolve = resource_store.resolve

    async def delayed_resolve(url: str):
        hit = await orig_resolve(url)
        if hit is None:
            await asyncio.sleep(0.05)
        return hit

    resource_store.resolve = delayed_resolve  # type: ignore[method-assign]

    urls = await asyncio.gather(
        *[resource_store.ingest_file(src, locator=locator) for _ in range(8)]
    )
    assert all(u is not None for u in urls)
    assert len(set(urls)) == 1

    async with resource_store._session() as session:
        rows = list((await session.exec(select(Resource).where(col(Resource.url) == locator))).all())
    assert len(rows) == 1
