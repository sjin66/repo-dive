# Repo Dive CLI 全阶段实施计划

> **供 Agent 执行：** 按 `tasks/todo.md` 的顺序逐项实施。每项行为变更必须遵循红—绿—重构；每个检查点必须停下来运行共享 Harness 并审阅差异。

**目标：** 把当前 CLI 基础壳发展为可由 GitHub Copilot 直接调用的纯 Python、本地优先 RAG CLI：它读取本地仓库，建立结构/BM25/可选向量索引，在预算内返回可追溯证据，并把调用方模型生成的内容持久化为 `<repository>/.repo-dive/wiki.md`。

**架构：** CLI 只负责确定性工作与显式配置的 Embedding；调用方 Agent 负责理解与生成。内部使用不可变领域对象连接扫描、解析、索引、检索、上下文和 Wiki 模块；SQLite 保存实现私有索引，公开状态使用带版本 JSON，所有公开写入都通过同目录临时文件原子替换。

**技术栈：** Python 3.11+、`argparse`、`dataclasses`、`pathlib`、`sqlite3`、Python `ast`、Tree-sitter 适配器、pytest、Ruff、严格 mypy。BM25 与余弦检索由项目实现；本地 Sentence Transformers 作为可选 extra，不进入离线基线。

**依据：** `AGENTS.md`、`docs/en/architecture.md`、`docs/en/cli-contract.md`、`docs/en/wiki-workflow.md` 及对应中文文档。

## 全局约束

- Python 最低版本是 3.11；项目不增加 Web Runtime、HTTP API、MCP 服务或前端。
- CLI 不隐式调用生成模型；Wiki 正文由 GitHub Copilot 当前会话生成并交回 CLI。
- `index`、`search`、`context` 和 `wiki` 功能命令必须非交互，并支持 `--format json`。
- JSON 模式的 `stdout` 只有一个完整 JSON 文档；进度和诊断只写入 `stderr`。
- 退出码固定为：成功 `0`、调用/校验错误 `2`、仓库/输入错误 `3`、内部错误 `4`。
- 证据路径使用仓库相对 POSIX 路径；可信行号从 1 开始且首尾均包含。
- 只允许写入被分析仓库的 `.repo-dive/`；不得自动修改其 `.gitignore`。
- 每个读取或写入路径必须经过仓库边界校验；拒绝符号链接逃逸和 `..` 路径穿越。
- BM25 与结构检索在无凭据、无网络环境中必须完整可用。
- Vector Provider 必须显式启用；默认禁止下载模型或访问网络。
- 英文和简体中文工程文档必须同一任务、同一提交更新，并保持技术契约一致。
- 人、Agent 和 CI 统一使用 `make setup`、`make check`、`make test-unit`、`make test-all`。

## 已完成基线

当前仓库已经完成基础交付：包结构、`repo-dive` 入口、`--help`/`--version`、AGENTS 权威规则、中英双语架构文档、共享 Make Harness、CI 与基础评测清单。后续计划不能把规划中的命令误写成已实现能力。

## 关键架构决策

### 1. 单进程分层 CLI

`src/repo_dive/cli.py` 只做参数解析、命令分派和进程 I/O。每个命令模块把 CLI 参数转换为应用服务请求；领域模块不读取环境变量、不打印终端内容，也不依赖 `argparse`。

```text
argv / stdin
    -> cli.py + commands/*
    -> application services
    -> scanner / parsing / indexing / retrieval / context / wiki
    -> storage + providers
    -> result envelope -> stdout
```

### 2. 领域对象是阶段契约

核心对象使用冻结 dataclass，并在 `schema_version = "1.0"` 的 JSON 边界显式编解码：

```python
RepositoryRef(root: Path, commit: str | None)
FileRecord(path: str, language: str, size_bytes: int, content_hash: str)
Chunk(id: str, path: str, start_line: int, end_line: int, text: str,
      symbol_id: str | None, content_hash: str)
Symbol(id: str, kind: str, name: str, qualified_name: str,
       path: str, start_line: int, end_line: int)
Relationship(source_id: str, target_id: str, kind: str, confidence: float)
SearchHit(chunk: Chunk, lexical_score: float | None,
          structural_score: float | None, vector_score: float | None,
          fused_score: float, reasons: tuple[str, ...])
EvidenceBundle(query: str, budget: int, estimated_tokens: int,
               truncated: bool, items: tuple[EvidenceItem, ...])
```

