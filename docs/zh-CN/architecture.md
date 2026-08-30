# 架构设计

## 系统边界

`repo-dive` 是由人或编码 Agent 调用的本地非交互进程。它读取一个明确指定的仓库，在 `.repo-dive/` 下写入仓库自有产物，并在 stdout 输出一个完整的 JSON 或 Markdown 结果。语言模型生成由调用方 Agent 负责；CLI 不会启动嵌套模型会话。

```text
调用方 Agent
    | argv / stdin
    v
CLI 命令
    |-- 扫描 -> 解析 -> 索引
    |-- 检索 -> 融合 -> 打包上下文
    `-- 持久化 Wiki 状态 -> 汇总 Markdown
    v
stdout JSON/Markdown + <repository>/.repo-dive/
```

实现遵循本地优先。默认关键词和结构路径不需要凭据或网络。Vector 支持必须显式启用，当前 Provider 只接受已经存在的本地 Sentence Transformers 模型目录。

## 设计原则

- **确定性核心，概率性调用方：**扫描、解析、索引、检索、校验和汇总都能由仓库字节与显式选项复现；理解和内容生成保留在调用模型中。
- **先证据，后叙述：**上下文和 Wiki 命令保留仓库相对 POSIX 路径、从 1 开始且首尾都包含的行号、Chunk 身份、哈希和可解释评分。
- **工作量有界：**文件大小、Chunk 行数、结果数量、图遍历、Embedding Batch 和上下文 Token 都有明确上限。
- **产物可恢复：**索引以完整代际发布；Wiki 页面拥有独立持久化状态；相同提交和 Build 不写入新字节。
- **进程契约稳定：**JSON Schema 版本、退出码、stdout/stderr 分离和公开产物路径是集成边界。Prompt 文案不是 API。

<!-- contract-section:packages -->
## 包与依赖边界

以下是已经实现的包边界，不是未来规划：

```text
src/repo_dive/
├── cli.py                 进程边界与错误/结果序列化
├── commands/              index、search、context、map、wiki 适配器
├── scanner/               确定性候选发现与文件读取
├── parsing/               提取 Chunk、Symbol、Relationship
├── indexing/              SQLite、BM25、图、Vector、代际发布
├── providers/             可选本地 Embedding Provider 选择
├── retrieval/             关键词、结构、Vector 与加权融合
├── context/               Token 估算与完整 Evidence 打包
├── knowledge_map/         确定性 Map、View、Evidence 与 Enrichment
├── wiki/                  状态、新鲜度、页面提交、汇总
├── storage/               仓库路径校验与原子写入
├── evaluation/            离线检索与上下文评测 Runner
├── errors.py              稳定错误类别与退出语义
└── schema.py              带版本的 JSON 结果信封
```

真实依赖方向如下：

```text
cli -> commands
commands -> indexing / retrieval / context / knowledge_map / wiki
scanner -> storage
parsing -> scanner
indexing -> scanner / parsing / providers / storage
retrieval -> indexing / parsing / providers
context -> retrieval / parsing
knowledge_map -> indexing / retrieval / context / storage
wiki -> indexing / retrieval / context / storage
evaluation -> indexing / retrieval / context
```

底层领域模型不会反向导入命令或 CLI 模块。需要替换实现的运行时边界使用窄 Protocol：`SourceParser`、`EmbeddingProvider`、`StructuralGraph` 和 `TokenEstimator`。文件系统和 SQLite 持久化是具体的本地适配器，不是尚未实现的远程抽象。

## 扫描与解析流水线

对于 Git 根目录，候选发现运行 `git ls-files --cached --others --exclude-standard`；否则执行确定性的文件系统遍历。两种模式都会排序仓库相对路径，排除包含 `.repo-dive/` 在内的生成或 Vendor 目录，应用显式 Include/Exclude Pattern，拒绝非普通文件和符号链接穿越，并在平台支持时使用 `O_NOFOLLOW` 读取。

扫描器记录 SHA-256 内容哈希，并把文件分类为 `read` 或 `skipped`。稳定跳过原因覆盖文件过大、二进制、非法 UTF-8 和无法读取。仓库清单指纹包含扫描模式、有序文件元数据、哈希、状态和最大文件大小。

Parser 选择实现如下：

- Python 使用标准库 AST 适配器。
- JavaScript、JSX、TypeScript 和 TSX 使用 Tree-sitter 适配器。
- 不支持的语言、文档和语法失败回退到文本 Parser，并保留诊断。
- 标准化流水线把每个 Chunk 拆到不超过 `max_chunk_lines`（默认 `200`），去除重复身份，并确定性排序 Chunk、Symbol、Relationship 和诊断。

## 本地 RAG 数据流

<!-- contract-section:rag-boundary -->

```text
仓库字节
  -> 候选清单 + repository_fingerprint
  -> 语言 Parser -> Chunk + Symbol + Relationship
  -> SQLite BM25 + 图 + 可选 Vector Row
  -> 关键词 + 结构 + 可选 Vector 候选
  -> weighted_rrf + 重叠去重
  -> token_budget 内的完整 Evidence
  -> 调用模型生成内容
  -> CLI 校验 Evidence ID 并持久化 Wiki 页面状态
