# Wiki 工作流

## 目标与所有权

Wiki 工作流把已经索引的本地仓库 Evidence 转换成一个稳定的 Markdown 产物，同时不让 CLI 持有语言模型会话。`repo-dive` 负责结构校验、检索、Evidence Snapshot、页面状态、引用校验和原子汇总；调用方 Agent 使用当前模型负责页面规划与内容生成。

最新索引是前置条件：

```bash
repo-dive index <repository> --format json
```

完整生成路径是 `structure -> evidence -> page -> build -> status`。`status` 也可以在任意检查点安全执行，是恢复流程的正常入口。

<!-- contract-section:commands -->
## 命令序列

```bash
repo-dive wiki structure <repository> --input structure.json --format json
repo-dive wiki status <repository> --format json
repo-dive wiki evidence <repository> --page <page-id> --token-budget 1200 --max-results 10 --format json
repo-dive wiki page <repository> --page <page-id> --input page.json --format json
repo-dive wiki page <repository> --page <page-id> --input - --format json < page.json
repo-dive wiki build <repository> --format json
repo-dive wiki status <repository> --format json
```

使用以下 Smoke 命令验证已安装的命令面，而不修改仓库：

```bash
repo-dive wiki structure --help
repo-dive wiki evidence --help
repo-dive wiki page --help
repo-dive wiki build --help
repo-dive wiki status --help
```

对每个页面重复 `evidence -> 调用模型生成 -> page`。仅当每页都是 `generated` 后执行 `build`，最后用 `status` 读取持久化摘要。`complete: true` 只表示全部页面已经生成；因为 Build 状态没有单独保存，它不能证明 `wiki.md` 已经构建。

## 产物布局

```text
<repository>/.repo-dive/
├── index -> index-generations/<build-id>
├── index-generations/<build-id>/
│   ├── index.sqlite3
│   ├── manifest.json
│   └── metadata.json
├── wiki.json
├── metadata.json
└── wiki.md
```

- `.repo-dive/wiki.json` 是严格 Schema `1.0` Wiki 结构和页面状态。
- `.repo-dive/metadata.json` 是严格 Schema `1.0` Wiki/仓库/索引身份，与代际内的索引 Metadata 不同。
- `.repo-dive/wiki.md` 只由成功的 `wiki build` 创建或替换。
- `.repo-dive/index` 是经过校验的当前索引指针。调用方可以读取已记录的 Metadata，但不能修改索引内部数据。

`wiki.json` 与根目录 Wiki Metadata 必须同时存在或同时不存在。只存在一份时命令返回 `wiki_state_incomplete`，不会猜测或修复另一份。非法 JSON、未知/缺失字段和不支持的版本会保持原始字节供诊断。

## 1. 提交结构

调用方提交无状态的结构提案，刻意不包含生命周期字段：

```json
{
  "schema_version": "1.0",
  "title": "Repository Wiki",
  "description": "Grounded local repository documentation.",
  "output_language": "en",
  "sections": [
    {
      "id": "guide",
      "title": "Guide",
      "pages": [
        {
          "id": "overview",
          "title": "Overview",
          "description": "Explain the application entrypoint.",
          "relevant_files": ["src/app.py"],
          "related_page_ids": []
        }
      ]
    }
  ]
}
```

Section 与 Page ID 必须唯一且非空。`related_page_ids` 必须引用同一提案中的页面。`relevant_files` 必须是当前索引中存在的仓库相对 POSIX 路径。未知字段、未知路径、绝对路径、`..` 和反斜杠都会被拒绝。

首次提交后每页进入 `pending`。重复应用相同结构不会写文件。只要 Title、Description、Relevant File、Relationship 和输出语言不变，稳定页面即使重排或移动 Section 也保留原状态。新页面被创建；结构变化页面、过期页面以及输出语言变化后的所有页面都会失效为 `pending`。

结果报告 `changed`、`created_page_ids`、`invalidated_page_ids`、`preserved_page_ids`、Schema 版本、数量和 Index Build 身份。

## 2. 收集并持久化 Evidence

`wiki evidence` 根据已持久化的页面 Title、Description 和 `path:<relevant-file>` Hint 构造 Query。当前命令只使用 BM25 关键词与结构通道；与 `search`、`context` 不同，它不接受或注入 Embedding Provider。因此 Vector 索引不会改变该命令当前的排序路径。

候选项通过 `weighted_rrf` 融合、重叠去重，再交给 `EvidencePacker`。只有完整且能放入 `token_budget` 的 Chunk 才会返回。CLI 先原子持久化 Evidence Reference 和 Snapshot，再把完整 Evidence 文本输出到 stdout。成功后页面进入 `evidence_ready`。

每个持久化 Evidence Reference 包含：

- `evidence_id`、`chunk_id`、`content_hash`；
- 仓库相对 POSIX `path`；
- 从 1 开始且首尾都包含的 `start_line` 与 `end_line`。

页面级 `evidence_snapshot` 包含 `query`、`repository_fingerprint`、`index_schema_version`、`index_build_id`、`token_budget`、`estimated_tokens`、`reserved_tokens`、`estimator`、`truncated`、`generated_at`，以及检索参数（`max_results`、`strategy`、`rrf_k`、`channel_weights`、`overlap_threshold`）。

收集期间发生仓库状态错误时，页面进入 `failed`，并且只保存安全错误码。非法 CLI 选项在进入收集前失败，不修改页面状态。

## 3. 生成并提交单页

