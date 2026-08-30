<!-- repo-dive:contribution=cli_tool; locale=zh-CN; -->
<!-- repo-dive:page=cli_installation_page; order=1; cardinality=1; shape=heading,paragraph,list,code_block; purpose=说明受支持的 CLI 安装与启动; evidence=必需证据包括包元数据、可执行入口、安装命令和单基行号; constraints=仅使用有证据的前置条件和可运行命令，不得重复外壳标题; -->
**{{repo_dive:cli_installation_page}}**：记录前置条件、安装方式、可执行文件发现和首次调用。
<!-- repo-dive:page=command_reference_page; order=2; cardinality=1; shape=heading,paragraph,table,code_block; purpose=提供准确的命令与选项参考; evidence=必需证据包括参数声明、帮助契约、处理器、符号和单基行号; constraints=准确保留名称、默认值、必需性、预算、输出和示例; -->
**{{repo_dive:command_reference_page}}**：列出命令、参数、选项、默认值、输出和代表性调用。
<!-- repo-dive:page=cli_configuration_page; order=3; cardinality=1; shape=heading,paragraph,table,code_block; purpose=说明 CLI 配置优先级和校验; evidence=必需证据包括配置模型、文件、标志、符号和单基行号; constraints=仅在有证据时陈述优先级、默认值和可接受值; -->
**{{repo_dive:cli_configuration_page}}**：说明配置来源、优先级、校验、默认值和安全示例。
<!-- repo-dive:page=execution_flow_page; order=4; cardinality=1; shape=heading,paragraph,list,code_block; purpose=追踪命令跨模块执行流程; evidence=必需证据包括入口、分派、服务、适配器和单基行号; constraints=保持确定顺序并区分 stdout、stderr 与持久化副作用; -->
**{{repo_dive:execution_flow_page}}**：追踪解析、校验、领域执行、适配器、输出和退出选择。
<!-- repo-dive:page=cli_extension_points_page; order=5; cardinality=1; shape=heading,paragraph,table,code_block; purpose=说明受支持的 CLI 扩展边界; evidence=必需证据包括协议、注册表、适配器、构造器和单基行号; constraints=不得把内部巧合描述为受支持的扩展 API; -->
**{{repo_dive:cli_extension_points_page}}**：记录显式接口、适配器契约、注册和兼容限制。
<!-- repo-dive:page=errors_exit_codes_page; order=6; cardinality=1; shape=heading,paragraph,table,code_block; purpose=映射失败、诊断和进程退出码; evidence=必需证据包括异常、错误信封、退出常量和单基行号; constraints=准确保留稳定代码、输出通道和重试指导; -->
**{{repo_dive:errors_exit_codes_page}}**：列出校验、输入、操作和内部失败的可观察行为。
<!-- repo-dive:page=terminology_reference_page; order=7; cardinality=1; shape=heading,paragraph,table,code_block; purpose=定义一致的代码库术语与来源解释; evidence=公共模型、Schema、状态字段、路径、符号与从一开始的行号; constraints=本地化术语首次出现时配对规范标识，且不得编造不支持的概念; -->
**{{repo_dive:terminology_reference_page}}**：一致定义 Evidence、Chunk、Index、Context、Provider、Corpus 与 Skill，并解释范围和版本字段。
补充规范本地检查、安全恢复，以及 Evidence/Chunk/Index/Context/Provider/Corpus/Skill 术语表。只有直接实现 Evidence 证明边界时才说明 Parser、Retriever 或 Provider 扩展流程。
