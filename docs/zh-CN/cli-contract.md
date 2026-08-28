# CLI 契约

## 目标调用方

这份契约面向 GitHub Copilot、Shell 脚本和 CI 等非交互调用方。相较于人类友好的展示，可预测的进程行为优先级更高。

## 调用方式

命令显式接收仓库路径，不能从无关父目录推断另一个仓库。相对输入路径基于当前工作目录解析，并在元数据中以规范化绝对仓库根目录返回。

功能命令支持：

```text
repo-dive <command> [repository] --format json
```

当前版本除 `--help` 和 `--version` 外，已经实现 `index`、`search`、`context`、`wiki structure`、`wiki evidence`、`wiki page`、`wiki build` 和 `wiki status`。

## RAG 命令边界

命令族分别暴露每个 RAG 阶段：

- `index`：扫描、解析、切分，并建立结构/BM25/可选向量索引。
- `search`：检索排序后的证据，并保留各通道评分。
- `context`：去重，并在调用方给定的 Token 预算下打包证据。
- `wiki`：持久化 Agent 生成的页面状态，并汇总 `.repo-dive/wiki.md`。

`index`、`search` 和 `context` 是确定性 RAG 操作。`wiki structure`、`wiki evidence`、`wiki page`、`wiki build` 和 `wiki status` 提供完整、持久且可恢复的离线 Wiki 工作流。这些命令都不会隐式调用生成模型。

`context` 命令要求正整数 Token 预算，并接受有上限的检索候选数量：

```text
repo-dive context <repository> <query> --token-budget N [--max-results COUNT] --format json|markdown
```

JSON 结果报告 `token_budget`、`estimated_tokens`、`reserved_tokens`、`estimator`、`truncated`、固定的 `duplicate`/`budget`/`low_score` 排除计数、融合参数和完整 Evidence 条目。每条 Evidence 包含稳定的 `evidence_id`、仓库相对路径、首尾都包含的行号范围、可用时的符号元数据、源码正文、评分和检索原因。

### 显式向量增强

`index`、`search` 和 `context` 接受相同的可选 Vector 参数：

```text
--embedding-model <existing-local-directory>
--vector-failure strict|degraded
```

未提供 `--embedding-model` 时，命令不会构造 Embedding Provider、导入
Sentence Transformers、增加 Vector 结果元数据，也不会改变 BM25/结构两通道
输出契约。显式提供后，`index` 保存 Provider/模型/维度身份；身份一致时只为新增
或内容变化的 Chunk 生成 Embedding，身份变化时重新生成全部 Chunk 的向量。

`strict` 是默认策略：Provider 初始化、模型身份不匹配、Embedding 或 Vector
索引错误会使命令失败，并保留此前发布的索引。`degraded` 会继续使用 BM25 与
结构检索，并返回安全的 `vector_degraded:<error-code>` 警告。Vector 结果元数据
报告状态、失败策略、不透明身份、已索引/新嵌入/复用 Chunk 数、Query Embedding
次数和安全错误码。SearchHit 始终保留 `lexical_score`、`structural_score`、
`vector_score` 与 `fused_score`；某通道未召回该 Chunk 时，对应评分为 `null`。

结构命令从显式文件读取有大小上限的 UTF-8 JSON 文档：

```text
repo-dive wiki structure <repository> --input structure.json --format json|markdown
repo-dive wiki evidence <repository> --page <page-id> --token-budget N [--max-results COUNT] --format json|markdown
repo-dive wiki page <repository> --page <page-id> --input <page.json|-> --format json|markdown
repo-dive wiki build <repository> --format json|markdown
repo-dive wiki status <repository> --format json|markdown
```

结构输入 Schema `1.0` 只接受 `schema_version`、`title`、`description`、`output_language` 和有序 `sections`。Section 只包含 `id`、`title` 和有序 `pages`；Page 只包含 `id`、`title`、`description`、`relevant_files` 和 `related_page_ids`。ID 必须唯一，关系必须指向本次提交的 Page ID，相关文件必须存在于当前已发布索引。调用方不能通过此命令注入 status、evidence、body 或 error 等生命周期字段。

