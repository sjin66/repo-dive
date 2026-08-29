<!-- repo-dive:contribution=mobile_application; locale=zh-CN; -->
<!-- repo-dive:page=mobile_runtime_architecture_page; order=1; cardinality=1; shape=heading,paragraph,list,code_block; purpose=说明移动运行时、模块与生命周期边界; evidence=必需证据包括入口、模块、服务、符号和单基行号; constraints=按顺序追踪生命周期与数据流，不重复外壳标题; -->
**{{repo_dive:mobile_runtime_architecture_page}}**：说明启动、前后台、依赖、资源所有权和故障。
<!-- repo-dive:page=mobile_navigation_page; order=2; cardinality=1; shape=heading,paragraph,list,code_block; purpose=说明界面与导航流程; evidence=必需证据包括路由、视图、深链、符号和单基行号; constraints=保持实际转换和导航状态所有权; -->
**{{repo_dive:mobile_navigation_page}}**：映射界面、转换、深链、恢复和访问守卫。
<!-- repo-dive:page=mobile_state_storage_page; order=3; cardinality=1; shape=heading,paragraph,table,list; purpose=说明移动状态与存储; evidence=必需证据包括存储、数据库、缓存、模型和单基行号; constraints=区分瞬态、安全、同步和持久状态; -->
**{{repo_dive:mobile_state_storage_page}}**：记录状态所有权、持久化、离线、同步和迁移。
<!-- repo-dive:page=platform_integration_page; order=4; cardinality=1; shape=heading,paragraph,table,code_block; purpose=记录操作系统集成; evidence=必需证据包括权限、服务、清单、适配器和单基行号; constraints=准确陈述平台与权限要求; -->
**{{repo_dive:platform_integration_page}}**：涵盖通知、传感器、后台任务、权限和原生服务。
<!-- repo-dive:page=mobile_security_page; order=5; cardinality=1; shape=heading,paragraph,table,list; purpose=说明移动安全与隐私边界; evidence=必需证据包括密钥存储、传输、权限、校验和单基行号; constraints=区分代码控制与平台保证; -->
**{{repo_dive:mobile_security_page}}**：说明身份、本地密钥、网络、隐私和不可信输入。
<!-- repo-dive:page=mobile_distribution_testing_page; order=6; cardinality=1; shape=heading,paragraph,list,code_block; purpose=说明移动测试、构建与分发; evidence=必需证据包括测试目标、构建、签名、自动化和单基行号; constraints=命令、变体、签名和渠道必须有依据; -->
**{{repo_dive:mobile_distribution_testing_page}}**：记录测试层、构建变体、签名、商店和发布。
