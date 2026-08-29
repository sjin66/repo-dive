<!-- repo-dive:contribution=game; locale=en; -->
<!-- repo-dive:page=game_runtime_loop_page; order=1; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Explain the game runtime loop and state; evidence=Entrypoints, loops, update code, paths, symbols, and one-based lines; constraints=Preserve frame phase order timing and ownership; -->
#### {{repo_dive:game_runtime_loop_page}}
Describe startup, input, simulation, rendering, audio, state transitions, and shutdown.
<!-- repo-dive:page=scene_world_page; order=2; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Explain scene or world organization; evidence=Scenes, entities, maps, loaders, paths, symbols, and one-based lines; constraints=Trace loading ownership lifetime and transition behavior; -->
#### {{repo_dive:scene_world_page}}
Map world structure, scenes, entities, loading, transitions, and persistence.
<!-- repo-dive:page=gameplay_systems_page; order=3; cardinality=1; shape=heading,paragraph,table,code_block; purpose=Catalog gameplay systems and interactions; evidence=Systems, components, rules, paths, symbols, and one-based lines; constraints=Use exact state inputs outputs and dependency relationships; -->
#### {{repo_dive:gameplay_systems_page}}
Describe controls, rules, physics, AI, progression, combat, and system coupling.
<!-- repo-dive:page=assets_content_page; order=4; cardinality=1; shape=heading,paragraph,table,list; purpose=Explain assets and content pipeline; evidence=Asset manifests, importers, formats, paths, and one-based lines; constraints=State source generated runtime forms and ownership; -->
#### {{repo_dive:assets_content_page}}
Catalog art, audio, levels, localization, import, packaging, and validation.
<!-- repo-dive:page=game_persistence_networking_page; order=5; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Explain save data and networking lifecycle; evidence=Serializers, protocols, sessions, paths, symbols, and one-based lines; constraints=Separate local and network state with exact authority and recovery; -->
#### {{repo_dive:game_persistence_networking_page}}
Cover saves, profiles, synchronization, sessions, authority, failure, and migration.
<!-- repo-dive:page=game_build_testing_page; order=6; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Explain game tests builds and distribution; evidence=Tests, export presets, builders, platform config, paths, and one-based lines; constraints=Keep target commands artifacts and release constraints grounded; -->
#### {{repo_dive:game_build_testing_page}}
Describe automated tests, play tests, builds, platforms, packaging, and releases.
