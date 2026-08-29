<!-- repo-dive:contribution=general_mixed; locale=zh-CN; -->
<!-- repo-dive:page=component_catalog_page; order=1; cardinality=1; shape=heading,paragraph,table,list; purpose=记录有独立证据的代码库组件; evidence=必需证据包括入口、清单、模块、符号和单基行号; constraints=不得强行指定主导类型并标明组件所有权; -->
**{{repo_dive:component_catalog_page}}**：识别组件用途、技术、入口、数据和所有者。
<!-- repo-dive:page=shared_contracts_page; order=2; cardinality=1; shape=heading,paragraph,table,code_block; purpose=说明跨组件共享契约; evidence=必需证据包括模式、协议、共享包和单基行号; constraints=准确保留生产者、消费者、版本和兼容性; -->
**{{repo_dive:shared_contracts_page}}**：记录共享类型、API、文件、消息、库和配置。
<!-- repo-dive:page=cross_component_workflows_page; order=3; cardinality=1; shape=heading,paragraph,list,code_block; purpose=追踪跨组件工作流; evidence=必需证据包括调用路径、作业、脚本、测试和单基行号; constraints=明确展示顺序和交接证据; -->
**{{repo_dive:cross_component_workflows_page}}**：追踪用户、数据、构建和运维流程。
<!-- repo-dive:page=build_test_matrix_page; order=4; cardinality=1; shape=heading,paragraph,table,list; purpose=说明各组件构建与测试契约; evidence=必需证据包括构建文件、测试、自动化和单基行号; constraints=区分共享门槛与组件专用命令; -->
**{{repo_dive:build_test_matrix_page}}**：映射设置、构建、测试、产物、依赖和 CI。
<!-- repo-dive:page=mixed_operations_page; order=5; cardinality=1; shape=heading,paragraph,list,code_block; purpose=说明协同运维与发布; evidence=必需证据包括部署、发布、手册、命令和单基行号; constraints=组件独立发布时不得暗示统一部署; -->
**{{repo_dive:mixed_operations_page}}**：说明组件发布、环境、可观测性、事故和恢复。