```

这种拆分仍然是 RAG：检索增强了调用模型的生成，只是确定性检索进程与概率性生成进程被有意分离。

### BM25 通道

每个新索引代际都从当前 Chunk 重建关键词语料。代码感知 Tokenizer 是 `code-v1`；它保留完整代码 Token，同时生成大小写折叠、分隔符拆分和 Camel Case 变体。默认值是 `k1 = 1.2` 与 `b = 0.75`。SQLite 保存 Term、文档频率、Posting、文档长度和聚合统计。

### 结构通道

SQLite 保存 Symbol 以及 `calls`、`contains`、`imports`、`inherits` Relationship。结构检索先执行规范化的精确/前缀/子串 Symbol 匹配，再以默认最小置信度 `0.75` 执行深度 `1` 的有界双向图遍历。它优先返回定义 Chunk，并保留 Relationship Path 原因。

### Vector 通道

Vector 检索是可选项。`--embedding-model` 选择当前 Sentence Transformers 适配器；该适配器从 `vector` Extra 延迟加载，并设置 `local_files_only=True` 和 `trust_remote_code=False`。Provider 名、不可逆的 `local:<sha256>` 模型身份和维度定义向量空间，同时避免持久化私有模型绝对路径。

索引 Schema 4 为每个 Chunk 保存一个固定长度、小端序 float32 BLOB。Row 同时绑定 `chunk_id`、`chunk_hash`、Provider、模型和维度。非有限值、维度不匹配、混合身份和过期 Chunk 哈希都会被拒绝。基于持久化 float32 精度的精确暴力余弦检索是确定性参考实现，同分按 Chunk ID 排序。

只有 Provider 身份和 Chunk 内容哈希都一致时才复用 Vector。`strict` Vector 失败会中止发布或检索；`degraded` 会移除 Vector 身份/通道，继续使用关键词加结构证据，并返回安全的 Warning/Error Code。

`search` 和 `context` 命令可以选择该 Provider。当前 `wiki evidence` Application Service 不会注入 Embedding Provider，因此即使已发布索引包含 Vector，它的实际检索路径仍是 BM25 加结构检索。

### 融合与上下文

关键词和结构排名始终以权重 `1.0` 参与；准备完成的 Vector 通道增加权重 `1.0`。策略名是 `weighted_rrf`，`rrf_k = 60`，重叠阈值是 `0.8`。结果保留原始通道评分，以及 Rank、Weight、Contribution、Symbol Match 和 Relationship Path 原因。融合完成后对重叠 Chunk 去重。

`EvidencePacker` 为信封和条目元数据预留 Token，优先选择实现 Chunk 而非文件级回退 Chunk，默认每个文件最多选择两项，并且绝不切开 Chunk。输出报告 `estimated_tokens`、`reserved_tokens`、`truncated`，以及原因是 `duplicate`、`budget` 或 `low_score` 的排除候选。

<!-- contract-section:index-storage -->
## SQLite 与索引发布

活动索引是指向不可变代际的符号链接：

```text
<repository>/.repo-dive/
├── index -> index-generations/<build-id>
└── index-generations/
    └── <build-id>/
        ├── index.sqlite3
        ├── manifest.json
        └── metadata.json
