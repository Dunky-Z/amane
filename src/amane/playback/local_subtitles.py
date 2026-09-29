"""已索引视频同目录的外挂字幕. 转成 WebVTT 后由播放端点提供.

轨道 id 以 ``local-`` 开头, 与插件声明的轨道分开. 扩展名取该库的字幕配置;
``.sub`` 仅在正文含 SRT 时间轴时纳入.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from ..organize.subtitles import discover_subtitles
from ..parsing import parse_file_info
from ..utils.threads import in_thread

_TEXT_EXTENSIONS = frozenset({".srt", ".vtt", ".ass", ".ssa"})
_LANG_TOKENS = {
    "zh": "zh",
    "zho": "zh",
    "chi": "zh",
    "chs": "zh",
    "cht": "zh-Hant",
    "zh-cn": "zh",
    "zh-tw": "zh-Hant",
    "zh-hans": "zh",
    "zh-hant": "zh-Hant",
    "en": "en",
    "eng": "en",
    "ja": "ja",
    "jp": "ja",
    "jpn": "ja",
    "ko": "ko",
    "kor": "ko",
}
_ASS_TAG = re.compile(r"\{[^}]*\}")
_SRT_TIME = re.compile(r"(\d{2}:\d{2}:\d{2}),(\d{3})")


@dataclass(frozen=True, slots=True)
class LocalSubtitle:
    track_id: str
    label: str
    language: str | None
    path: Path


def is_local_track_id(track_id: str) -> bool:
    return track_id.startswith("local-")


def _track_id(file_id: int, name: str) -> str:
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:12]
    return f"local-{file_id}-{digest}"


def _language(name: str) -> str | None:
    tokens = re.split(r"[.\-_ ]+", Path(name).stem.casefold())
    for token in reversed(tokens):
        language = _LANG_TOKENS.get(token)
        if language is not None:
            return language
    return None


def _convertible(path: Path) -> bool:
    suffix = path.suffix.lower()
    if suffix in _TEXT_EXTENSIONS:
        return True
    if suffix != ".sub":
        return False
    try:
        sample = path.read_bytes()[:4096]
    except OSError:
        return False
    return b"-->" in sample


def _read_text(path: Path) -> str:
    data = path.read_bytes()
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("gb18030")


def _ensure_vtt(text: str) -> str:
    body = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff").strip()
    if body.startswith("WEBVTT"):
        return body + "\n"
    return f"WEBVTT\n\n{body}\n"


def _srt_to_vtt(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    converted = _SRT_TIME.sub(r"\1.\2", normalized).strip()
    return f"WEBVTT\n\n{converted}\n"


def _ass_time(raw: str) -> str:
    """ASS 时间为 ``H:MM:SS.cs``. 不足两位的厘秒补齐成 WebVTT 的毫秒."""
    hour_text, minute_text, rest = raw.strip().split(":")
    if "." in rest:
        second_text, fraction = rest.split(".", 1)
    else:
        second_text, fraction = rest, "0"
    millis = (fraction + "000")[:3]
    return f"{int(hour_text):02d}:{int(minute_text):02d}:{int(second_text):02d}.{millis}"


def _ass_text(raw: str) -> str:
    cleaned = raw.replace(r"\N", "\n").replace(r"\n", "\n").replace(r"\h", " ")
    return _ASS_TAG.sub("", cleaned).strip()


def _ass_to_vtt(text: str) -> str:
    cues: list[str] = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").splitlines():
        if not line.startswith("Dialogue:"):
            continue
        parts = line[len("Dialogue:") :].lstrip().split(",", 9)
        if len(parts) < 10:
            continue
        body = _ass_text(parts[9])
        if not body:
            continue
        cues.append(f"{_ass_time(parts[1])} --> {_ass_time(parts[2])}\n{body}\n")
    joined = "\n".join(cues)
    return f"WEBVTT\n\n{joined}\n" if joined else "WEBVTT\n\n"


def to_webvtt(path: Path) -> str:
    text = _read_text(path)
    suffix = path.suffix.lower()
    if suffix == ".vtt":
        return _ensure_vtt(text)
    if suffix in {".ass", ".ssa"}:
        return _ass_to_vtt(text)
    return _srt_to_vtt(text)


@in_thread
def discover_local_subtitles(files: Sequence[tuple[int, str, Sequence[str]]]) -> list[LocalSubtitle]:
    """``files`` 为 ``(file_id, 视频路径, 字幕扩展名)``. 多条视频都有字幕时, 标签带上视频文件名."""
    grouped: list[tuple[str, list[Path], int]] = []
    for file_id, raw_path, extensions in files:
        video = Path(raw_path)
        found = [
            path for path in discover_subtitles.sync(video, extensions, parse_file_info(video)) if _convertible(path)
        ]
        if found:
            grouped.append((video.name, found, file_id))
    multiple = len(grouped) > 1
    tracks: list[LocalSubtitle] = []
    for video_name, paths, file_id in grouped:
        for path in paths:
            label = f"{video_name} / {path.name}" if multiple else path.name
            tracks.append(
                LocalSubtitle(
                    track_id=_track_id(file_id, path.name),
                    label=label,
                    language=_language(path.name),
                    path=path,
                )
            )
    return tracks


@in_thread
def read_webvtt(path: Path) -> str:
    return to_webvtt(path)
