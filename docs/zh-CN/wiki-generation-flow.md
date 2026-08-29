下面是当前 `repo-dive` 从安装 Skill、建立索引、规划结构、逐页检索 Evidence、Agent 生成正文，到最终构建 `wiki.md` 的完整流程。

## 总览

```text
安装 wiki Skill
    ↓
Agent 激活 wiki Skill
    ↓
预检 CLI、仓库和工作树
    ↓
repo-dive index
    ↓
Agent 规划 Wiki 结构
    ↓
repo-dive wiki structure
    ↓
对每个页面循环：
    repo-dive wiki evidence
        ↓
    Agent 根据 Evidence 生成 Markdown
        ↓
    repo-dive wiki page
    ↓
repo-dive wiki status
    ↓
repo-dive wiki build
    ↓
<repository>/.repo-dive/wiki.md
```

这套流程有一个明确边界：

| 参与者 | 职责 |
|---|---|
| `repo-dive` CLI | 扫描、解析、索引、检索、状态管理、引用校验、Evidence 新鲜度、Markdown 汇总 |
| 调用 Agent | 规划 Wiki 结构、调用当前模型生成页面正文、选择引用、处理恢复流程 |
| `wiki` Skill | 告诉 Agent 应按什么顺序调用 CLI，以及每一步应遵守哪些规则 |

CLI 不会自行调用生成模型。

---

# 1. 安装 Wiki Skill

在目标仓库中运行：

```bash
repo-dive init
```

TTY 终端会显示五个平台供多选：

```text
1. Claude Code
2. OpenAI Codex CLI
3. OpenCode
4. Gemini CLI
5. GitHub Copilot
```

也可以非交互安装：

```bash
repo-dive init . \
  --agent claude-code \
  --agent codex \
  --agent opencode \
  --agent gemini-cli \
  --agent github-copilot \
  --format json
```

安装位置：

| Agent | Skill 位置 |
|---|---|
| Claude Code | `.claude/skills/wiki` |
| Codex | `.agents/skills/wiki` |
| OpenCode | `.agents/skills/wiki` |
| Gemini CLI | `.agents/skills/wiki` |
| GitHub Copilot | `.agents/skills/wiki` |

后四个平台共享同一个安装目录，不会重复写四份。

这一步只安装 Skill，不生成 Wiki，也不建立索引。

---

# 2. Agent 激活 Skill

用户可以自然语言触发：

```text
为当前仓库生成一份中文 Wiki。
```

也可以使用 Agent 对应的显式调用方式：

| Agent | 常见调用方式 |
|---|---|
| Claude Code | `/wiki` |
| Codex | `$wiki` 或 `/skills` |
| OpenCode | 加载 `wiki` Skill |
| Gemini CLI | 激活 `wiki` Skill |
| GitHub Copilot | `/wiki` |

Skill 的核心编排规则位于：

```text
skills/wiki/SKILL.md
```

详细输入、恢复和错误契约位于：

```text
skills/wiki/references/workflow-contract.md
```

---

# 3. 预检阶段

Agent 首先执行预检，不直接开始生成。

## 3.1 确定仓库

默认使用当前工作区根目录。

如果用户传入的是 URL，Skill 不会自动克隆：

```text
https://github.com/example/project
```

必须先获得用户明确授权，才能执行克隆。

## 3.2 检查 CLI

Agent 会检查：

```bash
command -v repo-dive
repo-dive --version
repo-dive wiki --help
```

如果 CLI 不存在，Agent 停止执行并提示安装，不会静默下载软件。

## 3.3 检查工作树

```bash
git status --short
```

目的是记录并保护用户已有修改。生成 Wiki 不应该覆盖或回滚用户的代码。

## 3.4 决定索引范围

Agent会考虑排除高噪声目录，例如：

```text
node_modules/
.venv/
dist/
build/
generated/
vendor/
.repo-dive/
```

是否排除测试取决于 Wiki 目标。如果 Wiki 需要解释真实行为和验证方式，测试代码通常应该保留。

预检要求见 `skills/wiki/SKILL.md:21-32`。

---

# 4. 建立仓库索引

## 4.1 命令

```bash
repo-dive index <repository> \
  --exclude "node_modules/**" \
  --exclude ".venv/**" \
  --format json
```

完整参数包括：

