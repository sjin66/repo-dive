<!-- repo-dive:contribution=mobile_application; locale=en; -->
<!-- repo-dive:page=mobile_runtime_architecture_page; order=1; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Explain mobile runtime and module boundaries; evidence=Application entrypoints, modules, services, paths, symbols, and one-based lines; constraints=Trace lifecycle and data flow without reproducing CLI-owned shell headings; -->
#### {{repo_dive:mobile_runtime_architecture_page}}
Describe startup, foreground and background lifecycle, modules, dependencies, and failures.
<!-- repo-dive:page=mobile_navigation_page; order=2; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Explain screens and navigation flow; evidence=Routes, coordinators, views, deep links, paths, symbols, and one-based lines; constraints=Preserve actual transitions and ownership of navigation state; -->
#### {{repo_dive:mobile_navigation_page}}
Map screens, transitions, deep links, state restoration, and access guards.
<!-- repo-dive:page=mobile_state_storage_page; order=3; cardinality=1; shape=heading,paragraph,table,list; purpose=Explain mobile state and storage; evidence=Stores, databases, caches, models, paths, symbols, and one-based lines; constraints=Separate transient secure synchronized and durable state; -->
#### {{repo_dive:mobile_state_storage_page}}
Document state owners, persistence, synchronization, offline behavior, and migration.
<!-- repo-dive:page=platform_integration_page; order=4; cardinality=1; shape=heading,paragraph,table,code_block; purpose=Catalog operating-system integrations; evidence=Permissions, services, manifests, adapters, paths, and one-based lines; constraints=State platform and permission requirements exactly; -->
#### {{repo_dive:platform_integration_page}}
Cover notifications, sensors, background work, permissions, and native services.
<!-- repo-dive:page=mobile_security_page; order=5; cardinality=1; shape=heading,paragraph,table,list; purpose=Explain mobile security and privacy boundaries; evidence=Key storage, transport, permissions, validation, paths, and one-based lines; constraints=Distinguish code controls from platform guarantees; -->
#### {{repo_dive:mobile_security_page}}
Describe identity, local secrets, network protection, privacy, and untrusted input.
<!-- repo-dive:page=mobile_distribution_testing_page; order=6; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Explain mobile testing build and distribution; evidence=Test targets, build settings, signing, automation, paths, and one-based lines; constraints=Keep commands variants signing and release channels grounded; -->
#### {{repo_dive:mobile_distribution_testing_page}}
Document test layers, build variants, signing, packaging, stores, and rollout.
