# Wiki 工作流

## 目标

Wiki 工作流把本地仓库证据转换成一个稳定的 Markdown 文档，同时不要求 CLI 持有语言模型会话。调用方 Agent 编排理解过程；`repo-dive` 负责确定性状态、证据、校验和汇总。

## 产物布局

```text
<repository>/.repo-dive/
├── wiki.md
├── wiki.json
├── metadata.json
└── index/
```

- `wiki.md`：原子汇总的当前文档。
- `wiki.json`：带版本的 Wiki 结构、页面状态、相关文件、证据引用和已生成页面正文。
- `metadata.json`：仓库身份、源码 Commit、输出语言、时间戳、Schema 版本和索引版本。
- `index/`：实现私有的关键词、向量和关系数据。

只有 `wiki.md`、`wiki.json` 和 `metadata.json` 属于公开产物契约。调用方不能依赖 `index/` 内部文件。

### 公开 JSON 状态

`wiki.json` 使用独立的 `schema_version`，并保存 `title`、`description` 和有序 `sections`。每个 Section 包含稳定 `id`、`title` 和有序 `pages`。每个页面记录：

- 稳定的 `id`、`title` 和 `description`；
- `status`、`relevant_files` 和 `related_page_ids`；
- 完整的 `evidence` 引用，包括 `evidence_id`、`chunk_id`、仓库相对 POSIX `path` 和首尾都包含的行号范围；
- 可为空的已生成 `body` 和安全 `error` 摘要。

`metadata.json` 拥有可独立演进的 `schema_version`。它记录规范化仓库身份与指纹、可选源码 Commit、输出语言、时间戳、`wiki_schema_version`、`index_schema_version` 和 `index_build_id`。

读取方拒绝不支持的产物 Schema 版本，以及缺少必填字段或包含未知字段的文档。非法或损坏 JSON 保持原始字节不变，供后续诊断。每个公开 JSON 文件都先完整序列化再原子替换；替换失败时，该文件的旧字节保持不变。

## 阶段 1：仓库清单

CLI 校验仓库根目录，应用包含/排除规则，扫描支持的文件，读取项目级文档，并记录确定性清单。隐藏的生成目录和 `.repo-dive/` 自身会被排除。

清单结果包括路径、大小、检测语言、内容指纹，以及可用时的源码 Commit。二进制或不可读文件作为跳过证据报告，不能静默当成空文本。

## 阶段 2：构建 RAG 索引

CLI 解析支持的源文件，创建与符号边界对齐的 Chunk，并建立本地 RAG 索引：

- 用于文件、符号、Import、调用、继承和包含关系的结构索引；
- 用于标识符、精确字符串、配置和领域术语的 BM25 关键词索引；
- 显式配置 Embedding Provider 后，用于语义召回的可选向量索引。

每个索引 Chunk 保留仓库相对路径、行号范围、符号元数据、内容指纹和关系。BM25 加结构检索构成离线基线；向量检索是可选增强，不是前置条件。

## 阶段 3：Wiki 结构

调用方 Agent 接收清单，并提出带版本的结构，其中包含：

- Wiki 标题和描述；
- 有序章节和页面；
- 在重新生成时保持稳定的页面 ID；
- 页面描述和关系；
- 初始相关文件候选。

CLI 校验引用，并把接受的结构持久化到 `wiki.json`。它不能自行虚构缺失页面，也不能静默修复未知文件路径。

## 阶段 4：RAG 页面证据

Agent 针对每个页面，使用页面主题和相关文件提示请求证据。RAG 检索流水线查询结构、BM25 和可选向量通道，融合候选项，移除重复或重叠 Chunk，按需扩展符号关系，然后应用明确的上下文预算。

每条证据记录仓库相对路径、可信时的行号范围、已知时的符号、各项评分以及内容指纹。在内容生成开始前，证据先与页面状态一起保存。

## 阶段 5：增强生成与持久化

调用方 Agent 使用当前模型和返回证据撰写单个 Markdown 页面。页面通过 stdin 或结构化输入文件交回 CLI。CLI 在保存前校验页面身份、证据引用、编码和大小。

每个页面可以独立重试。完成一个页面不应要求重新生成其他已完成页面。

这是 RAG 的生成阶段。它运行在调用方 Copilot 会话中，而不是 CLI 内部，因此能够复用调用方选择的模型和对话，同时证据仍然是带版本、可检查的 CLI 结果。

## 阶段 6：汇总

所有必需页面准备完成后，CLI 汇总：

1. 文档标题与生成元数据；
2. 目录；
3. 有序页面锚点和标题；
4. 相关页面链接；
5. 页面正文和来源引用。

汇总先写入同目录临时文件，校验通过后原子替换 `.repo-dive/wiki.md`。校验或替换失败时，旧文档保持完整。

## 状态模型

工作流使用显式状态：

```text
uninitialized -> inventoried -> indexed -> structured -> retrieving -> generating -> complete
                                  |           |             |             |
                                  +-----------+-------------+-> failed <--+
```

页面状态是 `pending`、`evidence_ready`、`generated` 或 `failed`。重试失败页面不会重置成功页面。源码指纹变化会把受影响证据和页面标记为过期，但不删除旧内容。

合法页面转换是显式的：

- `pending -> evidence_ready | failed`；
- `evidence_ready -> generated | failed | pending`；
- `generated -> failed | pending`；
- `failed -> pending`。

回到 `pending` 表示重试或失效；在后续命令替换正文前，可以保留旧正文供诊断。所有自转换和跨越生命周期阶段的转换都会被拒绝。

## 重新生成

重新生成时比较仓库指纹与元数据。未变化的清单和索引继续复用；变化文件使对应 Chunk 和依赖页面证据失效。稳定页面 ID 允许调用方只更新受影响内容，然后重新构建单一 Markdown 产物。

## 失败语义

- 非法仓库输入在创建产物前失败。
- 索引失败时保留旧的有效索引和 Wiki。
- 非法的 Agent 结构或页面内容以结构化诊断拒绝。
- 部分生成状态保留在 `wiki.json`，可继续执行。
- 汇总失败绝不能截断旧的 `wiki.md`。