重复提交相同结构时，公开文件保持字节级幂等。新页面从 `pending` 开始；修改页面标题、描述、相关文件或关系时，只把该页面重置为 `pending`，并保留旧 evidence/body/error 供诊断。仅重新排序或移动未改变的页面会保留其状态。仓库/索引身份或输出语言变化会使所有保留页面失效。

状态输出包含有序章节与页面、状态计数、正文或错误是否存在，以及每页的下一步动作，但不返回已生成正文。映射为 `pending -> collect_evidence`、`evidence_ready -> generate_page`、`generated -> complete`、`failed -> retry`。

`wiki evidence` 根据已持久化的页面标题、描述和 `path:<相关文件>` 提示确定性构造 Query。它使用与 `context` 相同的有界混合检索和完整 Chunk 上下文打包，但会先写入页面 Evidence 快照，再向 stdout 返回源码。成功后页面进入 `evidence_ready`；空 Bundle 或仓库/索引检索失败时，只把请求页面标为 `failed`，并保存安全错误码。

持久化快照记录 Query、仓库指纹、索引 Schema/build 身份、Token 账目、估算器、截断标志、检索/融合参数和生成时间；每条引用记录 Chunk ID、内容哈希、路径和首尾都包含的行号范围。Build 身份用于审计；新鲜度依据当前索引 Schema 和逐 Chunk 身份/哈希判断，因此无关索引重建不会使未受影响页面失效。页面提交与 build 校验边界会拒绝过期 Evidence。

`wiki page` 接受有界 UTF-8 JSON 文件，或通过 `--input -` 从 stdin 读取。提交 Schema `1.0` 只接受 `schema_version`、`page_id`、Markdown `body` 和非空且唯一的 `evidence_ids` 数组。命令行与输入中的 Page ID 必须一致；每个引用 ID 必须属于该页当前 Evidence 快照；快照仍须匹配已发布索引；正文最多为 200,000 个 UTF-8 字节。外层输入上限是 1,500,000 字节，避免转义后的 JSON 造成无界读取。

合法的 `evidence_ready` 页面进入 `generated`。拥有仍然有效 Evidence 快照的 `failed` 页面可以修正后重提，其他页面不会变化。完全相同的正文和引用列表重复提交时成功但不写文件；通过该命令替换已生成页面会被拒绝。结果和诊断只报告大小、数量、ID、状态和安全错误码，不回显提交正文或仓库源码。

`wiki build` 要求每个页面都是 `generated`，并且拥有正文和至少一个当前有效引用。命令基于同一个当前已发布索引视图校验全部页面 Evidence，并在写入前再次确认 build 身份。未完成页面返回 `wiki_build_incomplete`，过期页面返回 `wiki_evidence_stale`，并发索引发布返回 `index_changed_during_operation`。这些失败都会保留已有 `.repo-dive/wiki.md`；页面相关错误只包含有序 Page ID。

汇总文档保留 Section/Page 顺序，包含 Wiki 标题与描述、目录、显式稳定锚点、页面标题、调用方生成正文、相关页面链接以及带首尾行号的来源链接。锚点由 `section-` 或 `page-` 前缀加持久化 ID 的完整 SHA-256 构成。来源目标是相对于 `.repo-dive/wiki.md` 的 URL 编码路径。调用方提交的页面正文应省略由 CLI 统一生成的页面标题。CLI 把 Markdown 当作数据保存，不执行页面正文，也不承诺正文已经过 HTML 清理；把产物渲染为 HTML 的消费者必须使用可信 Markdown 渲染器和合适的 HTML 清理策略。

JSON 输出报告 `artifact_path`、UTF-8 `bytes`、`changed`、Section/Page/来源数量和 `sha256`，不返回汇总正文。Markdown 输出把完全相同的汇总文档写入 stdout；两种格式都会先遵守相同的原子产物写入。对相同状态重复 build 时不写文件，并返回 `changed: false`。

## Agent 调用示例

不需要 MCP Server。调用方 Agent 应直接执行 CLI；持久 Wiki 使用以下顺序：

