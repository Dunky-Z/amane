"""本地 sidecar 查找与全量命中判定.

查找顺序: 视频父目录 → 各 ``local_roots`` (深度上限 4 的 BFS).
full_hit = 可解析 NFO 且至少有 poster 或 thumb.
"""

from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from ..parsing.nfo_movie import ParsedNfo, read_nfo
from .models import MediaMetadata

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = structlog.get_logger()

IMAGE_EXTS = frozenset({".jpg", ".jpeg", ".png", ".webp"})
ROOT_MAX_DEPTH = 4
LOCAL_FILE_PREFIX = "localfile:"


class ProbeKind(StrEnum):
    FULL_HIT = "full_hit"
    PARTIAL = "partial"
    MISS = "miss"


@dataclass
class SidecarFiles:
    directory: Path
    nfo: Path | None = None
    poster: Path | None = None
    thumb: Path | None = None
    fanart: Path | None = None
    extrafanart: list[Path] = field(default_factory=list)


@dataclass
class ProbeResult:
    kind: ProbeKind
    sidecar: SidecarFiles | None = None
    parsed: ParsedNfo | None = None
    metadata: MediaMetadata | None = None
    warnings: list[str] = field(default_factory=list)


def number_key(number: str) -> str:
    """番号归一化: 去横杠/下划线/空白后大写."""
    return re.sub(r"[-_\s]", "", number).upper()


def name_contains_number(name: str, number: str) -> bool:
    return number_key(number) in number_key(Path(name).stem if "." in name else name)


def localfile_locator(path: Path) -> str:
    return f"{LOCAL_FILE_PREFIX}{path.resolve().as_posix()}"


def is_localfile_locator(url: str) -> bool:
    return url.startswith(LOCAL_FILE_PREFIX)


def localfile_path(url: str) -> Path | None:
    if not is_localfile_locator(url):
        return None
    return Path(url[len(LOCAL_FILE_PREFIX) :])


def collect_sidecar(directory: Path, number: str) -> SidecarFiles:
    """收集单目录内 sidecar; 不递归子视频目录, 只扫 ``extrafanart/`` 一层."""
    directory = directory.resolve()
    result = SidecarFiles(directory=directory)
    if not directory.is_dir():
        return result

    nfos: list[Path] = []
    posters: list[Path] = []
    thumbs: list[Path] = []
    fanarts: list[Path] = []

    try:
        entries = list(directory.iterdir())
    except OSError:
        logger.warning("sidecar dir unreadable", path=str(directory))
        return result

    for entry in entries:
        name_lower = entry.name.lower()
        if entry.is_file():
            suffix = entry.suffix.lower()
            if suffix == ".nfo":
                nfos.append(entry)
                continue
            if suffix not in IMAGE_EXTS:
                continue
            if "poster" in name_lower:
                posters.append(entry)
            elif "thumb" in name_lower:
                thumbs.append(entry)
            elif "fanart" in name_lower:
                fanarts.append(entry)
        elif entry.is_dir() and "extrafanart" in name_lower:
            try:
                images = sorted(p for p in entry.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS)
            except OSError:
                images = []
            result.extrafanart.extend(images)

    def _pick(candidates: list[Path]) -> Path | None:
        if not candidates:
            return None
        numbered = [p for p in candidates if name_contains_number(p.name, number)]
        pool = numbered or candidates
        return min(pool, key=lambda p: p.name.lower())

    result.nfo = _pick(nfos)
    result.poster = _pick(posters)
    result.thumb = _pick(thumbs)
    result.fanart = _pick(fanarts)
    return result


def _has_cover(sidecar: SidecarFiles) -> bool:
    return sidecar.poster is not None or sidecar.thumb is not None


async def _parse_sidecar_nfo(sidecar: SidecarFiles) -> ParsedNfo | None:
    if sidecar.nfo is None:
        return None
    return await read_nfo(sidecar.nfo)


def _metadata_from_sidecar(
    query_number: str,
    parsed: ParsedNfo | None,
    sidecar: SidecarFiles,
) -> MediaMetadata:
    if parsed is not None:
        meta = parsed.to_media_metadata(query_number=query_number)
    else:
        meta = MediaMetadata(number=query_number)

    if sidecar.poster is not None:
        meta.poster_urls = [localfile_locator(sidecar.poster)]
    if sidecar.thumb is not None:
        meta.thumb_urls = [localfile_locator(sidecar.thumb)]
    elif sidecar.fanart is not None:
        # fanart 可作为 thumb 候选补充 (非 full_hit 门槛).
        meta.thumb_urls = [localfile_locator(sidecar.fanart)]
    if sidecar.extrafanart:
        meta.extrafanart = [localfile_locator(p) for p in sidecar.extrafanart]
    meta.source_url = str(sidecar.directory)
    return meta


def _classify(sidecar: SidecarFiles, parsed: ParsedNfo | None) -> ProbeKind:
    if parsed is not None and _has_cover(sidecar):
        return ProbeKind.FULL_HIT
    if parsed is not None or _has_cover(sidecar) or sidecar.fanart or sidecar.extrafanart or sidecar.nfo:
        return ProbeKind.PARTIAL
    return ProbeKind.MISS


