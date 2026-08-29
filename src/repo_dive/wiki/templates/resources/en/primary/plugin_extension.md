<!-- repo-dive:contribution=plugin_extension; locale=en; -->
<!-- repo-dive:page=host_contract_page; order=1; cardinality=1; shape=heading,paragraph,table,code_block; purpose=Define the plugin host contract; evidence=Host APIs, manifests, protocols, paths, symbols, and one-based lines; constraints=Separate documented extension contracts from host internals; -->
#### {{repo_dive:host_contract_page}}
Document host versions, APIs, lifecycle callbacks, data exchange, and errors.
<!-- repo-dive:page=plugin_activation_page; order=2; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Explain plugin discovery activation and shutdown; evidence=Entrypoints, registration, events, paths, symbols, and one-based lines; constraints=Preserve trigger order state and cleanup behavior; -->
#### {{repo_dive:plugin_activation_page}}
Trace discovery, loading, activation, runtime events, deactivation, and failure.
<!-- repo-dive:page=contribution_points_page; order=3; cardinality=1; shape=heading,paragraph,table,code_block; purpose=Catalog plugin contribution points; evidence=Commands, providers, hooks, schemas, paths, and one-based lines; constraints=Use exact identifiers inputs outputs and registration rules; -->
#### {{repo_dive:contribution_points_page}}
Describe every registered capability, invocation contract, and implementation owner.
<!-- repo-dive:page=plugin_permissions_page; order=4; cardinality=1; shape=heading,paragraph,table,list; purpose=Explain permissions isolation and trust; evidence=Permission declarations, sandbox boundaries, validation, paths, and one-based lines; constraints=State granted capabilities and untrusted boundaries without inferred sandboxing; -->
#### {{repo_dive:plugin_permissions_page}}
Cover host access, data access, network use, secret handling, and validation.
<!-- repo-dive:page=plugin_compatibility_page; order=5; cardinality=1; shape=heading,paragraph,table,list; purpose=Explain host and plugin compatibility; evidence=Version ranges, feature checks, migrations, tests, paths, and one-based lines; constraints=Preserve explicit compatibility and degradation behavior; -->
#### {{repo_dive:plugin_compatibility_page}}
Document supported host versions, feature negotiation, changes, and migration.
<!-- repo-dive:page=plugin_packaging_testing_page; order=6; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Explain plugin testing packaging and publication; evidence=Harnesses, manifests, builders, release config, paths, and one-based lines; constraints=Keep package contents validation and publication steps grounded; -->
#### {{repo_dive:plugin_packaging_testing_page}}
Describe host tests, packaging, signing, validation, publication, and updates.
