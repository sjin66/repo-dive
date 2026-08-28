# Repo Dive CLI 开发任务清单

> 执行规则：一次只领取一个任务；先写失败测试，再做最小实现。每个任务完成后运行聚焦测试；每个 Checkpoint 运行 `make check` 和 `make test-all`。任务中的文件列表是责任边界，不授权无关重构。

## Phase 1：公共契约与安全基础

## Task 1：稳定结果信封与错误模型

**Description:** 定义成功/错误 JSON 信封、稳定错误码和异常到退出码的唯一映射，避免各命令自行拼 JSON。

**Acceptance criteria:**
- [x] `ResultEnvelope[T]` 和 `ErrorEnvelope` 序列化为 `schema_version = "1.0"` 的单一 JSON 文档。
- [x] 调用/校验、仓库/输入、内部错误分别映射到退出码 `2`、`3`、`4`。
- [x] JSON 序列化失败不会向 stdout 写出半截文档。

**Verification:**
- [x] Tests pass: `.venv/bin/pytest tests/unit/test_schema.py tests/unit/test_cli_errors.py -q`
- [x] Contract check: `.venv/bin/python -m repo_dive --version`

**Dependencies:** None

**Files likely touched:**
- `src/repo_dive/schema.py`
- `src/repo_dive/errors.py`
- `tests/unit/test_schema.py`
- `tests/unit/test_cli_errors.py`

**Estimated scope:** Medium (4 files)

## Task 2：统一 CLI 命令分派与 stdout/stderr

**Description:** 保留 `argparse`，建立命令注册与执行边界；CLI 捕获领域错误、输出信封，并保证 JSON stdout 隔离。

**Acceptance criteria:**
- [x] `cli.main(argv)` 可分派命令处理器并返回整数退出码。
- [x] JSON 模式 stdout 只有一个以换行结尾的 JSON 文档，stderr 承载诊断且无 ANSI。
- [x] 未知命令和坏参数退出 `2`，并保持 `--help`/`--version` 兼容。

**Verification:**
- [x] Tests pass: `.venv/bin/pytest tests/unit/test_cli.py tests/integration/test_cli_io.py -q`
- [x] Manual check: `.venv/bin/repo-dive --help`

**Dependencies:** Task 1

**Files likely touched:**
- `src/repo_dive/cli.py`
- `src/repo_dive/commands/__init__.py`
- `tests/unit/test_cli.py`
- `tests/integration/test_cli_io.py`

**Estimated scope:** Medium (4 files)

## Task 3：仓库边界与安全路径

**Description:** 提供所有模块共享的仓库根校验、相对 POSIX 路径转换和仓库内路径解析，拒绝路径穿越与符号链接逃逸。

**Acceptance criteria:**
- [x] 不存在、非目录、不可读仓库返回稳定 repository error。
- [x] `..`、绝对路径注入和指向仓库外的符号链接被拒绝。
- [x] Windows 风格输入在证据边界规范化为仓库相对 POSIX 路径。

**Verification:**
- [x] Tests pass: `.venv/bin/pytest tests/unit/storage/test_paths.py -q`
- [x] Security check: 测试在临时仓库外创建目标，并确认没有读取发生。

**Dependencies:** Task 1

**Files likely touched:**
- `src/repo_dive/storage/__init__.py`
- `src/repo_dive/storage/paths.py`
- `tests/unit/storage/test_paths.py`

**Estimated scope:** Medium (3 files)

## Task 4：原子文件与 JSON 写入

**Description:** 实现同目录临时文件、flush/fsync、原子替换和失败清理，作为 Metadata、Wiki 与 Manifest 的唯一公开写入方式。

**Acceptance criteria:**
- [x] 成功写入不会留下临时文件，JSON 使用 UTF-8 和稳定键顺序。
- [x] 替换前失败时旧文件字节保持不变。
- [x] 目标路径必须先通过 Task 3 的仓库边界检查。

**Verification:**
- [x] Tests pass: `.venv/bin/pytest tests/unit/storage/test_atomic.py -q`
- [x] Failure injection: 模拟 `os.replace` 失败并验证旧文件仍可读取。

**Dependencies:** Task 3

**Files likely touched:**
- `src/repo_dive/storage/atomic.py`
- `tests/unit/storage/test_atomic.py`

**Estimated scope:** Small (2 files)

## Checkpoint A：公共契约

- [ ] `make check`（被现有未跟踪 `.agents/skills/code-simplification/SKILL.md` 的 Ruff 格式问题阻断）
- [x] `make test-all`
- [x] JSON stdout/stderr 与退出码契约通过进程级测试。
- [x] 人工审阅 Schema、错误码和路径 API；后续任务不得绕过它们。

## Phase 2：仓库摄取、解析与切分

## Task 5：确定性候选文件发现

**Description:** 为 Git 和非 Git 仓库建立候选文件源，统一 include/exclude、默认排除和稳定排序。

