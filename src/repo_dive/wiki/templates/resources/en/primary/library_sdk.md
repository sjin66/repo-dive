<!-- repo-dive:contribution=library_sdk; locale=en; -->
<!-- repo-dive:page=library_installation_page; order=1; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Explain supported library installation and imports; evidence=Package metadata, exports, version constraints, paths, symbols, and one-based lines; constraints=Use evidenced environments and minimal runnable examples; -->
#### {{repo_dive:library_installation_page}}
Document installation, import paths, initialization, and platform prerequisites.
<!-- repo-dive:page=public_api_page; order=2; cardinality=1; shape=heading,paragraph,table,code_block; purpose=Define the supported public API; evidence=Exports, signatures, types, docstrings, paths, symbols, and one-based lines; constraints=Separate public contracts from implementation details and preserve exact signatures; -->
#### {{repo_dive:public_api_page}}
Catalog public types, functions, parameters, returns, errors, and lifecycle rules.
<!-- repo-dive:page=usage_examples_page; order=3; cardinality=1; shape=heading,paragraph,table,code_block; purpose=Provide grounded usage patterns; evidence=Examples, tests, fixtures, call sites, paths, symbols, and one-based lines; constraints=Keep examples executable and identify setup and cleanup; -->
#### {{repo_dive:usage_examples_page}}
Show basic, composed, and failure-handling usage without inventing capabilities.
<!-- repo-dive:page=library_extension_page; order=4; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Explain supported customization and extension; evidence=Protocols, hooks, subclasses, adapters, paths, symbols, and one-based lines; constraints=Name stability and ownership boundaries for every extension point; -->
#### {{repo_dive:library_extension_page}}
Describe extension interfaces, registration, lifecycle, and implementation obligations.
<!-- repo-dive:page=compatibility_page; order=5; cardinality=1; shape=heading,paragraph,table,list; purpose=Explain version and platform compatibility; evidence=Version metadata, deprecations, matrices, tests, paths, and one-based lines; constraints=Do not infer support beyond explicit configuration or tests; -->
#### {{repo_dive:compatibility_page}}
Cover language and platform support, semantic changes, deprecations, and migration.
