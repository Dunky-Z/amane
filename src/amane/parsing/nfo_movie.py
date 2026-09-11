"""读取 Kodi/Emby ``<movie>`` NFO, 与 ``write_nfo`` 对称."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import aiofiles
import structlog

from ..crawlers.models import FilmActor, MediaMetadata
from ..utils.dates import normalize_calendar_date

if TYPE_CHECKING:
    pass

logger = structlog.get_logger()

_NUMBER_PREFIX_RE = re.compile(
    r"^(?P<num>[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*)\s+",
)


@dataclass
class ParsedNfo:
    """NFO 解析结果. ``number`` 可能为空 (仅有 title 时)."""

    number: str | None = None
    title: str | None = None
    plot: str | None = None
    release: str | None = None
    runtime: int | None = None
    studio: str | None = None
    publisher: str | None = None
    series: str | None = None
    actors: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    directors: list[str] = field(default_factory=list)
    score: float | None = None

    def to_media_metadata(self, *, query_number: str) -> MediaMetadata:
        """以 query 番号为准构造 ``MediaMetadata`` (不含图片 URL)."""
        return MediaMetadata(
            number=query_number,
            title=self.title,
            plot=self.plot,
            release=self.release,
            runtime=self.runtime,
            studio=self.studio,
            publisher=self.publisher,
            series=self.series,
            actors=[FilmActor(name=n) for n in self.actors if n],
            tags=list(self.tags),
            directors=list(self.directors),
            score=self.score,
        )


def _text(el: ET.Element | None) -> str | None:
    if el is None or el.text is None:
        return None
    text = el.text.strip()
    return text or None


def _texts(root: ET.Element, tag: str) -> list[str]:
    out: list[str] = []
    for el in root.findall(tag):
        t = _text(el)
        if t:
            out.append(t)
    return out


def _strip_number_prefix(title: str | None, number: str | None) -> str | None:
    if not title:
        return None
    cleaned = title.strip()
    candidates: list[str] = []
    if number:
        candidates.append(number)
        candidates.append(number.replace("-", ""))
    m = _NUMBER_PREFIX_RE.match(cleaned)
    if m:
        candidates.append(m.group("num"))
    for cand in candidates:
        if not cand:
            continue
        # 大小写不敏感剥前缀番号.
        pattern = re.compile(rf"^{re.escape(cand)}\s+", re.IGNORECASE)
        new = pattern.sub("", cleaned, count=1)
        if new != cleaned:
            return new.strip() or None
    return cleaned


def parse_nfo(text: str) -> ParsedNfo | None:
    """解析 ``<movie>`` XML. 根元素非 movie 或解析失败返回 None."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        logger.warning("nfo parse failed: invalid xml")
        return None

    tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag
    if tag.lower() != "movie":
        logger.warning("nfo parse failed: root is not movie", root=tag)
        return None

    number = _text(root.find("num"))
    raw_title = _text(root.find("title")) or _text(root.find("originaltitle"))
    title = _strip_number_prefix(raw_title, number)

    plot = _text(root.find("plot")) or _text(root.find("outline"))
    release = normalize_calendar_date(_text(root.find("premiered")) or _text(root.find("releasedate")))

    runtime: int | None = None
    runtime_text = _text(root.find("runtime"))
    if runtime_text:
        try:
            runtime = int(float(runtime_text))
        except ValueError:
            runtime = None

    studio = _text(root.find("studio")) or _text(root.find("maker"))
    publisher = _text(root.find("publisher")) or _text(root.find("label"))

    series = _text(root.find("series"))
    if not series:
        set_el = root.find("set")
        if set_el is not None:
            series = _text(set_el.find("name"))

    actors: list[str] = []
    for actor_el in root.findall("actor"):
        name = _text(actor_el.find("name"))
        if name:
            actors.append(name)

    tags = _texts(root, "tag")
    if not tags:
        tags = _texts(root, "genre")
    # 去重保序
    seen: set[str] = set()
    uniq_tags: list[str] = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            uniq_tags.append(t)

    directors = _texts(root, "director")

    score: float | None = None
    rating_text = _text(root.find("rating"))
    if rating_text:
        try:
            score = float(rating_text)
        except ValueError:
            score = None

    return ParsedNfo(
        number=number,
        title=title,
        plot=plot,
        release=release,
        runtime=runtime,
        studio=studio,
        publisher=publisher,
        series=series,
        actors=actors,
        tags=uniq_tags,
        directors=directors,
        score=score,
    )


async def read_nfo(path: Path) -> ParsedNfo | None:
    """异步读取并解析 NFO 文件."""
    try:
        async with aiofiles.open(path, encoding="utf-8") as f:
            text = await f.read()
    except OSError:
        logger.warning("nfo read failed", path=str(path))
        return None
    return parse_nfo(text)
