<!-- repo-dive:contribution=service_api; locale=en; -->
<!-- repo-dive:page=service_runtime_architecture_page; order=1; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Explain service startup and request processing; evidence=Entrypoints, middleware, handlers, dependencies, paths, symbols, and one-based lines; constraints=Trace the evidenced lifecycle in order and omit CLI-owned shell headings; -->
#### {{repo_dive:service_runtime_architecture_page}}
Trace initialization, request dispatch, domain work, persistence, and response handling.
<!-- repo-dive:page=api_contracts_page; order=2; cardinality=1; shape=heading,paragraph,table,code_block; purpose=Catalog stable API contracts; evidence=Specifications, schemas, endpoint declarations, paths, symbols, and one-based lines; constraints=Use exact methods fields and status behavior with grounded examples; -->
#### {{repo_dive:api_contracts_page}}
Document endpoint purpose, request and response shapes, compatibility, and ownership.
<!-- repo-dive:page=request_validation_page; order=3; cardinality=1; shape=heading,paragraph,table,code_block; purpose=Explain request validation and error mapping; evidence=Validators, parsers, error types, paths, symbols, and one-based lines; constraints=Separate invocation validation from domain failure and preserve exact error semantics; -->
#### {{repo_dive:request_validation_page}}
Map untrusted input through validation, normalization, rejection, and stable errors.
<!-- repo-dive:page=service_persistence_page; order=4; cardinality=1; shape=heading,paragraph,table,list; purpose=Explain service data ownership and consistency; evidence=Models, queries, transactions, migrations, paths, symbols, and one-based lines; constraints=Identify transactional boundaries and avoid inferred schemas; -->
#### {{repo_dive:service_persistence_page}}
Describe owned data, access paths, consistency, migrations, and recovery.
<!-- repo-dive:page=service_security_page; order=5; cardinality=1; shape=heading,paragraph,table,list; purpose=Explain service trust boundaries; evidence=Authentication, authorization, secret handling, paths, symbols, and one-based lines; constraints=Distinguish configured policy from code-enforced controls; -->
#### {{repo_dive:service_security_page}}
Cover identity, authorization, transport boundaries, input safety, and secrets.
<!-- repo-dive:page=service_operations_page; order=6; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Explain deployment and service operation; evidence=Manifests, health checks, telemetry, runbooks, paths, and one-based lines; constraints=Keep commands and failure procedures grounded and ordered; -->
#### {{repo_dive:service_operations_page}}
Describe deployment, health, observability, scaling, failure handling, and rollback.
