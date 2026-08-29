<!-- repo-dive:contribution=data_pipeline; locale=zh-CN; -->
<!-- repo-dive:page=pipeline_sources_sinks_page; order=1; cardinality=1; shape=heading,paragraph,table,list; purpose=记录管道输入与输出边界; evidence=必需证据包括连接器、模式、清单、符号和单基行号; constraints=准确陈述所有权、格式、频率和敏感性; -->
**{{repo_dive:pipeline_sources_sinks_page}}**：映射来源、目标、契约、数据量、新鲜度和所有权。
<!-- repo-dive:page=pipeline_orchestration_page; order=2; cardinality=1; shape=heading,paragraph,list,code_block; purpose=说明调度与依赖编排; evidence=必需证据包括 DAG、作业、计划、命令和单基行号; constraints=保留依赖顺序、触发器和重试语义; -->
**{{repo_dive:pipeline_orchestration_page}}**：追踪调度、依赖、分区、回填、重试和并发。
<!-- repo-dive:page=pipeline_transformations_page; order=3; cardinality=1; shape=heading,paragraph,table,code_block; purpose=说明转换契约; evidence=必需证据包括转换代码、查询、模式、符号和单基行号; constraints=输入、输出和不变量必须有依据; -->
**{{repo_dive:pipeline_transformations_page}}**：列出阶段、映射、连接、聚合、模式和血缘。
<!-- repo-dive:page=data_quality_page; order=4; cardinality=1; shape=heading,paragraph,table,list; purpose=说明数据质量执行; evidence=必需证据包括断言、校验器、阈值、测试和单基行号; constraints=区分阻断检查与观察指标; -->
**{{repo_dive:data_quality_page}}**：记录完整性、有效性、新鲜度、对账和隔离行为。
<!-- repo-dive:page=pipeline_failure_recovery_page; order=5; cardinality=1; shape=heading,paragraph,list,code_block; purpose=说明管道失败与恢复; evidence=必需证据包括重试策略、检查点、死信、手册和单基行号; constraints=准确陈述幂等与重放边界; -->
**{{repo_dive:pipeline_failure_recovery_page}}**：涵盖检测、重试、部分状态、重放、回填和人工操作。
<!-- repo-dive:page=pipeline_operations_page; order=6; cardinality=1; shape=heading,paragraph,list,code_block; purpose=说明持续管道运维; evidence=必需证据包括部署、遥测、告警、命令和单基行号; constraints=运维流程必须有顺序且有证据; -->
**{{repo_dive:pipeline_operations_page}}**：说明部署、监控、容量、血缘、事故和维护。