```text
index -> wiki structure -> wiki evidence (Context) -> caller generates prose -> wiki page -> wiki build
```

在可恢复阶段之间运行 `wiki status`。通用 `context` 适用于临时回答；Wiki 页面
必须使用 `wiki evidence`，因为它会持久化供 `wiki page` 和 `wiki build` 校验的
Evidence 快照。

### Index 成功

<!-- contract-example:index-success -->

```bash
repo-dive index /workspace/project --format json
```

```json
{
  "schema_version": "1.0",
  "command": "index",
  "repository": "/workspace/project",
  "result": {
    "build_id": "0123456789abcdef0123456789abcdef",
    "chunks": 24,
    "deleted_files": 0,
    "files": 8,
    "index_schema_version": 4,
    "indexed_files": 8,
    "manifest_schema_version": "1.0",
    "rebuilt_files": 8,
    "relationships": 11,
    "repository_fingerprint": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "reused_files": 0,
    "skipped_files": 0,
    "symbols": 17,
    "warning_count": 0
  },
  "warnings": []
}
```

### Search 成功

<!-- contract-example:search-success -->

```bash
repo-dive search /workspace/project "build_parser" --max-results 10 --format json
```

```json
{
  "schema_version": "1.0",
  "command": "search",
  "repository": "/workspace/project",
  "result": {
    "fusion": {
      "channel_weights": {
        "lexical": 1.0,
        "structural": 1.0
      },
      "overlap_threshold": 0.8,
      "rrf_k": 60,
      "strategy": "weighted_rrf"
    },
    "hits": [
      {
        "chunk_id": "chunk:example",
        "end_line": 25,
        "fused_score": 0.03278688524590164,
        "lexical_score": 1.25,
        "path": "src/repo_dive/cli.py",
        "reasons": [
          "lexical_match:build",
          "lexical_match:parser",
          "rrf:lexical:rank=1,weight=1.000000,contribution=0.016393442623",
          "symbol_match:name_exact:repo_dive.cli.build_parser",
          "rrf:structural:rank=1,weight=1.000000,contribution=0.016393442623"
        ],
        "start_line": 12,
        "structural_score": 0.95,
        "symbol": {
          "id": "symbol:example",
          "kind": "function",
          "name": "build_parser",
          "qualified_name": "repo_dive.cli.build_parser"
        },
        "text": "def build_parser():\n    ...\n",
        "vector_score": null
      }
    ],
    "max_results": 10,
    "query": "build_parser",
    "result_count": 1
  },
  "warnings": []
}
```

### Context 成功

<!-- contract-example:context-success -->

```bash
repo-dive context /workspace/project "build_parser" --token-budget 1200 --max-results 10 --format json
```

```json
{
  "schema_version": "1.0",
  "command": "context",
  "repository": "/workspace/project",
  "result": {
    "estimated_tokens": 184,
    "estimator": "conservative_utf8_bytes_v1",
    "excluded": {
      "budget": 0,
      "duplicate": 0,
      "low_score": 0
    },
    "fusion": {
      "channel_weights": {
        "lexical": 1.0,
        "structural": 1.0
      },
      "overlap_threshold": 0.8,
      "rrf_k": 60,
      "strategy": "weighted_rrf"
    },
    "items": [
      {
        "chunk_id": "chunk:example",
        "end_line": 25,
        "estimated_tokens": 116,
        "evidence_id": "evidence:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "fused_score": 0.03278688524590164,
        "lexical_score": 1.25,
        "path": "src/repo_dive/cli.py",
        "reasons": [
          "lexical_match:build",
          "lexical_match:parser",
          "rrf:lexical:rank=1,weight=1.000000,contribution=0.016393442623",
          "symbol_match:name_exact:repo_dive.cli.build_parser",
          "rrf:structural:rank=1,weight=1.000000,contribution=0.016393442623"
        ],
        "start_line": 12,
        "structural_score": 0.95,
        "symbol": {
          "id": "symbol:example",
          "kind": "function",
          "name": "build_parser",
          "qualified_name": "repo_dive.cli.build_parser"
        },
        "text": "def build_parser():\n    ...\n",
        "vector_score": null
      }
    ],
    "max_results": 10,
    "query": "build_parser",
    "reserved_tokens": 68,
    "result_count": 1,
    "token_budget": 1200,
    "truncated": false
  },
  "warnings": []
}
```

