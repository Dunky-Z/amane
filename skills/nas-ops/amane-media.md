# Amane / JAV 媒体参考

MDCx 已归档，继任为 **Amane**（`ghcr.io/sqzw-x/amane:latest`，本地 `amane-local:libgomp`）。

当前运行版本：**0.10.0**（2026-09-06 已 `docker pull` + rebuild 本地 libgomp 层；ghcr 无独立 `v0.10.0` tag，以 `latest` 为准）。

## 路径与挂载

宿主机：

```text
/root/sharedfolder/media/netflav/jav/
  JAV_output/     # 旧 MDCx 整理产物（体量大，同盘改名迁入）
  inbox/          # 待刮削工作队列（分批放入）
  library/        # Amane 整理输出（Jellyfin NETFLAV 读这里）
  .amane_trash/   # 黑名单/过小等丢弃

/root/sharedfolder/media/netflav/VR/
  DarkRoomVR/     # 既有 VR 片源
  JVR/
  VR-Censored/
  inbox/          # 待刮削工作队列
  library/        # Amane 整理输出（按番号，无制作商目录）
  .amane_trash/
```

容器内 Amane：
- `/root/sharedfolder/media/netflav` → `/media`
- 字幕库：`.../javadatabase/sub-202303/sub` → `/subtitle-cache`（插件 `nas.javsubs`）
- `jav` 库路径：`/media/jav`
- `vr` 库路径：`/media/VR`
- `AMANE_SAFE_DIRS=/media,/subtitle-cache`

Jellyfin：`/root/sharedfolder/media` → `/media`，库路径 `/media/netflav/jav/library`  
不在 Amane 挂载内：`netflav/failed/`、`netflav/american/` 等。

## 媒体库（id=1, name=`jav`）

| 项 | 值 |
| --- | --- |
| path | `/media/jav` |
| automation | 建议 **`none`**（勿用 `scrape` 监控整棵含 `JAV_output` 的树） |
| move_mode | `move` |
| link_mode | `strm` |
| min_file_size | `104857600`（100MB） |
| video_template | `library/{studio}/{number}/{number}[-CD{cd?}][-{sub?}].{ext}` |
| thumb/poster/fanart/nfo | `{link_dir}/{number}[-CD{cd?}][-{sub?}]-thumb.jpg` 等同理；nfo 为 `{number}….nfo` |
| extrafanart_template | `{link_dir}/extrafanart`（**目录**；文件名由代码写死为 `1.jpg`,`2.jpg`,…） |

用户明确要求：**剧照保持序号名**，不要 `{number}-extrafanart-N.jpg`。不要再往镜像打 extrafanart 改名补丁。

过滤规则从旧 `config.v2.json` 迁过：媒体后缀、字幕、最小体积、黑名单等；改库配置用 API/`PATCH /api/libraries/1`。

## 媒体库（id=2, name=`vr`）

与 `jav` 同套过滤/move/link/资源模板；差异如下。

| 项 | 值 |
| --- | --- |
| path | `/media/VR` |
| automation | **`none`**（勿对整棵 VR 树开 `scrape`） |
| video_template | `library/{number}/{number}[-CD{cd?}][-{sub?}].{ext}` |
| 整理目标 | 按番号落盘，**无** `{studio}` 层级 |

创建时已 `scan=false`，避免一次扫完整 `DarkRoomVR`/`JVR`/`VR-Censored`（合计约 2TB+）锁死 SQLite。现改为统一挂载 `netflav:/media`，再用库路径 `/media/jav` 与 `/media/VR` 做隔离；需要入库时对目标子路径 `refresh` 且 `scan: ["add"]`，或分批搬入各自 `inbox/` 再刮削/整理。

## 字幕插件 `nas.javsubs`

影片刮削时自动补中文字幕（不改标题/简介）。源码在 `/root/sharedfolder/develop/amane-javsubs-plugin`，安装目录 `{data}/plugins/sources/nas.javsubs/`。

- 顺序：视频旁已有 sidecar → 本地字幕库 `/subtitle-cache` → SubtitleCat + 迅雷
- 自动选匹配度最高的中文字幕，优先 `srt` 再 `ass`
- 远程成功后抖动等待 5–10 秒；插件不自重试
- 写入视频同目录 `{stem}.zh.{ext}`，并缓存 `{NUMBER}/{NUMBER}.zh.{ext}`
- 按番号刮削没有 `file_path` 时，会在 `/media/library` 与 `/media/inbox` 按番号找视频再写 sidecar
- 使用：单部在详情页刮削；批量按 `media_id` 限量入队。必须把 `nas.javsubs` 放在内容路由**开头**，否则聚合器短路后不会调用（插件仍显示已启用，但 `sites_queried` 没有它，日志也没有字幕请求）

