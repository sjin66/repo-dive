<!-- repo-dive:contribution=data_pipeline; locale=en; -->
<!-- repo-dive:page=pipeline_sources_sinks_page; order=1; cardinality=1; shape=heading,paragraph,table,list; purpose=Catalog pipeline inputs and outputs; evidence=Connectors, schemas, manifests, paths, symbols, and one-based lines; constraints=State ownership formats frequency and sensitivity for each boundary; -->
#### {{repo_dive:pipeline_sources_sinks_page}}
Map source and sink systems, contracts, volumes, freshness, and ownership.
<!-- repo-dive:page=pipeline_orchestration_page; order=2; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Explain scheduling and dependency orchestration; evidence=DAGs, jobs, schedules, commands, paths, and one-based lines; constraints=Preserve dependency order triggers and retry semantics; -->
#### {{repo_dive:pipeline_orchestration_page}}
Trace scheduling, dependencies, partitioning, backfills, retries, and concurrency.
<!-- repo-dive:page=pipeline_transformations_page; order=3; cardinality=1; shape=heading,paragraph,table,code_block; purpose=Explain transformation contracts; evidence=Transform code, queries, schemas, paths, symbols, and one-based lines; constraints=Keep input output and invariant descriptions grounded; -->
#### {{repo_dive:pipeline_transformations_page}}
Catalog stages, mappings, joins, aggregations, schemas, and lineage.
<!-- repo-dive:page=data_quality_page; order=4; cardinality=1; shape=heading,paragraph,table,list; purpose=Explain data-quality enforcement; evidence=Assertions, validators, thresholds, tests, paths, and one-based lines; constraints=Distinguish blocking checks from observational metrics; -->
#### {{repo_dive:data_quality_page}}
Document completeness, validity, freshness, reconciliation, and quarantine behavior.
<!-- repo-dive:page=pipeline_failure_recovery_page; order=5; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Explain pipeline failure and recovery; evidence=Retry policies, checkpoints, dead letters, runbooks, paths, and one-based lines; constraints=State idempotency and replay boundaries exactly; -->
#### {{repo_dive:pipeline_failure_recovery_page}}
Cover detection, retries, partial state, replay, backfill, and operator action.
<!-- repo-dive:page=pipeline_operations_page; order=6; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Explain ongoing pipeline operation; evidence=Deployment, telemetry, alerts, commands, paths, and one-based lines; constraints=Keep operational procedures ordered and evidence-bound; -->
#### {{repo_dive:pipeline_operations_page}}
Describe deployment, monitoring, capacity, lineage, incidents, and maintenance.
