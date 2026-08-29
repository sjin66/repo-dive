<!-- repo-dive:contribution=game; locale=zh-CN; -->
<!-- repo-dive:page=game_runtime_loop_page; order=1; cardinality=1; shape=heading,paragraph,list,code_block; purpose=说明游戏运行循环与状态; evidence=必需证据包括入口、循环、更新代码和单基行号; constraints=保持帧阶段顺序、时序和所有权; -->
**{{repo_dive:game_runtime_loop_page}}**：说明启动、输入、模拟、渲染、音频和关闭。
<!-- repo-dive:page=scene_world_page; order=2; cardinality=1; shape=heading,paragraph,list,code_block; purpose=说明场景或世界组织; evidence=必需证据包括场景、实体、地图、加载器和单基行号; constraints=准确追踪加载、所有权、生命周期和转换; -->
**{{repo_dive:scene_world_page}}**：映射世界、场景、实体、加载、转换和持久化。
<!-- repo-dive:page=gameplay_systems_page; order=3; cardinality=1; shape=heading,paragraph,table,code_block; purpose=记录玩法系统及交互; evidence=必需证据包括系统、组件、规则、符号和单基行号; constraints=准确使用状态、输入、输出与依赖; -->
**{{repo_dive:gameplay_systems_page}}**：说明控制、规则、物理、AI、进度和系统耦合。
<!-- repo-dive:page=assets_content_page; order=4; cardinality=1; shape=heading,paragraph,table,list; purpose=说明资源与内容管道; evidence=必需证据包括资源清单、导入器、格式和单基行号; constraints=标明源、生成与运行时形式及所有权; -->
**{{repo_dive:assets_content_page}}**：记录美术、音频、关卡、本地化、导入和打包。
<!-- repo-dive:page=game_persistence_networking_page; order=5; cardinality=1; shape=heading,paragraph,list,code_block; purpose=说明存档与网络生命周期; evidence=必需证据包括序列化器、协议、会话和单基行号; constraints=区分本地与网络状态并准确陈述权威和恢复; -->
**{{repo_dive:game_persistence_networking_page}}**：涵盖存档、同步、会话、权威、失败和迁移。
<!-- repo-dive:page=game_build_testing_page; order=6; cardinality=1; shape=heading,paragraph,list,code_block; purpose=说明游戏测试、构建与分发; evidence=必需证据包括测试、导出预设、构建器和单基行号; constraints=目标命令、产物与发布约束必须有依据; -->
**{{repo_dive:game_build_testing_page}}**：说明自动测试、试玩、平台构建、打包和发布。