**Acceptance criteria:**
- [ ] Git 模式包含 tracked 与未忽略 untracked 文件，并尊重 `.gitignore`。
- [ ] 非 Git 模式排除 `.git/`、`.repo-dive/`、虚拟环境、缓存、依赖与构建目录。
- [ ] 空格、Unicode 和换行文件名不会破坏 NUL 分隔解析；结果按 POSIX 路径排序。

**Verification:**
- [ ] Tests pass: `.venv/bin/pytest tests/unit/scanner/test_candidates.py -q`
- [ ] Fixture check: Git 与 filesystem Fixture 产生已记录的确定列表。

**Dependencies:** Task 3

**Files likely touched:**
- `src/repo_dive/scanner/__init__.py`
- `src/repo_dive/scanner/candidates.py`
- `tests/unit/scanner/test_candidates.py`
- `tests/fixtures/scanner_repo/README.md`

**Estimated scope:** Medium (4 files)

## Task 6：仓库清单与文件安全分类

**Description:** 读取候选文件，检测二进制、编码、大小和语言，生成内容哈希与跳过原因明确的 Inventory。

**Acceptance criteria:**
- [ ] 每个 `FileRecord` 包含相对路径、大小、语言、SHA-256 与读取状态。
- [ ] 二进制、超限、不可读和坏编码文件以结构化 skip reason 报告，不当成空文本。
- [ ] 同一仓库和参数重复扫描产生相同有序清单与仓库指纹。

**Verification:**
- [ ] Tests pass: `.venv/bin/pytest tests/unit/scanner/test_service.py -q`
- [ ] Determinism check: 对同一 Fixture 扫描两次并比较除耗时外的完整结果。

**Dependencies:** Task 5

**Files likely touched:**
- `src/repo_dive/scanner/models.py`
- `src/repo_dive/scanner/service.py`
- `tests/unit/scanner/test_service.py`
- `tests/fixtures/scanner_repo/binary.dat`

**Estimated scope:** Medium (4 files)

## Task 7：解析 Protocol 与文本回退切分

**Description:** 定义 Parser 适配器、Chunk/Symbol/Relationship 对象和不支持语言的确定性文本切分器。

**Acceptance criteria:**
- [ ] Parser 接口只接收文件记录与文本，不访问文件系统或终端。
- [ ] Markdown 按标题/段落切分，普通文本按有重叠的行窗切分。
- [ ] Chunk ID、行号、内容哈希在重复解析时稳定；空白与超长行有明确行为。

**Verification:**
- [ ] Tests pass: `.venv/bin/pytest tests/unit/parsing/test_text.py tests/unit/parsing/test_models.py -q`
- [ ] Line check: 每个 Chunk 文本可由原文件声明行区间重新取得。

**Dependencies:** Task 6

**Files likely touched:**
- `src/repo_dive/parsing/models.py`
- `src/repo_dive/parsing/text.py`
- `tests/unit/parsing/test_models.py`
- `tests/unit/parsing/test_text.py`

**Estimated scope:** Medium (4 files)

## Task 8：Python AST 符号与关系适配器

**Description:** 使用标准库 `ast` 提取模块、类、函数、方法、Import、调用和继承关系，并按符号边界切分 Python。

**Acceptance criteria:**
- [ ] 提取 qualified name、kind、1-based inclusive 行号和稳定 Symbol ID。
- [ ] `contains`、`imports`、`calls`、`inherits` 关系携带来源和置信度。
- [ ] SyntaxError 产生诊断并回退文本切分，不导致整个仓库索引失败。

**Verification:**
- [ ] Tests pass: `.venv/bin/pytest tests/unit/parsing/test_python_ast.py -q`
- [ ] Fixture check: 嵌套类/函数、别名 Import、装饰器和多行签名行号正确。

**Dependencies:** Task 7

**Files likely touched:**
- `src/repo_dive/parsing/python_ast.py`
- `tests/unit/parsing/test_python_ast.py`
- `tests/fixtures/python_repo/sample.py`

**Estimated scope:** Medium (3 files)

## Task 9：Tree-sitter 注册表与统一解析流水线

**Description:** 增加延迟加载的 Tree-sitter 适配器和语言注册表，将 Python AST、Tree-sitter 和文本回退组合成单一解析流水线。

**Acceptance criteria:**
- [ ] JS/TS/TSX 至少有一个完整 Symbol/Chunk Fixture；Grammar 缺失时回退并报告 warning。
- [ ] Tree-sitter 依赖版本范围固定且 Python 3.11–3.13 可安装。
- [ ] 统一 Pipeline 按路径选择适配器，规范化/拆分超大 Chunk，并稳定输出有序结果。

**Verification:**
- [ ] Tests pass: `.venv/bin/pytest tests/unit/parsing/test_tree_sitter.py tests/unit/parsing/test_pipeline.py -q`
- [ ] Packaging check: `make setup` 可从空环境安装 Parser 依赖。

