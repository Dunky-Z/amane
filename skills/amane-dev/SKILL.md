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

就绪以 HTTP 为准. 探测与回显一律用 `localhost`, 禁止 `127.0.0.1` (进程不一定监听 IPv4).

| 进程 | 就绪 |
|------|------|
| API | `GET http://localhost:${AMANE_PORT:-8000}/api/health` 返回 200; 日志 `amane service ready` 亦可 |
| Web | `GET http://localhost:5173/` 返回 200 |

已在监听则禁止再启动一份. 就绪后回显:

```
API: http://localhost:8000
Web: http://localhost:5173
```

`AMANE_PORT` 或 Vite 占用顺延时, 按实际端口写.
