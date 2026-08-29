<!-- repo-dive:contribution=general_mixed; locale=en; -->
<!-- repo-dive:page=component_catalog_page; order=1; cardinality=1; shape=heading,paragraph,table,list; purpose=Catalog independently evidenced repository components; evidence=Entrypoints, manifests, modules, paths, symbols, and one-based lines; constraints=Do not force a dominant archetype and state ownership for each component; -->
#### {{repo_dive:component_catalog_page}}
Identify each component, purpose, technology, entrypoint, data, and owner.
<!-- repo-dive:page=shared_contracts_page; order=2; cardinality=1; shape=heading,paragraph,table,code_block; purpose=Explain contracts shared across components; evidence=Schemas, protocols, shared packages, paths, symbols, and one-based lines; constraints=Preserve exact producers consumers versions and compatibility; -->
#### {{repo_dive:shared_contracts_page}}
Document shared types, APIs, files, messages, libraries, and configuration.
<!-- repo-dive:page=cross_component_workflows_page; order=3; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Trace workflows crossing component boundaries; evidence=Call paths, jobs, scripts, tests, paths, symbols, and one-based lines; constraints=Keep sequence and handoff evidence explicit; -->
#### {{repo_dive:cross_component_workflows_page}}
Trace user, data, build, and operational flows across component ownership.
<!-- repo-dive:page=build_test_matrix_page; order=4; cardinality=1; shape=heading,paragraph,table,list; purpose=Explain per-component build and test contracts; evidence=Build files, test suites, automation, paths, and one-based lines; constraints=Separate shared gates from component-specific commands and requirements; -->
#### {{repo_dive:build_test_matrix_page}}
Map setup, build, test, artifacts, dependencies, and CI coverage by component.
<!-- repo-dive:page=mixed_operations_page; order=5; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Explain coordinated operation and release; evidence=Deployment, publishing, runbooks, commands, paths, and one-based lines; constraints=Do not imply unified deployment where components release independently; -->
#### {{repo_dive:mixed_operations_page}}
Describe component releases, shared environments, observability, incidents, and recovery.
