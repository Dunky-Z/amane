---
name: nas-ops
description: >-
  Operate this personal NAS (host LAN IP 192.168.31.220): Docker Compose
  fleets under /root/sharedfolder/docker-compose, appdata/media layout,
  Amane JAV scraping (MDCx successor), Jellyfin libraries, proxy/network
  quirks, batch media workflows, and syncing the Dunky-Z/amane fork from
  upstream sqzw-x/amane (merge, no upstream PR). Use when the user mentions
  NAS, 这台 服务器, docker-compose, sharedfolder, amane, MDCx, Jellyfin,
  netflav, JAV_output, inbox/library, 刮削, 整理, 番号命名, r18.dev postgres,
  qbittorrent, syncthing, clash/yacd, metatube, 同步上游, sync upstream,
  fork merge, or any service deployed on this machine. Prefer acting with
  local docker/curl/fs tools over asking the user to restate paths or history.
---

# NAS Ops

本机是个人 NAS（局域网 `192.168.31.220`）。运维默认在本机直接执行命令，不要让用户重复交代目录、挂载、Amane/Jellyfin 约定。

详细媒体/Amane 背景见 [amane-media.md](amane-media.md)。

## 目录总图

| 路径 | 用途 |
| --- | --- |
| `/root/sharedfolder/docker-compose/docker-compose.yml` | 主编排（多数核心服务） |
| `/root/sharedfolder/docker-compose/<svc>/` | 单服务补充目录（如 `amane/`、`fitsync/`、`nginx/`） |
| `/root/sharedfolder/appdata/<svc>/` | 容器持久化配置/数据 |
| `/root/sharedfolder/media/` | 媒体根；Jellyfin 挂载整棵 `/media` |
| `/root/sharedfolder/media/netflav/jav/` | Amane JAV 媒体根（容器内 `/media/jav`） |
| `/root/sharedfolder/media/netflav/VR/` | Amane VR 媒体根（容器内 `/media/VR`） |
| `/root/sharedfolder/develop/amane/` | fork 二次开发源码（`origin=Dunky-Z/amane`，`upstream=sqzw-x/amane` 只 fetch） |
| `/root/sharedfolder/appdata/amane-dev/` | 二次开发独立数据目录（勿与生产 `appdata/amane` 混用） |

主 compose 之外，还有不少服务在独立子目录用自己的 compose 编排；改服务前先确认实际 compose 文件位置。

## 常用主机约定

- 时区：`Asia/Shanghai`
- 常见 UID/GID：`1000:1000`（Jellyfin / Amane 等）
- HTTP 代理：`http://192.168.31.220:7890`
- SOCKS：`socks5://192.168.31.220:7891`（**不要**给 Amane 配 `all_proxy`/socks，缺 `socksio` 会导致智能体起不来）
- Git：进入**实际仓库目录**再执行 git；文档/代码有改动须本地 commit（一般不 push）
- 回复语言：中文；文档/代码勿加 emoji

## 主 compose 中与媒体相关的服务

| 服务 | 要点 |
| --- | --- |
| `jellyfin` | `network_mode: host`；挂载 `/root/sharedfolder/media:/media`；NETFLAV 库指向 `/media/netflav/jav/library` |
| `amane` | 生产容器；镜像 `amane-local:latest`，由 `/root/sharedfolder/develop/amane` 当前源码构建；Web `http://192.168.31.220:8800`（`8800→8000`）；数据 `/root/sharedfolder/appdata/amane`；统一挂载 `.../netflav:/media`；字幕库挂 `.../javadatabase/sub-202303/sub:/subtitle-cache`；插件 `nas.javsubs`；库 `jav`(id=1, path=`/media/jav`) / `vr`(id=2, path=`/media/VR`) |
| `amane` 二次开发 | 源码 `/root/sharedfolder/develop/amane`；数据 `appdata/amane-dev`；API `:8000`；Vite `:8899`；与上游同步见 [amane-media.md](amane-media.md)「与上游同步」 |
| `amane-r18-postgres` | r18.dev 离线库；宿主机端口 **5433**；`NO_PROXY` 须含 `amane-r18-postgres` |
| `metatube` + `metatube-postgres` | 元数据相关，与 Amane 并存 |
| `qbittorrent` / `syncthing` | 下载与同步 |

生产 Amane 镜像一律从当前 fork 源码构建，不在 compose 目录叠 libgomp/vulkan 等临时层。缺依赖或超分问题须在 `develop/amane` 的 Dockerfile / 源码中修复后再构建。构建须用国内包源 + `192.168.31.220:7890` 代理（见 [amane-media.md](amane-media.md)「构建加速」）。

## 运维操作原则

1. **先定位 compose**：主文件 vs 子目录独立编排，再 `docker compose`。
2. **改挂载/环境后**：在对应目录 `up -d`；涉及镜像依赖则 `build` 再 recreate。
3. **Amane API**：`TOKEN=$(docker exec amane cat /data/token)`，请求 `http://127.0.0.1:8800`（或局域网 8800），头 `Authorization: Bearer $TOKEN`。
4. **合入上游冲突**：非特性冲突自行处理；影响功能/特性的冲突先分别说明双方行为，等用户决定后再继续。细则见 [amane-media.md](amane-media.md)「冲突处理」。
5. **任务队列卡住**：先查 `GET /api/tasks/worker`、`docker logs amane` 是否出现 `database is locked`；Watcher + 全库 `automation=scrape` 大目录搬迁极易锁死 SQLite。
6. **不要对子目录 refresh 开 `scan: ["add","remove"]`**：`remove` 按「本次扫描未见」删全库索引，会误删 `library/` / `JAV_output/` 记录。子目录刷新只用 `scan: ["add"]`，或对 `/media` 全树谨慎操作。
7. **批量刮削**：`refresh` 的 `path` 只限制扫描范围；勾选刮削范围 `pending` 时只扇出待处理（失败已标 `failed` 的不会再进）。要限量时：只把目标片放进 `inbox/`，再按 `media_id` 提交 scrape；或取消其它 pending 的刮削任务。重试失败片请勾选 `failed`。
8. **整理 = TRASH + ORGANIZE**（上游 0.12）：UI 整理按钮会先回收再落盘；API 若只提 ORGANIZE，不会移动黑名单/过小文件。
9. **翻译 LLM 额度有限**：inbox 分批（例如每次约几十～100），不要一次刮完整 `JAV_output`。当前 LLM 提供商与 ChatAnywhere 回切参数见 [amane-media.md](amane-media.md)「LLM 提供商切换备忘」。
10. **空目录**：Amane **无**刮削后自动删空目录选项；inbox 残留空目录需手动/`find … -empty -delete`（注意勿误删仍有用的父目录）。

## 快速检查

```bash
docker ps --filter name=amane --format '{{.Names}} {{.Status}}'
TOKEN=$(docker exec amane cat /data/token)
curl -sS -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8800/api/tasks/worker
curl -sS -H "Authorization: Bearer $TOKEN" 'http://127.0.0.1:8800/api/tasks?status=running&limit=10'
curl -sS -H "Authorization: Bearer $TOKEN" 'http://127.0.0.1:8800/api/libraries/1'
```

## 提交约定

- compose / Dockerfile / 本 skill 等有修改：进入对应 git 仓库目录后 commit，不 push（除非用户明确要求）。
- 勿把密钥、token、`.env` 机密写进 skill 正文的可复制示例以外的新位置；已有 compose 密码视作环境事实，勿扩散到无关仓库。
