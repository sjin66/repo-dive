<!-- repo-dive:contribution=data_science; locale=en; -->
<!-- repo-dive:page=data_sources_page; order=1; cardinality=1; shape=heading,paragraph,table,list; purpose=Catalog analysis data sources and assumptions; evidence=Loaders, schemas, notebooks, paths, symbols, and one-based lines; constraints=Record provenance sensitivity and sampling without exposing private values; -->
#### {{repo_dive:data_sources_page}}
Describe source ownership, fields, acquisition, quality assumptions, and preparation.
<!-- repo-dive:page=analysis_workflow_page; order=2; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Explain the analysis workflow; evidence=Notebooks, scripts, transformations, commands, paths, and one-based lines; constraints=Keep execution order and dependencies reproducible; -->
#### {{repo_dive:analysis_workflow_page}}
Trace exploration, cleaning, feature work, analysis, visualization, and output.
<!-- repo-dive:page=reproducibility_page; order=3; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Explain reproducibility controls; evidence=Locks, seeds, environments, parameters, paths, and one-based lines; constraints=Distinguish deterministic controls from undocumented analyst practice; -->
#### {{repo_dive:reproducibility_page}}
Document environments, versions, seeds, parameters, execution order, and reruns.
<!-- repo-dive:page=analysis_evaluation_page; order=4; cardinality=1; shape=heading,paragraph,table,list; purpose=Explain analytical validation and metrics; evidence=Metric code, checks, baselines, tests, paths, and one-based lines; constraints=Report metric definitions and limitations without quality judgments; -->
#### {{repo_dive:analysis_evaluation_page}}
Cover validation design, metrics, comparisons, uncertainty, and acceptance gates.
<!-- repo-dive:page=analysis_artifacts_page; order=5; cardinality=1; shape=heading,paragraph,table,code_block; purpose=Catalog generated analysis artifacts; evidence=Output writers, reports, models, plots, paths, symbols, and one-based lines; constraints=Identify formats ownership and regeneration commands exactly; -->
#### {{repo_dive:analysis_artifacts_page}}
Describe outputs, locations, schemas, consumers, retention, and regeneration.
<!-- repo-dive:page=analysis_operationalization_page; order=6; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Explain how analysis becomes repeatable operation; evidence=Jobs, exports, automation, monitoring, paths, and one-based lines; constraints=Separate exploratory work from productionized paths; -->
#### {{repo_dive:analysis_operationalization_page}}
Trace promotion, scheduling, handoff, monitoring, refresh, and failure recovery.
