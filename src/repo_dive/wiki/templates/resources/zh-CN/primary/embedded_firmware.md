<!-- repo-dive:contribution=embedded_firmware; locale=zh-CN; -->
<!-- repo-dive:page=target_hardware_page; order=1; cardinality=1; shape=heading,paragraph,table,list; purpose=记录目标硬件与资源限制; evidence=必需证据包括板卡配置、内存映射、外设和单基行号; constraints=仅陈述代码库证实的目标、时钟、内存与外设; -->
**{{repo_dive:target_hardware_page}}**：说明处理器、板卡、内存、外设和变体。
<!-- repo-dive:page=firmware_architecture_page; order=2; cardinality=1; shape=heading,paragraph,list,code_block; purpose=说明固件模块与启动; evidence=必需证据包括引导、驱动、任务、链接配置和单基行号; constraints=在资源限制下按顺序追踪启动与依赖; -->
**{{repo_dive:firmware_architecture_page}}**：映射引导、硬件抽象、驱动、服务、逻辑和故障。
<!-- repo-dive:page=realtime_lifecycle_page; order=3; cardinality=1; shape=heading,paragraph,list,code_block; purpose=说明调度、中断与时序; evidence=必需证据包括任务、ISR、定时器、状态机和单基行号; constraints=准确保留优先级、并发边界和时间值; -->
**{{repo_dive:realtime_lifecycle_page}}**：说明调度、中断、并发、截止时间和复位。
<!-- repo-dive:page=io_protocols_page; order=4; cardinality=1; shape=heading,paragraph,table,code_block; purpose=记录设备输入输出与协议; evidence=必需证据包括驱动、数据包、引脚、符号和单基行号; constraints=准确使用单位、帧、范围与错误行为; -->
**{{repo_dive:io_protocols_page}}**：记录引脚、总线、数据包、命令、遥测和校验。
<!-- repo-dive:page=safety_constraints_page; order=5; cardinality=1; shape=heading,paragraph,table,list; purpose=说明安全、保障与硬件约束; evidence=必需证据包括边界、看门狗、检查、安全启动和单基行号; constraints=不得推断代码库未证明的认证或保证; -->
**{{repo_dive:safety_constraints_page}}**：涵盖失效安全、限制、看门狗、更新完整性和危险输入。
<!-- repo-dive:page=firmware_testing_distribution_page; order=6; cardinality=1; shape=heading,paragraph,list,code_block; purpose=说明固件测试、构建、烧录与发布; evidence=必需证据包括测试工具、模拟器、构建、烧录命令和单基行号; constraints=目标命令、产物与回滚必须有依据; -->
**{{repo_dive:firmware_testing_distribution_page}}**：说明测试、镜像、烧录、版本和恢复。