调用模型接收 Evidence 结果并撰写页面正文 Markdown。它必须引用返回结果中精确 `evidence_id` 的非空子集。CLI 不生成或重写这段内容。

```json
{
  "schema_version": "1.0",
  "page_id": "overview",
  "body": "The entrypoint delegates application startup.\n",
  "evidence_ids": ["evidence:<sha256>"]
}
```

提交是严格的：只接受 `schema_version`、`page_id`、`body` 和 `evidence_ids`。正文必须是非空 UTF-8 Markdown，并处于 CLI 字节上限内。Evidence ID 必须唯一、非空、属于该页，并仍能通过 Chunk ID、哈希、路径和行号范围匹配当前索引。

合法提交把正文与 `citation_ids` 一起保存，并把页面移动到 `generated`。成功结果只报告正文字节数和引用元数据，不返回正文。重复提交完全相同的 Generated 页面不会写文件；向已生成页面提交不同内容会被拒绝。显式重新生成先再次运行 `wiki evidence`，它清除旧引用，并使用新 Snapshot 把页面恢复到 `evidence_ready`。

汇总文档拥有 Page Heading；调用方应只提供正文，不要重复该标题。

<!-- contract-section:page-state -->
## 页面状态机与 Status

不存在单独持久化的仓库级状态机。持久生命周期以页面为单位：

```text
pending -> evidence_ready
pending -> failed
evidence_ready -> generated
evidence_ready -> failed
evidence_ready -> pending
generated -> failed
generated -> pending
failed -> pending
```

自转换和跨越模型状态的转换会被拒绝。Service 操作可以在一个原子操作中组合多个合法转换；例如使用仍然有效的 Evidence 从 `failed` 重新提交修正内容时，会经过 `pending` 和 `evidence_ready`，最后持久化为 `generated`。

`wiki status` 是只读命令，不返回生成正文或已保存的错误码。它报告 Wiki/Index Schema 身份、四种状态的 Count、`complete`，并为每页报告 `status`、`next_action`、`evidence_count`、`citation_count`、`has_body` 和 `has_error`。

```text
pending        -> collect_evidence
evidence_ready -> generate_page
generated      -> complete
failed         -> retry
```

Status 只反映持久化状态；它不会重新扫描仓库或校验 Evidence 新鲜度。新鲜度由 `wiki evidence`、`wiki page` 和 `wiki build` 强制检查。

## 4. 构建 Markdown

`wiki build` 要求每页都是 `generated`，拥有正文，并至少有一项引用。随后它根据当前已发布索引校验每个引用的 Evidence，并确认汇总期间索引没有变化。

确定性 Markdown 包含 Wiki Title/Description、目录、有序 Section 与 Page Heading、相关页面链接、调用方生成的正文和来源链接。Section/Page Anchor 使用类型前缀加稳定 ID 的完整 SHA-256。Source Link 相对于 `.repo-dive/wiki.md`，并带 `#Lx` 或 `#Lx-Ly` Fragment。

所有检查通过后 Store 才原子替换 `.repo-dive/wiki.md`。失败时保留旧 Markdown。对相同状态重复构建返回 `changed: false`；`--format markdown` 返回精确的持久化文档，JSON 返回路径、字节数、SHA-256、Section/Page/Source 数量和 `changed`。

<!-- contract-section:single-page-recovery -->
## 单页恢复

每次恢复都从以下命令开始：

```bash
repo-dive wiki status <repository> --format json
```

然后只恢复受影响页面：

1. 对 `pending`，运行 `wiki evidence`，根据返回 Evidence 生成正文，再用 `wiki page` 提交。
2. 对 `evidence_ready`，直接根据已保存/当前 Evidence 结果生成并提交。
3. 对 `failed`，检查失败命令返回的错误，或 `.repo-dive/wiki.json` 中公开 Page 的 `error`：
   - 如果页面校验失败但 Evidence 仍然有效，修正 `page.json` 后直接重新提交；
   - 如果 Evidence 缺失/过期或收集失败，按需修复/重建索引，再运行 `wiki evidence` 后生成。
4. 不改动无关的 `generated` 页面。
5. 全部页面生成后运行 `wiki build`，然后运行 `wiki status`。

源码变化后先运行 `repo-dive index`。后续 Build 可能返回 `wiki_evidence_stale`，并且只列出受影响的 `page_ids`；旧 `.repo-dive/wiki.md` 保持有效且不变。只重新收集并生成这些页面。仅在 `wiki status` 中看到 `generated` 不能保证 Evidence 仍然新鲜。

如果 Evidence 收集或页面校验把页面设为 `failed`，成功恢复会清除安全 `error` 字段。旧正文或 Evidence Reference 可能保留在持久化状态中供诊断，但消费者必须遵循 `status`/`next_action`，不能把它们当作当前输出。

## 失败保证

- `index_not_found` 与 `index_stale`：运行 `repo-dive index`，再继续受影响的 Wiki 阶段。
- `wiki_not_initialized`：索引完成后提交合法结构。
- `wiki_build_incomplete`：只生成列出的页面。
- `wiki_evidence_stale`：只重新收集并生成列出的页面。
- `wiki_page_state_invalid`：遵循当前页面状态；Generated 内容不能直接覆盖。
- `wiki_state_invalid`、`wiki_metadata_invalid` 或不支持版本：保留原字节供诊断；命令不会修复。
- 原子写入或汇总失败绝不会截断旧的公开 JSON 或 Markdown 产物。