```bash
repo-dive index <repository> \
  [--include <glob>]... \
  [--exclude <glob>]... \
  [--max-file-size <bytes>] \
  [--max-chunk-lines <lines>] \
  [--embedding-model <local-model-directory>] \
  [--vector-failure strict|degraded] \
  --format json
```

默认值：

| 参数 | 默认值 |
|---|---:|
| `max-file-size` | 1,000,000 bytes |
| `max-chunk-lines` | 200 |
| 向量模型 | 不启用 |

## 4.2 索引处理过程

```text
扫描仓库文件
    ↓
读取并分类文件
    ↓
Python AST / Tree-sitter / 文本解析
    ↓
切分为 Chunk
    ↓
提取 Symbol 和 Relationship
    ↓
建立 BM25 索引
    ↓
建立结构关系索引
    ↓
可选建立 Vector 索引
    ↓
写入临时 SQLite
    ↓
完整性校验
    ↓
原子发布当前 Index Generation
```

索引包含：

- 文件记录
- Chunk
- Symbol
- Import、Call、Inheritance、Contains 等关系
- BM25 Posting 和统计
- 可选 float32 Vector

## 4.3 索引文件

```text
<repository>/.repo-dive/
├── index -> index-generations/<build-id>
└── index-generations/
    └── <build-id>/
        ├── index.sqlite3
        ├── manifest.json
        └── metadata.json
```

`.repo-dive/index` 是指向当前有效索引代际的符号链接。

新索引会先完整构建，再原子切换指针。构建失败不会破坏旧索引。

## 4.4 成功结果

结果大致如下：

```json
{
  "schema_version": "1.0",
  "command": "index",
  "repository": "/absolute/project",
  "result": {
    "build_id": "abc123",
    "files": 120,
    "indexed_files": 115,
    "skipped_files": 5,
    "chunks": 850,
    "symbols": 430,
    "relationships": 970,
    "reused_files": 0,
    "rebuilt_files": 120
  },
  "warnings": []
}
```

Agent 必须检查退出码为 `0` 后才能继续。

## 4.5 索引新鲜度

后续 Wiki 命令会重新扫描仓库，并使用原来的 Include/Exclude 参数计算仓库指纹。

如果索引后又向仓库中写入 `structure.json` 或 `page.json`，可能导致：

```text
index_stale
```

因此 Skill 要求把这些编排输入放到仓库外的临时目录。

---

# 5. Agent 规划 Wiki 结构

索引成功后，Agent 根据仓库文档、目录结构、入口代码、模块边界和用户要求规划 Wiki。

CLI 不会自动决定页面数量，也不会固定使用某套模板。

Agent 需要决定：

- Wiki 标题
- Wiki 描述
- 输出语言
- Section
- Page
- 稳定 Section ID
- 稳定 Page ID
- 页面描述
- 页面相关文件
- 页面之间的关系

## 5.1 `structure.json`

```json
{
  "schema_version": "1.0",
  "title": "Repo Dive 项目 Wiki",
  "description": "面向开发者的架构与实现文档。",
  "output_language": "zh-CN",
  "sections": [
    {
      "id": "foundations",
      "title": "基础",
      "pages": [
        {
          "id": "overview",
          "title": "项目概览",
          "description": "解释项目目标、边界、核心模块和主要工作流。",
          "relevant_files": [
            "README.md",
            "src/repo_dive/cli.py"
          ],
          "related_page_ids": [
            "architecture"
          ]
        },
        {
          "id": "architecture",
          "title": "系统架构",
          "description": "解释扫描、解析、索引、检索、Context 和 Wiki 的依赖关系。",
          "relevant_files": [
            "src/repo_dive/indexing/service.py",
            "src/repo_dive/retrieval/service.py",
            "src/repo_dive/wiki/service.py"
          ],
          "related_page_ids": [
            "overview"
          ]
        }
      ]
    }
  ]
}
```

## 5.2 结构校验

CLI 强制检查：

- `schema_version` 必须为 `"1.0"`
- 至少存在一个 Section
- 每个 Section 至少存在一个 Page
- Section ID 唯一
- Page ID 全局唯一
- ID、标题、描述不能为空
- `related_page_ids` 必须指向当前结构内的页面
- 页面不能关联自身
- `relevant_files` 必须是当前索引中的文件
- 路径必须是仓库相对 POSIX 路径
- 禁止绝对路径
- 禁止 `..`
- 禁止反斜杠
- 禁止未知字段

