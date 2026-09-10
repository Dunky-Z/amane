# Git Flow 规则拆分 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** firmware git flow 仅作用于 firmware; amane 使用中文 `type: 说明`; 改写相对 origin/main 的 11 条 Dominic 提交说明.

**Architecture:** 共享规则在 `.vscode/.agent/rules/` 与 workspace
`/root/sharedfolder/.cursor/rules/` 同步收窄/新建; agent-dots 配置补充
extra_rules; amane 仓非交互 rebase 只改 message.

**Tech Stack:** Markdown `.mdc` frontmatter, agent-dots, git rebase

**Spec:** `docs/superpowers/specs/2026-09-10-git-flow-rules-split-design.md`

## File map

| 路径 | 职责 |
| ---- | ---- |
| `.vscode/.agent/rules/31-firmware-git-flow.mdc` | firmware 专用 (重命名自 31-git-flow) |
| `.vscode/.agent/rules/32-amane-git-flow.mdc` | amane 提交规范 |
| `/root/sharedfolder/.cursor/rules/` 同名文件 | workspace 级 always 规则同步 |
| `~/.config/agent-dots/config.json` | amane extra_rules |
| amane `origin/main..HEAD` 中 11 条 | 仅改 message |

### Task 1: 重命名并收窄 firmware 规则

- [ ] 将 `.vscode/.agent/rules/31-git-flow.mdc` 重命名为 `31-firmware-git-flow.mdc`
- [ ] frontmatter 改为 `alwaysApply: false`, `projects: [firmware]`, 标题标明 firmware
- [ ] 同步修改 `/root/sharedfolder/.cursor/rules/` 对应文件
- [ ] 在 `.vscode` 仓提交

### Task 2: 新建 amane git flow

- [ ] 新建 `32-amane-git-flow.mdc` (`alwaysApply: true`, `projects: [amane]`)
- [ ] 同步到 `/root/sharedfolder/.cursor/rules/`
- [ ] 在 `.vscode` 仓提交 (可与 Task 1 同提交若同仓一次完成)

### Task 3: 更新 agent-dots 配置

- [ ] `projects.amane.extra_rules` 加入 `32-amane-git-flow`

### Task 4: rebase 改写 11 条 message

- [ ] 按 spec 对照表非交互 rebase (设计说明那条已是中文, 保持不变)
- [ ] 验证 `git log origin/main..HEAD` 与 `git diff` 树不变

### Task 5: 验收

- [ ] firmware 规则不再 alwaysApply
- [ ] amane 规则 alwaysApply
- [ ] 11 条无 FI-0000, subject/body 中文
