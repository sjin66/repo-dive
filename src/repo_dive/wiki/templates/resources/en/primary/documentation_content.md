<!-- repo-dive:contribution=documentation_content; locale=en; -->
<!-- repo-dive:page=information_architecture_page; order=1; cardinality=1; shape=heading,paragraph,table,list; purpose=Explain documentation information architecture; evidence=Navigation, content trees, metadata, paths, and one-based lines; constraints=Use actual audiences categories and hierarchy without inventing coverage; -->
#### {{repo_dive:information_architecture_page}}
Describe audiences, content types, hierarchy, ownership, and cross-linking.
<!-- repo-dive:page=authoring_conventions_page; order=2; cardinality=1; shape=heading,paragraph,table,code_block; purpose=Catalog authoring formats and conventions; evidence=Examples, style config, templates, paths, and one-based lines; constraints=Preserve required metadata syntax and examples exactly; -->
#### {{repo_dive:authoring_conventions_page}}
Document formats, front matter, style, terminology, code samples, and assets.
<!-- repo-dive:page=documentation_generation_page; order=3; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Explain documentation generation flow; evidence=Generators, plugins, commands, configuration, paths, and one-based lines; constraints=Trace source transformation ordering and generated boundaries; -->
#### {{repo_dive:documentation_generation_page}}
Describe source discovery, transformation, rendering, assets, and generated outputs.
<!-- repo-dive:page=documentation_validation_page; order=4; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Explain documentation validation; evidence=Linters, link checks, tests, commands, paths, and one-based lines; constraints=State enforced checks separately from editorial expectations; -->
#### {{repo_dive:documentation_validation_page}}
Cover formatting, links, examples, schemas, builds, and publication gates.
<!-- repo-dive:page=navigation_discovery_page; order=5; cardinality=1; shape=heading,paragraph,table,list; purpose=Explain navigation and content discovery; evidence=Menus, indexes, search config, paths, and one-based lines; constraints=Use actual ordering labels and discovery mechanisms; -->
#### {{repo_dive:navigation_discovery_page}}
Map menus, indexes, search, related content, redirects, and version selection.
<!-- repo-dive:page=documentation_publishing_page; order=6; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Explain documentation publication and maintenance; evidence=Build pipelines, hosting config, release jobs, paths, and one-based lines; constraints=Keep environments commands and rollback procedures grounded; -->
#### {{repo_dive:documentation_publishing_page}}
Describe previews, builds, hosting, versions, rollout, ownership, and updates.
