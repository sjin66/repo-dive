# 开发指南

## 环境要求

- Python 3.11 或更高版本
- GNU Make
- Git

项目不需要 Node.js、Web Runtime 或模型 Provider 凭据。

## 环境初始化

创建项目管理的虚拟环境，并以 Editable 模式安装包和开发工具：

```bash
make setup
```

环境位于 `.venv/`。必要时可以覆盖引导解释器：

```bash
make setup PYTHON=/path/to/python3.12
```

### 可选本地 Embedding

默认开发安装不会包含或导入 Sentence Transformers。只有开发本地
Embedding 适配器时才安装显式的 Vector Extra：

```bash
.venv/bin/python -m pip install -e ".[vector]"
```

适配器只接受已经存在的本地模型目录，并向 Sentence Transformers 传入
`local_files_only=True` 和 `trust_remote_code=False`；模型缺失时直接报错，
不会发起下载。Provider 错误与持久化模型身份都不会暴露模型绝对路径。
显式执行 `index`、`search` 和 `context` 时应使用同一个模型目录。
`--vector-failure strict` 是默认策略；只有接受可观察的 BM25/结构降级时才选择
`degraded`。

## 统一验证命令

```bash
make check
make test-unit
make test-all
```

- `check` 执行格式检查、Lint、类型检查和仓库契约校验。
- `test-unit` 执行 `tests/unit/` 下的聚焦测试。
- `test-all` 执行完整测试集，包括存在时的集成测试。

CI 调用相同目标。除非先把工具命令加入对应 Make 目标，否则不能直接写入 CI。

## 测试驱动变更

对于行为变更：

1. 编写一个描述可观察失败的测试。
2. 运行测试，确认它因为行为缺失而失败。
3. 编写让测试通过的最小实现。
4. 运行聚焦测试，再运行完整相关测试集。
5. 只有在测试保持绿色时才能重构。

测试应该执行真实行为。面向人的文档不需要单元测试；仓库级文档契约由 `make check` 中的校验脚本负责。

## 项目布局

```text
src/repo_dive/        Python 包
tests/unit/           隔离的行为测试
tests/integration/    仓库工作流测试
tests/performance/    确定性的规模与资源预算测试
tests/fixtures/       小型且明确的仓库 Fixture
evals/cases/          机器可读的 Agent/RAG 评测用例
docs/en/              英文工程文档
docs/zh-CN/           简体中文对应文档
docs/superpowers/     已批准的规范和实施计划
```

## 文档变更

英文与简体中文文件必须在同一提交中更新。技术常量、路径、退出码、JSON 字段名和命令示例必须一致。Agent 与 Harness 策略放在根目录 `AGENTS.md`；兼容文件只引用它，不能复制策略。

## 依赖变更

运行时依赖必须支持 Python 3.11，并拥有边界清晰的用途。把决策写入功能设计，在 `pyproject.toml` 中添加依赖，并测试适配器行为，而不是重复测试依赖自身内部实现。重型依赖或 Provider 专用依赖必须放入命名的可选 Extra，并在适配器边界延迟导入。

仅开发使用的工具放入 `dev` 可选依赖。贡献者和 CI 都以 `make setup` 作为唯一安装路径。

## 评测变更

检索与上下文启发式算法必须增加 `evals/cases/` 用例。每个用例包含稳定 ID、类别、Prompt 和预期行为。尚不可执行的用例用于记录产品契约，不能假装功能已经存在。

## 规模与性能预算

修改 Scanner、Parser、索引、检索、Context 打包或 Wiki Evidence 行为时，
单独运行确定性的规模检查：

```bash
.venv/bin/pytest tests/performance -q
```

这些测试在运行时生成仓库，不断言会随机器变化的绝对毫秒值，而是比较工作量和
内存趋势：Corpus 扩大四倍时，峰值内存必须保持在六倍以内；64 文件仓库只修改
一个文件时必须只重建一个文件；Search、Context 和 Wiki 集合必须始终处于公开
结果数量与 Token 预算之内。

推荐的交互式工作区间是不超过 5,000 个选中源码文件或 50,000 个 Chunk。这是
运行建议，不是仓库硬上限。处理更大的 Monorepo 时，先使用 `--include` 和
`--exclude` 缩小 Corpus，再执行性能测试或有代表性的本地测量，然后再依赖交互式
延迟。精确 BM25 与可选 Vector 检索目前每次查询会读取一次持久化 Chunk Corpus，
因此工作内存随选中 Corpus 线性增长；返回给调用方的 Search、Context 和 Wiki
集合不随 Corpus 无界增长。

Scanner 使用固定的 64 KiB 数据块读取源码并对完整文件计算 Hash；一旦超过配置的
文件限制，就不再保留源码字节。Parser 按确定顺序一次接收并处理一个 `SourceFile`。
索引通过新 Generation 发布；增量重建工作量与发生变化的文件和 Chunk 成正比，
而不是与完整解析数量成正比。

| 边界 | 默认值或建议 | 硬行为 |
| --- | --- | --- |
| 选中仓库 | 建议不超过 5,000 个文件或 50,000 个 Chunk | 没有全局硬上限；更大的 Corpus 应显式缩小范围 |
| 源文件 | `--max-file-size 1000000` 字节 | 更大的文件记录为 `skipped`/`too_large`，不导致命令失败 |
| Chunk | `--max-chunk-lines 200` | 必须为正数；无效 CLI 输入返回 `invalid_invocation` 和退出码 2 |
| Query | 最多 1,000 个字符 | 空输入或超限输入返回 `invalid_invocation` 和退出码 2 |
| Search 候选 | 内部上限 200 | 不会作为无界结果集合暴露给调用方 |
| Search 结果 | 默认 10，硬上限 50 | 超出 1–50 返回 `invalid_invocation` 和退出码 2 |
| Context/Wiki Evidence 预算 | 必填；建议 1,200–8,000 Token | 必须为正数；只打包完整 Chunk，`estimated_tokens <= token_budget`，最多检索 50 条结果 |
| Wiki 结构输入 | 1,000,000 字节 | `wiki_structure_input_too_large`，退出码 2 |
| Wiki 页面输入/正文 | 1,500,000 / 200,000 字节 | `wiki_page_input_too_large` / `wiki_page_body_too_large`，退出码 2 |

不能仅仅因为某台机器上的测试较慢就放宽阈值。先比较工作量、Corpus 比例和峰值内存
比例，再分析具体路径。只有相同测量显示改进超过运行间噪声，并且正确性测试保持绿色
时，才保留优化。

## 交付前检查

在仓库根目录执行新的验证：

```bash
make check
make test-all
.venv/bin/repo-dive --help
.venv/bin/repo-dive --version
git status --short
```

报告真实命令输出和剩余限制，不能声称规划中的命令已经可用。
