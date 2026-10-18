"""drop leftover uppercase trash tasks

Revision ID: 6587ccd946ea
Revises: 9054ebacea29
Create Date: 2026-10-18 12:04:13.942743

1f050b272f7d 只删除 ``type = 'trash'``. 本库把枚举成员名写入该列, 历史行是 ``TRASH``.
这两种写法读入已删除的枚举成员时都会失败, 任务列表因此整页 500.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6587ccd946ea"
down_revision: str | None = "9054ebacea29"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """删除回收任务的残留行, 大小写都覆盖. 先删链上的边, 避免留下指向已删任务的行."""
    op.execute(
        sa.text("DELETE FROM task_links WHERE parent_task_id IN (SELECT id FROM tasks WHERE lower(type) = 'trash')")
    )
    op.execute(
        sa.text("DELETE FROM task_links WHERE child_task_id IN (SELECT id FROM tasks WHERE lower(type) = 'trash')")
    )
    op.execute(sa.text("DELETE FROM tasks WHERE lower(type) = 'trash'"))


def downgrade() -> None:
    """删除的历史行不可恢复."""
