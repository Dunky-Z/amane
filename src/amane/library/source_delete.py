"""删除已索引视频路径. 只删除调用方给出的路径, 不跟随符号链接."""

from __future__ import annotations

import stat
from collections.abc import Sequence
from pathlib import Path

from ..utils.threads import in_thread


class SourceDeleteError(Exception):
    """路径不能删, 或删除时操作系统拒绝. ``reason`` 给终端用户."""

    def __init__(self, path: str, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"{reason}: {path}")


def _unlink_target(raw: str) -> Path | None:
    """返回要 ``unlink`` 的路径. 路径不存在时返回 None. 不安全的路径抛 ``SourceDeleteError``."""
    text = raw.strip()
    if not text:
        raise SourceDeleteError(raw, "路径为空")
    path = Path(text)
    if not path.is_absolute():
        raise SourceDeleteError(text, "路径不是绝对路径")
    if path.parent == path:
        raise SourceDeleteError(text, "拒绝删除根路径")
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise SourceDeleteError(text, exc.strerror or "无法读取路径") from exc
    if stat.S_ISDIR(info.st_mode):
        raise SourceDeleteError(text, "路径是目录")
    if stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode):
        return path
    raise SourceDeleteError(text, "不是普通文件")


@in_thread
def unlink_indexed_files(paths: Sequence[str]) -> None:
    """先核对全部路径, 再删除. 任一路径不能删时, 已核对的文件也不删除.

    符号链接只删除链接本身. 路径已经不存在视为成功.
    """
    targets = [_unlink_target(raw) for raw in paths]
    for path in targets:
        if path is None:
            continue
        try:
            path.unlink()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise SourceDeleteError(str(path), exc.strerror or "删除失败") from exc