**Dependencies:** Tasks 7–8

**Files likely touched:**
- `src/repo_dive/parsing/tree_sitter.py`
- `src/repo_dive/parsing/registry.py`
- `src/repo_dive/parsing/pipeline.py`
- `tests/unit/parsing/test_pipeline.py`
- `pyproject.toml`

**Estimated scope:** Medium (5 files)

## Checkpoint B：摄取与解析

- [ ] `make check`
- [ ] `make test-all`
- [ ] 同一 Fixture 重跑得到相同 File/Chunk/Symbol/Relationship ID。
- [ ] 解析错误只影响对应文件，并产生结构化 warning。

## Phase 3：持久化索引与 `index`

## Task 10：SQLite 索引 Schema 与 Store

**Description:** 建立内部索引数据库、版本迁移拒绝策略和类型化读写 Store。

**Acceptance criteria:**
- [ ] Schema 包含 files、chunks、symbols、relationships、terms、postings、stats 和 vectors 表。
- [ ] 外键、唯一键和事务保证不存在悬空 Symbol/Relationship/Posting。
- [ ] 未知内部 Schema 版本被明确拒绝，不尝试猜测迁移。

**Verification:**
- [ ] Tests pass: `.venv/bin/pytest tests/unit/indexing/test_store.py -q`
- [ ] Integrity check: 测试执行 `PRAGMA foreign_key_check` 和 `PRAGMA integrity_check`。

**Dependencies:** Tasks 4、7

**Files likely touched:**
- `src/repo_dive/indexing/__init__.py`
- `src/repo_dive/indexing/store.py`
- `src/repo_dive/indexing/schema.sql`
- `tests/unit/indexing/test_store.py`

**Estimated scope:** Medium (4 files)

## Task 11：代码感知 Tokenizer 与 BM25 建索引

**Description:** 实现保留原标识符并拆分 snake_case、camelCase、路径和符号的 Tokenizer，以及可解释 BM25 posting/stat 写入。

**Acceptance criteria:**
- [ ] `HTTPServer`, `http_server` 和 `path/to/file.py` 同时保留整体和拆分 Token。
- [ ] BM25 文档频率、文档长度、平均长度和参数被持久化且重建确定。
- [ ] 空 Chunk、仅符号 Chunk 和 Unicode 标识符有测试覆盖。

**Verification:**
- [ ] Tests pass: `.venv/bin/pytest tests/unit/indexing/test_bm25.py -q`
- [ ] Golden check: 固定 Corpus 的 posting 与统计等于记录值。

**Dependencies:** Task 10

**Files likely touched:**
- `src/repo_dive/indexing/bm25.py`
- `tests/unit/indexing/test_bm25.py`

**Estimated scope:** Small (2 files)

## Task 12：结构关系索引与邻接查询

**Description:** 持久化符号和关系，并提供按 symbol name、qualified name、path 和边类型查询邻居的窄接口。

**Acceptance criteria:**
- [ ] 精确和大小写归一化符号查询行为有明确优先级。
- [ ] 邻接查询限制深度、边类型和最大节点数，防止关系爆炸。
- [ ] 每条返回关系保留 kind、confidence 和来源位置。

**Verification:**
- [ ] Tests pass: `.venv/bin/pytest tests/unit/indexing/test_graph.py -q`
- [ ] Cycle check: 环图在给定深度内终止且顺序稳定。

**Dependencies:** Task 10

**Files likely touched:**
- `src/repo_dive/indexing/graph.py`
- `tests/unit/indexing/test_graph.py`

**Estimated scope:** Small (2 files)

## Task 13：增量 Index Service 与 Manifest

**Description:** 编排扫描、解析、BM25 和结构写入；依据内容哈希和构建参数决定复用、增量或全量重建。

**Acceptance criteria:**
- [ ] 首次索引构建临时数据库并原子发布 index + manifest + metadata。
- [ ] 未变化文件不重新解析；变化/删除文件只失效相关记录。
- [ ] 构建失败保留旧有效索引，并返回失败阶段与安全诊断。

**Verification:**
- [ ] Tests pass: `.venv/bin/pytest tests/unit/indexing/test_service.py -q`
- [ ] Incremental check: 修改一个 Fixture 文件，只对应文件的 Chunk ID 集发生变化。

**Dependencies:** Tasks 6、9–12

**Files likely touched:**
- `src/repo_dive/indexing/service.py`
- `src/repo_dive/indexing/manifest.py`
- `tests/unit/indexing/test_service.py`
- `tests/fixtures/index_repo/README.md`

**Estimated scope:** Medium (4 files)

## Task 14：公开 `index` 命令

**Description:** 暴露 `repo-dive index <repository>`，接入 include/exclude、文件大小、Chunk 和 JSON 格式参数。

