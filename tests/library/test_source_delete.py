"""已索引路径的删除: 普通文件与符号链接可删, 目录与根路径拒绝且不删已核对的文件."""

from pathlib import Path

import pytest

from amane.library.source_delete import SourceDeleteError, unlink_indexed_files


def test_unlink_indexed_files(tmp_path: Path) -> None:
    unlink_indexed_files.sync([])

    video = tmp_path / "clip.mp4"
    video.write_bytes(b"v")
    missing = tmp_path / "gone.mp4"
    target = tmp_path / "target.mp4"
    target.write_bytes(b"t")
    link = tmp_path / "link.mp4"
    link.symlink_to(target)

    unlink_indexed_files.sync([str(video), str(missing), str(link)])
    assert not video.exists()
    assert not link.exists()
    assert target.read_bytes() == b"t"

    kept = tmp_path / "kept.mp4"
    kept.write_bytes(b"k")
    folder = tmp_path / "dir"
    folder.mkdir()
    unlink_indexed_files.sync([str(tmp_path / "missing-dir" / "clip.mp4")])

    with pytest.raises(SourceDeleteError, match="路径是目录"):
        unlink_indexed_files.sync([str(kept), str(folder)])
    assert kept.read_bytes() == b"k"
    assert folder.is_dir()

    with pytest.raises(SourceDeleteError, match="绝对路径"):
        unlink_indexed_files.sync(["clip.mp4"])
    with pytest.raises(SourceDeleteError, match="根路径"):
        unlink_indexed_files.sync(["/"])
