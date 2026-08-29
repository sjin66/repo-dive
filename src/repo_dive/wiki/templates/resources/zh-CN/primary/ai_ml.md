<!-- repo-dive:contribution=ai_ml; locale=zh-CN; -->
<!-- repo-dive:page=ml_data_features_page; order=1; cardinality=1; shape=heading,paragraph,table,list; purpose=说明模型数据与特征契约; evidence=必需证据包括数据集、特征代码、模式、符号和单基行号; constraints=记录来源、泄漏风险和预处理且不得暴露数据; -->
**{{repo_dive:ml_data_features_page}}**：说明获取、标注、划分、特征、预处理和治理。
<!-- repo-dive:page=training_pipeline_page; order=2; cardinality=1; shape=heading,paragraph,list,code_block; purpose=说明模型训练流程; evidence=必需证据包括训练脚本、配置、作业、命令和单基行号; constraints=保留阶段顺序、参数、种子和资源假设; -->
**{{repo_dive:training_pipeline_page}}**：追踪准备、训练、调优、检查点和复现控制。
<!-- repo-dive:page=inference_architecture_page; order=3; cardinality=1; shape=heading,paragraph,list,code_block; purpose=说明推理执行与服务; evidence=必需证据包括加载器、预测器、端点、队列和单基行号; constraints=区分批量与在线路径并准确描述输入输出; -->
**{{repo_dive:inference_architecture_page}}**：说明加载、预处理、推理、后处理、扩缩容和失败。
<!-- repo-dive:page=model_evaluation_page; order=4; cardinality=1; shape=heading,paragraph,table,list; purpose=说明模型评估与门槛; evidence=必需证据包括指标、数据集、基线、测试和单基行号; constraints=定义切片、阈值和限制，不作无依据质量声明; -->
**{{repo_dive:model_evaluation_page}}**：涵盖离线在线指标、基线、切片、漂移和验收门槛。
<!-- repo-dive:page=model_artifacts_page; order=5; cardinality=1; shape=heading,paragraph,table,code_block; purpose=记录模型产物与身份; evidence=必需证据包括检查点、注册表、元数据、序列化器和单基行号; constraints=保留格式、版本、血缘和加载契约; -->
**{{repo_dive:model_artifacts_page}}**：记录创建、存储、版本、提升、加载和回滚。
<!-- repo-dive:page=ml_operations_page; order=6; cardinality=1; shape=heading,paragraph,list,code_block; purpose=说明模型发布后的运维; evidence=必需证据包括部署、监控、告警、再训练和单基行号; constraints=区分已实现自动化与预期流程; -->
**{{repo_dive:ml_operations_page}}**：说明部署、监控、漂移响应、再训练、事故和回滚。