**Acceptance criteria:**
- [ ] 成功结果报告文件/Chunk/Symbol/Relationship 数、复用数、warning 和索引版本。
- [ ] 非法仓库在创建 `.repo-dive/` 前退出 `3`；坏参数退出 `2`。
- [ ] 相同仓库与参数重跑幂等，并明确报告 reused/rebuilt。

**Verification:**
- [ ] Tests pass: `.venv/bin/pytest tests/integration/test_index_command.py -q`
- [ ] Manual check: `.venv/bin/repo-dive index tests/fixtures/index_repo --format json`

**Dependencies:** Tasks 2、13

**Files likely touched:**
- `src/repo_dive/commands/index.py`
- `src/repo_dive/cli.py`
- `tests/integration/test_index_command.py`
- `evals/cases/indexing.jsonl`

**Estimated scope:** Medium (4 files)

## Checkpoint C：离线索引

- [ ] `make check`
- [ ] `make test-all`
- [ ] `index` 在无网络和无凭据环境完成。
- [ ] 故障注入证明旧索引与旧 metadata 不被破坏。

## Phase 4：检索与 `search`

## Task 15：BM25 查询与解释

**Description:** 使用索引统计计算 BM25 分数，返回稳定排序、命中词和原始 lexical score。

**Acceptance criteria:**
- [ ] 固定 Corpus 的分数与手工公式结果在容差内一致。
- [ ] 相同分数按路径、行号和 Chunk ID 稳定打破平局。
- [ ] 空查询、未知词和 `max_results` 边界返回可预测结果。

**Verification:**
- [ ] Tests pass: `.venv/bin/pytest tests/unit/retrieval/test_lexical.py -q`
- [ ] Formula check: 固定 `k1`/`b` Golden Test 通过。

**Dependencies:** Tasks 11、13

**Files likely touched:**
- `src/repo_dive/retrieval/__init__.py`
- `src/repo_dive/retrieval/lexical.py`
- `tests/unit/retrieval/test_lexical.py`

**Estimated scope:** Medium (3 files)

## Task 16：结构检索与受限关系扩展

**Description:** 从查询中的路径/符号线索召回定义与相邻实现，并对 Import、调用、继承和包含关系进行受限扩展。

**Acceptance criteria:**
- [ ] 精确 qualified name 优先于模糊名称；定义 Chunk 优先于仅引用 Chunk。
- [ ] 扩展遵守深度、节点数和最小 confidence 上限。
- [ ] 每个命中说明 symbol match 或 relationship path，不隐藏扩展来源。

**Verification:**
- [ ] Tests pass: `.venv/bin/pytest tests/unit/retrieval/test_structural.py -q`
- [ ] Cycle check: 循环调用图不产生重复或无限扩展。

**Dependencies:** Tasks 12–13

**Files likely touched:**
- `src/repo_dive/retrieval/structural.py`
- `tests/unit/retrieval/test_structural.py`

**Estimated scope:** Small (2 files)

## Task 17：RRF 融合、重叠去重和证据解释

**Description:** 融合 lexical/structural 候选，删除 ID 重复与高比例行区间重叠，同时保留每通道分数和原因。

**Acceptance criteria:**
- [ ] Weighted RRF 参数进入结果元数据；缺失通道不被当作零分伪排名。
- [ ] 包含/重叠 Chunk 只保留信息量更高者，除非二者来自不同符号。
- [ ] 排序与去重在输入通道顺序变化时仍确定。

**Verification:**
- [ ] Tests pass: `.venv/bin/pytest tests/unit/retrieval/test_fusion.py -q`
- [ ] Eval case: 增加一个 BM25 单独失败、结构融合成功的固定用例。

**Dependencies:** Tasks 15–16

**Files likely touched:**
- `src/repo_dive/retrieval/fusion.py`
- `tests/unit/retrieval/test_fusion.py`
- `evals/cases/retrieval.jsonl`

**Estimated scope:** Medium (3 files)

## Task 18：公开 `search` 命令

**Description:** 暴露只读 `repo-dive search <repository> <query>`，返回可解释 SearchHit，不修改仓库状态。

**Acceptance criteria:**
- [ ] 强制 `--max-results` 合法上限，结果包含路径、行号、符号、文本、各通道分数和 fused score。
- [ ] 缺失/过期索引返回退出 `3` 和稳定错误码，不自动建立索引。
- [ ] 命令前后 `.repo-dive/` 文件摘要不变。

**Verification:**
- [ ] Tests pass: `.venv/bin/pytest tests/integration/test_search_command.py -q`
- [ ] Manual check: `.venv/bin/repo-dive search tests/fixtures/index_repo "entrypoint" --max-results 5 --format json`

**Dependencies:** Tasks 2、17

**Files likely touched:**
- `src/repo_dive/commands/search.py`
- `src/repo_dive/cli.py`
- `tests/integration/test_search_command.py`
- `evals/cases/search.jsonl`

**Estimated scope:** Medium (4 files)

## Checkpoint D：离线 Search

