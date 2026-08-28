# CLI 契约

## 目标调用方

这份契约面向 GitHub Copilot、Shell 脚本和 CI 等非交互调用方。相较于人类友好的展示，可预测的进程行为优先级更高。

## 调用方式

命令显式接收仓库路径，不能从无关父目录推断另一个仓库。相对输入路径基于当前工作目录解析，并在元数据中以规范化绝对仓库根目录返回。

功能命令支持：

```text
repo-dive <command> [repository] --format json
```

当前版本除 `--help` 和 `--version` 外，已经实现 `index`、`search`、`context`、`wiki structure`、`wiki evidence` 和 `wiki status`。

## RAG 命令边界

命令族分别暴露每个 RAG 阶段：

- `index`：扫描、解析、切分，并建立结构/BM25/可选向量索引。
- `search`：检索排序后的证据，并保留各通道评分。
- `context`：去重，并在调用方给定的 Token 预算下打包证据。
- `wiki`：持久化 Agent 生成的页面状态，并汇总 `.repo-dive/wiki.md`。

`index`、`search` 和 `context` 是当前可用的确定性 RAG 操作。`wiki structure`、`wiki evidence` 和 `wiki status` 提供持久、可恢复的 Wiki 状态；页面提交与最终汇总仍属于后续计划。这些命令都不会隐式调用生成模型。

`context` 命令要求正整数 Token 预算，并接受有上限的检索候选数量：

```text
repo-dive context <repository> <query> --token-budget N [--max-results COUNT] --format json|markdown
```

JSON 结果报告 `token_budget`、`estimated_tokens`、`reserved_tokens`、`estimator`、`truncated`、固定的 `duplicate`/`budget`/`low_score` 排除计数、融合参数和完整 Evidence 条目。每条 Evidence 包含稳定的 `evidence_id`、仓库相对路径、首尾都包含的行号范围、可用时的符号元数据、源码正文、评分和检索原因。

结构命令从显式文件读取有大小上限的 UTF-8 JSON 文档：

```text
repo-dive wiki structure <repository> --input structure.json --format json|markdown
repo-dive wiki evidence <repository> --page <page-id> --token-budget N [--max-results COUNT] --format json|markdown
repo-dive wiki status <repository> --format json|markdown
```

结构输入 Schema `1.0` 只接受 `schema_version`、`title`、`description`、`output_language` 和有序 `sections`。Section 只包含 `id`、`title` 和有序 `pages`；Page 只包含 `id`、`title`、`description`、`relevant_files` 和 `related_page_ids`。ID 必须唯一，关系必须指向本次提交的 Page ID，相关文件必须存在于当前已发布索引。调用方不能通过此命令注入 status、evidence、body 或 error 等生命周期字段。

重复提交相同结构时，公开文件保持字节级幂等。新页面从 `pending` 开始；修改页面标题、描述、相关文件或关系时，只把该页面重置为 `pending`，并保留旧 evidence/body/error 供诊断。仅重新排序或移动未改变的页面会保留其状态。仓库/索引身份或输出语言变化会使所有保留页面失效。

状态输出包含有序章节与页面、状态计数、正文或错误是否存在，以及每页的下一步动作，但不返回已生成正文。映射为 `pending -> collect_evidence`、`evidence_ready -> generate_page`、`generated -> complete`、`failed -> retry`。

`wiki evidence` 根据已持久化的页面标题、描述和 `path:<相关文件>` 提示确定性构造 Query。它使用与 `context` 相同的有界混合检索和完整 Chunk 上下文打包，但会先写入页面 Evidence 快照，再向 stdout 返回源码。成功后页面进入 `evidence_ready`；空 Bundle 或仓库/索引检索失败时，只把请求页面标为 `failed`，并保存安全错误码。

持久化快照记录 Query、仓库指纹、索引 Schema/build 身份、Token 账目、估算器、截断标志、检索/融合参数和生成时间；每条引用记录 Chunk ID、内容哈希、路径和首尾都包含的行号范围。Build 身份用于审计；新鲜度依据当前索引 Schema 和逐 Chunk 身份/哈希判断，因此无关索引重建不会使未受影响页面失效。页面提交与 build 校验边界会拒绝过期 Evidence。

## 标准流

### JSON 模式

- `stdout` 只包含一个 UTF-8 JSON 文档。
- 文档以一个换行符结尾。
- 进度、警告和诊断输出到 `stderr`。
- 禁止 ANSI 转义序列。
- 不能输出不完整 JSON；必须先构造完整结果再写出。

### Markdown 模式

显式返回 Markdown 的命令可以把原始 UTF-8 Markdown 写入 `stdout`，诊断信息仍然写入 `stderr`。

## 结果信封

JSON 命令使用以下顶层结构：

```json
{
  "schema_version": "1.0",
  "command": "context",
  "repository": "/absolute/path/to/repository",
  "result": {},
  "warnings": []
}
```

JSON 模式下的错误在 `stdout` 输出完整错误信封，同时在 `stderr` 输出供人阅读的诊断：

```json
{
  "schema_version": "1.0",
  "command": "context",
  "error": {
    "code": "repository_not_found",
    "message": "Repository path does not exist."
  }
}
```

错误码是稳定的机器标识；错误消息可以改进，而不要求升级 Schema 版本。

## 退出码

| 代码 | 含义 |
|---:|---|
| `0` | 命令成功完成。 |
| `2` | 调用、选项或输入 Schema 校验失败。 |
| `3` | 仓库或请求的仓库数据不可用。 |
| `4` | 合法调用后的内部操作失败。 |

信号和平台级故障可以使用表格之外的常规 Shell 退出码。

## 证据位置

路径统一使用仓库相对的 POSIX 字符串，包括 Windows。行号从 1 开始并包含首尾行：

```json
{
  "path": "src/repo_dive/cli.py",
  "start_line": 12,
  "end_line": 25,
  "symbol": "build_parser"
}
```

无法确认可信行号范围时，同时省略两个行号字段，不能猜测。

## 预算

可能返回仓库内容的命令必须提供 `--token-budget` 或 `--max-results` 等明确限制。响应要报告实际预算、估算用量以及证据是否被截断。上下文预算在接纳完整源码正文前，先为稳定信封和条目元数据预留空间；不能通过截断 Evidence 行号范围来挤入预算。

## 幂等性与写入

只读命令不能产生仓库副作用。索引和 Wiki 命令只能写入 `<repository>/.repo-dive/`。仓库状态和参数相同时，重复执行产生等价的结构化输出，时间戳和耗时字段除外。

写入使用同目录临时文件和原子替换。失败命令不能暴露只写了一半的 JSON 或 Markdown 产物。

## 兼容性

新增可选字段属于向后兼容。字段重命名或删除、类型变化、退出码语义变化以及产物路径变化，都要求升级 Schema 或命令版本。
