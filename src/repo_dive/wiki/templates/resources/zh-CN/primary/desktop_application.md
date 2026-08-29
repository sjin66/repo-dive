<!-- repo-dive:contribution=desktop_application; locale=zh-CN; -->
<!-- repo-dive:page=desktop_process_architecture_page; order=1; cardinality=1; shape=heading,paragraph,list,code_block; purpose=说明桌面进程与运行边界; evidence=必需证据包括入口、进程、IPC、模块和单基行号; constraints=准确追踪启动、通信和所有权; -->
**{{repo_dive:desktop_process_architecture_page}}**：说明启动、进程隔离、IPC、资源和关闭。
<!-- repo-dive:page=desktop_ui_lifecycle_page; order=2; cardinality=1; shape=heading,paragraph,list,code_block; purpose=说明窗口、界面和应用生命周期; evidence=必需证据包括窗口、视图、菜单、钩子和单基行号; constraints=保持真实事件与状态转换; -->
**{{repo_dive:desktop_ui_lifecycle_page}}**：映射窗口、导航、命令、后台行为和事件。
<!-- repo-dive:page=desktop_state_storage_page; order=3; cardinality=1; shape=heading,paragraph,table,list; purpose=说明桌面状态与本地存储; evidence=必需证据包括模型、偏好、数据库、缓存和单基行号; constraints=区分设置、会话与持久内容; -->
**{{repo_dive:desktop_state_storage_page}}**：记录状态所有权、位置、迁移和恢复。
<!-- repo-dive:page=os_integration_page; order=4; cardinality=1; shape=heading,paragraph,table,code_block; purpose=记录操作系统集成; evidence=必需证据包括原生 API、文件关联、协议和单基行号; constraints=准确陈述平台差异、权限和回退; -->
**{{repo_dive:os_integration_page}}**：涵盖文件系统、通知、菜单、快捷键和原生适配器。
<!-- repo-dive:page=desktop_security_page; order=5; cardinality=1; shape=heading,paragraph,table,list; purpose=说明桌面信任边界; evidence=必需证据包括沙箱、更新、IPC 校验、密钥和单基行号; constraints=标明执行位置和不可信边界; -->
**{{repo_dive:desktop_security_page}}**：说明本地信任、IPC、安全存储、隔离和更新。
<!-- repo-dive:page=desktop_distribution_testing_page; order=6; cardinality=1; shape=heading,paragraph,list,code_block; purpose=说明桌面测试、打包与更新; evidence=必需证据包括测试、构建器、签名、更新代码和单基行号; constraints=平台命令和发布渠道必须有依据; -->
**{{repo_dive:desktop_distribution_testing_page}}**：记录测试、安装包、签名、更新、兼容和回滚。