## 刮削 / 翻译 / 图源偏好（经验）

- LLM 凭据在 `/root/sharedfolder/appdata/amane/config.toml` 的 `[llm]` 与 `[agent]`（可 `PATCH /api/config` 热更新）。
- **当前（2026-09-09）**：ChatAnywhere，`base_url=https://api.chatanywhere.tech/v1`，模型 `gpt-5-mini`；llm / agent 均走 chat。
- FastAIToken（`fastaitoken.com`）曾用，服务器不可用时切回 ChatAnywhere。
- 智谱 GLM 会拦截成人向翻译（contentFilter 1301），不适合本库刮削译文。
- `field_priority.plot` 偏好 dmm；`field_blacklist.plot` 含 r18dev（评论常空）。
- 封面：偏好 dmm/mgstage；javbus 的 poster/thumb 易 403，已黑名单。
- r18 Postgres：周更可从 `https://r18.dev/dumps/latest` 导入；DSN 在 Amane 配置里。
- r18 导入失败常见原因（2026-09-09）：对 `r18.dev` 的 HEAD 被重置后，回退为整包 GET，`network.timeout=180` 下约 271MB dump 下不完（报"下载 dump 失败"）。可经代理把 Wasabi 直链下到 `/data/r18_dump/`，再在容器内本地 gunzip + psql 导入并更新 `/data/r18_import.json`。
- ChatAnywhere 免费额度约 **100 次/天**；整库刮削极易 429，翻译失败后标题保留日文原文，任务仍可能 `done`。

### LLM 提供商切换备忘

热切换示例（改完立刻生效，无需重启容器）：

```bash
TOKEN=$(docker exec amane cat /data/token)
curl -sS -X PATCH -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"llm":{"api_key":"<KEY>","base_url":"<BASE>","model":"<MODEL>"},"agent":{"api_type":"<chat|response>","api_key":"<KEY>","base_url":"<BASE>","model":"<MODEL>","thinking":"medium"}}' \
  http://127.0.0.1:8800/api/config
```

#### ChatAnywhere（当前）

| 项 | 值 |
| --- | --- |
| base_url | `https://api.chatanywhere.tech/v1` |
| model | `gpt-5-mini` |
| api_key | `sk-L70RihER8k0WsqLYa4XZVG8DUpo9QNp6i9C0Lc8t7tGVP0Mf` |
| agent.api_type | `chat` |

#### FastAIToken（可切回）

| 项 | 值 |
| --- | --- |
| base_url | `https://www.fastaitoken.com/v1` |
| model | `gpt-5.4-mini`（API key 分组须包含该模型） |
| api_key | `sk-843315c8ce957902e4128c168140c86dbd7ceb880aa83e91fadb8e9b367b8f35` |
| llm | chat completions |
| agent.api_type | `response` |
| agent.thinking | `medium` |

#### 智谱（不推荐本库翻译）

| 项 | 值 |
| --- | --- |
| base_url | `https://open.bigmodel.cn/api/paas/v4` |
| model | `glm-4.7` |
| api_key | `c0f04ecbfd6144078d2885ea68f53c64.0fHeGfaS9VAivLnc` |
| 备注 | 成人内容易 1301 拦截 |

切回时把对应字段同时写回 `[llm]` 与 `[agent]`。

## 推荐工作流

### 分批从 JAV_output → inbox → 刮削

1. 按路径排序取下一批视频（例如 100），**只搬视频**（及同 stem 字幕）到 `inbox/<stem>/`，旧 MDCx 图/nfo 可留在原目录。
2. 需要更新索引时：`refresh` 用 `scan: ["add"]`（或全树 add），**不要**对 `inbox` 单独 `add+remove`。
3. 仅对 inbox 的 `media_id` 提交 `scrape`（可用 `use_cache: ["metadata","trans"]` 省翻译额度）。
4. 刮削后再 `organize`；整理后 inbox 空目录可脚本删除。

### 任务 API 要点

- `POST /api/tasks`：`refresh` / `scrape` / `organize` / `cleanup` …
- `content_type` 必须小写枚举（`censored` / `uncensored` / `amateur` …），大写会导致校验落到错误 schema
- `use_cache: []` = 强制全刷（含重新抓 plot/简介并翻译）；`["metadata"]` 复用 DB 快照时，若历史 plot 为空则简介仍会是空
- `POST /api/metadata/batch/scrape`：按 metadata id 批量补刮；大批量插入易与 worker 抢 SQLite，宜先 `worker/pause` 再入队
- `GET /api/tasks/schema`：看 payload
- `POST /api/tasks/batch`：`cancel` / `delete` / `retry`（status/type 用小写：`queued`/`scrape`）
- `GET|POST /api/tasks/worker`：`pause` / `resume`；`paused=false` 仍可能因 worker 协程已死而不跑——查日志与重启容器
- Token：容器内 `/data/token`

