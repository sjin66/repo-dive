# Agent 插件安装

`repo-dive` Agent 插件提供一个名为 `wiki` 的可移植 Agent Skill。它编排单独
安装的 `repo-dive` Python CLI；安装插件**不会**安装该可执行文件或模型
Provider。

## 前置条件

- 一个待生成文档的本地 Git 仓库。未经用户另行授权，Skill 不会克隆 URL。
- `PATH` 中有可用的 `repo-dive` 可执行文件。使用 `repo-dive --version` 和
  `repo-dive wiki --help` 验证。对于源码检出，`make setup` 会创建
  `.venv/bin/repo-dive`；请把该环境加入 `PATH`。
- 仅在使用备选的第三方 `skills` 安装器时需要 Node.js 和 npm。
- 支持 Agent Skills 的 Host 版本。打包约定变化较快；可复现环境应把插件
  Source 固定到 Release Tag 或 Commit。

## 安装到项目

在目标项目根目录中，使用单独安装的 Python CLI。这个项目级安装方式完全离线，
无需 Node.js 或源码检出：

```bash
repo-dive init . --agent claude-code --agent codex --agent opencode \
  --agent gemini-cli --agent github-copilot
```

在终端中直接运行 `repo-dive init` 会显示多选提示，并在写入前要求明确确认。
自动化调用必须重复传入 `--agent`；JSON 模式或非 TTY 环境没有指定 Agent 时会
直接校验失败，不会等待输入：

```bash
repo-dive init /path/to/project --agent codex --agent opencode --format json
```

内容相同的重复运行会报告 `reused`。如果已有内容不同，命令会保留原字节并报告
冲突；仅在检查内容后使用 `--force`。命令会对共享的
`.agents/skills/wiki` 目标去重。

作为备选方案，可使用第三方 `skills` CLI 为五个受支持 Host 安装同一个权威
`skills/wiki` 目录：

```bash
npx skills add OWNER/repo-dive --skill wiki \
  -a claude-code -a codex -a opencode -a gemini-cli \
  -a github-copilot -y
```

请把 `OWNER/repo-dive` 替换为 Git 仓库或本地检出路径。项目映射如下：

| Host | 安装后的发现路径 | 调用/发现方式 |
| --- | --- | --- |
| Claude Code | `.claude/skills/wiki` | `/wiki` |
| OpenAI Codex CLI | `.agents/skills/wiki` | `$wiki` 或 `/skills` |
| OpenCode | `.agents/skills/wiki` | 模型可见的 `skill` Tool |
| Gemini CLI | `.agents/skills/wiki` | 经同意后激活 Skill |
| GitHub Copilot | `.agents/skills/wiki` | `/wiki` 或 `/skills info wiki` |

第三方安装器通常保留一个项目内的规范副本，并为 Host 创建符号链接。仅在不适合
符号链接时使用 `--copy`。不要分别编辑已安装副本；应从插件 Source 更新。

安装前可运行 `npx skills add OWNER/repo-dive --list` 检查发现结果。使用
`npx skills update` 更新受跟踪安装。除非设置 `DISABLE_TELEMETRY=1` 或
`DO_NOT_TRACK=1`，该第三方安装器会收集遥测。

## 原生与 Host 专用方式

上面的通用项目安装是 OpenCode 的受支持方式。它的 JavaScript/TypeScript
插件 API 属于另一种能力，本包特意不使用它。

- **Claude Code：**使用 `claude plugin validate .` 和
  `claude --plugin-dir .` 验证或开发当前检出。原生插件暴露
  `/repo-dive:wiki`。本次发布不包含 Marketplace 发布。
- **Codex：**内置 `$skill-installer` 可以从 Git 仓库安装 `skills/wiki`。
  Codex 也可识别本包的 `.codex-plugin/plugin.json`；原生 Marketplace 安装
  对版本敏感，应使用选定 Codex Build 进行冒烟测试。
- **Gemini CLI：**使用
  `gemini skills install https://github.com/OWNER/repo-dive.git --path skills/wiki --scope workspace`
  安装独立 Skill，或使用
  `gemini extensions install https://github.com/OWNER/repo-dive --ref TAG`
  安装 Extension。
- **GitHub Copilot：**使用 GitHub CLI 2.90.0 或更高版本运行
  `gh skill install OWNER/repo-dive wiki --agent github-copilot --scope project`，
  或运行 `copilot plugin install OWNER/repo-dive` 安装根目录的 Agent Plugins
  Manifest。

## 使用与输出

要求 Host 生成或刷新仓库 Wiki，或使用上表的 Host 语法调用 `wiki`。Skill
会先检查可执行文件，使用 JSON CLI 模式，保留现有工作树，并由当前 Agent
模型生成正文。Build 成功后使用：

```text
<repository>/.repo-dive/wiki.md
```

## 卸载与回滚

对于 `repo-dive init`，先确认目录包含预期 Skill，再只删除项目内安装目录：

```bash
rm -rf .claude/skills/wiki .agents/skills/wiki
```

使用第三方安装器时，从所有选定 Host 删除项目 Skill：

```bash
npx skills remove wiki \
  -a claude-code -a codex -a opencode -a gemini-cli \
  -a github-copilot -y
```

原生方式使用各 Host 命令：

```bash
gemini skills uninstall wiki --scope workspace
gemini extensions uninstall repo-dive
copilot plugin uninstall repo-dive
```

预览版 `gh skill` 命令目前没有卸载子命令。对于该安装方式，请运行
`gh skill list`，确认已安装 Skill 的 Source，然后只删除其项目目录
`.agents/skills/wiki`。删除 Agent Skill 不会卸载 Python CLI，也不会删除已有的
`.repo-dive/` 目录。回滚后检查 `git status --short` 并保留无关更改。

## 兼容性限制

- 五个 Host 均支持项目级安装。由于第三方 `skills` CLI 记录的全局目标与
  Codex 当前官方用户路径不同，本指南不声明通过它支持 Codex 全局安装。
- 各 Host 的调用和同名优先级不同。Claude 原生插件将 Skill 命名为
  `/repo-dive:wiki`；其他 Host 可能优先使用已有的项目或个人 `wiki` Skill。
- 原生插件 Cache 可能复制包，因此所有资源均特意保留在 `skills/wiki/` 下。
- Claude 严格验证会把这个 CLI/插件组合仓库根目录的 `CLAUDE.md` 视为未加载的
 兼容文件。普通插件验证可以通过；如果发布流程要求严格验证，请验证暂存的
 纯插件归档。
- Vendor CLI 冒烟测试需要已安装且固定版本的 Client，不属于默认离线 Python
  测试套件。
