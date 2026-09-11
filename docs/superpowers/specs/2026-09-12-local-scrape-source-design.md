# 本地路径作为刮削来源

## 背景

用户从 MDCx 等工具迁入时, 视频旁常已有 Kodi/Emby 风格 sidecar
(`.nfo` / poster / thumb / fanart / `extrafanart/`). 今日 SCRAPE 只走在线站,
ORGANIZE 只从 ResourceStore 取图, **不读**旁路文件. 全量在线重刮浪费反爬配额.

`docs/prd.md` 需求是: **刮削源可选本地路径**, 不是独立"导入任务".
查找以视频所在目录为准, 不依赖上层是发行商还是演员目录.

现行 `docs/dev/data-model.md` 写明日常不以 NFO 反推 Metadata.
本特性将引入**显式本地来源**: 仅当路由启用 `local` 时参与刮削; 日常重建仍以
DB 为真源、ORGANIZE 再写出 NFO.

## 已确认取舍

| 项 | 选择 |
| -- | ---- |
| 定位 | C: 全局可配根目录 + **视频父目录优先** |
| 与在线关系 | C: **全量命中则本片不请求任何在线站**; 残缺才回退在线聚合 |
| 全量门槛 | B: 可解析 `.nfo` **且**至少一张封面类图 (poster 或 thumb) |
| 形态 | 内置来源 ID `local`, 进入 `content_routes` / 聚合管线 |

## 目标

- 内置刮削来源 `local`, 可写入各 `content_routes` 与 `field_priority`
- 配置一个或多个本地根路径 (`local_roots`), 路径须落在 `AMANE_SAFE_DIRS`
- 查找顺序: 当前 `SearchQuery` 视频父目录 → 各根下按番号匹配
- 全量命中 (门槛 B): `ScrapeHandler` 短路, 不调用其它爬虫
- 残缺: 正常 `aggregate`; 若路由含 `local`, 本地已有字段/图仍可参与填空
- sidecar 图经本地 ingest 进入 ResourceStore, Metadata URL 写内部资源 URL
- 解析 NFO → `upsert_metadata` + `finalize_media_file` (成功路径与在线刮削一致)

## 非目标

- 独立 LOCAL_IMPORT / 迁移任务 UI
- 导入后自动 ORGANIZE / 移动视频
- 无 NFO 仅靠图片建完整片
- 把本地 sidecar 当作 ORGANIZE 的旁路复制源 (仍只从 Resource / DB 派生落盘)
- 首版支持任意非 Kodi `<movie>` 私有格式 (可后续扩展)

## 现状 (相关)

| 组件 | 行为 |
| ---- | ---- |
| `write_nfo` | 只写 Kodi `<movie>` XML |
| NFO 读 | 无 |
| `ResourceStore.acquire` | 仅 HTTP |
| ORGANIZE 配图 | 只从 Metadata URL → Resource |
| 同目录 sidecar | 仅字幕发现 |
| 插件 | 可做影片源, 但难以单独表达"全片短路不联网" |

## 架构

```
ScrapeHandler.handle
  │
  ├─ 路由含 local?
  │     否 → 既有 aggregate(在线…)
  │     是 → LocalSource.probe(query, roots)
  │              │
  │              ├─ full_hit (nfo + poster|thumb)
  │              │     → ingest 图 → upsert + finalize
  │              │     → 不请求其它站; 可照常翻译/物化策略按配置
  │              │
  │              └─ miss / partial
  │                    → aggregate(含 local crawler + 其它站)
  │                    → 既有物化 / upsert / finalize
  └─ …
```

`LocalSource` / 内置 crawler `local`:

- `fetch(SearchQuery) → MediaMetadata | None`
- 图片 URL 使用稳定 locator (见下), 供 ingest 与 `raw` 快照
- `field_sources` 标量记 `local`

## 配置

建议 Hot `scraping` 段 (名称以实现时与现有风格对齐为准):

```toml
[scraping]
# 示例; 实际字段名落在 ScrapingConfig
local_roots = ["/media/jav/JAV_output"]
```

或 `site_config.local` 内承载 `roots` / `enabled` 同类项.
`local_roots` 空且仅依赖视频旁目录时仍可工作 (B 命中只靠父目录).

校验:

- 每个 root 必须存在且为目录
- 必须通过 `safe_dirs` (与 PathPicker / 插件 path 安装同契约)
- `content_routes` 允许成员 `local` (内置单段 ID)

前端: 刮削设置增加本地根路径列表 (PathPicker directory); 片种路由多选中出现
`local`. 无独立"导入"页.

## 定位与匹配

输入: `SearchQuery.number` (已规范化)、可选 `SearchQuery.path` (视频路径).

1. **旁路优先**: 若 `path` 有父目录, 在该目录收集 sidecar (不递归子视频目录;
   `extrafanart/` 只扫这一层子目录).
2. **根目录**: 对每个 `local_roots`, 按番号查找候选目录或同级文件组.
   匹配规则 (大小写不敏感):
   - 目录名包含规范化番号 (允许去横杠等价, 如 `MIDV-123` / `MIDV123`)
   - 或目录内存在文件名包含番号的视频/nfo