### 已知故障与修复

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 任务一直 queued、无 running | SQLite `database is locked`；Watcher 在大树搬迁时刷爆写；worker 循环可能挂掉 | `automation=none`；重启 `amane`；取消无效 queued；再限量提交 |
| 局部 refresh 后 scraped 变 0 | `scan` 含 `remove` 且 `path` 仅为子目录 | 立刻 cancel；用全树或正确范围 `add` 重建；library 可能需重刮/重整理 |
| 智能体起不来 | 配了 `all_proxy`/socks5 | 只留 http(s)_proxy；`NO_PROXY` 含 localhost 与 postgres 服务名 |
| healthcheck 误杀 | 探活走代理 | health 用容器内 `127.0.0.1:8000`；`NO_PROXY` 含 localhost |
| waifu2x 缺库 | 官方镜像无 libgomp/vulkan | 用 `docker-compose/amane/Dockerfile` 构建 `amane-local:libgomp` |
| 同时存在 `thumb.jpg` 与 `番号-thumb.jpg` | 改模板后旧文件未删 | organize 后可清无番号残留；剧照勿留 `*-extrafanart-*.jpg` 补丁产物 |

## Clash / 日本节点（刮削）

Clash 单元：`clash.service`，配置 `/etc/clash/glados.yaml`（`-d /etc/clash/`）。

备份（改前已留）：

```text
/etc/clash/glados.yaml.bak.20260907-004814
/etc/clash/glados.yaml.bak
```

恢复示例：

```bash
sudo cp -a /etc/clash/glados.yaml.bak.20260907-004814 /etc/clash/glados.yaml
sudo /usr/local/bin/clash -t -f /etc/clash/glados.yaml -d /etc/clash/
sudo systemctl restart clash.service
```

刮削专用策略组：`JP Scrape`（`select`，默认 **`JP-Dedicated-B1-2`**）。

重要：GLaDOS 名称含 JP 不等于日本出口。实测（Cloudflare `cdn-cgi/trace`）：

| 节点 | 实际 loc |
| --- | --- |
| JP-Dedicated-B1-2 | **JP / NRT**（可用） |
| JP-Dedicated-B1-1/3/4 | US / LAX（会触发 DMM/Prestige 地域墙） |

勿再用 `url-test` 自动选这组：延迟更低的往往是美西节点。改配置后用 `curl -x http://127.0.0.1:7890 https://www.cloudflare.com/cdn-cgi/trace` 并先把 Default Proxy 切到待测节点验证 `loc=JP`。  
Amane 相关域名以高优先级 `DOMAIN-SUFFIX` 指向该组（优先于原 Streaming 等规则），含 dmm / mgstage / prestige / javlibrary / javdb / javbus / r18 等。

### 刮削限速（方案 A，2026-09-07）

| 项 | 值 |
| --- | --- |
| `network.concurrency` | `1` |
| `network.default_rate_limit` | `0.5` |
| `network.max_retries` | `3` |
| 敏感站 `rate_limit` | dmm/mgstage/javlibrary/prestige/javdb/javbus = `0.3` |
| 其余站 `rate_limit` | `0.5` |

说明：旧配置里 dmm/javlibrary 曾匹配到 `Streaming`（当时出口为 Express，非日本），易出现地域受限；现已强制 `JP Scrape`。

## Jellyfin

- 配置：`/root/sharedfolder/appdata/jellyfin/config/`
- NETFLAV：指向 `…/jav/library`（`library.mblink` / `options.xml`）
- 远程 API 扫库曾 401：可在 UI 手动扫描 NETFLAV

## 二次开发（fork）

源码：`/root/sharedfolder/develop/amane`（`git@github.com:Dunky-Z/amane.git`）。

### 与上游同步（不向上游提 PR）

| Remote | 仓库 | 用途 |
| --- | --- | --- |
| `origin` | `Dunky-Z/amane` | 本 fork；日常 push |
| `upstream` | `sqzw-x/amane` | 只 fetch；push URL 设为 `DISABLE_PUSH` |

长期个人 fork 用 **merge** 吃上游，不要反复 `rebase` 到 `upstream/main`（本地提交会越积越多，rebase 成本高且要 force push）。

日常步骤：

```bash
cd /root/sharedfolder/develop/amane
git checkout main
git fetch upstream
git merge upstream/main
# 解冲突 → 相关测试 → 完成 merge commit
git push origin main
```

