<!-- repo-dive:contribution=desktop_application; locale=en; -->
<!-- repo-dive:page=desktop_process_architecture_page; order=1; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Explain desktop processes and runtime boundaries; evidence=Entrypoints, processes, IPC, modules, paths, symbols, and one-based lines; constraints=Trace startup and communication with exact ownership; -->
#### {{repo_dive:desktop_process_architecture_page}}
Describe startup, process separation, IPC, modules, resource ownership, and shutdown.
<!-- repo-dive:page=desktop_ui_lifecycle_page; order=2; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Explain windows UI and application lifecycle; evidence=Windows, views, menus, lifecycle hooks, paths, symbols, and one-based lines; constraints=Preserve actual event and state transitions; -->
#### {{repo_dive:desktop_ui_lifecycle_page}}
Map windows, navigation, commands, background behavior, and lifecycle events.
<!-- repo-dive:page=desktop_state_storage_page; order=3; cardinality=1; shape=heading,paragraph,table,list; purpose=Explain desktop state and local storage; evidence=Models, preferences, databases, caches, paths, and one-based lines; constraints=Separate user settings session state and durable content; -->
#### {{repo_dive:desktop_state_storage_page}}
Document state ownership, file locations, persistence, migration, and recovery.
<!-- repo-dive:page=os_integration_page; order=4; cardinality=1; shape=heading,paragraph,table,code_block; purpose=Catalog operating-system integrations; evidence=Native APIs, file associations, protocols, paths, symbols, and one-based lines; constraints=State platform differences permissions and fallbacks exactly; -->
#### {{repo_dive:os_integration_page}}
Cover filesystem, notifications, menus, shortcuts, protocols, and native adapters.
<!-- repo-dive:page=desktop_security_page; order=5; cardinality=1; shape=heading,paragraph,table,list; purpose=Explain desktop trust boundaries; evidence=Sandboxing, updates, IPC validation, secrets, paths, and one-based lines; constraints=Identify enforcement location and untrusted boundaries; -->
#### {{repo_dive:desktop_security_page}}
Describe local trust, IPC safety, content isolation, secret storage, and updates.
<!-- repo-dive:page=desktop_distribution_testing_page; order=6; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Explain desktop testing packaging and updates; evidence=Test suites, builders, signing, update code, paths, and one-based lines; constraints=Keep platform commands and release channels grounded; -->
#### {{repo_dive:desktop_distribution_testing_page}}
Document tests, installers, signing, update delivery, compatibility, and rollback.