对象 ID 来自稳定内容与位置，不使用随机 UUID。Schema 编解码失败返回稳定错误码，不能静默丢字段。

### 3. 仓库发现与安全读取

Git 仓库优先使用 `git ls-files -co --exclude-standard -z` 获得“已跟踪 + 未忽略的未跟踪”候选；非 Git 目录使用确定性文件系统遍历和内置排除规则。两种路径共用大小、二进制、编码、符号链接和仓库边界检查。

扫描结果按 POSIX 路径排序。默认排除 `.git/`、`.repo-dive/`、缓存、虚拟环境、依赖与构建目录；用户通过重复的 `--include`/`--exclude` 显式覆盖，但不能突破安全边界。

### 4. 解析、切分与符号关系

解析采用适配器注册表：

- Python 使用标准库 `ast`，作为零额外依赖的参考实现。
- JavaScript、TypeScript、TSX、Java、Go、Rust 等通过 Tree-sitter 语言适配器启用。
- 不支持语言、Markdown 和配置文件回退到按标题/空行/行窗切分的文本解析器。

优先按符号边界生成 Chunk；超大符号按语句或行窗二次切分，小相邻 Chunk 在上限内合并。结构关系先实现 `contains`、`imports`、`calls` 和 `inherits`；无法静态确认的边只降低置信度，不伪装成确定关系。

### 5. SQLite 私有索引

`.repo-dive/index/index.sqlite3` 是实现私有索引，包含文件、Chunk、符号、关系、BM25 posting、文档长度和可选向量。`.repo-dive/index/manifest.json` 记录索引 Schema、构建参数、仓库指纹和 Provider 身份。

索引先构建到同目录临时数据库，事务提交并校验后原子替换。增量更新按文件内容哈希删除和重建受影响记录；参数或 Schema 变化触发完整重建。旧索引在失败时保持可用。

### 6. BM25、结构与向量混合检索

离线基线由 BM25 和结构通道组成：

- Tokenizer 保留标识符整体，同时切分 snake_case、camelCase 和路径片段。
- BM25 使用固定、可记录的 `k1` 与 `b`，返回原始分数和命中词。
- 结构通道支持精确符号、文件邻近、Import/调用/继承扩展。
- 融合使用加权 Reciprocal Rank Fusion；每通道权重和 RRF 常数进入结果元数据。
- 去重依据 Chunk ID、包含关系和高比例行区间重叠。

可选向量通道遵守 `EmbeddingProvider` Protocol。首个具体 Provider 只接受本地模型路径，并设置 `local_files_only=True`；SQLite 保存定长 `float32`，MVP 用确定性暴力余弦检索，避免引入 FAISS。Vector 失败可配置为严格失败或降级并产生 warning，默认严格。

### 7. 上下文预算

`context` 在融合候选上进行预算选择：预留信封和证据元数据空间，优先高分且来源多样的实现 Chunk，再进行关系扩展。默认使用保守、确定性的字符/Token 估算器；可选 tokenizer 适配器必须显式声明。

输出报告 `token_budget`、`estimated_tokens`、`truncated`、被排除原因和每条证据的稳定 ID。不得通过截断行号或丢弃路径来挤入更多正文。

### 8. Wiki 是可恢复状态机

Wiki 命令族采用以下子命令：

```text
repo-dive wiki structure <repository> --input structure.json --format json
repo-dive wiki evidence  <repository> --page <page-id> --token-budget N --format json
repo-dive wiki page      <repository> --page <page-id> --input page.json --format json
repo-dive wiki build     <repository> [--format json|markdown]
repo-dive wiki status    <repository> --format json
```

`wiki.json` 保存稳定页面 ID、顺序、状态、页面正文、Evidence ID 和来源；`metadata.json` 保存仓库身份、Commit、Schema、索引版本和时间。结构与页面输入严格校验未知路径、未知 Evidence、编码、大小与状态转换。

页面状态为 `pending -> evidence_ready -> generated`，任何阶段可进入 `failed` 并单页重试。`wiki build` 只在必需页面完成后构建标题、目录、锚点、正文和来源，并原子替换 `wiki.md`。

### 9. 评测驱动的检索演进

评测 Fixture 必须小、可读、固定。评测 Runner 输出 Recall@k、MRR、路径命中率、符号命中率、预算遵守率和引用覆盖率。任何排序、扩展或预算启发式修改，都必须先增加一个能失败的用例。