CLI 可以验证文件是否存在，但不能判断 Agent 选择的文件是否真的最相关。

---

# 6. 提交 Wiki 结构

## 6.1 命令

```bash
repo-dive wiki structure <repository> \
  --input /tmp/repo-dive-structure.json \
  --format json
```

`structure` 当前只接受文件路径，不接受 stdin。

## 6.2 首次提交行为

首次提交会创建：

```text
<repository>/.repo-dive/wiki.json
<repository>/.repo-dive/metadata.json
```

所有页面初始状态为：

```text
pending
```

成功结果示例：

```json
{
  "schema_version": "1.0",
  "command": "wiki structure",
  "repository": "/absolute/project",
  "result": {
    "changed": true,
    "created_page_ids": [
      "overview",
      "architecture"
    ],
    "invalidated_page_ids": [],
    "preserved_page_ids": [],
    "section_count": 1,
    "page_count": 2,
    "wiki_schema_version": "1.0",
    "metadata_schema_version": "1.0",
    "index_schema_version": 4,
    "index_build_id": "abc123"
  },
  "warnings": []
}
```

## 6.3 重复提交

完全相同的结构会返回：

```json
{
  "changed": false
}
```

不会更新状态或重写文件。

如果只调整 Section 顺序、Page 顺序或把页面移动到另一个 Section，只要页面定义没有改变，页面状态可以保留。

以下变化会让页面失效并回到 `pending`：

- 标题变化
- 描述变化
- `relevant_files` 变化
- `related_page_ids` 变化
- 输出语言变化
- 页面使用的 Evidence 已过期

输出语言变化会使全部页面失效。

---

# 7. Wiki 持久状态

## 7.1 页面状态

```text
pending
evidence_ready
generated
failed
```

状态机如下：

```text
pending
  ├── evidence 成功 ───────────────→ evidence_ready
  └── evidence 仓库错误 ──────────→ failed

evidence_ready
  ├── page 成功 ──────────────────→ generated
  ├── page 内容校验失败 ──────────→ failed
  └── 重新收集 Evidence ──────────→ pending → evidence_ready

generated
  ├── 重新收集 Evidence ──────────→ pending → evidence_ready
  ├── 结构变化或 Evidence 失效 ───→ pending
  └── 仓库错误 ──────────────────→ failed

failed
  ├── 重新收集 Evidence ──────────→ pending → evidence_ready
  └── 修正页面提交 ───────────────→ pending → evidence_ready → generated
```

允许转换定义在 `src/repo_dive/wiki/models.py:17-33`。

## 7.2 `wiki.json`

页面状态会持久化到：

```json
{
  "id": "architecture",
  "title": "系统架构",
  "description": "解释核心模块和数据流。",
  "status": "pending",
  "relevant_files": [
    "src/repo_dive/wiki/service.py"
  ],
  "related_page_ids": [],
  "evidence": [],
  "evidence_snapshot": null,
  "citation_ids": [],
  "body": null,
  "error": null
}
```

这个文件是可恢复工作流的核心。

---

# 8. 获取当前状态

Agent 通常在结构提交后或恢复任务时执行：

```bash
repo-dive wiki status <repository> --format json
```

结果示例：

```json
{
  "complete": false,
  "counts": {
    "pending": 2,
    "evidence_ready": 0,
    "generated": 0,
    "failed": 0
  },
  "sections": [
    {
      "id": "foundations",
      "title": "基础",
      "pages": [
        {
          "id": "architecture",
          "title": "系统架构",
          "status": "pending",
          "next_action": "collect_evidence",
          "evidence_count": 0,
          "citation_count": 0,
          "has_body": false,
          "has_error": false
        }
      ]
    }
  ]
}
```

状态到下一步的映射：

| 状态 | `next_action` |
|---|---|
| `pending` | `collect_evidence` |
| `evidence_ready` | `generate_page` |
| `generated` | `complete` |
| `failed` | `retry` |

需要注意：

- `status` 是只读操作。
- `status` 不重新扫描仓库。
- `status` 不检查 Evidence 是否仍然新鲜。
- `complete: true` 只表示所有页面状态为 `generated`。
- `complete: true` 不证明 `wiki.md` 已经执行过 Build。

