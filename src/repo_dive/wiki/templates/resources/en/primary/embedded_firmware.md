<!-- repo-dive:contribution=embedded_firmware; locale=en; -->
<!-- repo-dive:page=target_hardware_page; order=1; cardinality=1; shape=heading,paragraph,table,list; purpose=Catalog target hardware and resource limits; evidence=Board configs, memory maps, datasheets referenced in source, paths, and one-based lines; constraints=State only repository-evidenced targets clocks memory and peripherals; -->
#### {{repo_dive:target_hardware_page}}
Describe processors, boards, memory, peripherals, electrical assumptions, and variants.
<!-- repo-dive:page=firmware_architecture_page; order=2; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Explain firmware modules and startup; evidence=Boot code, drivers, tasks, linker config, paths, symbols, and one-based lines; constraints=Trace boot and dependency order under declared resource limits; -->
#### {{repo_dive:firmware_architecture_page}}
Map boot, hardware abstraction, drivers, services, application logic, and faults.
<!-- repo-dive:page=realtime_lifecycle_page; order=3; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Explain scheduling interrupts and timing; evidence=Tasks, ISRs, timers, state machines, paths, symbols, and one-based lines; constraints=Preserve priorities concurrency boundaries and timing values exactly; -->
#### {{repo_dive:realtime_lifecycle_page}}
Describe scheduling, interrupts, concurrency, state transitions, deadlines, and reset.
<!-- repo-dive:page=io_protocols_page; order=4; cardinality=1; shape=heading,paragraph,table,code_block; purpose=Catalog device input output and protocols; evidence=Drivers, packet definitions, pins, paths, symbols, and one-based lines; constraints=Use exact units framing ranges and error behavior; -->
#### {{repo_dive:io_protocols_page}}
Document pins, buses, packet formats, commands, telemetry, and validation.
<!-- repo-dive:page=safety_constraints_page; order=5; cardinality=1; shape=heading,paragraph,table,list; purpose=Explain safety security and hardware constraints; evidence=Bounds, watchdogs, checks, boot security, paths, and one-based lines; constraints=Do not infer certification or guarantees absent from evidence; -->
#### {{repo_dive:safety_constraints_page}}
Cover fail-safe states, limits, watchdogs, update integrity, and hazardous inputs.
<!-- repo-dive:page=firmware_testing_distribution_page; order=6; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Explain firmware test build flash and release; evidence=Harnesses, simulators, build configs, flashing tools, paths, and one-based lines; constraints=Keep target-specific commands artifacts and rollback grounded; -->
#### {{repo_dive:firmware_testing_distribution_page}}
Describe unit and hardware tests, builds, images, flashing, versioning, and recovery.
