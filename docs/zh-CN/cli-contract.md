# CLI 契约

## 目标调用方

这份契约面向 GitHub Copilot、Shell 脚本和 CI 等非交互调用方。相较于人类友好的展示，可预测的进程行为优先级更高。

## 调用方式

命令显式接收仓库路径，不能从无关父目录推断另一个仓库。相对输入路径基于当前工作目录解析，并在元数据中以规范化绝对仓库根目录返回。

功能命令将支持：

```text
repo-dive <command> [repository] --format json
```

基础版本当前只实现 `repo-dive --help` 和 `repo-dive --version`。

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

未来 JSON 命令使用以下顶层结构：

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

可能返回仓库内容的命令必须提供 `--token-budget` 或 `--max-results` 等明确限制。响应要报告实际预算、估算用量以及证据是否被截断。稳定元数据不占用调用方的证据预算。

## 幂等性与写入

只读命令不能产生仓库副作用。索引和 Wiki 命令只能写入 `<repository>/.repo-dive/`。仓库状态和参数相同时，重复执行产生等价的结构化输出，时间戳和耗时字段除外。

写入使用同目录临时文件和原子替换。失败命令不能暴露只写了一半的 JSON 或 Markdown 产物。

## 兼容性

新增可选字段属于向后兼容。字段重命名或删除、类型变化、退出码语义变化以及产物路径变化，都要求升级 Schema 或命令版本。