- [ ] `make check`
- [ ] `make test-all`
- [ ] Search 命中可由路径、行号、符号和分数完整解释。
- [ ] Eval Fixture 上的基线 Recall@k 与 MRR 被记录，尚不设未经验证的高阈值。

## Phase 5：预算上下文与 `context`

## Task 19：Token 估算和证据预算选择

**Description:** 实现可替换 TokenEstimator 与预算 Packer，在保留元数据、来源多样性和完整行范围的前提下选择证据。

**Acceptance criteria:**
- [ ] 预算先扣除稳定信封/元数据预留；正文不会使 `estimated_tokens` 超预算。
- [ ] 优先高分实现，并限制单文件占比；排除项报告 duplicate、budget 或 low_score。
- [ ] 过小预算返回空 items + truncated，而不是输出破损 Evidence。

**Verification:**
- [ ] Tests pass: `.venv/bin/pytest tests/unit/context/test_tokens.py tests/unit/context/test_packer.py -q`
- [ ] Property check: 多组预算下估算用量始终小于等于预算且随预算不减少。

**Dependencies:** Task 17

**Files likely touched:**
- `src/repo_dive/context/tokens.py`
- `src/repo_dive/context/packer.py`
- `tests/unit/context/test_tokens.py`
- `tests/unit/context/test_packer.py`

**Estimated scope:** Medium (4 files)

## Task 20：公开 `context` 命令与 Evidence Schema

**Description:** 暴露 `repo-dive context`，把查询、检索参数和 Token 预算转换为可供 Copilot 使用的带版本 EvidenceBundle。

**Acceptance criteria:**
- [ ] `--token-budget` 为必填正整数，并报告 estimator、实际估算、truncated 与 excluded summary。
- [ ] 每个 Evidence Item 有稳定 Evidence ID、路径、可信行号、符号、正文和检索解释。
- [ ] 同一索引、查询和参数返回字节等价 JSON（排除明确列出的耗时字段）。

**Verification:**
- [ ] Tests pass: `.venv/bin/pytest tests/integration/test_context_command.py -q`
- [ ] Manual check: `.venv/bin/repo-dive context tests/fixtures/index_repo "architecture" --token-budget 1200 --format json`

**Dependencies:** Tasks 2、18–19

**Files likely touched:**
- `src/repo_dive/commands/context.py`
- `src/repo_dive/cli.py`
- `tests/integration/test_context_command.py`
- `evals/cases/context.jsonl`

**Estimated scope:** Medium (4 files)

## Checkpoint E：可调用离线 RAG

- [ ] `make check`
- [ ] `make test-all`
- [ ] `index -> search -> context` 端到端 Fixture 通过。
- [ ] Agent 可以只读取 JSON Schema 完成证据消费，不依赖日志文案。

## Phase 6：Wiki 状态机与 Markdown 汇总

## Task 21：Wiki Schema 与持久状态 Store

**Description:** 定义 Wiki/Section/Page/EvidenceRef/Metadata 对象和严格状态转换，使用原子 JSON Store 保存公开产物。

**Acceptance criteria:**
- [ ] 页面状态只允许 `pending`、`evidence_ready`、`generated`、`failed` 的合法转换。
- [ ] `wiki.json` 与 `metadata.json` 带独立 Schema/索引版本，并拒绝未知必填字段缺失。
- [ ] 读到损坏 JSON 时返回稳定错误，不覆盖损坏文件供诊断。

**Verification:**
- [ ] Tests pass: `.venv/bin/pytest tests/unit/wiki/test_models.py tests/unit/wiki/test_store.py -q`
- [ ] Atomic check: 任一文件写入失败时现有公开产物保持完整。

**Dependencies:** Tasks 1、4、20

**Files likely touched:**
- `src/repo_dive/wiki/models.py`
- `src/repo_dive/wiki/store.py`
- `tests/unit/wiki/test_models.py`
- `tests/unit/wiki/test_store.py`

**Estimated scope:** Medium (4 files)

## Task 22：Wiki 结构与状态命令

**Description:** 实现 `wiki structure` 和 `wiki status`，让调用方提交带稳定 Page ID 的章节/页面结构并查询可恢复状态。

**Acceptance criteria:**
- [ ] 结构输入校验标题、唯一 ID、有序章节、页面描述和仓库内相关文件。
- [ ] 未知文件路径和重复 Page ID 被拒绝，CLI 不自动修正或虚构页面。
- [ ] 重提相同结构幂等；结构改变只把受影响页面标记为 pending/stale。

**Verification:**
- [ ] Tests pass: `.venv/bin/pytest tests/integration/test_wiki_structure.py -q`
- [ ] Manual check: `wiki status` 能显示每种页面状态和下一步动作。

**Dependencies:** Task 21

**Files likely touched:**
- `src/repo_dive/wiki/service.py`
- `src/repo_dive/commands/wiki.py`
- `src/repo_dive/cli.py`
- `tests/integration/test_wiki_structure.py`

