---
name: amane-dev
description: >-
  Amane 本地开发: 遵守 docs/dev 约定, 经 `just dev` 启动 API + Vite.
  Use when developing Amane, just dev, 启动开发服务器, 起前端,
  or start the dev servers.
---

# 开发约定

凡本 skill 覆盖的 Amane 开发工作, 必须先读并遵守 `docs/dev/` 下现行约定.
入口: `docs/dev/index.md`. 用语最高优先级: `docs/dev/writing.md`.

1. **优先读文档**, 再按需读源码. 跨文件边界、顺序、契约、取舍以 `docs/dev/` 为准.
2. 修改架构、API 或工作流后, **同步更新**对应 `docs/dev/` 文档.
3. 注释、文档、提交说明、对话用语遵守 `writing.md`.

按主题选读 `docs/dev/index.md` 中的链接 (architecture / frontend / testing / database 等).
禁止凭习惯绕过文档中的禁止事项.

# 开发服务器

`just dev` 先 `generate` 再并行起 API 与 Vite. 后台启动. 禁止等待 Vite 的 `Local:` / `ready in` — just 并行输出经常没有这两行.

## 监听地址 (NAS / 远程开发)

默认对局域网可访问, 禁止改回只绑 `127.0.0.1` 后仍让用户用 NAS IP 打开页面:

| 进程 | 绑定 | 配置 |
|------|------|------|
| API | `AMANE_HOST` (默认 `0.0.0.0`) | Justfile `_dev-uvicorn` |
| Vite | 全部网卡 (`host: true`) | `web/vite.config.ts` |

浏览器在 Windows 等远程机上应使用 **NAS 局域网 IP** (如 `http://192.168.x.x:8899/`), 不是仅在 NAS 本机有效的 `127.0.0.1`.
Vite 将 `/api` 代理到本机 uvicorn (`localhost:8000`), 前端经局域网打开时 API 请求仍走同源代理.

仅本机访问时可 `AMANE_HOST=127.0.0.1 just dev`; Vite 仍可经 `host: true` 被局域网访问.

## 就绪探测

就绪以 HTTP 为准. 探测一律用 `localhost`, 禁止 `127.0.0.1` (进程不一定监听 IPv4).

| 进程 | 就绪 |
|------|------|
| API | `GET http://localhost:${AMANE_PORT:-8000}/api/health` 返回 200; 日志 `amane service ready` 亦可 |
| Web | `GET http://localhost:8899/` 返回 200 |

已在监听则禁止再启动一份. `AMANE_PORT` 或 Vite 占用顺延时, 按实际端口写.

## 地址的输出

**只输出 Web 地址**, 且**只以纯文本给出**, 不放进代码块 —— 代码块内的 URL 不会渲染成可点击链接, 纯文本才会.

就绪后输出一行 Web: http://localhost:8899 (实际回复里是裸文本, 可点击).

若用户在远程机 (如 Windows 连 NAS) 打开页面, 额外给出局域网 URL, 例如 Web: http://192.168.31.220:8899.

API 地址只在探测就绪时使用, 不写给用户: 用户经浏览器访问前端, 请求由 Vite 代理到 `/api`.

要用户打开某个页面时, 给出带路径的完整地址, 同样纯文本, 例如 Web: http://localhost:8899/meta/1393.

## 让用户验证时

凡请用户手测、复验、确认现象, 回复里必须再打印一次 Web 地址与要打开的具体页面, 不允许只写「刷新页面」「再试一次」. 是否已在运行都要打印.
