# repo-dive

[English](README.md)

`repo-dive` 是一个纯 Python CLI，帮助编码 Agent 从本地仓库收集可追溯证据，并在仓库内生成知识产物。

这个 CLI 刻意不充当另一个 Agent。它负责确定性的仓库处理；GitHub Copilot 或其他调用方 Agent 负责理解证据和撰写内容。

## 当前状态

当前基础版本提供：

- 可安装的 `repo-dive` 命令，支持 `--help` 和 `--version`；
- 跨 Agent 的权威指令；
- 架构、CLI、工作流和开发契约的中英双语文档；
- 本地与 CI 共用的验证入口；
- 测试和评测骨架。

仓库扫描、语法解析、索引、检索、上下文组装和 Wiki 生成尚未实现。

## 设计哲学

- 确定性核心，概率性边缘；
- 先证据，后叙述；
- 阶段可检查、流程可恢复；
- 稳定的 JSON、退出码和文件系统契约；
- 源码和生成产物默认归本地仓库所有；
- 解析与检索组件可以替换；
- 人、Agent 和 CI 使用同一套 Harness。

完整说明见[架构设计](docs/zh-CN/architecture.md)。

## 预期 Agent 工作流

规划中的工作流是：

```text
调用方 Agent
  -> 调用 repo-dive 扫描并索引本地仓库
  -> 请求某个 Wiki 页面的结构化证据
  -> 使用调用方当前模型生成内容
  -> 把页面交给 repo-dive 持久化
  -> 要求 repo-dive 汇总最终 Markdown
```

稳定的最终产物路径是：

```text
<repository>/.repo-dive/wiki.md
```

阶段与产物细节见 [Wiki 工作流](docs/zh-CN/wiki-workflow.md)。

## 开发环境

要求 Python 3.11 或更高版本。

```bash
make setup
make check
make test-unit
make test-all
```

环境创建完成后：

```bash
.venv/bin/repo-dive --help
.venv/bin/repo-dive --version
```

实现命令前请阅读[开发指南](docs/zh-CN/development.md)和 [CLI 契约](docs/zh-CN/cli-contract.md)。

## 项目文档

- [架构设计](docs/zh-CN/architecture.md)
- [CLI 契约](docs/zh-CN/cli-contract.md)
- [Wiki 工作流](docs/zh-CN/wiki-workflow.md)
- [开发指南](docs/zh-CN/development.md)
- [Agent 指南](AGENTS.md)

