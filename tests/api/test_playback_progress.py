"""Playback progress persistence API."""

from typing import TYPE_CHECKING

import pytest

from tests.api.test_playback import _seed_title

if TYPE_CHECKING:
    from httpx2 import AsyncClient

    from amane.db.repository import Repository


@pytest.mark.asyncio
async def test_playback_progress_roundtrip(client: "AsyncClient", repo: "Repository") -> None:
    metadata_id = await _seed_title(repo, number="PROG-001")

    empty = await client.get(f"playback/progress/{metadata_id}")
    assert empty.status_code == 200, empty.text
    assert empty.json() == {"position_seconds": None}

    put = await client.put(f"playback/progress/{metadata_id}", json={"position_seconds": 123.5})
    assert put.status_code == 200, put.text
    assert put.json() == {"position_seconds": 123.5}

    got = await client.get(f"playback/progress/{metadata_id}")
    assert got.status_code == 200
    assert got.json() == {"position_seconds": 123.5}

    again = await client.put(f"playback/progress/{metadata_id}", json={"position_seconds": 10})
    assert again.status_code == 200
    assert again.json() == {"position_seconds": 10.0}


@pytest.mark.asyncio
async def test_playback_progress_unknown_metadata(client: "AsyncClient") -> None:
    assert (await client.get("playback/progress/999999")).status_code == 404
    assert (await client.put("playback/progress/999999", json={"position_seconds": 1})).status_code == 404


@pytest.mark.asyncio
async def test_playback_progress_rejects_negative(client: "AsyncClient", repo: "Repository") -> None:
    metadata_id = await _seed_title(repo, number="PROG-NEG")
    res = await client.put(f"playback/progress/{metadata_id}", json={"position_seconds": -1})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_playback_progress_deleted_with_metadata(client: "AsyncClient", repo: "Repository") -> None:
    metadata_id = await _seed_title(repo, number="PROG-DEL")
    assert (await client.put(f"playback/progress/{metadata_id}", json={"position_seconds": 42})).status_code == 200
    assert await repo.delete_metadata(metadata_id) is True
    assert (await client.get(f"playback/progress/{metadata_id}")).status_code == 404
