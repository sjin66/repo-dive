<!-- repo-dive:contribution=plugin_extension; locale=zh-CN; -->
<!-- repo-dive:page=host_contract_page; order=1; cardinality=1; shape=heading,paragraph,table,code_block; purpose=定义插件宿主契约; evidence=必需证据包括宿主 API、清单、协议和单基行号; constraints=区分公开扩展契约与宿主内部实现; -->
**{{repo_dive:host_contract_page}}**：记录宿主版本、API、回调、数据交换和错误。
<!-- repo-dive:page=plugin_activation_page; order=2; cardinality=1; shape=heading,paragraph,list,code_block; purpose=说明插件发现、激活与关闭; evidence=必需证据包括入口、注册、事件、符号和单基行号; constraints=保持触发顺序、状态和清理行为; -->
**{{repo_dive:plugin_activation_page}}**：追踪发现、加载、激活、事件、停用和失败。
<!-- repo-dive:page=contribution_points_page; order=3; cardinality=1; shape=heading,paragraph,table,code_block; purpose=记录插件贡献点; evidence=必需证据包括命令、提供者、钩子、模式和单基行号; constraints=准确使用标识、输入、输出与注册规则; -->
**{{repo_dive:contribution_points_page}}**：说明每个注册能力、调用契约和所有者。
<!-- repo-dive:page=plugin_permissions_page; order=4; cardinality=1; shape=heading,paragraph,table,list; purpose=说明权限、隔离与信任; evidence=必需证据包括权限声明、沙箱边界、校验和单基行号; constraints=不得推断不存在的沙箱保证; -->
**{{repo_dive:plugin_permissions_page}}**：涵盖宿主、数据、网络、密钥和校验权限。
<!-- repo-dive:page=plugin_compatibility_page; order=5; cardinality=1; shape=heading,paragraph,table,list; purpose=说明宿主与插件兼容性; evidence=必需证据包括版本范围、功能检查、迁移、测试和单基行号; constraints=保留显式兼容与降级行为; -->
**{{repo_dive:plugin_compatibility_page}}**：记录宿主版本、协商、变化和迁移。
<!-- repo-dive:page=plugin_packaging_testing_page; order=6; cardinality=1; shape=heading,paragraph,list,code_block; purpose=说明插件测试、打包与发布; evidence=必需证据包括工具、清单、构建器、发布配置和单基行号; constraints=包内容、校验和发布步骤必须有依据; -->
**{{repo_dive:plugin_packaging_testing_page}}**：说明宿主测试、打包、签名、发布和更新。
