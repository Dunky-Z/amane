# Git Flow 规则按项目拆分与提交说明改写

## 背景

共享 `.agent/rules/31-git-flow.mdc` 当前为 `alwaysApply: true`, 且内容面向
firmware (FI 票号、Fork/MR、`type(scope) [TICKET]:` 英文 subject).
该规则进入 amane 工作区后, 提交说明被写成 firmware 形态, 与本仓库历史不一致.

## 目标

1. 将既有 git flow 限定为 **仅 firmware 固件开发** 使用.
2. 新建 **amane** git flow, 提交说明对齐本仓库约四天前的历史风格.
3. 仅改写相对 `origin/main` 超前的 **11** 条作者为 Dominic 的提交说明;
   不改动树内容, 不改写他人提交.

## 非目标

- 改写 `origin/main` 及更早历史
- 自动 force push
- 统一 fitsync 等其它项目的提交规范 (本变更不触及其规则文件)

## 规则布局

真相源: `.vscode/.agent/rules/` (经 agent-dots 软链到各 agent 家目录).

| 文件 | Cursor / 渲染 | 内容 |
| ---- | ------------- | ---- |
| `31-firmware-git-flow.mdc` (由 `31-git-flow.mdc` 重命名) | `alwaysApply: false`, `projects: [firmware]` | 保留 FI、Fork/MR、`type(scope) [TICKET]:` |
| `32-amane-git-flow.mdc` (新建) | `alwaysApply: true`, `projects: [amane]` | 见下节 |

`agent-dots` 用户配置:

- `projects.amane.extra_rules` 含 `32-amane-git-flow`
- 若存在 `projects.firmware`, `extra_rules` 含 `31-firmware-git-flow`

说明: 当前本机 `source_root` 挂在 amane 下, 故 amane 规则使用 `alwaysApply: true`
以进入 Cursor. firmware 规则关闭 alwaysApply, 避免污染 amane.
若日后同一 source_root 同时服务多仓库, 再将 amane 规则改为 false, 仅靠各仓渲染.

## Amane 提交说明规范

格式:

```text
type: 中文说明

可选中文正文
```

约束:

- **必须** 使用 conventional `type` (`feat` / `fix` / `docs` / `chore` / `refactor` /
  `test` / `perf` / `ci` / `build` / `revert` / `release` / `i18n` 等与仓库历史一致者)
- **禁止** 写 `FI-xxxx` 或其它 firmware 票号括号
- **一般不写** `(scope)`; 需要区分模块时把对象写进中文说明
- subject 与 body **全中文** (专有名词、路径、命令、API 可保留英文)
- body 可选; 有 body 时说明目的与行为差异, 用语遵守 `docs/dev/writing.md`
- **禁止** 未经明确指示执行 `git push` / force push

示例 (对齐历史):

```text
fix: 整理后路径离开本库时删除索引, 避免 UNIQUE 冲突

跨库整理时本库不再把 path 写成库外路径.
```

## 提交说明改写对照

范围: `origin/main..HEAD` 共 11 条, 仅改 message.

| 原 subject | 新 subject | 新 body |
| ---------- | ---------- | ------- |
| `chore(web) [FI-0000]: pin rolldown linux binding for NAS local dev` | `chore: 为 NAS 本地开发固定 rolldown linux 绑定` | 显式依赖 `@rolldown/binding-linux-x64-gnu`, 避免 pnpm optional 缺失导致 Vite 无法启动. 增加 `scripts/dev-nas.sh`, 以 appdata/amane-dev 运行 API 与 Vite. |
| `docs(agents) [FI-0000]: require docs/dev conventions in amane-dev skill` | `docs: 在 amane-dev skill 中要求遵守 docs/dev` | 开发须先阅读并遵守 docs/dev; 保留既有 just dev 就绪探测流程. |
| `docs(specs) [FI-0000]: add metadata field translate design` | `docs: 增加元数据字段即时翻译设计说明` | 影片编辑页字段即时翻译: 同步 LLM API 与 SchemaForm x-translate. |
| `docs(specs) [FI-0000]: clarify scalar translate keeps original text` | `docs: 澄清标量翻译在无需翻译时保留原文` | 无需翻译或返回 None 时标量响应回填原文, 避免清空表单字段. |
| `docs(plans) [FI-0000]: add metadata field translate plan` | `docs: 增加元数据字段即时翻译实现计划` | 任务拆分为 translator/runtime、API、SchemaForm 与验收. |
| `feat(llm) [FI-0000]: expose translator on AppRuntime for translate API` | `feat: 在 AppRuntime 上挂载 translator 供翻译 API 使用` | 扩展字段提示词; build_handlers 返回 HandlerBundle; bootstrap/rebuild 挂载 translator. |
| `feat(api) [FI-0000]: add POST /llm/translate for field translation` | `feat: 增加 POST /llm/translate 字段翻译接口` | 同步翻译不入队; PartialMetadata 八字段标记 x-translate; 更新 llm/api 文档. |
| `fix(organize) [FI-0000]: mark sidecar subtitles as chinese sub` | `fix: 整理时将匹配的外挂字幕标为中文字幕` | 找到匹配外挂字幕后, 在渲染目标路径前提升字幕相位, 使文件名写入 -C、启用字幕水印, 并在整理路径投影中保留 has_subtitle. |
| `feat(web) [FI-0000]: add metadata edit translate buttons` | `feat: 影片编辑增加元数据字段翻译按钮` | SchemaForm 支持 x-translate; 编辑页调用 /api/llm/translate 写回表单; 同步更新生成的 client. |
| `fix(dev) [FI-0000]: bind Vite and API for LAN remote access` | `fix: 绑定 Vite 与 API 以支持局域网访问` | Vite 使用 host:true; AMANE_HOST 默认 0.0.0.0; amane-dev skill 补充 NAS 局域网访问约定. |
| `docs(nas-ops) [FI-0000]: add NAS ops skill and debug config mirror notes` | `docs: 增加 NAS 运维 skill 与调试配置镜像说明` | 记录生产与二次开发路径约定; 说明调试库对齐 jav 以及热配置在宿主机上的差异. |

## 执行顺序

1. 在 `.vscode` 仓重命名并收窄 firmware 规则, 新建 amane 规则, 提交.
2. 更新本机 `~/.config/agent-dots/config.json` 的 `extra_rules`.
3. 在 amane 仓用非交互 rebase 仅改写上述 11 条 message (例如
   `GIT_SEQUENCE_EDITOR` + `git commit --amend` / `git filter-repo --message-callback`
   等价手段), 验证 `git log origin/main..HEAD` 与对照表一致.
4. 将本设计说明提交到 amane (若与规则变更分仓, 则分仓各自提交).

## 验收

- Cursor 在 amane 工作区不再 always 加载 firmware git flow
- amane git flow 以 alwaysApply 生效, 格式为 `type: 中文说明`
- `git log origin/main..HEAD` 11 条 subject/body 均为中文且无 `FI-0000`
- 这 11 条的 `git diff origin/main..HEAD` 树与改写前一致 (仅 hash/message 变)