冲突常见于双方都改过的文件，以及 `web/package.json` / 生成的 `web/src/client/*`。
本机需保留 `@rolldown/binding-linux-x64-gnu` 时，与上游依赖升级一并手工合并；
`openapi.json` 合好后可清空再生成 client：

```bash
rm -rf web/src/client && mkdir -p web/src/client && (cd web && pnpm gen-client)
```

若双方都动 Alembic migration：合完后 `uv run alembic heads` 必须只剩一个 head；
多 head 时按 amane-pr 约定改本侧最早 revision 的 `down_revision` 串成单链，禁止手写新 revision ID。

冲突预期较大时，可先在旁路分支合入再并回 `main`：

```bash
git fetch upstream
git checkout -b sync/upstream-$(date +%Y%m%d)
git merge upstream/main
# 解冲突、跑测试
git checkout main
git merge sync/upstream-YYYYMMDD
git push origin main
```

一次性准备（若尚未配置）：

```bash
git remote add upstream git@github.com:sqzw-x/amane.git
git remote set-url --push upstream DISABLE_PUSH
```

与生产隔离：

| 项 | 生产 | 二次开发 |
| --- | --- | --- |
| 进程 | Docker `amane` | 本机 `uvicorn` + Vite |
| 数据目录 | `/root/sharedfolder/appdata/amane` | `/root/sharedfolder/appdata/amane-dev` |
| Web | `http://192.168.31.220:8800` | `http://192.168.31.220:5173`（代理 API） |
| API | `:8800` | `:8000` |
| Token | `docker exec amane cat /data/token` | `cat …/amane-dev/token` |

本地 `.env`（已 gitignore，勿提交）要点：

```text
AMANE_DATA_DIR=/root/sharedfolder/appdata/amane-dev
AMANE_SAFE_DIRS=ALLOW_ALL
```

注意：不要把 `AMANE_HOST` / `AMANE_PORT` 写进 `.env`，`ColdSettings` 会把未知 `AMANE_*` 当成非法字段拒绝启动。监听地址用 uvicorn / Just 参数传入。

依赖与启动：

```bash
export PATH="/root/app/nodejs/bin:$HOME/.local/bin:$PATH"
export http_proxy=http://192.168.31.220:7890 https_proxy=http://192.168.31.220:7890
cd /root/sharedfolder/develop/amane
just sync          # 或 just setup
# 一键：scripts/dev-nas.sh
# 或分别：
uv run uvicorn amane.api.app:create_app --factory --reload --host 0.0.0.0 --port 8000
(cd web && pnpm exec vite --host 0.0.0.0 --port 5173)
```

本机 Debian 10 / 旧 glibc 下，pnpm 可能漏装 rolldown optional binding；`web/package.json` 已显式依赖 `@rolldown/binding-linux-x64-gnu`。Vite 可能提示需 Node ≥20.19，当前 20.13 可跑但建议后续升级。

调试媒体库：`netflav-amane-debug`（id=1），路径 `/root/sharedfolder/media/netflav-amane-debug`。
库配置与生产 `jav` 对齐（模板 / 黑名单 / min_file_size / copy_resources 等），`automation=none`。
热配置从生产拷贝时注意宿主机差异：

| 项 | 生产容器 | 二次开发本机 |
| --- | --- | --- |
| `network.proxy` | `http://192.168.31.220:7890` | 同左 |
| `r18.dsn` | `…@amane-r18-postgres:5432/…` | `…@127.0.0.1:5433/…` |
| `nas.javsubs` `local_cache_dir` | `/subtitle-cache` | `…/media/netflav/javadatabase/sub-202303/sub` |
| `nas.javsubs` `video_search_roots` | `/media/library,/media/inbox` | 调试库下 `library,inbox,库根` |

不要默认挂生产 `netflav/jav` 整树，避免误整理。插件从生产树安装：

```bash
TOKEN=$(cat /root/sharedfolder/appdata/amane-dev/token)
curl -sS -X POST -H "Authorization: Bearer $TOKEN" \
  -F 'path=/root/sharedfolder/appdata/amane/plugins/sources/nas.javsubs' \
  http://127.0.0.1:8000/api/plugins
```


## Compose 片段备忘

- Amane 用户 `1000:1000`，`AMANE_SAFE_DIRS=/media,/subtitle-cache`，`AMANE_SUPERVISED=1`
- 挂载：`netflav→/media`、字幕库→`/subtitle-cache`
- 库路径：`jav=/media/jav`、`vr=/media/VR`
- 构建：`cd /root/sharedfolder/docker-compose && docker compose build amane && docker compose up -d amane`
- r18 库密码在主 compose 的 `amane-r18-postgres` 环境变量中；改密需同步 Amane 配置
