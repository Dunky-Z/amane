# 播放进度、复制按钮与海报标记 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 控制条可复制时间戳/链接；按影片服务端持久化进度并自动续播；全部海报墙可点「已播放」「收藏」并写入固定名用户标签。

**Architecture:** 进度独立表 + playback 路由（须注册在 `/{source_id}/…` 之前）；标记复用 `user_tag` 批量 API，列表批量填充 `user_tags`；复制复用既有 ContextMenu 动作与 `copyText`。

**Tech Stack:** FastAPI · SQLModel · Alembic · React · Mantine · media-chrome · pytest

**Spec:** `docs/superpowers/specs/2026-09-29-playback-progress-and-poster-marks-design.md`

## Global Constraints

- 进度键仅为 `metadata_id`；接近片尾不清除；`?t=` 优先于已存进度。
- 标签名固定：`已播放`、`收藏`；与进度互不读写。
- 触屏长按 2 倍速与桌面画面右键菜单保留。
- 迁移必须 `uv run alembic revision`；禁止手写 revision ID。
- 提交说明遵守 `32-amane-git-flow`；用语遵守 `docs/dev/writing.md`。
- 工作区：`amane-playback-float` / `feat/playback-float`。

---

### Task 1: 播放进度表、仓储与 API

**Files:**
- Modify: `src/amane/db/models.py` — 新增 `PlaybackProgress`
- Create: Alembic revision via `uv run alembic revision --autogenerate -m "playback_progress"`
- Modify: `src/amane/db/repos/`（playback 相关或 metadata/新模块）+ `repository.py` 暴露方法
- Modify: `src/amane/api/models/` — `PlaybackProgressResponse` / PUT body
- Modify: `src/amane/api/routes/playback.py` — `GET|PUT /progress/{metadata_id}`，**注册顺序在** `/{source_id}/…` **之前**
- Test: `tests/api/test_playback_progress.py`（或并入 `test_playback.py`）

**Interfaces:**
- Produces: `get_playback_progress(metadata_id) -> float | None`；`upsert_playback_progress(metadata_id, position_seconds: float) -> float`；HTTP `{ position_seconds: number | null }`

- [ ] 写失败测试：无进度 GET 200 null；PUT 后 GET 回读；删 metadata 级联；未知 id 404；负数 422
- [ ] 模型 + alembic + repo + 路由
- [ ] 测试通过并提交

### Task 2: 前端进度读写与自动 seek

**Files:**
- Modify: `web/src/components/media/playback-panel.tsx` / `playback-player.tsx` / 详情或浮层接线
- 生成 client：`just generate`（若 OpenAPI 变）

**Interfaces:**
- Consumes: Task 1 HTTP
- Produces: 节流 PUT；打开可 seek 且无覆盖性 `?t=` 时注入 `seekRequest`

- [ ] 接 GET/PUT；节流 5–10s + pause/pagehide/关浮层
- [ ] `?t=` 优先；否则恢复进度
- [ ] 提交

### Task 3: 控制条复制菜单

**Files:**
- Modify: `web/src/components/media/playback-player.tsx`（及 module.css / i18n 若需）

- [ ] 控制条按钮 + 与右键相同两项；不可寻址禁用
- [ ] 提交

### Task 4: 列表批量 `user_tags` + 海报开关

**Files:**
- Modify: `src/amane/db/repos/facets.py` — `list_user_tags_for_metadata_ids(ids) -> dict[int, list[UserTag]]`
- Modify: `src/amane/api/routes/metadata.py` — `list_metadata` 填充 `user_tags`
- Test: API 列表含标签
- Modify: `web/src/components/media/poster-card.tsx` — 开关 UI；常量名 `已播放`/`收藏`
- Modify: i18n 按钮文案
- Docs: `docs/dev/frontend.md`、`docs/dev/api.md` 各补契约一句

- [ ] 后端批量附带 + 测试
- [ ] PosterCard 乐观切换（get-or-create + attach/detach）
- [ ] 文档 + `just generate`（若需要）+ 提交

### Task 5: 验收服务

- [ ] 按 `amane-serve` 在 worktree 起 API+Vite，确认续播与海报开关可点