**Estimated scope:** Medium (4 files)

## Task 23：页面 Evidence 绑定与过期检查

**Description:** 实现 `wiki evidence`：以页面描述和相关文件为检索提示生成 EvidenceBundle，并先保存 Evidence 状态再返回调用方。

**Acceptance criteria:**
- [ ] Evidence 保存 query、索引版本、Chunk hash、预算、检索参数与生成时间。
- [ ] 成功后页面进入 `evidence_ready`；失败只标记本页，不重置其他页面。
- [ ] 仓库/索引变化后过期 Evidence 不能用于页面提交或 build。

**Verification:**
- [ ] Tests pass: `.venv/bin/pytest tests/integration/test_wiki_evidence.py -q`
- [ ] Staleness check: 修改一个相关文件只使依赖其 Evidence 的页面过期。

**Dependencies:** Tasks 20–22

**Files likely touched:**
- `src/repo_dive/wiki/service.py`
- `src/repo_dive/wiki/validation.py`
- `tests/integration/test_wiki_evidence.py`
- `evals/cases/wiki_evidence.jsonl`

**Estimated scope:** Medium (4 files)

## Task 24：Agent 页面提交与引用校验

**Description:** 实现 `wiki page`，从 JSON stdin/文件接收 Copilot 生成的 Markdown 和 Evidence ID，验证后原子持久化单页。

**Acceptance criteria:**
- [ ] 拒绝未知/过期 Evidence ID、错误 Page ID、非法 UTF-8、超限正文和不允许的状态转换。
- [ ] 成功页面进入 `generated`，正文与引用可独立重试且不影响其他页面。
- [ ] 诊断不回显完整私有源码或完整页面正文。

**Verification:**
- [ ] Tests pass: `.venv/bin/pytest tests/integration/test_wiki_page.py -q`
- [ ] Retry check: failed 页面修正后可提交，已 generated 页面字节不变。

**Dependencies:** Task 23

**Files likely touched:**
- `src/repo_dive/wiki/validation.py`
- `src/repo_dive/wiki/service.py`
- `tests/integration/test_wiki_page.py`
- `evals/cases/wiki_page.jsonl`

**Estimated scope:** Medium (4 files)

## Task 25：Wiki Markdown 原子汇总与完整工作流

**Description:** 实现 `wiki build`，按结构顺序生成标题、目录、稳定锚点、页面正文、相关页面和来源，原子替换 `wiki.md`。

**Acceptance criteria:**
- [ ] 必需页面未 generated 或 Evidence 过期时拒绝 build，并保留旧 `wiki.md`。
- [ ] 成功 Markdown 的目录、锚点、章节顺序和来源在重复构建时稳定。
- [ ] `--format markdown` 向 stdout 返回 Markdown，但仓库写入仍遵守原子产物契约。

**Verification:**
- [ ] Tests pass: `.venv/bin/pytest tests/unit/wiki/test_assembler.py tests/integration/test_wiki_workflow.py -q`
- [ ] E2E check: `index -> structure -> evidence -> page -> build -> status` 全流程通过。

**Dependencies:** Tasks 22–24

**Files likely touched:**
- `src/repo_dive/wiki/assembler.py`
- `src/repo_dive/commands/wiki.py`
- `tests/unit/wiki/test_assembler.py`
- `tests/integration/test_wiki_workflow.py`
- `evals/cases/wiki_workflow.jsonl`

**Estimated scope:** Medium (5 files)

## Checkpoint F：Wiki MVP

- [ ] `make check`
- [ ] `make test-all`
- [ ] 无网络、无 Vector 的 Fixture 仓库可以产出完整 `.repo-dive/wiki.md`。
- [ ] 中断、单页失败、过期 Evidence 和汇总失败均可恢复，旧产物保持完整。

## Phase 7：可选向量增强

## Task 26：SQLite Vector Store 与余弦检索

**Description:** 保存定长 float32 向量、Provider/模型身份和 Chunk hash，并实现受 `max_results` 限制的确定性暴力余弦检索。

**Acceptance criteria:**
- [ ] 拒绝维度不一致、NaN/Inf 和模型身份不匹配的向量。
- [ ] 固定向量集合的余弦分数和顺序与手工结果一致。
- [ ] Vector 表为空时不会影响 BM25/结构索引和查询。

**Verification:**
- [ ] Tests pass: `.venv/bin/pytest tests/unit/indexing/test_vectors.py tests/unit/retrieval/test_vector.py -q`
- [ ] Determinism check: 同分向量按 Chunk ID 稳定排序。

**Dependencies:** Tasks 10、17

**Files likely touched:**
- `src/repo_dive/indexing/vectors.py`
- `src/repo_dive/retrieval/vector.py`
- `tests/unit/indexing/test_vectors.py`
- `tests/unit/retrieval/test_vector.py`

**Estimated scope:** Medium (4 files)

