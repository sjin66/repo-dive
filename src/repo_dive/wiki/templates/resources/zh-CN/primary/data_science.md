<!-- repo-dive:contribution=data_science; locale=zh-CN; -->
<!-- repo-dive:page=data_sources_page; order=1; cardinality=1; shape=heading,paragraph,table,list; purpose=记录分析数据来源与假设; evidence=必需证据包括加载器、模式、笔记本、符号和单基行号; constraints=记录来源、敏感性和抽样且不得暴露私有值; -->
**{{repo_dive:data_sources_page}}**：说明所有权、字段、获取、质量假设和准备。
<!-- repo-dive:page=analysis_workflow_page; order=2; cardinality=1; shape=heading,paragraph,list,code_block; purpose=说明分析工作流; evidence=必需证据包括笔记本、脚本、转换、命令和单基行号; constraints=保持执行顺序与依赖可复现; -->
**{{repo_dive:analysis_workflow_page}}**：追踪探索、清理、特征、分析、可视化和输出。
<!-- repo-dive:page=reproducibility_page; order=3; cardinality=1; shape=heading,paragraph,list,code_block; purpose=说明可复现性控制; evidence=必需证据包括锁文件、随机种子、环境、参数和单基行号; constraints=区分确定性控制与未记录的分析习惯; -->
**{{repo_dive:reproducibility_page}}**：记录环境、版本、种子、参数、顺序和重新运行。
<!-- repo-dive:page=analysis_evaluation_page; order=4; cardinality=1; shape=heading,paragraph,table,list; purpose=说明分析校验与指标; evidence=必需证据包括指标代码、检查、基线、测试和单基行号; constraints=定义指标与限制，不作无证据质量判断; -->
**{{repo_dive:analysis_evaluation_page}}**：涵盖校验设计、指标、比较、不确定性和门槛。
<!-- repo-dive:page=analysis_artifacts_page; order=5; cardinality=1; shape=heading,paragraph,table,code_block; purpose=记录生成的分析产物; evidence=必需证据包括输出写入器、报告、模型、图表和单基行号; constraints=准确标明格式、所有权和再生成命令; -->
**{{repo_dive:analysis_artifacts_page}}**：说明输出、位置、模式、消费者、保留和再生成。
<!-- repo-dive:page=analysis_operationalization_page; order=6; cardinality=1; shape=heading,paragraph,list,code_block; purpose=说明分析如何成为可重复运行; evidence=必需证据包括作业、导出、自动化、监控和单基行号; constraints=区分探索性工作与生产化路径; -->
**{{repo_dive:analysis_operationalization_page}}**：追踪提升、调度、交接、监控、刷新和恢复。
