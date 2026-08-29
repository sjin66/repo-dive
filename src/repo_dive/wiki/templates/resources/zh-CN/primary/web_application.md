<!-- repo-dive:contribution=web_application; locale=zh-CN; -->
<!-- repo-dive:page=web_runtime_architecture_page; order=1; cardinality=1; shape=heading,paragraph,list,code_block; purpose=说明浏览器与服务端运行边界和请求生命周期; evidence=必需证据包括入口、组件、调用路径、符号和单基行号; constraints=按顺序使用 H4/H5、正文、列表和代码，且不得重复外壳标题; -->
**{{repo_dive:web_runtime_architecture_page}}**：追踪启动、渲染、请求处理、状态所有权和故障边界。
<!-- repo-dive:page=routes_interfaces_page; order=2; cardinality=1; shape=heading,paragraph,table,code_block; purpose=记录路由及外部接口契约; evidence=必需证据包括路由声明、处理器、模式、符号和单基行号; constraints=使用准确名称、对照表和有依据的示例，不得虚构端点; -->
**{{repo_dive:routes_interfaces_page}}**：说明输入、输出、认证和实现所有权。
<!-- repo-dive:page=web_state_persistence_page; order=3; cardinality=1; shape=heading,paragraph,table,list; purpose=说明客户端与服务端状态持久化; evidence=必需证据包括存储、模型、迁移、缓存、符号和单基行号; constraints=区分瞬态与持久状态并保持声明的节点顺序; -->
**{{repo_dive:web_state_persistence_page}}**：映射状态生产者、消费者、一致性和失效策略。
<!-- repo-dive:page=web_security_page; order=4; cardinality=1; shape=heading,paragraph,table,list; purpose=说明 Web 信任边界和安全控制; evidence=必需证据包括认证、授权、校验、响应头、符号和单基行号; constraints=仅陈述有证据的控制并区分代码执行与配置; -->
**{{repo_dive:web_security_page}}**：涵盖身份、会话、授权、输入处理、浏览器防护和密钥。
<!-- repo-dive:page=web_deployment_operations_page; order=5; cardinality=1; shape=heading,paragraph,list,code_block; purpose=说明构建、部署和运行运维; evidence=必需证据包括构建文件、环境配置、部署清单和单基行号; constraints=命令必须有依据、有顺序并区分构建时与运行时; -->
**{{repo_dive:web_deployment_operations_page}}**：说明产物、环境、发布、可观测性、扩缩容和恢复。
<!-- repo-dive:page=web_testing_page; order=6; cardinality=1; shape=heading,paragraph,list,code_block; purpose=说明 Web 测试策略; evidence=必需证据包括测试套件、夹具、浏览器工具、命令和单基行号; constraints=区分单元、集成与浏览器覆盖，不作无证据质量判断; -->
**{{repo_dive:web_testing_page}}**：展示测试层次、设置、命令和覆盖边界。