## Task 27：显式本地 Embedding Provider

**Description:** 定义 `EmbeddingProvider` Protocol 和延迟导入的 Sentence Transformers 适配器；只接受本地模型目录且禁止隐式下载。

**Acceptance criteria:**
- [ ] 默认安装不包含/导入 Sentence Transformers；`.[vector]` extra 才安装它。
- [ ] Provider 要求存在的本地模型路径，并以 `local_files_only=True` 加载。
- [ ] Fake Provider 单元测试覆盖批处理、维度、模型身份和错误脱敏。

**Verification:**
- [ ] Tests pass: `.venv/bin/pytest tests/unit/providers/test_embeddings.py -q`
- [ ] Offline check: 未配置 Provider 的完整测试不访问网络或导入重型模块。

**Dependencies:** Tasks 3、26

**Files likely touched:**
- `src/repo_dive/providers/embeddings.py`
- `tests/unit/providers/test_embeddings.py`
- `pyproject.toml`

**Estimated scope:** Medium (3 files)

## Task 28：三通道 Index/Search/Context 集成

**Description:** 把显式 Vector Provider 接入增量索引和 RRF 融合，加入 CLI 参数、降级策略和向量收益评测。

**Acceptance criteria:**
- [ ] 未提供 `--embedding-model` 时行为与 Checkpoint F 字节兼容。
- [ ] 提供本地模型时只重嵌入内容变化或 Provider 身份变化的 Chunk。
- [ ] SearchHit 同时报告 lexical/structural/vector/fused 分数；strict/degraded 策略可观察。

**Verification:**
- [ ] Tests pass: `.venv/bin/pytest tests/integration/test_hybrid_retrieval.py -q`
- [ ] Eval case: 至少一个语义改写查询证明 Vector 提升 Recall@k 且不破坏预算。

**Dependencies:** Tasks 13、17、20、26–27

**Files likely touched:**
- `src/repo_dive/indexing/service.py`
- `src/repo_dive/retrieval/fusion.py`
- `src/repo_dive/cli.py`
- `tests/integration/test_hybrid_retrieval.py`
- `evals/cases/hybrid_retrieval.jsonl`

**Estimated scope:** Medium (5 files)

## Checkpoint G：Hybrid RAG

- [ ] `make check`
- [ ] `make test-all`
- [ ] 默认安装与默认运行保持离线、轻量。
- [ ] 向量通道的收益、成本、模型身份和失败策略均可观察。

## Phase 8：评测、硬化与发布

## Task 29：可执行评测 Runner 与指标

**Description:** 把 JSONL 规范用例扩展为可执行 RAG 评测，输出 Recall@k、MRR、路径/符号命中、预算遵守和引用覆盖。

**Acceptance criteria:**
- [ ] 可执行与 specification-only 用例明确分开，后者不计作通过。
- [ ] Runner 输出带版本 JSON 和每例诊断，聚合结果可在 CI 比较。
- [ ] 指标实现有手工可验证的 Golden Test，不评价 Markdown 文风。

**Verification:**
- [ ] Tests pass: `.venv/bin/pytest tests/unit/evaluation -q`
- [ ] Runner check: `.venv/bin/python -m repo_dive.evaluation.runner evals/cases --format json`

**Dependencies:** Tasks 18、20、25、28

**Files likely touched:**
- `src/repo_dive/evaluation/metrics.py`
- `src/repo_dive/evaluation/runner.py`
- `tests/unit/evaluation/test_metrics.py`
- `tests/unit/evaluation/test_runner.py`
- `evals/README.md`

**Estimated scope:** Medium (5 files)

## Task 30：安全、损坏与恢复集成测试

**Description:** 建立跨模块故障矩阵，验证路径逃逸、坏编码、损坏索引、陈旧 Evidence、写入失败和诊断脱敏。

**Acceptance criteria:**
- [ ] 每种故障都有稳定 error code、退出码和不泄露源码的 stderr。
- [ ] 任何失败都不会留下半写 JSON/SQLite/Markdown 或删除旧有效产物。
- [ ] 恶意文件名、符号链接和超大输入不能突破仓库与预算边界。

**Verification:**
- [ ] Tests pass: `.venv/bin/pytest tests/integration/test_security.py tests/integration/test_recovery.py -q`
- [ ] Full suite: `make test-all`

**Dependencies:** Tasks 14、18、20、25、28

**Files likely touched:**
- `tests/integration/test_security.py`
- `tests/integration/test_recovery.py`
- `tests/fixtures/security_repo/README.md`
- `evals/cases/security.jsonl`

**Estimated scope:** Medium (4 files)

## Task 31：规模与性能预算

**Description:** 使用运行时生成 Fixture 测量扫描、索引、Search、Context 和 Wiki 的趋势，建立内存/结果上限和增量重建回归门槛。

