"""外挂字幕发现与 WebVTT 转换."""

from pathlib import Path

from amane.playback.local_subtitles import discover_local_subtitles, read_webvtt

_SRT = "1\n00:00:01,000 --> 00:00:02,000\n你好\n"
_ASS = """[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.18,0:00:03.00,Default,,0,0,0,,{\\b1}你好\\N世界
"""
_VTT = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHello\n"


def test_discover_and_convert_sidecars(tmp_path: Path) -> None:
    video = tmp_path / "SSIS-001.mp4"
    video.write_bytes(b"v")
    srt = tmp_path / "SSIS-001.chs.srt"
    srt.write_text(_SRT, encoding="utf-8")
    ass = tmp_path / "SSIS-001.eng.ass"
    ass.write_text(_ASS, encoding="utf-8")
    vtt = tmp_path / "SSIS-001.ja.vtt"
    vtt.write_text(_VTT, encoding="utf-8")
    other = tmp_path / "OTHER-999.srt"
    other.write_text(_SRT, encoding="utf-8")
    (tmp_path / "SSIS-001.frame.sub").write_text("{1}{2}frame\n", encoding="utf-8")
    subrip = tmp_path / "SSIS-001.sub"
    subrip.write_text("1\n00:00:01,000 --> 00:00:02,000\nsub\n", encoding="utf-8")

    tracks = discover_local_subtitles.sync([(7, str(video), (".srt", ".ass", ".ssa", ".vtt", ".sub"))])
    by_suffix = {track.path.suffix: track for track in tracks}
    assert set(by_suffix) == {".srt", ".ass", ".vtt", ".sub"}
    assert by_suffix[".srt"].language == "zh"
    assert by_suffix[".ass"].language == "en"
    assert by_suffix[".vtt"].language == "ja"
    assert by_suffix[".srt"].label == "SSIS-001.chs.srt"
    assert all(track.track_id.startswith("local-7-") for track in tracks)

    srt_vtt = read_webvtt.sync(srt)
    assert srt_vtt.startswith("WEBVTT\n")
    assert "00:00:01.000 --> 00:00:02.000" in srt_vtt
    assert "你好" in srt_vtt
    ass_vtt = read_webvtt.sync(ass)
    assert "00:00:01.180 --> 00:00:03.000" in ass_vtt
    assert "你好" in ass_vtt
    assert r"\b1" not in ass_vtt
    assert "世界" in ass_vtt
    assert read_webvtt.sync(vtt) == _VTT if _VTT.endswith("\n") else _VTT + "\n"

    assert discover_local_subtitles.sync([(7, str(video), ())]) == []


def test_multiple_videos_label_includes_filename(tmp_path: Path) -> None:
    first = tmp_path / "a" / "SSIS-001.mp4"
    second = tmp_path / "b" / "SSIS-002.mp4"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_bytes(b"a")
    second.write_bytes(b"b")
    (first.parent / "SSIS-001.srt").write_text(_SRT, encoding="utf-8")
    (second.parent / "SSIS-002.srt").write_text(_SRT, encoding="utf-8")

    tracks = discover_local_subtitles.sync(
        [
            (1, str(first), (".srt",)),
            (2, str(second), (".srt",)),
        ]
    )
    assert [track.label for track in tracks] == [
        "SSIS-001.mp4 / SSIS-001.srt",
        "SSIS-002.mp4 / SSIS-002.srt",
    ]