---

# 9. 为单个页面收集 Evidence

对于 `pending` 页面，Agent 执行：

```bash
repo-dive wiki evidence <repository> \
  --page architecture \
  --token-budget 8000 \
  --max-results 40 \
  --format json
```

参数约束：

| 参数 | 约束 |
|---|---|
| `--page` | 必须是当前结构内的 Page ID |
| `--token-budget` | 必须是正整数 |
| `--max-results` | 1 到 50，默认 10 |
| `--format json` | Agent 自动化应显式传入 |

## 9.1 查询构造

CLI 根据页面定义构造 Query：

```text
<页面标题>
<页面描述>
path:<relevant-file-1>
path:<relevant-file-2>
```

例如：

```text
系统架构
解释扫描、索引、检索和 Wiki 的模块关系。
path:src/repo_dive/indexing/service.py
path:src/repo_dive/wiki/service.py
```

`path:` 当前只是检索提示，不是硬路径过滤器。因此结果可能包含其他相关文件。

## 9.2 实际检索通道

当前 `wiki evidence` 使用：

```text
BM25 关键词检索
+ 结构符号与关系检索
+ Weighted RRF 融合
+ 重叠去重
+ Token Budget 打包
```

当前不使用向量通道，即使索引中已经存在 Vector。

默认融合参数：

| 参数 | 值 |
|---|---:|
| 策略 | `weighted_rrf` |
| `rrf_k` | 60 |
| BM25 权重 | 1.0 |
| 结构权重 | 1.0 |
| 向量权重 | 0.0 |
| 重叠阈值 | 0.8 |

这和通用 `search`、`context` 不同。通用命令可以传入 `--embedding-model` 使用向量检索，但 `wiki evidence` 当前没有这个参数。

## 9.3 EvidencePacker

候选结果进入预算打包器。

Packer 保证：

- 只返回完整 Chunk
- 不从中间截断源码
- 总估算 Token 不超过预算
- 默认限制单个文件占用过多结果
- 对重叠 Chunk 去重
- 保留路径和行号
- 生成稳定 Evidence ID

排除原因包括：

```text
duplicate
budget
low_score
```

如果预算太小，连一个完整 Chunk 都放不下，会返回：

```text
wiki_evidence_empty
```

Agent 不得在没有 Evidence 时虚构引用。

## 9.4 Evidence 输出

结果大致如下：

```json
{
  "page_id": "architecture",
  "status": "evidence_ready",
  "query": "系统架构\n解释核心模块。\npath:src/repo_dive/wiki/service.py",
  "token_budget": 8000,
  "estimated_tokens": 3150,
  "reserved_tokens": 120,
  "truncated": false,
  "result_count": 8,
  "max_results": 40,
  "excluded": {
    "duplicate": 2,
    "budget": 0,
    "low_score": 3
  },
  "fusion": {
    "strategy": "weighted_rrf",
    "rrf_k": 60,
    "channel_weights": {
      "lexical": 1.0,
      "structural": 1.0
    },
    "overlap_threshold": 0.8
  },
  "repository_fingerprint": "...",
  "index_schema_version": 4,
  "index_build_id": "abc123",
  "generated_at": "...",
  "items": [
    {
      "evidence_id": "evidence:...",
      "chunk_id": "chunk:...",
      "content_hash": "...",
      "path": "src/repo_dive/wiki/service.py",
      "start_line": 263,
      "end_line": 363,
      "estimated_tokens": 850,
      "text": "完整源码 Chunk...",
      "symbol": {
        "id": "symbol:...",
        "kind": "method",
        "name": "collect_evidence",
        "qualified_name": "WikiService.collect_evidence"
      },
      "lexical_score": 2.14,
      "structural_score": 1.0,
      "vector_score": null,
      "fused_score": 0.0325,
      "reasons": []
    }
  ]
}
```

## 9.5 Evidence 持久化

CLI 不只是把 Evidence 输出到 stdout，还会把引用和 Snapshot 写入 `wiki.json`：