async def probe_directory(directory: Path, number: str) -> ProbeResult:
    sidecar = collect_sidecar(directory, number)
    warnings: list[str] = []
    parsed = await _parse_sidecar_nfo(sidecar)
    if sidecar.nfo is not None and parsed is None:
        warnings.append(f"nfo unreadable: {sidecar.nfo}")
    if parsed is not None and parsed.number and number_key(parsed.number) != number_key(number):
        warnings.append(f"nfo number {parsed.number} differs from query {number}; using query")

    kind = _classify(sidecar, parsed)
    if kind == ProbeKind.MISS:
        return ProbeResult(kind=kind, sidecar=sidecar, warnings=warnings)

    meta = _metadata_from_sidecar(number, parsed, sidecar)
    return ProbeResult(kind=kind, sidecar=sidecar, parsed=parsed, metadata=meta, warnings=warnings)


def _dir_matches_number(directory: Path, number: str) -> bool:
    if name_contains_number(directory.name, number):
        return True
    # 目录内存在含番号的视频/nfo
    try:
        for entry in directory.iterdir():
            if not entry.is_file():
                continue
            if entry.suffix.lower() in {".nfo", ".mp4", ".mkv", ".avi", ".wmv", ".mov", ".ts", ".m4v"} and name_contains_number(
                entry.name, number
            ):
                return True
    except OSError:
        return False
    return False


def find_in_roots(number: str, roots: Sequence[str | Path], *, max_depth: int = ROOT_MAX_DEPTH) -> list[Path]:
    """各 root 下深度受限 BFS, 返回候选目录 (较精确/较短优先, 并列按 mtime 新)."""
    candidates: list[Path] = []
    seen: set[Path] = set()

    for root_raw in roots:
        root = Path(root_raw).expanduser().resolve()
        if not root.is_dir():
            logger.warning("local root missing", path=str(root))
            continue
        queue: deque[tuple[Path, int]] = deque([(root, 0)])
        while queue:
            current, depth = queue.popleft()
            if current in seen:
                continue
            seen.add(current)
            if current != root and _dir_matches_number(current, number):
                candidates.append(current)
                # 命中后不再深入该分支
                continue
            if depth >= max_depth:
                continue
            try:
                children = [p for p in current.iterdir() if p.is_dir() and not p.name.startswith(".")]
            except OSError:
                continue
            for child in children:
                queue.append((child, depth + 1))

    def _rank(p: Path) -> tuple[int, int, float]:
        exact = 0 if number_key(p.name) == number_key(number) else 1
        try:
            mtime = -p.stat().st_mtime
        except OSError:
            mtime = 0.0
        return (exact, len(p.name), mtime)

    candidates.sort(key=_rank)
    return candidates


async def probe(
    number: str,
    *,
    file_path: str | None = None,
    roots: Sequence[str | Path] | None = None,
) -> ProbeResult:
    """旁路优先, 再扫 ``local_roots``. 父目录 full_hit 时不读根."""
    roots = list(roots or [])
    warnings: list[str] = []

    if file_path:
        parent = Path(file_path).expanduser().resolve().parent
        parent_result = await probe_directory(parent, number)
        warnings.extend(parent_result.warnings)
        if parent_result.kind == ProbeKind.FULL_HIT:
            return parent_result
        # 父目录 partial 先记下, 根目录 full_hit 可覆盖
        best_partial = parent_result if parent_result.kind == ProbeKind.PARTIAL else None
    else:
        best_partial = None

    for candidate in find_in_roots(number, roots):
        result = await probe_directory(candidate, number)
        warnings.extend(result.warnings)
        if result.kind == ProbeKind.FULL_HIT:
            result.warnings = warnings + result.warnings
            return result
        if best_partial is None and result.kind == ProbeKind.PARTIAL:
            best_partial = result

    if best_partial is not None:
        best_partial.warnings = warnings + best_partial.warnings
        return best_partial

    return ProbeResult(kind=ProbeKind.MISS, warnings=warnings)


def sidecar_raw_snapshot(sidecar: SidecarFiles, parsed: ParsedNfo | None) -> dict:
    """写入 raw['local'] 的规范化结构."""
    return {
        "directory": str(sidecar.directory),
        "nfo": str(sidecar.nfo) if sidecar.nfo else None,
        "poster": str(sidecar.poster) if sidecar.poster else None,
        "thumb": str(sidecar.thumb) if sidecar.thumb else None,
        "fanart": str(sidecar.fanart) if sidecar.fanart else None,
        "extrafanart": [str(p) for p in sidecar.extrafanart],
        "parsed": None
        if parsed is None
        else {
            "number": parsed.number,
            "title": parsed.title,
            "plot": parsed.plot,
            "release": parsed.release,
            "runtime": parsed.runtime,
            "studio": parsed.studio,
            "publisher": parsed.publisher,
            "series": parsed.series,
            "actors": parsed.actors,
            "tags": parsed.tags,
            "directors": parsed.directors,
            "score": parsed.score,
        },
    }
