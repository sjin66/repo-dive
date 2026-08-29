<!-- repo-dive:contribution=infrastructure; locale=zh-CN; -->
<!-- repo-dive:page=resource_topology_page; order=1; cardinality=1; shape=heading,paragraph,table,list; purpose=记录托管资源与依赖拓扑; evidence=必需证据包括声明、模块、堆栈、符号和单基行号; constraints=准确使用资源身份、范围和依赖方向; -->
**{{repo_dive:resource_topology_page}}**：说明计算、存储、网络、身份、依赖和所有权。
<!-- repo-dive:page=environments_state_page; order=2; cardinality=1; shape=heading,paragraph,table,list; purpose=说明环境、配置与状态; evidence=必需证据包括后端、变量、工作区和单基行号; constraints=不得暴露密钥值并区分共享与环境状态; -->
**{{repo_dive:environments_state_page}}**：映射环境、配置输入、状态存储、提升和漂移。
<!-- repo-dive:page=network_security_page; order=3; cardinality=1; shape=heading,paragraph,table,list; purpose=说明网络与身份边界; evidence=必需证据包括策略、路由、角色、加密和单基行号; constraints=仅陈述实际执行和最小权限关系; -->
**{{repo_dive:network_security_page}}**：涵盖信任区、出入站、身份、密钥、加密和审计。
<!-- repo-dive:page=infrastructure_change_page; order=4; cardinality=1; shape=heading,paragraph,list,code_block; purpose=说明计划、应用与变更控制; evidence=必需证据包括自动化、命令、管道、策略和单基行号; constraints=前置顺序、审批与回滚必须有依据; -->
**{{repo_dive:infrastructure_change_page}}**：追踪校验、计划、审批、应用、发布和回滚。
<!-- repo-dive:page=observability_recovery_page; order=5; cardinality=1; shape=heading,paragraph,list,code_block; purpose=说明基础设施监控与恢复; evidence=必需证据包括指标、日志、告警、备份、手册和单基行号; constraints=区分自动恢复与人工流程; -->
**{{repo_dive:observability_recovery_page}}**：说明健康信号、告警、备份、恢复和故障转移。
<!-- repo-dive:page=infrastructure_testing_page; order=6; cardinality=1; shape=heading,paragraph,list,code_block; purpose=说明基础设施校验与测试; evidence=必需证据包括静态检查、策略测试、集成测试和单基行号; constraints=如实陈述范围与环境影响; -->
**{{repo_dive:infrastructure_testing_page}}**：记录格式、校验、策略、计划、集成和冒烟测试。
