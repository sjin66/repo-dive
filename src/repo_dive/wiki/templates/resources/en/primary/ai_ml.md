<!-- repo-dive:contribution=ai_ml; locale=en; -->
<!-- repo-dive:page=ml_data_features_page; order=1; cardinality=1; shape=heading,paragraph,table,list; purpose=Explain model data and feature contracts; evidence=Datasets, feature code, schemas, paths, symbols, and one-based lines; constraints=Record provenance leakage risks and preprocessing without exposing data; -->
#### {{repo_dive:ml_data_features_page}}
Describe acquisition, labeling, splitting, features, preprocessing, and governance.
<!-- repo-dive:page=training_pipeline_page; order=2; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Explain model training flow; evidence=Training scripts, configs, jobs, commands, paths, and one-based lines; constraints=Preserve stage order parameters seeds and resource assumptions; -->
#### {{repo_dive:training_pipeline_page}}
Trace preparation, training, tuning, checkpointing, and reproducibility controls.
<!-- repo-dive:page=inference_architecture_page; order=3; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Explain inference execution and serving; evidence=Loaders, predictors, endpoints, queues, paths, symbols, and one-based lines; constraints=Separate batch and online paths with exact input output behavior; -->
#### {{repo_dive:inference_architecture_page}}
Describe model loading, preprocessing, inference, postprocessing, scaling, and failure.
<!-- repo-dive:page=model_evaluation_page; order=4; cardinality=1; shape=heading,paragraph,table,list; purpose=Explain model evaluation and gates; evidence=Metrics, datasets, baselines, tests, paths, and one-based lines; constraints=Define metrics slices thresholds and limitations without unsupported quality claims; -->
#### {{repo_dive:model_evaluation_page}}
Cover offline and online metrics, baselines, slices, drift, and acceptance gates.
<!-- repo-dive:page=model_artifacts_page; order=5; cardinality=1; shape=heading,paragraph,table,code_block; purpose=Catalog model artifacts and identity; evidence=Checkpoints, registries, metadata, serializers, paths, and one-based lines; constraints=Preserve formats versions lineage and loading contracts; -->
#### {{repo_dive:model_artifacts_page}}
Document artifact creation, storage, versioning, promotion, loading, and rollback.
<!-- repo-dive:page=ml_operations_page; order=6; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Explain model operation after release; evidence=Deployment, monitoring, alerts, retraining, paths, and one-based lines; constraints=Separate observed automation from intended process; -->
#### {{repo_dive:ml_operations_page}}
Describe deployment, monitoring, drift response, retraining, incidents, and rollback.