```

物理数据库路径是 `.repo-dive/index-generations/<build-id>/index.sqlite3`；消费者使用稳定指针路径 `.repo-dive/index/index.sqlite3`。`manifest.json` 记录 Schema `1.0`、Build ID、仓库指纹、扫描模式、构建参数、File-to-Chunk Membership、数量以及可选 Embedding 身份。代际内的 `metadata.json` 是该索引代际的公开指针摘要，与 `.repo-dive/metadata.json` 的 Wiki Metadata 不同。

SQLite Schema 5 由 `PRAGMA user_version = 5` 声明，包含 `files`、`symbols`、`chunks`、`relationships`、`terms`、`postings`、`stats` 和 `vectors`。关系记录保留精确的语法出现位置与来源，而图遍历会按端点和关系类型聚合为唯一邻接边。发布前必须通过外键和完整性检查。

索引构建先创建 Staging 目录，从兼容的旧代际复用未变化文件的解析结果，写入并校验完整的新数据库和元数据，把 Staging 移到 `index-generations/<build-id>`，然后原子替换 `.repo-dive/index -> index-generations/<build-id>` 符号链接。构建或指针替换失败时保留上一代并删除临时数据。只读命令使用持久化构建参数重新扫描，仓库指纹不一致时返回 `index_stale`。

## Wiki 持久化与恢复边界

Wiki 状态使用 `.repo-dive/wiki.json` 和 `.repo-dive/metadata.json` 中的严格 Schema `2.0` JSON。完整文件先序列化再原子替换；损坏、不支持或不完整的状态会被拒绝且不会修复。只有全部页面和 Evidence 校验通过后才替换 `.repo-dive/wiki.md`；字节相同时返回 `changed: false`。

Evidence 新鲜度以页面为单位：索引 Schema 必须仍是 `4`，每个持久化引用的 Chunk ID、内容哈希、路径和首尾都包含的行号都必须匹配当前索引。Index Build ID 用于审计溯源，本身不是全局失效信号。

## Knowledge Map 边界

可选 Knowledge Map 是 `.repo-dive/knowledge-map.json` 中的严格 Schema `1.0` 文档。它从一个当前已发布索引推导 Repository、Module、File、Symbol 事实，以及 Architecture、Static Flow、Reading Tour 投影。Source Chunk 仍是 Evidence 引用而不是 Fact Node。语义区为空时，确定性 Build 仍然有用，并且不会调用模型。

所有 Writer 共用 `.repo-dive/knowledge-map.lock` 的有界 OS Advisory Lock，然后在锁内重新校验索引、检查精确 Intent 等价性、执行 Revision/Hash Compare-and-Swap、校验完整 Candidate、执行字节容量约束并原子替换。`artifact_revision` 只在字节发生变化时递增。确定性变化会清空语义状态；满足约束的纯 Capacity 变化会保留语义。`map show` 与 `map validate` 是只读操作。

可选 Scope Evidence 与 Claim Enrichment 使用同一个 Writer。每条 Claim 自有 Fact Node 与 Evidence 引用。Validation 校验 Schema、Ownership、Referential Integrity 与 Evidence Freshness；`semantic_entailment_checked` 始终为 `false`，因此 Citation Presence 不是 Truth 或 Entailment Score。Knowledge Map 不会修改或供给 Wiki Schema `2.0`、Template、Command 或 Artifact。

## 错误与安全边界

- 退出码 `2` 表示非法调用或输入，`3` 表示仓库/状态条件，`4` 表示安全的内部失败。
- stdout 始终是一个机器可读文档；stderr 只包含简短安全诊断，绝不包含源码 Evidence。
- 仓库相对输入拒绝绝对路径、Windows Drive、`..` 和符号链接逃逸。
- 损坏的 SQLite/JSON 不会被静默重写。索引和 Wiki 发布失败时保留最后有效产物。
- 网络访问不属于当前默认路径或 Vector 路径；当前 Embedding Provider 只接受本地模型文件。
