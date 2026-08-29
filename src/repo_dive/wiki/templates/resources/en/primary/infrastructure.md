<!-- repo-dive:contribution=infrastructure; locale=en; -->
<!-- repo-dive:page=resource_topology_page; order=1; cardinality=1; shape=heading,paragraph,table,list; purpose=Catalog managed infrastructure resources and dependencies; evidence=Declarations, modules, stacks, paths, symbols, and one-based lines; constraints=Use exact resource identity scope and dependency direction; -->
#### {{repo_dive:resource_topology_page}}
Describe compute, storage, networking, identities, dependencies, and ownership.
<!-- repo-dive:page=environments_state_page; order=2; cardinality=1; shape=heading,paragraph,table,list; purpose=Explain environments configuration and state; evidence=Backends, variables, workspaces, paths, symbols, and one-based lines; constraints=Do not expose secret values and distinguish shared from environment-specific state; -->
#### {{repo_dive:environments_state_page}}
Map environments, configuration inputs, state storage, promotion, and drift.
<!-- repo-dive:page=network_security_page; order=3; cardinality=1; shape=heading,paragraph,table,list; purpose=Explain network and identity boundaries; evidence=Policies, routes, roles, encryption config, paths, and one-based lines; constraints=State actual enforcement and least-privilege relationships only; -->
#### {{repo_dive:network_security_page}}
Cover trust zones, ingress, egress, identities, secrets, encryption, and audit.
<!-- repo-dive:page=infrastructure_change_page; order=4; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Explain plan apply deployment and change control; evidence=Automation, commands, pipelines, policies, paths, and one-based lines; constraints=Keep prerequisite ordering approvals and rollback behavior grounded; -->
#### {{repo_dive:infrastructure_change_page}}
Trace validation, planning, approval, application, rollout, and rollback.
<!-- repo-dive:page=observability_recovery_page; order=5; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Explain infrastructure monitoring and recovery; evidence=Metrics, logs, alerts, backups, runbooks, paths, and one-based lines; constraints=Distinguish automated recovery from manual procedure; -->
#### {{repo_dive:observability_recovery_page}}
Describe health signals, alerting, backup, restore, failover, and incidents.
<!-- repo-dive:page=infrastructure_testing_page; order=6; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Explain infrastructure validation and testing; evidence=Static checks, policy tests, integration tests, commands, paths, and one-based lines; constraints=Report test scope and environment impact without inferred guarantees; -->
#### {{repo_dive:infrastructure_testing_page}}
Document formatting, validation, policy, plan, integration, and smoke tests.
