<!-- repo-dive:contribution=library_sdk; locale=zh-CN; -->
<!-- repo-dive:page=library_installation_page; order=1; cardinality=1; shape=heading,paragraph,list,code_block; purpose=说明库的安装、导入与初始化; evidence=必需证据包括包元数据、导出、版本约束和单基行号; constraints=仅使用有证据的环境与最小可运行示例; -->
**{{repo_dive:library_installation_page}}**：记录安装、导入路径、初始化和平台前置条件。
<!-- repo-dive:page=public_api_page; order=2; cardinality=1; shape=heading,paragraph,table,code_block; purpose=定义受支持的公共 API; evidence=必需证据包括导出、签名、类型、文档字符串和单基行号; constraints=区分公共契约与实现细节并保留准确签名; -->
**{{repo_dive:public_api_page}}**：列出公共类型、函数、参数、返回值、错误和生命周期。
<!-- repo-dive:page=usage_examples_page; order=3; cardinality=1; shape=heading,paragraph,table,code_block; purpose=提供有依据的使用模式; evidence=必需证据包括示例、测试、夹具、调用点和单基行号; constraints=示例必须可执行并标明设置与清理; -->
**{{repo_dive:usage_examples_page}}**：展示基础、组合和失败处理用法，不得虚构能力。
<!-- repo-dive:page=library_extension_page; order=4; cardinality=1; shape=heading,paragraph,list,code_block; purpose=说明受支持的定制与扩展; evidence=必需证据包括协议、钩子、子类、适配器和单基行号; constraints=标明每个扩展点的稳定性和所有权边界; -->
**{{repo_dive:library_extension_page}}**：说明扩展接口、注册、生命周期和实现义务。
<!-- repo-dive:page=compatibility_page; order=5; cardinality=1; shape=heading,paragraph,table,list; purpose=说明版本与平台兼容性; evidence=必需证据包括版本元数据、弃用、矩阵、测试和单基行号; constraints=不得超出显式配置或测试推断支持范围; -->
**{{repo_dive:compatibility_page}}**：涵盖语言平台支持、语义变化、弃用和迁移。
