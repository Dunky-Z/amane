# 影片重刮填空合并

## 背景

重刮成功时 `ScrapeHandler` 将本次聚合结果整字段写入 `upsert_metadata`.
某站反爬失败时该站不再进入本次 `extrafanart_urls` / `raw`, 已有剧照引用与站点快照会被冲掉.
演员刮削已有 `merge_actor_rows_fill_empty`; 影片侧缺对等保护.

## 已确认取舍

| 项 | 选择 |
| -- | ---- |
| 合并时机 | 物化之后、`upsert_metadata` 之前 |
| 无已有行 | 与今日相同, 直接写入 |
| 有已有行 (含强制刮削) | 相对 DB fill-empty / 并集 |
| 强制刮削 | 仅忽略 `raw` 缓存并强制出站; **不**整份覆盖已有非空字段 |
| 库路径旁路图 | 本阶段不改 ORGANIZE |
| 更高清主图 | 另阶段; 本设计不含 |

## 目标

- 已有非空标量 / 非空列表不被空的新结果覆盖
- `poster` / `thumb` / `trailer` URL 保序并集; 新列表空时保留旧列表
- `extrafanart_urls` / `raw` 按站点 key 并集: 成功站更新, 失败或未返回站保留旧值
- `scores` / `external_ids` / `source_urls` / `field_sources` 以已有为先补缺
- `local` 全量短路写库同样合并, 避免残缺本地 NFO 冲掉更完整的 DB

## 非目标

- 独立 `merge_policy` 开关
- 按分辨率替换主图 (后续)
- 自动 ORGANIZE / 清理库路径旧 sidecar
- 与手动 `merge_metadata` API (`compute_merge_updates`) 合并为一套

## 合并规则

纯函数 `merge_film_rows_fill_empty` (建议模块 `aggregate/film_merge.py`):

输入: 已有 `Metadata` + 本次 `AggregatedMetadata` + 物化后的三类 URL 列表 + 本次 `raw` / `field_sources`.

| 字段类 | 规则 |
| ------ | ---- |
| 标量 title / plot / studio / … | 已有非空保留; 空则用新值 |
| actors / tags / directors | 已有非空列表保留; 空则用新值 (不做并集) |
| poster / thumb / trailer URLs | 旧非空且新空 → 旧; 旧空 → 新; 双方非空 → 旧序在前, 追加仅新出现的 URL |
| extrafanart_urls | 新结果某站非空列表则更新该站; 某站本次缺失 → 保留旧站 |
| scores / external_ids / source_urls | setdefault 并集 |
| raw | 本次成功站覆盖对应 key; 其余保留旧 raw |
| field_sources | 已有 key 保留; 仅补新定值 |

空判定: 标量为 `None` 或 `""`; 列表 / dict 以“无元素”为空.

## 挂载

`ScrapeHandler.handle`:

1. 始终按番号读取已有 Metadata (合并用); 仅当 `metadata ∈ use_cache` 时把其 `raw` 交给 `aggregate`
2. 聚合 / local 短路 → 翻译 → 物化
3. 若已有行: `merge_film_rows_fill_empty` → 用合并结果 `upsert_metadata`
4. 整任务无任何 `field_sources` 仍不写库 (与今日一致)

## 风险

- 错误旧标量占坑: 须用户手动清空字段后再刮; 文档写明强制刮削不再推倒重来
- 译文非空阻止源语言更新: 与填空语义一致; 重译须清空字段或后续单独动作
- ORGANIZE 仍按 Metadata 重写库路径: 合并后 URL 更不易变空

## 测试要点

- 已有 plot + 本次 plot 空 → 保留
- 已有空 plot + 本次有 plot → 补上
- 已有 dmm 剧照 + 本次无 dmm → 保留 dmm URL 与 raw
- URL 双方非空 → 保序并集
- 无已有行 → 直通本次结果