```json
{
  "status": "evidence_ready",
  "evidence": [
    {
      "evidence_id": "evidence:...",
      "chunk_id": "chunk:...",
      "path": "src/repo_dive/wiki/service.py",
      "start_line": 263,
      "end_line": 363,
      "content_hash": "..."
    }
  ],
  "evidence_snapshot": {
    "query": "...",
    "repository_fingerprint": "...",
    "index_schema_version": 4,
    "index_build_id": "abc123",
    "token_budget": 8000,
    "estimated_tokens": 3150,
    "reserved_tokens": 120,
    "truncated": false,
    "retrieval": {
      "max_results": 40,
      "strategy": "weighted_rrf",
      "rrf_k": 60,
      "channel_weights": {
        "lexical": 1.0,
        "structural": 1.0
      },
      "overlap_threshold": 0.8
    },
    "generated_at": "..."
  }
}
```

因此通用 `repo-dive context` 不能替代 `wiki evidence`。通用 Context 不会建立页面级持久 Snapshot。

---

# 10. Agent 根据 Evidence 生成正文

这是 CLI 与生成模型的边界。

CLI 已经完成：

```text
扫描
索引
检索
融合
去重
预算选择
Evidence 持久化
```

Agent 接下来使用当前模型，根据 `items` 生成页面 Markdown。

Agent 应遵守：

- 只使用当前页面返回的 Evidence。
- 不使用其他页面的 Evidence ID。
- 不自行构造 Evidence ID。
- 不重复页面标题。
- 解释设计意图和权衡，而不是只复述语法。
- 图表必须有 Evidence 支持。
- 引用只选择真正支持正文的 Evidence。

CLI 能验证引用是否合法，但不能验证正文每一句话是否真的被 Evidence 支持。

例如 Agent 即使写了存在幻觉的正文，同时附上合法 Evidence ID，CLI 也无法进行语义事实判断。

---

# 11. 构造页面提交

Agent 生成：

```json
{
  "schema_version": "1.0",
  "page_id": "architecture",
  "body": "该系统将扫描、解析、索引和 Wiki 汇总分成独立阶段……\n",
  "evidence_ids": [
    "evidence:abc...",
    "evidence:def..."
  ]
}
```

严格要求恰好四个字段：

```text
schema_version
page_id
body
evidence_ids
```

正文约束：

- 去除空白后不能为空
- 必须能编码为 UTF-8
- 不能包含 NUL
- 最大 200,000 UTF-8 bytes
- 不应重复 Page Heading

Evidence ID 约束：

- 列表不能为空
- ID 必须唯一
- ID 必须来自该页面当前 Snapshot
- ID 不得包含首尾空白
- ID 必须仍然对应当前索引中的 Chunk

---

# 12. 提交单个页面

## 12.1 文件输入

```bash
repo-dive wiki page <repository> \
  --page architecture \
  --input /tmp/architecture-page.json \
  --format json
```

## 12.2 stdin 输入

```bash
repo-dive wiki page <repository> \
  --page architecture \
  --input - \
  --format json < /tmp/architecture-page.json
```

## 12.3 CLI 校验顺序

CLI 会检查：

1. Wiki 是否已初始化。
2. `--page` 是否存在。
3. JSON 中的 `page_id` 是否与 `--page` 一致。
4. 页面状态是否允许提交。
5. 页面是否有完整 Evidence Snapshot。
6. Evidence 是否仍然新鲜。
7. 正文是否合法。
8. `evidence_ids` 是否属于当前页面。
9. 页面是否已经生成。

页面为 `pending` 时直接提交会返回：

```text
wiki_page_state_invalid
```

页面必须先进入：

```text
evidence_ready
```

## 12.4 已生成页面的幂等性

如果页面已经是 `generated`，再次提交完全相同的正文和 Evidence IDs：

```json
{
  "changed": false
}
```

不会重写文件。

如果正文或 Evidence IDs 不同，CLI 拒绝覆盖：

```text
wiki_page_state_invalid
```

要重新生成，必须先重新执行：

```bash
repo-dive wiki evidence ...
```

这会把页面重新带回：

```text
generated → pending → evidence_ready
```

## 12.5 成功输出

```json
{
  "page_id": "architecture",
  "status": "generated",
  "changed": true,
  "body_bytes": 5240,
  "citation_count": 4,
  "evidence_ids": [
    "evidence:abc...",
    "evidence:def..."
  ]
}
```

成功结果不会回显正文。

---

# 13. 对所有页面顺序循环

