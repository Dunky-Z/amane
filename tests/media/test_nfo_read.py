"""测试 NFO 读取与 write_nfo 对称."""

from typing import TYPE_CHECKING

import pytest

from amane.db.models import Metadata
from amane.media import write_nfo
from amane.media.nfo_read import parse_nfo, read_nfo

if TYPE_CHECKING:
    from pathlib import Path as PathType


@pytest.fixture
def metadata() -> Metadata:
    return Metadata(
        number="MIDV-123",
        title="Test Title",
        actors=["Actor A", "Actor B"],
        studio="Studio X",
        publisher="Label Y",
        release="2026-01-15",
        runtime=120,
        tags=["Drama", "Romance"],
        series="Series Y",
        plot="A plot line",
        scores={"javdb": 85.0},
        directors=["Director Z"],
    )


@pytest.mark.asyncio(loop_scope="function")
async def test_read_nfo_roundtrip_write_nfo(tmp_path: PathType, metadata: Metadata):
    nfo_path = tmp_path / "MIDV-123.nfo"
    assert await write_nfo(metadata, nfo_path) is True

    parsed = await read_nfo(nfo_path)
    assert parsed is not None
    assert parsed.number == "MIDV-123"
    assert parsed.title == "Test Title"
    assert parsed.actors == ["Actor A", "Actor B"]
    assert parsed.studio == "Studio X"
    assert parsed.publisher == "Label Y"
    assert parsed.release == "2026-01-15"
    assert parsed.runtime == 120
    assert parsed.series == "Series Y"
    assert parsed.plot == "A plot line"
    assert parsed.directors == ["Director Z"]
    assert "Drama" in parsed.tags
    assert parsed.score == 85.0


def test_parse_nfo_mdcx_style_minimal():
    xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<movie>
  <title>300MAAN-1065 Sample Title</title>
  <num>300MAAN-1065</num>
  <plot>Outline text</plot>
  <premiered>2024-05-01</premiered>
  <runtime>90</runtime>
  <studio>MAAN</studio>
  <actor>
    <name>Someone</name>
  </actor>
  <genre>Amateur</genre>
  <tag>Amateur</tag>
  <set>
    <name>Series Z</name>
  </set>
</movie>
"""
    parsed = parse_nfo(xml)
    assert parsed is not None
    assert parsed.number == "300MAAN-1065"
    assert parsed.title == "Sample Title"
    assert parsed.plot == "Outline text"
    assert parsed.release == "2024-05-01"
    assert parsed.runtime == 90
    assert parsed.studio == "MAAN"
    assert parsed.actors == ["Someone"]
    assert parsed.tags == ["Amateur"]
    assert parsed.series == "Series Z"


def test_parse_nfo_rejects_non_movie_root():
    assert parse_nfo("<episodedetails><title>x</title></episodedetails>") is None


def test_parse_nfo_rejects_invalid_xml():
    assert parse_nfo("<movie><title>oops") is None


def test_to_media_metadata_uses_query_number():
    xml = """<movie><num>OTHER-1</num><title>OTHER-1 Hello</title></movie>"""
    parsed = parse_nfo(xml)
    assert parsed is not None
    meta = parsed.to_media_metadata(query_number="MIDV-123")
    assert meta.number == "MIDV-123"
    assert meta.title == "Hello"