## 目标文件结构

```text
src/repo_dive/
├── cli.py
├── errors.py
├── schema.py
├── commands/
│   ├── index.py
│   ├── search.py
│   ├── context.py
│   └── wiki.py
├── storage/
│   ├── paths.py
│   └── atomic.py
├── scanner/
│   ├── candidates.py
│   └── service.py
├── parsing/
│   ├── models.py
│   ├── registry.py
│   ├── text.py
│   ├── python_ast.py
│   ├── tree_sitter.py
│   └── pipeline.py
├── indexing/
│   ├── store.py
│   ├── bm25.py
│   ├── vectors.py
│   └── service.py
├── retrieval/
│   ├── lexical.py
│   ├── structural.py
│   ├── vector.py
│   └── fusion.py
├── context/
│   ├── tokens.py
│   └── packer.py
├── providers/
│   └── embeddings.py
├── wiki/
│   ├── models.py
│   ├── store.py
│   ├── validation.py
│   ├── service.py
│   └── assembler.py
└── evaluation/
    ├── metrics.py
    └── runner.py
```

`domain.py` 大杂烩被刻意避免；类型放在拥有行为的模块中。跨边界只暴露必要 Protocol 和冻结对象。

## 依赖图与开发阶段

```text
命令信封 + 错误模型 + 安全路径/原子写
    |
    +--> 扫描清单 --> 解析注册表 --> AST/Tree-sitter --> Chunk/关系
    |                                              |
    +----------------------------------------------+
                                                   v
                                  SQLite + BM25 + 结构索引
                                                   |
                                  增量 index 命令与 Manifest
                                                   |
                         BM25/结构检索 --> 融合/去重 --> search
                                                   |
                                       Token 预算 --> context
                                                   |
                           Wiki 状态/证据/页面/原子 build
                                                   |
                           可选向量 Provider + 混合检索
                                                   |
                               评测/性能/安全/发布验收
```

### Phase 1：公共契约与安全基础

任务 1–4 建立错误信封、Schema 编解码、路径边界和原子写。后续模块只能使用这些公共行为，不能各自发明 JSON 或异常处理。

### Phase 2：摄取、解析与切分

任务 5–9 交付确定性仓库清单、文本回退、Python AST、Tree-sitter 和统一解析流水线。阶段结束时，Fixture 仓库可以稳定产出 File、Chunk、Symbol 和 Relationship，但尚不写索引。

### Phase 3：持久化索引与 `index`

任务 10–14 交付 SQLite Schema、BM25、结构关系、增量构建和 `repo-dive index`。阶段结束时 CLI 能离线、原子、幂等地索引仓库。

### Phase 4：检索与 `search`

任务 15–18 交付 BM25 查询、结构扩展、RRF 融合、去重和公开 `search` 命令。所有命中保留通道分数和解释。

### Phase 5：预算上下文与 `context`

任务 19–20 交付 Token 估算、证据选择和公开 `context` 命令。输出成为调用方 Copilot 生成内容的稳定输入。

### Phase 6：Wiki 状态机与 Markdown 汇总

任务 21–25 交付结构、证据、页面、状态、失效和原子汇总。阶段结束时 Copilot 可以按页面循环调用 CLI，恢复失败页面并生成稳定 `.repo-dive/wiki.md`。

### Phase 7：可选向量增强

任务 26–28 交付 Vector Store、显式本地 Embedding Provider 和三通道混合检索。该阶段不得改变无 Vector 配置时的离线行为。

### Phase 8：评测、硬化与发布

任务 29–34 交付可执行评测、端到端/安全/性能覆盖、中英双语调用文档和发布验收。

## 里程碑

| 里程碑 | 完成条件 | 可供调用方使用的能力 |
|---|---|---|
| M1 摄取 | 任务 1–9 | 稳定扫描、AST/Tree-sitter Chunk 与符号关系 |
| M2 离线索引 | 任务 10–14 | `repo-dive index` |
| M3 离线 RAG | 任务 15–20 | `search` + `context`，BM25/结构混合证据 |
| M4 Wiki MVP | 任务 21–25 | 结构、证据、页面、状态、`wiki.md` |
| M5 Hybrid RAG | 任务 26–28 | 显式启用的向量增强 |
| M6 Release Candidate | 任务 29–34 | 评测、性能、安全、文档和打包验收 |