Agent 对每个 Page 执行：

```text
wiki evidence
    ↓
Agent 生成 Markdown
    ↓
wiki page
```

伪代码如下：

```text
for page in structure.pages:
    if page.status == pending:
        evidence = repo-dive wiki evidence(page)
        body = current_agent_model.generate(evidence.items)
        repo-dive wiki page(page, body, evidence_ids)

    if page.status == evidence_ready:
        body = current_agent_model.generate(saved_evidence)
        repo-dive wiki page(page, body, evidence_ids)

    if page.status == generated:
        skip

    if page.status == failed:
        recover based on error
```

这些写操作不能并发执行，因为每次都会更新共享的：

```text
.repo-dive/wiki.json
.repo-dive/metadata.json
```

当前 Skill 明确要求顺序执行，见 `skills/wiki/SKILL.md:49-60`。

---

# 14. Evidence 新鲜度校验

页面提交和 Build 都会重新校验 Evidence。

以下任一变化会使 Evidence 过期：

- Chunk 已不存在
- Chunk ID 不匹配
- Chunk 内容哈希变化
- 文件路径变化
- 起始行变化
- 结束行变化
- Evidence Snapshot 缺失
- Index Schema 版本变化

校验逻辑位于 `src/repo_dive/wiki/validation.py:33-72`。

需要注意：新鲜度不是简单比较 Build ID。

重新索引后，如果某个 Evidence 对应的：

```text
Chunk ID
内容哈希
路径
行号范围
```

仍然完全一致，该 Evidence 可以继续有效。

---

# 15. 检查所有页面状态

```bash
repo-dive wiki status <repository> --format json
```

目标结果：

```json
{
  "complete": true,
  "counts": {
    "pending": 0,
    "evidence_ready": 0,
    "generated": 8,
    "failed": 0
  }
}
```

这表示所有页面正文都已提交，但还不表示最终 `wiki.md` 已构建。

---

# 16. 构建最终 Wiki

## 16.1 命令

```bash
repo-dive wiki build <repository> --format json
```

## 16.2 强制前置条件

Build 要求：

- 所有页面状态为 `generated`
- 每页有正文
- 每页至少一个 Citation
- 当前索引有效
- 所有 Evidence 未过期
- Build 期间索引没有切换

如果存在未生成页面：

```json
{
  "error": {
    "code": "wiki_build_incomplete",
    "details": {
      "page_ids": [
        "architecture",
        "retrieval"
      ]
    }
  }
}
```

如果 Evidence 过期：

```json
{
  "error": {
    "code": "wiki_evidence_stale",
    "details": {
      "page_ids": [
        "retrieval"
      ]
    }
  }
}
```

Build 失败不会覆盖旧的 `wiki.md`。

## 16.3 Markdown 汇总内容

最终文档按结构顺序包含：

```text
# Wiki Title

Wiki Description

## Contents

Section/Page 目录

## Section

### Page

Agent 生成的正文

#### Related pages

#### Sources
```

Source 会转换成带行号的相对链接：

```markdown
- [src/repo_dive/wiki/service.py:263-363](../src/repo_dive/wiki/service.py#L263-L363)
```

Section 和 Page Anchor 使用稳定 ID 的 SHA-256：

```text
section-<sha256(section-id)>
page-<sha256(page-id)>
```

因此页面重排不会改变页面 Anchor。

## 16.4 Build 输出

```json
{
  "artifact_path": ".repo-dive/wiki.md",
  "bytes": 48210,
  "changed": true,
  "page_count": 8,
  "section_count": 3,
  "source_count": 34,
  "sha256": "..."
}
```

最终文件：

```text
<repository>/.repo-dive/wiki.md
```

重复执行相同 Build：

```json
{
  "changed": false,
  "sha256": "与上次相同"
}
```

---

# 17. 最终产物布局

完整 `.repo-dive/` 大致如下：

```text
.repo-dive/
├── index -> index-generations/<build-id>
├── index-generations/
│   └── <build-id>/
│       ├── index.sqlite3
│       ├── manifest.json
│       └── metadata.json
├── wiki.json
├── metadata.json
└── wiki.md
```

各文件职责：

