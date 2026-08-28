# repo-dive

[English](README.md)

`repo-dive` 是一个纯 Python 的本地代码仓库 RAG CLI，帮助编码 Agent 索引源码、检索可追溯证据，并在仓库内生成知识产物。

这个 CLI 刻意不充当另一个 Agent。它负责确定性的仓库处理；GitHub Copilot 或其他调用方 Agent 负责理解证据和撰写内容。

## 当前状态

当前离线 RAG 核心提供：

- 具有安全仓库边界的确定性 Git/文件系统扫描；
- Python AST 与 Tree-sitter 解析，以及稳定的 Chunk、符号和关系；
- 原子发布的本地 SQLite 索引、BM25 与结构检索；
- 支持 JSON 或 Markdown 的只读 `search` 和 Token 预算 `context` 命令；
- 带原子产物的可恢复 `wiki structure`、`wiki evidence`、`wiki page`、`wiki build` 和 `wiki status` 命令；
- 稳定的进程、Schema、评测及本地/CI Harness 契约。

可选的 SQLite float32 Vector Store、确定性余弦检索器、显式本地 Sentence Transformers Provider，以及 `index`/`search`/`context` 三通道集成已经实现。离线 Wiki 工作流保持完整可用。

## 设计哲学

- 确定性核心，概率性边缘；
- 先证据，后叙述；
- 结合语法结构、BM25 关键词检索和可选向量检索的混合 RAG；
- 阶段可检查、流程可恢复；
- 稳定的 JSON、退出码和文件系统契约；
- 源码和生成产物默认归本地仓库所有；
- 解析与检索组件可以替换；
- 人、Agent 和 CI 使用同一套 Harness。

完整说明见[架构设计](docs/zh-CN/architecture.md)。

## Agent 工作流

当前可用的端到端 Wiki RAG 流程是：

```text
调用方 Agent
  -> 调用 repo-dive 扫描并解析本地仓库
  -> 建立结构、BM25 和可选向量索引
  -> 为某个 Wiki 页面检索并按预算组装结构化证据
  -> 使用调用方当前模型生成内容
  -> 把页面交给 repo-dive 持久化
  -> 要求 repo-dive 汇总最终 Markdown
```

稳定的最终产物路径是：

```text
<repository>/.repo-dive/wiki.md
```

阶段与产物细节见 [Wiki 工作流](docs/zh-CN/wiki-workflow.md)。

这里的 RAG 是一种**执行边界分离的检索增强生成**：`repo-dive` 负责摄取、索引、检索、排序和上下文打包；调用方 Copilot 会话负责生成。CLI 不会再启动一个隐藏的模型会话。

## 开发环境

要求 Python 3.11 或更高版本。

```bash
make setup
make check
make test-unit
make test-all
.venv/bin/python -m repo_dive.evaluation.runner evals/cases --format json
```

环境创建完成后：

```bash
.venv/bin/repo-dive --help
.venv/bin/repo-dive --version
.venv/bin/repo-dive index /path/to/repository --format json
.venv/bin/repo-dive search /path/to/repository "entrypoint" --max-results 10 --format json
.venv/bin/repo-dive context /path/to/repository "architecture" --token-budget 1200 --format json
.venv/bin/repo-dive index /path/to/repository --embedding-model /path/to/local/model --format json
.venv/bin/repo-dive search /path/to/repository "request lifecycle" --embedding-model /path/to/local/model --format json
.venv/bin/repo-dive wiki structure /path/to/repository --input structure.json --format json
.venv/bin/repo-dive wiki evidence /path/to/repository --page overview --token-budget 1200 --format json
.venv/bin/repo-dive wiki page /path/to/repository --page overview --input page.json --format json
.venv/bin/repo-dive wiki build /path/to/repository --format markdown
.venv/bin/repo-dive wiki status /path/to/repository --format json
```

支持的工作流与公开契约参见[开发指南](docs/zh-CN/development.md)和 [CLI 契约](docs/zh-CN/cli-contract.md)。

## 项目文档

- [架构设计](docs/zh-CN/architecture.md)
- [CLI 契约](docs/zh-CN/cli-contract.md)
- [Wiki 工作流](docs/zh-CN/wiki-workflow.md)
- [开发指南](docs/zh-CN/development.md)
- [Agent 指南](AGENTS.md)
