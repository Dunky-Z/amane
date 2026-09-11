# 刮削失败写回 MediaFile 状态

## 背景

全库刮削后大量文件会失败. `MediaFile.status` 已有 `failed`, REFRESH
的刮削范围也可勾选 `pending` / `failed`, 但 SCRAPE 失败时只将 Task 标为
`failed`, **不**更新 `MediaFile`. 失败文件一直停在 `pending`, 下次勾选
"待处理"会再次扇出, 浪费请求与队列资源.

`docs/prd.md` 已记录该需求: 失败文件标记失败, 避免与新增文件混刮; 需要时
在提交任务中单独勾选"失败"重试.

## 目标

- SCRAPE 任务失败且存在 `media_file_id` 时, 将对应 `MediaFile.status` 写为
  `failed`
- SCRAPE 成功仍经 `finalize_media_file` 写为 `scraped` (含从 `failed` 重试成功)
- REFRESH 勾选 `pending` 只扇出待处理 (含新注册文件); 勾选 `failed` 只扇出
  历史失败, 供主动重试
- 失败策略取全量失败写回: 凡 SCRAPE 失败均标 `failed`, 不区分瞬时网络与
  无可用元数据

## 非目标

- 将失败文件移动到独立目录或自动归档
- 自动改为 `skip` (永久忽略仍由用户手动设置)
- 修改任务提交 UI 文案或勾选控件 (选项已存在)
- 按失败原因细分状态或重试策略
- 改变 by-number (无 `media_file_id`) 刮削对 MediaFile 的行为

## 现状

| 组件 | 行为 |
| ---- | ---- |
| `MediaFileStatus` | 含 `pending` / `scraped` / `failed` / `skip` |
| `RefreshPayload.scrape` | 默认 `{pending}`, 按状态列表扇出 SCRAPE |
| `finalize_media_file` | 成功时写 `scraped` + `metadata_id` |
| `ScrapeHandler` 失败路径 | 仅 `TaskResult(success=False)`, 不改 MediaFile |
| Worker | `fail_task` 只更新 Task, 不改 MediaFile |
| 代码库 | **无任何**写出 `MediaFileStatus.FAILED` 的路径 |

## 架构

```
ScrapeHandler.handle
  成功 → finalize_media_file → MediaFile.scraped
  失败 → mark_media_file_failed → MediaFile.failed → TaskResult(success=False)
Worker (SCRAPE 进入 fail_task 时)
  → mark_media_file_failed (幂等) → fail_task (Task)
```

REFRESH 扇出逻辑不变: `list_media_files(..., status=payload.scrape)`.
待处理与失败的分流完全依赖 MediaFile 状态写回是否正确.

## 行为契约

1. **失败写回**: 存在 `media_file_id` 时, SCRAPE 失败将 `MediaFile.status`
   设为 `failed`. `media_file_id` 为 `None` 时跳过.
2. **成功覆盖**: 成功路径写 `scraped`; 对先前 `failed` 的文件重试成功后回到
   `scraped`.
3. **显式失败路径**: 至少覆盖 `ScrapeHandler` 内所有
   `TaskResult(success=False)` 返回点 (无路由爬虫、无可用爬虫、无可用元数据等).
4. **Worker 兜底 (必做)**: SCRAPE 在 handler 抛未捕获异常、用户取消、或
   `success=False` 进入 `fail_task` 时, 若 payload 含 `media_file_id`, 调用
   `mark_media_file_failed`. 取消与崩溃不经过 handler 的显式失败返回, 只能
   由 Worker 覆盖. 与 handler 内调用幂等 (重复写 `failed` 无害).
5. **取消**: 取消视为任务失败, 有 `media_file_id` 则写 `failed` (由上条兜底).
6. **不挪文件**: 不改变磁盘路径; ORGANIZE / 归档规则不变.

## 实现要点

### 共享单元

在 `handlers/_common.py` 增加与 `finalize_media_file` 对称的:

```python
async def mark_media_file_failed(repo, media_file_id: int | None) -> None:
    """media_file_id 为 None 时静默跳过."""
```

仅更新 `status=MediaFileStatus.FAILED`, 不清除已有 `metadata_id` (失败文件
通常本就无关联; 若曾有关联被删元数据后回 `pending`, 失败再标 `failed` 即可).

### ScrapeHandler

每条失败返回前 `await mark_media_file_failed(self._repo, payload.media_file_id)`.
禁止只改 Task 而留下 `pending`.

### Worker

对 `TaskType.SCRAPE`, 凡进入 `fail_task` 的路径 (含 `success=False`、未捕获
异常、取消) 在 `fail_task` 之前解析 payload 的 `media_file_id`, 调用
`mark_media_file_failed`. 解析失败则跳过写回, 不阻断 `fail_task`.

### 文档

- `docs/dev/task-system.md`: 在 SCRAPE / 共享单元表补充失败写回说明.
- `docs/prd.md`: 对应条目可在实现合并后删除或标注已完成 (实现计划阶段处理).

## 测试

- Handler: 无元数据失败后 `MediaFile.status == failed`.
- Handler: 成功后仍为 `scraped`.
- REFRESH: 库内含 `pending` 与 `failed` 时, `scrape={pending}` 只扇出 pending;
  `scrape={failed}` 只扇出 failed.
- `media_file_id is None` 的失败不抛错、不写库.

## 风险与取舍

- 瞬时网络失败也会进入 `failed`, 不会在下次"待处理"扫描中自动重试; 用户须
  显式勾选"失败". 这是产品选择 (方案 A), 换取日常扫描不浪费资源.
- 历史已失败但仍为 `pending` 的存量文件不会自动迁移; 再跑一轮刮削后才会被
  标为 `failed`. 不要求一次性数据迁移脚本.
