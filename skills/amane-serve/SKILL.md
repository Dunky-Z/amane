---
name: amane-serve
description: >-
  Starts Amane local API + Vite via `just dev`, or the built SPA served by the
  backend for mobile / LAN access. Use when the user asks to just dev,
  启动开发服务器, 起前端, start the dev servers, 手机端检查, or 局域网访问.
---

# 开发服务器

`just dev` 先 `generate` 再并行起 API 与 Vite. 后台启动. 禁止等待 Vite 的 `Local:` / `ready in` — just 并行输出经常没有这两行.

## 监听地址

开发服务默认仅本机可访问:

| 进程 | 绑定 | 配置 |
|------|------|------|
| API | `AMANE_HOST` (默认 `127.0.0.1`) | Justfile `_dev-uvicorn` |
| Vite | `127.0.0.1:8899` | `web/vite.config.ts`, 端口占用即失败 |

Vite 将 `/api` 代理到本机 uvicorn (`127.0.0.1:${AMANE_PORT:-8000}`), 浏览器始终经同源请求.

局域网验证使用下述构建与后端托管流程.

就绪以 HTTP 为准, 使用实际监听地址探测.

| 进程 | 就绪 |
|------|------|
| API | `GET http://localhost:${AMANE_PORT:-8000}/api/health` 返回 200; 日志 `amane service ready` 亦可 |
| Web | `GET http://localhost:8899/` 返回 200 |

已在监听则禁止再启动一份. Web 固定使用 8899, 禁止改用自动顺延的端口.

## 地址的输出

**只输出 Web 地址**, 且**只以纯文本给出**, 不放进代码块 —— 代码块内的 URL 不会渲染成可点击链接, 纯文本才会.

就绪后输出一行 `Web: http://localhost:8899` (行内代码只是本文件的排版, 实际回复里是裸文本).

API 地址只在探测就绪时使用, 不写给用户: 用户经浏览器访问前端, 请求由 Vite 代理到 `/api`.

要用户打开某个页面时, 给出带路径的完整地址, 同样纯文本, 例如 `Web: http://localhost:8899/meta/1393`.

## 手机 APP 访问

当涉及到移动端 APP 内验证时, **禁止用 `just dev`** 启动

这是因为 APP 使用安卓内置 webview, 版本一般较低, 需 `@vitejs/plugin-legacy` 的语法降级与 polyfill, 而二者只在 `vite build` 时生效

一律走构建 + 后端托管:

```bash
just build                          # generate + 前端构建 (降级产物在此生成)
AMANE_HOST=0.0.0.0 just start       # 后端托管 web/dist, 监听 0.0.0.0:8000
```

端口只有 8000: 前后端同源, `/api` 由后端自身处理. 就绪探测仍走 `localhost`, 对用户输出的是局域网 IP 形式:

```
Web: http://<en0/en1 的 IP>:8000
```

IP 取 `ipconfig getifaddr en1` (或 en0, 取有值的那个).

`dist` 不随源码热更新: 改动前端后必须重新 `just build`.

## 让用户验证时

凡请用户手测、复验、确认现象, 回复里必须再打印一次 Web 地址与要打开的具体页面, 不允许只写「刷新页面」「再试一次」. 是否已在运行都要打印.