**Acceptance criteria:**
- [ ] 性能测试不依赖机器绝对毫秒值，而检查复杂度趋势、结果上限和增量工作量。
- [ ] Scanner/Parser 流式处理文件；Search/Context 不把无界 Corpus 全部载入返回列表。
- [ ] 记录推荐仓库规模、默认文件/Chunk/结果/预算上限及超限错误。

**Verification:**
- [ ] Tests pass: `.venv/bin/pytest tests/performance -q`
- [ ] Regression check: 修改单文件的增量索引处理数小于全量文件数。

**Dependencies:** Tasks 13、20、25、28

**Files likely touched:**
- `tests/performance/test_index_scaling.py`
- `tests/performance/test_retrieval_budget.py`
- `docs/en/development.md`
- `docs/zh-CN/development.md`

**Estimated scope:** Medium (4 files)

## Task 32：Agent 调用契约与 CLI 用户文档

**Description:** 更新 AGENTS 调用规范、README 和 CLI 契约，给出 GitHub Copilot 完整命令序列、JSON/Markdown 输入输出样例、错误处理与限制。

**Acceptance criteria:**
- [ ] README 和 CLI 契约不再把已实现命令标作规划中，且中英文技术常量一致。
- [ ] AGENTS.md 包含 Agent 的 `index -> context -> generate -> wiki page -> build` 调用规范，不要求 MCP。
- [ ] 文档包含四个命令族的成功、错误、stdin 文件和恢复示例，示例可由契约测试解析。

**Verification:**
- [ ] Contract check: `.venv/bin/pytest tests/unit/test_repo_contract.py -q`
- [ ] CLI smoke: `.venv/bin/repo-dive --help`、`--version`、四个功能命令的 `--help`
- [ ] Bilingual check: 中英文 CLI 标题、命令、字段、退出码和路径逐项相同。

**Dependencies:** Tasks 29–31

**Files likely touched:**
- `AGENTS.md`
- `README.md`
- `README.zh-CN.md`
- `docs/en/cli-contract.md`
- `docs/zh-CN/cli-contract.md`

**Estimated scope:** Medium (5 files)

## Task 33：架构、RAG 与 Wiki 开发文档同步

**Description:** 更新中英双语架构与 Wiki 工作流，使模块、Schema、状态机、向量边界和恢复语义与真实实现一致。

**Acceptance criteria:**
- [ ] 架构文档列出的包、依赖方向、SQLite/BM25/结构/Vector 行为与源码一致。
- [ ] Wiki 文档完整描述 `structure -> evidence -> page -> build -> status` 和单页恢复流程。
- [ ] 中英文对应文件拥有等价标题、命令、状态、字段和技术常量。

**Verification:**
- [ ] Contract check: `.venv/bin/python scripts/check_repo_contract.py`
- [ ] Example check: Wiki 文档中的命令示例能在 Fixture 仓库上执行或通过 `--help` 验证。

**Dependencies:** Task 32

**Files likely touched:**
- `docs/en/architecture.md`
- `docs/zh-CN/architecture.md`
- `docs/en/wiki-workflow.md`
- `docs/zh-CN/wiki-workflow.md`

**Estimated scope:** Medium (4 files)

## Task 34：打包、CI 与 Release Candidate 验收

**Description:** 更新开发文档和发布 Harness，从全新环境构建 wheel/sdist，在 Python 3.11–3.13 执行共享验证与 CLI smoke test。

**Acceptance criteria:**
- [ ] 默认安装不包含 Vector extra；`.[vector]` 安装路径和本地模型限制有文档说明。
- [ ] CI 的 Python 3.11、3.12、3.13 矩阵只调用共享 Make 目标，不复制 Ruff/mypy/pytest 命令。
- [ ] wheel 与 sdist 均包含所需 SQL/Schema 资源；从 wheel 安装后四个命令族可启动。

**Verification:**
- [ ] Fresh harness: `make setup`
- [ ] Fresh harness: `make check`
- [ ] Fresh harness: `make test-all`
- [ ] Package smoke: 从构建 wheel 的临时 venv 执行 `repo-dive --version` 和四个功能命令的 `--help`。
- [ ] Repository review: `git status --short` 与 `git diff --check`。

**Dependencies:** Task 33

**Files likely touched:**
- `pyproject.toml`
- `Makefile`
- `.github/workflows/ci.yml`
- `docs/en/development.md`
- `docs/zh-CN/development.md`

**Estimated scope:** Medium (5 files)

## Checkpoint H：Release Candidate

- [ ] 所有 Task 验收条件完成并可追溯到测试或评测。
- [ ] `make check`、`make test-unit`、`make test-all` 全部通过。
- [ ] 离线 Wiki E2E、可选 Vector E2E、安全/恢复和评测 Runner 全部通过。
- [ ] 中英文文档与真实 CLI 输出一致。
- [ ] 未实现非目标：无前端、无 MCP、无隐式生成模型调用、无远程仓库克隆。
- [ ] 人工审阅并批准 Release Candidate。