3. 多候选时: 优先目录名精确/更短者; 并列则取修改时间更新的; 记 warning.

单目录内收集 (关键字, 大小写不敏感):

| 角色 | 规则 |
| ---- | ---- |
| nfo | 扩展名 `.nfo`; 多名时优先文件名含番号者, 否则任取一份可解析者 |
| poster | 文件名含 `poster` |
| thumb | 文件名含 `thumb` |
| fanart | 文件名含 `fanart` 且非 poster/thumb |
| extrafanart | 子目录名等于 `extrafanart` (或含该关键字) 下的图片文件 |

图片扩展名: `.jpg` `.jpeg` `.png` `.webp` (与现有媒体习惯对齐).

## 全量命中与短路

**full_hit** 当且仅当:

1. 至少一份 `.nfo` 解析成功 (得到可用 `number` 或与 query 番号一致的标题字段), 且
2. 至少存在 poster **或** thumb 本地文件.

则:

- 不构造其它站 crawler 请求 (本 task 内零出站刮削 HTTP; 翻译 LLM 仍按
  `llm` 配置, 与今日刮削一致 — 若需"全离线含翻译"可作为后续开关, 首版不另做)
- 解析 NFO 字段 → Metadata; 图全部 ingest 后写入对应 URL 列表
- `finalize_media_file`

**非 full_hit**:

- 进入既有 `aggregate`
- 若路由含 `local`, `local` 作为普通节点贡献 partial `MediaMetadata`
- 其它站照常抓取

by-number 且无 `media_file_id` / 无 path: 仅根目录查找; 无旁路优先步.

## NFO 解析

新增 `read_nfo` / `parse_nfo` (与 `write_nfo` 同模块或 `media/nfo_read.py`).

首版目标格式: Kodi/Emby `<movie>` (与本仓库 `write_nfo` 及常见 MDCx 输出同族).

字段映射 (有则填):

| NFO | Metadata |
| --- | -------- |
| `num` / 从 `title` 剥番号 | `number` (与 query 不一致时以 query 为准并记 warning) |
| `title` / `originaltitle` (去掉前缀番号) | `title` |
| `plot` / `outline` | `plot` |
| `premiered` / `releasedate` | `release` |
| `runtime` | `runtime` |
| `studio` / `maker` | `studio` |
| `publisher` / `label` | `publisher` |
| `series` / `set/name` | `series` |
| `actor/name` | `actors` |
| `tag` / `genre` | `tags` |
| `director` | `directors` (若存在) |

无法解析或根元素非 `movie`: 该 nfo 视为无效, 不计入 full_hit.

`raw` 快照: 存规范化后的本地结构 (路径列表 + 解析字段), key `local`, 便于调试;
不假装成某在线站 HTML.

## 本地图 ingest

`ResourceStore` 增加本地入库 (名称以实现为准, 如 `ingest_file` / `acquire_local`):

- 计算内容 hash (与现有资源命名一致)
- 复制或硬链入 Resource 数据目录 (同盘优先硬链, 失败则复制)
- 写入 Resource 行; 返回内部 URL (`/api/resources/{hash}` 同类)

Metadata 的 `poster_urls` / `thumb_urls` / `trailer_urls` / `extrafanart_urls`
只存内部 URL 或经物化后的内部 URL, **不**把宿主机绝对路径暴露给前端长期持有.

短路路径上: 可跳过对已是本地文件的 HTTP `materialize_images`, 直接 ingest;
若仍走通用物化, 须识别本地 locator, 禁止对 `file://` 走 WebClient.

## 与 data-model 文档

更新 `docs/dev/data-model.md` / `task-system.md` / `crawlers.md` (或 content-routes):

- 明确: **禁止**静默"发现旁路 NFO 就改 DB"
- **允许**路由启用 `local` 时由刮削任务显式读入
- 重建落盘顺序仍是 DB → 派生文件

## 错误与可观测性

- 根路径非法 / 越出 safe_dirs: 配置校验失败, 不写入
- full_hit 成功: 任务摘要 `outcomes.local = ok`, `sites_queried` 可仅 `local`
- partial/miss: `local` 记 `no_usable_metadata` 或 ok+部分字段; 其它站照常
- 查找耗时: 大树根目录避免每次全树 glob; 按番号启发式 (直接子目录名匹配,
  必要时有限深度). 具体索引策略实现阶段选定, 须在计划中写明复杂度上限

## 测试要点

- 父目录 full_hit → 不调用其它 crawler mock
- 仅有 nfo 无图 → 不短路, aggregate 被调用
- 仅有图无 nfo → 不短路
- 父目录残缺 + 根目录 full_hit → 用根目录并短路
- 父目录优先于根目录 (父目录 full_hit 时不读根)
- NFO 字段映射与 ingest 后 URL 为内部资源
- `local_roots` 越权路径拒配
- by-number 无 path: 仅根查找

## 风险

- MDCx NFO 方言差异: 首版以本仓库 `write_nfo` 对称字段为主, 遇未知标签忽略
- 大库 `JAV_output` 查找性能: 必须限制遍历; 必要时后续加番号→路径缓存
- 短路仍可能触发 LLM 翻译: 与"省反爬配额"目标一致; 省 token 需另开配置
