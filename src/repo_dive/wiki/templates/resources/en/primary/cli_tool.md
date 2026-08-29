<!-- repo-dive:contribution=cli_tool; locale=en; -->
<!-- repo-dive:page=cli_installation_page; order=1; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Explain supported CLI installation and startup; evidence=Package metadata, executable entry points, setup commands, paths, symbols, and one-based lines; constraints=Use only evidenced prerequisites and runnable commands without reproducing shell headings; -->
#### {{repo_dive:cli_installation_page}}
Document prerequisites, installation variants, executable discovery, and first invocation.
<!-- repo-dive:page=command_reference_page; order=2; cardinality=1; shape=heading,paragraph,table,code_block; purpose=Provide an exact command and option reference; evidence=Argument declarations, help contracts, handlers, paths, symbols, and one-based lines; constraints=Preserve command names defaults requiredness output budgets and examples exactly; -->
#### {{repo_dive:command_reference_page}}
Catalog commands, arguments, options, defaults, outputs, and representative invocations.
<!-- repo-dive:page=cli_configuration_page; order=3; cardinality=1; shape=heading,paragraph,table,code_block; purpose=Explain CLI configuration precedence and validation; evidence=Configuration models, files, flags, paths, symbols, and one-based lines; constraints=State precedence and accepted values only when evidenced; -->
#### {{repo_dive:cli_configuration_page}}
Describe configuration sources, precedence, validation, defaults, and safe examples.
<!-- repo-dive:page=execution_flow_page; order=4; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Trace command execution across module boundaries; evidence=Entrypoint, dispatch, services, adapters, paths, symbols, and one-based lines; constraints=Keep the sequence deterministic and distinguish stdout stderr and persisted effects; -->
#### {{repo_dive:execution_flow_page}}
Trace parsing, validation, domain execution, adapter calls, output, and exit selection.
<!-- repo-dive:page=cli_extension_points_page; order=5; cardinality=1; shape=heading,paragraph,table,code_block; purpose=Explain supported CLI extension boundaries; evidence=Protocols, registries, adapters, constructors, paths, symbols, and one-based lines; constraints=Do not present internal coincidences as supported extension APIs; -->
#### {{repo_dive:cli_extension_points_page}}
Document explicit interfaces, adapter contracts, registration, and compatibility limits.
<!-- repo-dive:page=errors_exit_codes_page; order=6; cardinality=1; shape=heading,paragraph,table,code_block; purpose=Map failures to diagnostics and process exit codes; evidence=Exception types, error envelopes, exit constants, paths, symbols, and one-based lines; constraints=Preserve stable codes channels and retry guidance exactly; -->
#### {{repo_dive:errors_exit_codes_page}}
Catalog validation, input, operational, and internal failures with observable behavior.
