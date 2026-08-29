<!-- repo-dive:contribution=web_application; locale=en; -->
<!-- repo-dive:page=web_runtime_architecture_page; order=1; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Explain browser and server runtime boundaries; evidence=Entry points, components, request paths, symbols, and one-based lines; constraints=Use ordered H4/H5 subsections, grounded prose, lists, and code while omitting shell headings; -->
#### {{repo_dive:web_runtime_architecture_page}}
Trace startup, rendering, request handling, state ownership, and failure boundaries.
<!-- repo-dive:page=routes_interfaces_page; order=2; cardinality=1; shape=heading,paragraph,table,code_block; purpose=Catalog routes and external interfaces; evidence=Route declarations, handlers, schemas, symbols, and one-based lines; constraints=Use exact interface names, a comparison table, grounded examples, and no invented endpoints; -->
#### {{repo_dive:routes_interfaces_page}}
Document route purpose, inputs, outputs, authentication, and implementation ownership.
<!-- repo-dive:page=web_state_persistence_page; order=3; cardinality=1; shape=heading,paragraph,table,list; purpose=Explain client and server state persistence; evidence=Stores, models, migrations, caches, paths, symbols, and one-based lines; constraints=Separate durable from transient state and preserve the declared node order; -->
#### {{repo_dive:web_state_persistence_page}}
Map state producers, consumers, storage systems, consistency, and invalidation.
<!-- repo-dive:page=web_security_page; order=4; cardinality=1; shape=heading,paragraph,table,list; purpose=Explain web trust boundaries and controls; evidence=Authentication, authorization, validation, headers, paths, symbols, and one-based lines; constraints=State only evidenced controls and distinguish enforcement from configuration; -->
#### {{repo_dive:web_security_page}}
Cover identity, sessions, authorization, input handling, browser protections, and secrets.
<!-- repo-dive:page=web_deployment_operations_page; order=5; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Explain build deployment and runtime operation; evidence=Build files, environment configuration, deployment manifests, paths, and one-based lines; constraints=Keep commands grounded, ordered, and separate build-time from runtime behavior; -->
#### {{repo_dive:web_deployment_operations_page}}
Describe build artifacts, environments, rollout, observability, scaling, and recovery.
<!-- repo-dive:page=web_testing_page; order=6; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Explain the web testing strategy; evidence=Test suites, fixtures, browser harnesses, commands, paths, and one-based lines; constraints=Differentiate unit integration and browser coverage without claiming unobserved quality; -->
#### {{repo_dive:web_testing_page}}
Show test layers, setup, representative commands, and known coverage boundaries.