## 测试策略

- **单元测试：** 领域编解码、路径检查、Scanner、Parser、Tokenizer、评分、去重、预算、状态转换和汇总。
- **契约测试：** stdout/stderr、错误信封、退出码、POSIX 路径、行号、Schema 兼容和文档中英文同步。
- **集成测试：** 对小型 Fixture 执行 `index -> search -> context -> wiki`，全部通过真实 CLI 入口。
- **故障测试：** 不可读文件、坏编码、损坏索引、原子替换失败、过期 Evidence、非法页面和部分 Wiki 恢复。
- **安全测试：** `..`、绝对路径注入、仓库外符号链接、恶意 Git 文件名、超大文件和诊断脱敏。
- **评测：** 固定查询和期望路径/符号，计算检索与引用指标，不评价文章风格。
- **性能测试：** 生成型 Fixture 只检查上限和回归趋势，不使用脆弱的绝对毫秒门槛；内存峰值和返回数量必须受预算限制。

## 发布门槛

- Python 3.11、3.12、3.13 的共享 CI Harness 通过。
- `make check` 和 `make test-all` 从全新 `.venv` 通过。
- 四个功能命令的 JSON 成功与错误输出均通过进程级测试。
- 无 Vector、无凭据、无网络时可完成完整 Wiki 工作流。
- Vector Provider 未显式配置时不会导入重型依赖、下载模型或访问网络。
- 中断后可以复用有效索引和已生成页面；失败写入不破坏旧 Wiki。
- README、CLI 契约、架构、Wiki 流程和开发文档中英文内容同步。
- `git status --short` 只包含预期源码、测试、评测、文档和计划文件。

## 风险与缓解

| 风险 | 影响 | 缓解措施 |
|---|---|---|
| Tree-sitter Grammar 版本与 ABI 不兼容 | 高 | 语言适配器隔离；锁定兼容范围；每种语言一个最小解析 Fixture；文本回退保底 |
| Gitignore 与非 Git 扫描语义不一致 | 中 | Git 仓库委托 `git ls-files`；非 Git 路径使用有文档的确定性规则；结果记录扫描模式 |
| BM25 Tokenizer 对代码标识符召回不足 | 高 | 同时保留原标识符和拆分 Token；任何规则变化由评测用例驱动 |
| 结构调用边产生误报 | 中 | 关系携带置信度和来源；低置信边只用于弱扩展，不作为事实输出 |
| Token 估算与调用方模型不一致 | 中 | 明确标注 `estimated_tokens` 与 estimator；保守预留；支持可替换 Tokenizer |
| Sentence Transformers 依赖过重 | 中 | 独立 `vector` extra；延迟导入；仅本地模型路径；离线基线不依赖它 |
| SQLite 增量更新留下混合版本 | 高 | 临时数据库/事务/Manifest 校验后原子替换；失败保留旧索引 |
| Wiki 页面内容引用不存在的证据 | 高 | 页面提交时严格验证 Evidence ID；过期证据阻止 build 并返回稳定错误 |
| 计划跨度过大造成长期分支漂移 | 高 | 按里程碑交付；每 2–3 个任务设置 Harness 检查点；每个任务保持 S/M 尺寸 |

## 非目标

- 不克隆远程仓库；调用方传入本地路径。
- 不提供前端、Web Server、MCP Server 或常驻 Daemon。
- 不让 CLI 选择或调用 Wiki 生成模型。
- 不在首个版本实现分布式索引、远程数据库或近似最近邻服务。
- 不尝试对所有语言提供完美静态调用解析；未知关系必须保守表达。
- 不自动编辑被分析仓库的源码、配置或 `.gitignore`。

## 开放问题的默认决策

这些选择在实施中作为默认值；若验证显示不适合，再以独立 ADR 调整：

- 索引存储使用标准库 SQLite，不采用外部搜索服务。
- 离线 Token 估算使用保守字符估算；精确 tokenizer 是可选适配器。
- Vector MVP 使用 SQLite + 暴力余弦；只有评测和规模数据证明需要时才引入 ANN。
- 首个向量 Provider 只加载用户给定的本地 Sentence Transformers 模型目录。
- CLI 保持 `argparse`，不为命令样式引入 Typer/Click。
- 公开 JSON Schema 从 `1.0` 开始；索引内部 Schema 单独版本化。
