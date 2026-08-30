<!-- repo-dive:contribution=developer_tool; locale=en; -->
<!-- repo-dive:page=developer_workflow_page; order=1; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Explain the developer workflow the tool enables; evidence=Commands, hooks, tasks, examples, paths, and one-based lines; constraints=Trace prerequisites inputs outputs and side effects in order; -->
#### {{repo_dive:developer_workflow_page}}
Describe setup, daily use, automation, feedback, failure handling, and cleanup.
<!-- repo-dive:page=tool_architecture_page; order=2; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Explain developer-tool architecture and boundaries; evidence=Entrypoints, services, adapters, protocols, paths, symbols, and one-based lines; constraints=Separate orchestration domain logic and external integration; -->
#### {{repo_dive:tool_architecture_page}}
Map invocation, processing stages, integrations, persistence, and diagnostics.
<!-- repo-dive:page=tool_configuration_page; order=3; cardinality=1; shape=heading,paragraph,table,code_block; purpose=Catalog developer-tool configuration; evidence=Schemas, files, flags, defaults, paths, and one-based lines; constraints=Preserve accepted values precedence and validation exactly; -->
#### {{repo_dive:tool_configuration_page}}
Document configuration sources, keys, defaults, precedence, and examples.
<!-- repo-dive:page=tool_integrations_page; order=4; cardinality=1; shape=heading,paragraph,table,code_block; purpose=Catalog editor build and service integrations; evidence=Adapters, manifests, APIs, hooks, paths, and one-based lines; constraints=State installation lifecycle permissions and failure behavior per integration; -->
#### {{repo_dive:tool_integrations_page}}
Explain integration contracts, activation, data exchange, compatibility, and isolation.
<!-- repo-dive:page=tool_extension_points_page; order=5; cardinality=1; shape=heading,paragraph,table,code_block; purpose=Explain supported developer-tool parser retriever and Provider extension boundaries; evidence=Protocol declarations, adapter interfaces, registration paths, constructors, symbols, and one-based lines; constraints=Include only when direct implementation Evidence declares a supported protocol boundary; -->
#### {{repo_dive:tool_extension_points_page}}
Document protocol obligations, implementation steps, registration, compatibility limits, and verification for evidenced extension boundaries.
<!-- repo-dive:page=tool_diagnostics_page; order=6; cardinality=1; shape=heading,paragraph,table,code_block; purpose=Explain diagnostics and troubleshooting; evidence=Errors, logs, checks, debug commands, paths, and one-based lines; constraints=Map symptoms to evidenced causes and safe recovery steps; -->
#### {{repo_dive:tool_diagnostics_page}}
Catalog observable failures, diagnostics, remediation, and escalation evidence.
<!-- repo-dive:page=tool_distribution_page; order=7; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Explain testing packaging and distribution; evidence=Tests, package metadata, release automation, paths, and one-based lines; constraints=Keep supported platforms artifacts and install channels grounded; -->
#### {{repo_dive:tool_distribution_page}}
Describe test gates, builds, packages, versions, release channels, and upgrades.
<!-- repo-dive:page=terminology_reference_page; order=8; cardinality=1; shape=heading,paragraph,table,code_block; purpose=Define consistent repository terminology and provenance interpretation; evidence=Public models, schemas, status fields, paths, symbols, and one-based lines; constraints=Pair localized terms with canonical identifiers and do not invent unsupported concepts; -->
#### {{repo_dive:terminology_reference_page}}
Define Evidence, Chunk, Index, Context, Provider, Corpus, and Skill consistently and explain scope/version fields.
Include prerequisites, first run, common commands, local verification, recovery, and a concise Evidence/Chunk/Index/Context/Provider/Corpus/Skill glossary. Do not infer extension points without direct implementation Evidence.