| 文件 | 职责 |
|---|---|
| `index.sqlite3` | Chunk、Symbol、关系、BM25、可选 Vector |
| Index `manifest.json` | 索引参数、文件身份、Build ID、仓库指纹 |
| Index `metadata.json` | 当前索引代际元数据 |
| 根级 `wiki.json` | Wiki 结构、页面状态、Evidence、正文、引用 |
| 根级 `metadata.json` | Wiki 与仓库、索引的身份绑定 |
| `wiki.md` | 最终稳定公开文档 |

---

# 18. 中断恢复流程

每次恢复先执行：

```bash
repo-dive wiki status <repository> --format json
```

恢复矩阵：

| 页面状态 | 操作 |
|---|---|
| `pending` | 运行 `wiki evidence`，生成正文，再运行 `wiki page` |
| `evidence_ready` | 使用当前 Evidence 生成正文，再运行 `wiki page` |
| `generated` | 不处理 |
| `failed` | 根据错误类型修复，再重新 Evidence 或 Page |

如果丢失了先前 `wiki evidence` 的 stdout，而页面状态为 `evidence_ready`，最安全的做法是重新运行 Evidence，获得新的完整文本响应。

## 常见恢复错误

| 错误码 | 恢复方式 |
|---|---|
| `index_not_found` | 运行 `repo-dive index` |
| `index_stale` | 使用相同 Include/Exclude 参数重新索引 |
| `wiki_not_initialized` | 提交 Wiki Structure |
| `wiki_evidence_empty` | 增加预算或改进页面描述 |
| `wiki_evidence_missing` | 重新运行 `wiki evidence` |
| `wiki_evidence_stale` | 只重新生成列出的页面 |
| `wiki_build_incomplete` | 生成列出的未完成页面 |
| `wiki_page_state_invalid` | 按当前状态执行正确下一步 |
| `index_changed_during_operation` | 等索引稳定后重试 |
| `wiki_state_incomplete` | 诊断缺失的 `wiki.json` 或 Metadata，CLI 不自动修复 |

退出码：

| 退出码 | 含义 |
|---:|---|
| `0` | 成功 |
| `2` | 命令或输入校验错误 |
| `3` | 仓库、索引、Evidence 或 Wiki 状态错误 |
| `4` | 内部操作失败 |

退出码 `2` 不应该原样重试，必须先修改输入。

---

# 19. 原子性和幂等性

| 操作 | 行为 |
|---|---|
| `index` | 在新 Generation 构建完成后原子切换当前指针 |
| `wiki structure` | 相同结构返回 `changed: false` |
| `wiki evidence` | 每次成功都会生成新 Snapshot，不是无写入幂等 |
| `wiki page` | 相同页面重复提交返回 `changed: false` |
| `wiki page` | 不允许直接用不同正文覆盖 Generated 页面 |
| `wiki status` | 只读 |
| `wiki build` | 相同 Markdown 返回 `changed: false` |
| JSON 写入 | 单文件临时写入、`fsync`、`os.replace` |
| Markdown 写入 | 只有全部校验通过后才原子替换 |

需要注意，`wiki.json` 和根级 `metadata.json` 各自是原子文件，但两者之间不是一个跨文件数据库事务。

如果其中一个写入成功而另一个失败，后续读取会检测：

```text
wiki_state_incomplete
```

CLI 不会猜测修复。

---

# 20. 哪些由状态机保证，哪些依赖 Agent

## CLI 强制保证

- 页面状态转换合法
- 结构字段合法
- Page ID 唯一
- Relevant File 存在
- Evidence ID 属于当前页面
- Evidence 未过期
- 页面不能跳过 Evidence 直接生成
- Generated 页面不能直接覆盖
- Build 前所有页面必须完成
- 每页必须有正文和引用
- Build 失败不破坏旧 `wiki.md`
- 最终文档顺序和 Anchor 确定

## Agent 和 Skill 负责

- Wiki 结构是否合理
- 页面数量是否合适
- 页面描述是否能召回正确代码
- 是否认真使用 Evidence
- 正文是否真正事实准确
- 是否解释设计意图
- 图表是否有价值
- 页面写操作是否顺序执行
- 是否正确处理退出码和恢复
- 是否报告索引排除范围和 Evidence 局限

最终可以概括为：

```text
CLI 负责可验证的确定性边界
+
Skill 负责编排流程
+
Agent 负责规划和生成
=
完整 Wiki 生成系统
```
