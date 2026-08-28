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
tests/fixtures/       小型且明确的仓库 Fixture
evals/cases/          机器可读的 Agent/RAG 评测用例
docs/en/              英文工程文档
docs/zh-CN/           简体中文对应文档
docs/superpowers/     已批准的规范和实施计划
```

## 文档变更

英文与简体中文文件必须在同一提交中更新。技术常量、路径、退出码、JSON 字段名和命令示例必须一致。Agent 与 Harness 策略放在根目录 `AGENTS.md`；兼容文件只引用它，不能复制策略。

## 依赖变更

运行时依赖必须支持 Python 3.11，并拥有边界清晰的用途。把决策写入功能设计，在 `pyproject.toml` 中添加依赖，并测试适配器行为，而不是重复测试依赖自身内部实现。

仅开发使用的工具放入 `dev` 可选依赖。贡献者和 CI 都以 `make setup` 作为唯一安装路径。

## 评测变更

检索与上下文启发式算法必须增加 `evals/cases/` 用例。每个用例包含稳定 ID、类别、Prompt 和预期行为。尚不可执行的用例用于记录产品契约，不能假装功能已经存在。

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

