<!-- repo-dive:contribution=developer_tool; locale=zh-CN; -->
<!-- repo-dive:page=developer_workflow_page; order=1; cardinality=1; shape=heading,paragraph,list,code_block; purpose=说明工具支持的开发工作流; evidence=必需证据包括命令、钩子、任务、示例和单基行号; constraints=按顺序追踪前置条件、输入、输出和副作用; -->
**{{repo_dive:developer_workflow_page}}**：说明设置、日常使用、自动化、反馈、失败和清理。
<!-- repo-dive:page=tool_architecture_page; order=2; cardinality=1; shape=heading,paragraph,list,code_block; purpose=说明开发工具架构与边界; evidence=必需证据包括入口、服务、适配器、协议和单基行号; constraints=区分编排、领域逻辑和外部集成; -->
**{{repo_dive:tool_architecture_page}}**：映射调用、处理阶段、集成、持久化和诊断。
<!-- repo-dive:page=tool_configuration_page; order=3; cardinality=1; shape=heading,paragraph,table,code_block; purpose=记录开发工具配置; evidence=必需证据包括模式、文件、标志、默认值和单基行号; constraints=准确保留值、优先级和校验; -->
**{{repo_dive:tool_configuration_page}}**：说明配置来源、键、默认值、优先级和示例。
<!-- repo-dive:page=tool_integrations_page; order=4; cardinality=1; shape=heading,paragraph,table,code_block; purpose=记录编辑器、构建与服务集成; evidence=必需证据包括适配器、清单、API、钩子和单基行号; constraints=按集成陈述安装、生命周期、权限和失败; -->
**{{repo_dive:tool_integrations_page}}**：说明集成契约、激活、数据交换、兼容和隔离。
<!-- repo-dive:page=tool_extension_points_page; order=5; cardinality=1; shape=heading,paragraph,table,code_block; purpose=说明开发工具支持的解析器、检索器与 Provider 扩展边界; evidence=必需证据包括协议声明、适配器接口、注册路径、构造器、符号和单基行号; constraints=仅在直接实现 Evidence 声明受支持协议边界时包含; -->
**{{repo_dive:tool_extension_points_page}}**：说明有证据的扩展协议义务、实现步骤、注册、兼容限制和验证。
<!-- repo-dive:page=tool_diagnostics_page; order=6; cardinality=1; shape=heading,paragraph,table,code_block; purpose=说明诊断与故障排查; evidence=必需证据包括错误、日志、检查、调试命令和单基行号; constraints=把症状映射到有证据的原因与安全恢复; -->
**{{repo_dive:tool_diagnostics_page}}**：列出可观察失败、诊断、修复和升级证据。
<!-- repo-dive:page=tool_distribution_page; order=7; cardinality=1; shape=heading,paragraph,list,code_block; purpose=说明测试、打包与分发; evidence=必需证据包括测试、包元数据、发布自动化和单基行号; constraints=平台、产物与安装渠道必须有依据; -->
**{{repo_dive:tool_distribution_page}}**：说明测试门槛、构建、包、版本、渠道和升级。
<!-- repo-dive:page=terminology_reference_page; order=8; cardinality=1; shape=heading,paragraph,table,code_block; purpose=定义一致的代码库术语与来源解释; evidence=公共模型、Schema、状态字段、路径、符号与从一开始的行号; constraints=本地化术语首次出现时配对规范标识，且不得编造不支持的概念; -->
**{{repo_dive:terminology_reference_page}}**：一致定义 Evidence、Chunk、Index、Context、Provider、Corpus 与 Skill，并解释范围和版本字段。
补充前置条件、首次运行、常用命令、本地验证、恢复和 Evidence/Chunk/Index/Context/Provider/Corpus/Skill 术语表。没有直接实现 Evidence 时不得推断扩展点。
