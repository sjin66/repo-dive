# Knowledge Map 工作流

## 边界

Knowledge Map 是可选的仓库自有结构化 Artifact。CLI 确定性地推导 Fact 与 View，并且不会调用生成模型。Agent Claim 是可选内容，始终与确定性 Fact 分离。本工作流不会改变 Wiki 工作流。

## 构建与检查

索引前先在仓库内创建严格 Schema `1.0` Budget File：

```json
{
  "schema_version": "1.0",
  "node_budget": 10000,
  "edge_budget": 30000,
  "contributing_relationship_ids_per_edge": 32,
  "resolution_candidates_per_reference": 8,
  "cluster_budget": 1000,
  "minimum_cluster_files": 2,
  "flow_budget": 100,
  "flow_depth": 5,
  "nodes_per_flow": 30,
  "edges_per_flow": 29,
  "tour_budget": 100,
  "evidence_snapshots": 200,
  "evidence_references_per_snapshot": 128,
  "enrichment_records": 1000,
  "records_per_scope": 32,
  "claims_per_record": 32,
  "fact_node_ids_per_claim": 32,
  "related_node_ids_per_claim": 32,
  "evidence_ids_per_claim": 16,
  "enrichment_input_bytes": 1000000
}
```

每个字段都必填且为正数。`--source-fact-budget` 与 Derivation 字段影响 Deterministic Identity；Evidence/Enrichment 字段是 Semantic Capacity；`--artifact-byte-budget` 约束完整序列化 Artifact。

然后运行：

```text
repo-dive index <repository> --format json
repo-dive map build <repository> --source-fact-budget 10000 --artifact-byte-budget 5000000 --budget-file map-budgets.json --format json
repo-dive map show <repository> --view architecture --max-results 50 --format json
repo-dive map show <repository> --view flows --max-results 50 --format json
repo-dive map show <repository> --view tour --max-results 50 --format json
repo-dive map validate <repository> --format json
```

相同 Build 是不写入的成功操作。Index 或 Derivation Budget 发生变化时会创建新的 Deterministic Revision，并清空 Semantic State。只有当前所有值仍符合限制时，Capacity 变化才保留语义。

## 可选 Evidence 与 Enrichment

从持久化 Scope Contract 或有界 View 中选择 `scope_id`，收集 Evidence，让调用 Agent 生成一份严格 Claim Submission，然后校验：

```text
repo-dive map evidence <repository> --scope <scope-id> --token-budget 12000 --format json
repo-dive map enrich <repository> --input enrichment.json --format json
repo-dive map validate <repository> --format json
```

每条 Claim 独立拥有非空 `fact_node_ids` 和 `evidence_ids`；`related_node_ids` 可以为空。Submission 的 `expected_artifact_revision` 防止 Correction 覆盖并发工作。即使不相关 Scope 推进了 Artifact Revision，相同 Scope Content 的重放仍是不写入操作。

Validation 校验 Schema、当前 Reference、Scope Ownership 与 Evidence Freshness。它返回 `semantic_entailment_checked: false`：Citation 不能证明 Claim Text 为真或被 Evidence 蕴含。

## Reset 与恢复

引用的 Evidence 必须变化时，只 Reset 对应 Scope 并重新收集：

```text
repo-dive map reset <repository> --scope <scope-id> --format json
repo-dive map evidence <repository> --scope <scope-id> --token-budget 12000 --format json
```

遇到 `index_not_found` 或 `index_stale` 时重新索引。遇到 `knowledge_map_not_found` 或 `knowledge_map_stale` 时构建 Map。遇到 `knowledge_map_locked` 时等待当前 Writer。遇到 `knowledge_map_revision_conflict` 时重新加载当前状态并重新生成预期 Replacement。任何 Writer 失败都会保留最后有效的 `.repo-dive/knowledge-map.json` 字节。

## Wiki 独立性

Version 1 的 Knowledge Map 没有 Wiki Projection。发布 Wiki 时继续使用 `wiki classify -> wiki init -> wiki evidence -> calling Agent generation -> wiki page -> wiki validate -> wiki build`。通用 Map Evidence 不能替代持久化 Wiki Evidence。