调用方模型现在可以生成回答，但必须保留返回的路径和首尾行号作为引用。

### Wiki 文件输入与成功输出

<!-- contract-example:wiki-success -->

`structure.json`：

```json
{
  "schema_version": "1.0",
  "title": "Project Wiki",
  "description": "Grounded repository documentation.",
  "output_language": "en",
  "sections": [
    {
      "id": "guide",
      "title": "Guide",
      "pages": [
        {
          "id": "overview",
          "title": "Overview",
          "description": "Explain the CLI entrypoint.",
          "relevant_files": [
            "src/repo_dive/cli.py"
          ],
          "related_page_ids": []
        }
      ]
    }
  ]
}
```

```bash
repo-dive wiki structure /workspace/project --input structure.json --format json
repo-dive wiki evidence /workspace/project --page overview --token-budget 1200 --max-results 10 --format json
```

调用方只生成 `body`，页面标题由 CLI 统一管理。调用方把 `wiki evidence` 返回的
准确 ID 复制到 `page.json`：

```json
{
  "schema_version": "1.0",
  "page_id": "overview",
  "body": "The CLI entrypoint builds a bounded argument parser and dispatches a typed command handler.\n",
  "evidence_ids": [
    "evidence:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
  ]
}
```

```bash
repo-dive wiki page /workspace/project --page overview --input page.json --format json
```

```json
{
  "schema_version": "1.0",
  "command": "wiki page",
  "repository": "/workspace/project",
  "result": {
    "body_bytes": 92,
    "changed": true,
    "citation_count": 1,
    "evidence_ids": [
      "evidence:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    ],
    "page_id": "overview",
    "status": "generated"
  },
  "warnings": []
}
```

```bash
repo-dive wiki build /workspace/project --format json
```

```json
{
  "schema_version": "1.0",
  "command": "wiki build",
  "repository": "/workspace/project",
  "result": {
    "artifact_path": ".repo-dive/wiki.md",
    "bytes": 512,
    "changed": true,
    "page_count": 1,
    "section_count": 1,
    "sha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
    "source_count": 1
  },
  "warnings": []
}
```

### stdin 与 Markdown 输出

<!-- contract-example:stdin -->

文件输入与 stdin 使用相同的页面提交 Schema：

```bash
repo-dive wiki page /workspace/project --page overview --input page.json --format json
repo-dive wiki page /workspace/project --page overview --input - --format json < page.json
repo-dive search /workspace/project "build_parser" --max-results 10 --format markdown
```

具有代表性的 Markdown stdout 起始内容如下：

```markdown
# Repository search

- Query: "build_parser"
- Results: 1
- Fusion: weighted_rrf
```

### 错误与恢复

<!-- contract-example:error -->

JSON 模式下的命令即使失败，也会输出完整错误文档：

```json
{
  "schema_version": "1.0",
  "command": "context",
  "error": {
    "code": "index_stale",
    "message": "Repository index is stale; run `repo-dive index` first.",
    "details": {
      "build_id": "0123456789abcdef0123456789abcdef"
    }
  }
}
```

<!-- contract-example:recovery -->

解释信封之前，先检查进程退出码：

```text
0 -> consume result
2 -> correct arguments or JSON input; do not retry unchanged
3 + index_not_found/index_stale -> run index, then retry retrieval
3 + wiki_evidence_stale -> run wiki evidence again, regenerate, then submit wiki page
4 -> surface the safe diagnostic and preserve the last valid .repo-dive artifacts
```

Wiki 流程中断后，调用 `repo-dive wiki status ... --format json` 并遵循每个页面的
`next_action`。不能把 stderr 或旧的通用 `context` 响应当作持久化 Wiki Evidence。

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
