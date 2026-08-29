<!-- repo-dive:contribution=service_api; locale=zh-CN; -->
<!-- repo-dive:page=service_runtime_architecture_page; order=1; cardinality=1; shape=heading,paragraph,list,code_block; purpose=说明服务启动与请求处理架构; evidence=必需证据包括入口、中间件、处理器、依赖和单基行号; constraints=按顺序追踪生命周期且不得重复 CLI 外壳标题; -->
**{{repo_dive:service_runtime_architecture_page}}**：追踪初始化、分派、领域工作、持久化和响应。
<!-- repo-dive:page=api_contracts_page; order=2; cardinality=1; shape=heading,paragraph,table,code_block; purpose=记录稳定 API 契约; evidence=必需证据包括规范、模式、端点声明、符号和单基行号; constraints=准确保留方法、字段、状态行为和示例; -->
**{{repo_dive:api_contracts_page}}**：说明端点用途、请求响应形状、兼容性和所有权。
<!-- repo-dive:page=request_validation_page; order=3; cardinality=1; shape=heading,paragraph,table,code_block; purpose=说明请求校验和错误映射; evidence=必需证据包括校验器、解析器、错误类型和单基行号; constraints=区分调用校验与领域失败并保持错误语义; -->
**{{repo_dive:request_validation_page}}**：追踪不可信输入的规范化、拒绝和稳定错误。
<!-- repo-dive:page=service_persistence_page; order=4; cardinality=1; shape=heading,paragraph,table,list; purpose=说明服务数据所有权和一致性; evidence=必需证据包括模型、查询、事务、迁移和单基行号; constraints=标明事务边界且不得推断不存在的模式; -->
**{{repo_dive:service_persistence_page}}**：说明数据、访问路径、一致性、迁移和恢复。
<!-- repo-dive:page=service_security_page; order=5; cardinality=1; shape=heading,paragraph,table,list; purpose=说明服务信任边界; evidence=必需证据包括认证、授权、密钥处理和单基行号; constraints=区分配置策略与代码执行的控制; -->
**{{repo_dive:service_security_page}}**：涵盖身份、授权、传输、输入安全和密钥。
<!-- repo-dive:page=service_operations_page; order=6; cardinality=1; shape=heading,paragraph,list,code_block; purpose=说明服务部署与运维; evidence=必需证据包括清单、健康检查、遥测、运行手册和单基行号; constraints=命令、失败流程和回滚必须有依据并有顺序; -->
**{{repo_dive:service_operations_page}}**：说明部署、健康、扩缩容、故障处理和回滚。
