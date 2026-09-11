# 刮削失败写回 MediaFile 状态 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** SCRAPE 失败时将关联 `MediaFile` 标为 `failed`, 使 REFRESH 勾选 `pending` 不再重复扇出历史失败文件.

**Architecture:** `mark_media_file_failed` 与 `finalize_media_file` 对称; `ScrapeHandler` 显式失败路径调用; `AsyncWorker` 在 SCRAPE 的 cancel / crash / `success=False` 进入 `fail_task` 前幂等兜底. `complete_task_with_followups` 失败不写 `failed` (此时 MediaFile 已是 scraped).

**Tech Stack:** Python, pytest, SQLModel MediaFile, AsyncWorker

## Global Constraints

- 用语遵守 `docs/dev/writing.md`
- 提交说明遵守 `32-amane-git-flow.mdc` (`type: 中文说明` + 中文正文)
- Git 在被改文件最近公共父目录执行
- 不改 UI; 不做失败归档目录; 不区分瞬时/确定性失败

## File Map

| 文件 | 职责 |
| ---- | ---- |
| `src/amane/handlers/_common.py` | 新增 `mark_media_file_failed` |
| `src/amane/handlers/scrape.py` | 失败返回前写回 |
| `src/amane/scheduler/worker.py` | SCRAPE fail 路径兜底 |
| `tests/handlers/test_common.py` | 单元测试 mark 函数 |
| `tests/handlers/test_scraper.py` | Handler / REFRESH 行为 |
| `tests/scheduler/test_worker.py` | Worker 兜底 |
| `docs/dev/task-system.md` | 文档同步 |
| `docs/prd.md` | 删除已实现条目 |

---

### Task 1: `mark_media_file_failed` + Handler 写回

**Files:**
- Modify: `src/amane/handlers/_common.py`
- Modify: `src/amane/handlers/scrape.py`
- Modify: `tests/handlers/test_common.py`
- Modify: `tests/handlers/test_scraper.py`

**Interfaces:**
- Produces: `async def mark_media_file_failed(repo: Repository, media_file_id: int | None) -> None`

- [ ] **Step 1: 写失败测试**

在 `test_common.py` 增加 `TestMarkMediaFileFailed` (对称 `TestFinalizeMediaFile`): id 有效 → `failed`; `None` → noop.

在 `test_scraper.py` 的 `test_no_results_marks_failed` 末尾断言 `updated.status == MediaFileStatus.FAILED`.
在 `test_empty_route_returns_error` 同样断言.
新增 `test_no_results_without_media_file_id_ok`: `media_file_id=None` 失败不抛错.

新增 REFRESH 测试 `test_scrape_scope_pending_skips_failed`: 预置 pending + failed 各一, `scrape={PENDING}` 只扇出 1; `scrape={FAILED}` 只扇出 failed 那条.

- [ ] **Step 2: 跑测试确认失败**

```bash
cd /root/sharedfolder/develop/amane && python -m pytest tests/handlers/test_common.py tests/handlers/test_scraper.py::TestScrapeHandler::test_no_results_marks_failed -q
```

Expected: 新断言 FAIL (status 仍为 pending)

- [ ] **Step 3: 实现**

`_common.py`:

```python
async def mark_media_file_failed(repo: Repository, media_file_id: int | None) -> None:
    """media_file_id 为 None 时静默跳过."""
    if media_file_id is None:
        return
    await repo.update_media_file(media_file_id, status=MediaFileStatus.FAILED)
```

`scrape.py`: import `mark_media_file_failed`; 三处 `return TaskResult(success=False, ...)` 前:

```python
await mark_media_file_failed(self._repo, payload.media_file_id)
```

- [ ] **Step 4: 跑测试确认通过**

```bash
python -m pytest tests/handlers/test_common.py tests/handlers/test_scraper.py -q
```

- [ ] **Step 5: Commit**

```text
fix: 刮削失败时将 MediaFile 标记为 failed

与 finalize_media_file 对称增加 mark_media_file_failed.
显式失败路径写回后, REFRESH 勾选 pending 不再扇出历史失败.
```

---

### Task 2: Worker 兜底

**Files:**
- Modify: `src/amane/scheduler/worker.py`
- Modify: `tests/scheduler/test_worker.py`

**Interfaces:**
- Consumes: `mark_media_file_failed`
- Produces: Worker 在 SCRAPE 的 cancel / handle 异常 / `success=False` 路径调用兜底

- [ ] **Step 1: 写失败测试**

在 `test_worker.py` 增加: 创建 MediaFile (pending), 入队 SCRAPE payload 含 `media_file_id`, 用 `FailHandler` (dict payload 带 media_file_id), worker 跑完后 MediaFile 为 `failed`.

另测: ORGANIZE 类型失败不改 MediaFile (若 payload 误带 media_file_id 也不写 — 仅 `TaskType.SCRAPE`).

注意: `complete_task_with_followups` 失败路径**不**调用 mark (已 scraped).

- [ ] **Step 2: 实现 Worker 辅助方法并挂到三条 fail 路径**

```python
async def _mark_scrape_media_failed(self, task_type: TaskType, payload: Any) -> None:
    if task_type != TaskType.SCRAPE:
        return
    media_file_id = getattr(payload, "media_file_id", None) if not isinstance(payload, dict) else payload.get("media_file_id")
    if media_file_id is None:
        return
    try:
        from ..handlers._common import mark_media_file_failed
        await mark_media_file_failed(self._repo, int(media_file_id))
    except Exception:
        logger.exception("mark media file failed after scrape failure", media_file_id=media_file_id)
```

在 CancelledError / Exception / `else` (`success=False`) 中, `fail_task` **之前**调用; **不要**在 `complete_task_with_followups` 的 except 里调用.

- [ ] **Step 3: 跑测试**

```bash
python -m pytest tests/scheduler/test_worker.py tests/handlers/test_scraper.py -q
```

- [ ] **Step 4: Commit**

```text
fix: Worker 在 SCRAPE 失败兜底标记 MediaFile

取消与未捕获异常不经 Handler 显式返回, 由 Worker 写 failed.
```

---

### Task 3: 文档

**Files:**
- Modify: `docs/dev/task-system.md` (共享单元表 + SCRAPE 简述)
- Modify: `docs/prd.md` (删除已实现的失败标记条目)

- [ ] **Step 1: 更新文档并提交**

```text
docs: 说明刮削失败写回 MediaFile.failed

同步 task-system 共享单元表; 从 prd 移除已落地条目.
```
