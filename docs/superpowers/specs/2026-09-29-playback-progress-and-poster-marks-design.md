# 播放进度持久化、复制入口与海报标记

## 背景

详情页播放浮层已可用. 触屏无右键, 复制时间戳缺少入口; 播放位置仅存活于当前会话;
海报墙无法快速切换「已播放」「收藏」并进入既有用户标签筛选.

## 目标

1. 播放器控制条提供复制时间戳 / 分享链接按钮; 触屏长按 2 倍速与桌面画面右键菜单保持不变.
2. 按 `metadata_id` 在服务端持久化播放进度; 打开可寻址流时自动 seek 到上次位置; URL `?t=` 优先于已存进度; 接近片尾不清除进度.
3. 全部 `PosterCard` 海报墙提供「已播放」「收藏」可点开关; 开关通过固定名称的用户标签实现, 与播放进度互不读写.

## 非目标

- 独立浏览器窗口播放
- 按来源 / 码流分别存进度
- 接近片尾自动清除进度或自动打「已播放」
- 新增独立 `watched` / `favorite` 列或非用户标签的系统标志
- 专用「已播放 / 收藏」筛选控件 (沿用既有用户标签筛选)
- 本期提供清除进度的 DELETE API 或「从头播放」专用按钮
- 多用户分账号进度 (实例级单进度即可)

## 架构

```
控制条复制按钮 ──┐
画面右键菜单   ──┼→ 同一套复制动作 + copyText
                 └→ 时间戳 / 带 ?t= 的分享 URL

<video> timeupdate / pause / 关闭浮层
  → PUT /api/playback/progress/{metadata_id}
打开浮层且可 seek、无 ?t=
  → GET /api/playback/progress/{metadata_id} → seekRequest

PosterCard 开关
  → 确保用户标签「已播放」|「收藏」存在 (POST /api/facets/user_tag)
  → attach|detach (POST /api/metadata/batch/user-tags)
列表页
  → list metadata 批量附带当页 user_tags → 开关高亮
```

三块能力边界独立: 复制仅前端; 进度仅 playback 表与 API; 标记复用 facets / metadata 用户标签.

## 复制入口

- 控制条增加时钟类 `ActionIcon` / `Menu`: 两项为复制当前时钟文案、复制带 `?t=` 的分享 URL.
- 不可寻址时禁用; 复制走 `lib/copy-text.ts`.
- 桌面右键菜单保留; 触屏长按加速保留, 不改为弹出菜单.

## 播放进度

### 数据

表 `playback_progress`:

| 列 | 说明 |
| -- | ---- |
| `metadata_id` | PK, FK → `metadata.id`, `ON DELETE CASCADE` |
| `position_seconds` | float, 当前播放位置 |
| `updated_at` | 最后写入时间 |

每影片一行; 不区分 source / stream.

### API

挂在既有 playback 路由:

- `GET /api/playback/progress/{metadata_id}` → `{ "position_seconds": number | null }`. 无行时 `position_seconds` 为 `null`, HTTP 200.
- `PUT /api/playback/progress/{metadata_id}` body `{ "position_seconds": number }` (≥ 0) → upsert, 返回同上形状.

不实现 DELETE. 删 metadata 时由外键级联删除进度行.

### 前端行为

- 节流写入: 播放中约每 5–10s 一次; `pause`、`pagehide`、关闭播放浮层时再写一次.
- 打开浮层、流可寻址且已可 seek: 若存在 `position_seconds > 0`, 注入既有 `seekRequest` 管线自动跳转.
- 进入详情带 `?t=` 时: 只按查询参数 seek, 忽略已存进度 (不覆盖该次打开的跳转目标; 播放后仍按节流更新进度).
- 不因「接近片尾」清除或跳过恢复.

## 海报「已播放 / 收藏」

### 标签约定

- 写入数据库的标签名固定为中文: `已播放`、`收藏`.
- 按钮可见文案走 i18n; 匹配与创建一律按上述固定名.

### UI

- `PosterCard` 海报角放置两个可点图标 (已看 / 收藏), 已挂标签时高亮.
- 点击 `stopPropagation` / `preventDefault`, 不进入详情.
- 乐观更新; 失败回滚并通知.
- 所有使用 `PosterCard` 的墙 (片库、分类浏览、演员作品等) 均显示.

### 数据与写路径

- 列表接口对当页 `metadata_id` 批量填充 `MetadataResponse.user_tags` (id + name 即可), 供开关判态. 详情既有 `user_tags` 不变.
- 切换: 若对应标签尚不存在, 先 `POST /api/facets/user_tag` 取回或新建; 再 `POST /api/metadata/batch/user-tags` (`attach` / `detach`).
- 不引入新标志位字段; 筛选继续使用 `user_tag_id` 查询参数.

## 错误处理

- 进度 GET/PUT 失败: 不阻断播放; PUT 失败可静默或低频提示, 避免刷屏.
- 标签切换失败: 回滚该卡片乐观态并 toast.
- 未知 `metadata_id` 的进度 PUT: 404; GET 对未知 id 同样 404 (与其它 metadata 资源一致). 存在的影片无进度行则 GET 200 且 `position_seconds: null`.

## 测试

- 进度: upsert、按 metadata 级联删除、GET 无行返回 null、非法负数 422.
- 列表附带 `user_tags` 的仓储 / API 层抽样 (有标签 / 无标签页).
- 前端: 复制工具已有覆盖则不重复; 进度恢复与 `?t=` 优先可用组件级或轻量集成测; 海报开关以表测试覆盖「按名称判定高亮 + attach/detach 调用」优先于全 E2E.

## 文档

实现后按 `docs/dev/writing.md` 与 amane-docs 规范, 在 `docs/dev/frontend.md` / `docs/dev/api.md` (或既有播放相关段) 各补一句跨模块契约: 进度键、列表带 `user_tags`、固定标签名与进度无关. 禁止堆砌字段表与示例.
