"""Closed built-in registry for composed multilingual Wiki templates."""

from __future__ import annotations

import re
from dataclasses import dataclass
from importlib.resources import files
from importlib.resources.abc import Traversable
from typing import Literal, TypeAlias

from repo_dive.classification.registry import FACET_IDS, PRIMARY_IDS, TOPOLOGY_IDS
from repo_dive.wiki.templates.composition import (
    compose_registry,
    validate_composition_operations,
)
from repo_dive.wiki.templates.models import (
    ComposedContract,
    ContractNode,
    Contribution,
    ContributionDimension,
    FrameworkShell,
    LocaleCatalog,
    MergeOperation,
    NodeConstraints,
)
from repo_dive.wiki.templates.resources import read_guidance_resource
from repo_dive.wiki.templates.subsection_copy import load_subsection_copy

SUPPORTED_LOCALES = ("en", "zh-CN", "ja")
TEMPLATE_SCHEMA_VERSION = "1.0"
TEMPLATE_REGISTRY_VERSION = "3"

PageProfile = Literal["narrative", "reference", "procedure", "matrix"]
PageSpec: TypeAlias = tuple[str, PageProfile]
SectionSpec: TypeAlias = tuple[str, tuple[PageSpec, ...]]

_ONE = NodeConstraints(True, 1, 1)
_PAGE = NodeConstraints(True, 1, 1, (3,))
_BODY_HEADING = NodeConstraints(True, 1, 1, (4,))
_PARAGRAPHS = NodeConstraints(True, 2, 8)
_LISTS = NodeConstraints(True, 1, 4)
_TABLES = NodeConstraints(True, 1, 4)
_CODE_BLOCKS = NodeConstraints(True, 1, 6)
_SLOT = NodeConstraints(False, 0, 32, (3,))

_SCOPE_LABEL_IDS = (
    "scope_version",
    "scan_mode",
    "git_scope",
    "git_scope_description",
    "include_patterns",
    "exclude_patterns",
    "default_exclusions",
    "indexed_files",
    "skipped_files",
    "index_build",
    "repository_fingerprint",
    "source_commit",
    "source_state",
    "source_state_clean",
    "source_state_dirty",
    "source_state_non_git",
    "source_commit_none",
    "patterns_none",
    "generated_at",
)


def _spec(section_id: str, *pages: PageSpec) -> SectionSpec:
    return section_id, pages


_PRIMARY_BLUEPRINTS: dict[str, tuple[SectionSpec, ...]] = {
    "web_application": (
        _spec(
            "web_architecture_section",
            ("web_runtime_architecture_page", "procedure"),
            ("routes_interfaces_page", "reference"),
        ),
        _spec(
            "web_state_security_section",
            ("web_state_persistence_page", "matrix"),
            ("web_security_page", "matrix"),
        ),
        _spec(
            "web_delivery_section",
            ("web_deployment_operations_page", "procedure"),
            ("web_testing_page", "procedure"),
        ),
    ),
    "service_api": (
        _spec(
            "service_interfaces_section",
            ("service_runtime_architecture_page", "procedure"),
            ("api_contracts_page", "reference"),
            ("request_validation_page", "reference"),
        ),
        _spec(
            "service_data_security_section",
            ("service_persistence_page", "matrix"),
            ("service_security_page", "matrix"),
        ),
        _spec("service_delivery_section", ("service_operations_page", "procedure")),
    ),
    "cli_tool": (
        _spec(
            "cli_usage_section",
            ("cli_installation_page", "procedure"),
            ("command_reference_page", "reference"),
            ("cli_configuration_page", "reference"),
        ),
        _spec(
            "cli_runtime_section",
            ("execution_flow_page", "procedure"),
            ("cli_extension_points_page", "reference"),
            ("errors_exit_codes_page", "reference"),
            ("terminology_reference_page", "reference"),
        ),
    ),
    "library_sdk": (
        _spec(
            "library_adoption_section",
            ("library_installation_page", "procedure"),
            ("public_api_page", "reference"),
            ("usage_examples_page", "reference"),
        ),
        _spec(
            "library_evolution_section",
            ("library_extension_page", "procedure"),
            ("compatibility_page", "matrix"),
        ),
    ),
    "data_science": (
        _spec(
            "analysis_inputs_section",
            ("data_sources_page", "matrix"),
            ("analysis_workflow_page", "procedure"),
            ("reproducibility_page", "procedure"),
        ),
        _spec(
            "analysis_outputs_section",
            ("analysis_evaluation_page", "matrix"),
            ("analysis_artifacts_page", "reference"),
            ("analysis_operationalization_page", "procedure"),
        ),
    ),
    "data_pipeline": (
        _spec(
            "pipeline_flow_section",
            ("pipeline_sources_sinks_page", "matrix"),
            ("pipeline_orchestration_page", "procedure"),
            ("pipeline_transformations_page", "reference"),
        ),
        _spec(
            "pipeline_reliability_section",
            ("data_quality_page", "matrix"),
            ("pipeline_failure_recovery_page", "procedure"),
            ("pipeline_operations_page", "procedure"),
        ),
    ),
    "ai_ml": (
        _spec(
            "ml_development_section",
            ("ml_data_features_page", "matrix"),
            ("training_pipeline_page", "procedure"),
            ("inference_architecture_page", "procedure"),
        ),
        _spec(
            "ml_governance_section",
            ("model_evaluation_page", "matrix"),
            ("model_artifacts_page", "reference"),
            ("ml_operations_page", "procedure"),
        ),
    ),
    "mobile_application": (
        _spec(
            "mobile_runtime_section",
            ("mobile_runtime_architecture_page", "procedure"),
            ("mobile_navigation_page", "procedure"),
            ("mobile_state_storage_page", "matrix"),
            ("platform_integration_page", "reference"),
        ),
        _spec(
            "mobile_delivery_section",
            ("mobile_security_page", "matrix"),
            ("mobile_distribution_testing_page", "procedure"),
        ),
    ),
    "desktop_application": (
        _spec(
            "desktop_runtime_section",
            ("desktop_process_architecture_page", "procedure"),
            ("desktop_ui_lifecycle_page", "procedure"),
            ("desktop_state_storage_page", "matrix"),
            ("os_integration_page", "reference"),
        ),
        _spec(
            "desktop_delivery_section",
            ("desktop_security_page", "matrix"),
            ("desktop_distribution_testing_page", "procedure"),
        ),
    ),
    "embedded_firmware": (
        _spec(
            "firmware_platform_section",
            ("target_hardware_page", "matrix"),
            ("firmware_architecture_page", "procedure"),
            ("realtime_lifecycle_page", "procedure"),
            ("io_protocols_page", "reference"),
        ),
        _spec(
            "firmware_assurance_section",
            ("safety_constraints_page", "matrix"),
            ("firmware_testing_distribution_page", "procedure"),
        ),
    ),
    "infrastructure": (
        _spec(
            "infrastructure_design_section",
            ("resource_topology_page", "matrix"),
            ("environments_state_page", "matrix"),
            ("network_security_page", "matrix"),
        ),
        _spec(
            "infrastructure_operations_section",
            ("infrastructure_change_page", "procedure"),
            ("observability_recovery_page", "procedure"),
            ("infrastructure_testing_page", "procedure"),
        ),
    ),
    "developer_tool": (
        _spec(
            "developer_experience_section",
            ("developer_workflow_page", "procedure"),
            ("tool_architecture_page", "procedure"),
            ("tool_configuration_page", "reference"),
            ("tool_integrations_page", "reference"),
            ("tool_extension_points_page", "reference"),
        ),
        _spec(
            "tool_delivery_section",
            ("tool_diagnostics_page", "reference"),
            ("tool_distribution_page", "procedure"),
            ("terminology_reference_page", "reference"),
        ),
    ),
    "plugin_extension": (
        _spec(
            "plugin_contract_section",
            ("host_contract_page", "reference"),
            ("plugin_activation_page", "procedure"),
            ("contribution_points_page", "reference"),
            ("plugin_permissions_page", "matrix"),
        ),
        _spec(
            "plugin_delivery_section",
            ("plugin_compatibility_page", "matrix"),
            ("plugin_packaging_testing_page", "procedure"),
        ),
    ),
    "game": (
        _spec(
            "game_runtime_section",
            ("game_runtime_loop_page", "procedure"),
            ("scene_world_page", "procedure"),
            ("gameplay_systems_page", "reference"),
            ("assets_content_page", "matrix"),
        ),
        _spec(
            "game_delivery_section",
            ("game_persistence_networking_page", "procedure"),
            ("game_build_testing_page", "procedure"),
        ),
    ),
    "documentation_content": (
        _spec(
            "documentation_authoring_section",
            ("information_architecture_page", "matrix"),
            ("authoring_conventions_page", "reference"),
            ("documentation_generation_page", "procedure"),
        ),
        _spec(
            "documentation_delivery_section",
            ("documentation_validation_page", "procedure"),
            ("navigation_discovery_page", "matrix"),
            ("documentation_publishing_page", "procedure"),
        ),
    ),
    "general_mixed": (
        _spec(
            "mixed_components_section",
            ("component_catalog_page", "matrix"),
            ("shared_contracts_page", "reference"),
            ("cross_component_workflows_page", "procedure"),
        ),
        _spec(
            "mixed_delivery_section",
            ("build_test_matrix_page", "matrix"),
            ("mixed_operations_page", "procedure"),
        ),
    ),
}

_PROFILE_TYPES: dict[PageProfile, tuple[str, ...]] = {
    "narrative": ("heading", "paragraph", "list"),
    "reference": ("heading", "paragraph", "table", "code_block"),
    "procedure": ("heading", "paragraph", "list", "code_block"),
    "matrix": ("heading", "paragraph", "table", "list"),
}

_INTENTIONAL_SUBSECTIONS: dict[str, tuple[str, str]] = {
    "web_runtime_architecture_page": ("runtime_components", "request_lifecycle"),
    "routes_interfaces_page": ("route_contracts", "interface_handlers"),
    "web_state_persistence_page": ("state_model", "persistence_workflow"),
    "web_security_page": ("security_boundaries", "security_verification"),
    "web_deployment_operations_page": ("deployment_workflow", "runtime_operations"),
    "web_testing_page": ("test_strategy", "verification_commands"),
    "service_runtime_architecture_page": ("runtime_components", "request_lifecycle"),
    "api_contracts_page": ("api_surfaces", "compatibility_contracts"),
    "request_validation_page": ("validation_rules", "failure_responses"),
    "service_persistence_page": ("data_model", "persistence_workflow"),
    "service_security_page": ("security_boundaries", "authorization_flow"),
    "service_operations_page": ("deployment_workflow", "runtime_operations"),
    "cli_installation_page": ("prerequisites", "first_run"),
    "command_reference_page": ("command_syntax", "command_examples"),
    "cli_configuration_page": ("configuration_sources", "configuration_precedence"),
    "execution_flow_page": ("execution_pipeline", "failure_boundaries"),
    "cli_extension_points_page": ("extension_contracts", "registration_workflow"),
    "errors_exit_codes_page": ("error_contracts", "recovery_workflows"),
    "terminology_reference_page": ("canonical_terms", "scope_interpretation"),
    "library_installation_page": ("prerequisites", "first_usage"),
    "public_api_page": ("public_contracts", "usage_boundaries"),
    "usage_examples_page": ("common_workflows", "edge_cases"),
    "library_extension_page": ("extension_contracts", "extension_workflow"),
    "compatibility_page": ("supported_versions", "migration_constraints"),
    "data_sources_page": ("source_catalog", "ingestion_constraints"),
    "analysis_workflow_page": ("analysis_stages", "execution_workflow"),
    "reproducibility_page": ("environment_inputs", "reproduction_steps"),
    "analysis_evaluation_page": ("evaluation_metrics", "result_interpretation"),
    "analysis_artifacts_page": ("artifact_catalog", "artifact_lineage"),
    "analysis_operationalization_page": ("delivery_workflow", "runtime_monitoring"),
    "pipeline_sources_sinks_page": ("source_contracts", "sink_contracts"),
    "pipeline_orchestration_page": ("execution_graph", "scheduling_workflow"),
    "pipeline_transformations_page": ("transformation_stages", "data_contracts"),
    "data_quality_page": ("quality_rules", "quality_monitoring"),
    "pipeline_failure_recovery_page": ("failure_modes", "recovery_workflows"),
    "pipeline_operations_page": ("runtime_operations", "operational_verification"),
    "ml_data_features_page": ("training_data", "feature_pipeline"),
    "training_pipeline_page": ("training_stages", "training_reproducibility"),
    "inference_architecture_page": ("inference_flow", "serving_boundaries"),
    "model_evaluation_page": ("evaluation_metrics", "acceptance_decisions"),
    "model_artifacts_page": ("artifact_lineage", "model_versions"),
    "ml_operations_page": ("deployment_workflow", "model_monitoring"),
    "mobile_runtime_architecture_page": ("runtime_components", "application_lifecycle"),
    "mobile_navigation_page": ("navigation_graph", "transition_workflow"),
    "mobile_state_storage_page": ("state_model", "storage_boundaries"),
    "platform_integration_page": ("platform_contracts", "integration_lifecycle"),
    "mobile_security_page": ("security_boundaries", "platform_permissions"),
    "mobile_distribution_testing_page": ("distribution_workflow", "device_testing"),
    "desktop_process_architecture_page": ("process_boundaries", "runtime_coordination"),
    "desktop_ui_lifecycle_page": ("ui_components", "window_lifecycle"),
    "desktop_state_storage_page": ("state_model", "storage_boundaries"),
    "os_integration_page": ("os_contracts", "integration_lifecycle"),
    "desktop_security_page": ("security_boundaries", "os_permissions"),
    "desktop_distribution_testing_page": ("distribution_workflow", "platform_testing"),
    "target_hardware_page": ("hardware_profile", "resource_constraints"),
    "firmware_architecture_page": ("runtime_components", "firmware_boundaries"),
    "realtime_lifecycle_page": ("realtime_flow", "timing_constraints"),
    "io_protocols_page": ("io_contracts", "protocol_handling"),
    "safety_constraints_page": ("safety_requirements", "failure_mitigation"),
    "firmware_testing_distribution_page": ("hardware_testing", "distribution_workflow"),
    "resource_topology_page": ("resource_inventory", "dependency_topology"),
    "environments_state_page": ("environment_matrix", "state_management"),
    "network_security_page": ("network_boundaries", "security_controls"),
    "infrastructure_change_page": ("change_workflow", "rollback_verification"),
    "observability_recovery_page": ("observability_signals", "recovery_workflows"),
    "infrastructure_testing_page": ("validation_strategy", "deployment_verification"),
    "developer_workflow_page": ("local_setup", "verification_commands"),
    "tool_architecture_page": ("runtime_components", "data_flow"),
    "tool_configuration_page": ("configuration_sources", "configuration_precedence"),
    "tool_integrations_page": ("integration_contracts", "integration_setup"),
    "tool_extension_points_page": (
        "protocol_contracts",
        "implementation_workflow",
    ),
    "tool_diagnostics_page": ("diagnostic_signals", "failure_recovery"),
    "tool_distribution_page": ("packaging_workflow", "release_verification"),
    "host_contract_page": ("host_interfaces", "lifecycle_contracts"),
    "plugin_activation_page": ("activation_conditions", "activation_workflow"),
    "contribution_points_page": ("registered_contributions", "contribution_contracts"),
    "plugin_permissions_page": ("permission_model", "trust_boundaries"),
    "plugin_compatibility_page": ("supported_versions", "compatibility_testing"),
    "plugin_packaging_testing_page": ("packaging_workflow", "host_testing"),
    "game_runtime_loop_page": ("runtime_loop", "frame_lifecycle"),
    "scene_world_page": ("world_structure", "scene_lifecycle"),
    "gameplay_systems_page": ("system_catalog", "system_interactions"),
    "assets_content_page": ("asset_pipeline", "content_lifecycle"),
    "game_persistence_networking_page": ("persistence_model", "networking_flow"),
    "game_build_testing_page": ("build_workflow", "runtime_testing"),
    "information_architecture_page": ("content_structure", "navigation_model"),
    "authoring_conventions_page": ("authoring_rules", "content_examples"),
    "documentation_generation_page": ("generation_workflow", "generated_artifacts"),
    "documentation_validation_page": ("validation_rules", "verification_commands"),
    "navigation_discovery_page": ("navigation_paths", "discovery_mechanisms"),
    "documentation_publishing_page": ("publishing_workflow", "release_verification"),
    "component_catalog_page": ("component_inventory", "component_ownership"),
    "shared_contracts_page": ("shared_interfaces", "compatibility_boundaries"),
    "cross_component_workflows_page": ("workflow_stages", "component_handoffs"),
    "build_test_matrix_page": ("build_matrix", "test_coverage"),
    "mixed_operations_page": ("operational_ownership", "recovery_workflows"),
    "single_project_topology_page": ("project_boundary", "internal_dependencies"),
    "monorepo_topology_page": ("workspace_inventory", "cross_package_dependencies"),
    "microservices_topology_page": ("service_boundaries", "service_communication"),
    "ui_facet_page": ("interface_composition", "interaction_accessibility"),
    "api_facet_page": ("api_surfaces", "authorization_compatibility"),
    "database_facet_page": ("data_models", "consistency_migrations"),
    "messaging_facet_page": ("producer_consumer_flow", "delivery_retries"),
    "infrastructure_facet_page": ("runtime_resources", "security_recovery"),
    "model_training_inference_facet_page": (
        "training_evaluation",
        "inference_monitoring",
    ),
    "multi_tenancy_facet_page": ("tenant_identity", "isolation_operations"),
    "saas_facet_page": ("customer_lifecycle", "billing_operations"),
}
_INTENTIONAL_SUBSECTION_IDS = frozenset(
    f"{page_id.removesuffix('_page')}_{suffix}"
    for page_id, suffixes in _INTENTIONAL_SUBSECTIONS.items()
    for suffix in suffixes
)


def _shell() -> FrameworkShell:
    return FrameworkShell(
        (
            ContractNode("wiki", "root", "cli", _ONE),
            ContractNode("contents", "contents", "cli", _ONE),
            ContractNode(
                "section_heading", "heading", "cli", NodeConstraints(True, 1, 1, (2,))
            ),
            ContractNode(
                "page_heading", "heading", "cli", NodeConstraints(True, 1, 1, (3,))
            ),
            ContractNode("related_pages", "related_pages", "cli", _ONE),
            ContractNode("sources", "sources", "cli", _ONE),
            *(
                ContractNode(logical_id, "paragraph", "cli", _ONE)
                for logical_id in _SCOPE_LABEL_IDS
            ),
        )
    )


def _body_node(page_id: str, node_type: str) -> ContractNode:
    stem = page_id.removesuffix("_page")
    suffixes = {
        "heading": "subsections",
        "paragraph": "explanation",
        "list": "items",
        "table": "matrix",
        "code_block": "example",
    }
    constraints = {
        "heading": _BODY_HEADING,
        "paragraph": _PARAGRAPHS,
        "list": _LISTS,
        "table": _TABLES,
        "code_block": _CODE_BLOCKS,
    }
    return ContractNode(
        f"{stem}_{suffixes[node_type]}",
        node_type,  # type: ignore[arg-type]
        "caller",
        constraints[node_type],
    )


def _page(page_id: str, profile: PageProfile) -> ContractNode:
    content_types = tuple(
        node_type for node_type in _PROFILE_TYPES[profile] if node_type != "heading"
    )
    stem = page_id.removesuffix("_page")
    suffixes = _INTENTIONAL_SUBSECTIONS[page_id]
    midpoint = max(1, len(content_types) // 2)
    grouped_types = (content_types[:midpoint], content_types[midpoint:])
    return ContractNode(
        page_id,
        "page",
        "contract",
        _PAGE,
        tuple(
            ContractNode(
                f"{stem}_{suffix}",
                "subsection",
                "contract",
                _BODY_HEADING,
                tuple(
                    _body_node(f"{page_id}_{suffix}", node_type) for node_type in types
                ),
            )
            for suffix, types in zip(suffixes, grouped_types, strict=True)
        ),
    )


def _primary(primary_id: str) -> Contribution:
    sections = tuple(
        ContractNode(
            section_id,
            "section",
            "contract",
            _ONE,
            tuple(_page(page_id, profile) for page_id, profile in pages),
        )
        for section_id, pages in _PRIMARY_BLUEPRINTS[primary_id]
    )
    overlay_sections = (
        ContractNode(
            "repository_topology_section",
            "section",
            "contract",
            _ONE,
            (
                ContractNode(
                    "topology_pages",
                    "extension_slot",
                    "contract",
                    _SLOT,
                    allowed_child_types=("page",),
                ),
            ),
        ),
        ContractNode(
            "registered_facets_section",
            "section",
            "contract",
            _ONE,
            (
                ContractNode(
                    "facet_pages",
                    "extension_slot",
                    "contract",
                    _SLOT,
                    allowed_child_types=("page",),
                ),
            ),
        ),
    )
    version = "3" if primary_id == "developer_tool" else "2"
    return Contribution(
        primary_id, "primary", version, nodes=(*sections, *overlay_sections)
    )


def _overlay(id_: str, dimension: ContributionDimension) -> Contribution:
    suffix = "topology" if dimension == "topology" else "facet"
    target = "topology_pages" if dimension == "topology" else "facet_pages"
    node = _page(f"{id_}_{suffix}_page", "narrative")
    return Contribution(
        id_,
        dimension,
        "2",
        operations=(MergeOperation("append_to_slot", target, node),),
    )


_SHELL_LABELS = {
    "wiki": ("Repository Wiki", "代码库 Wiki", "リポジトリ Wiki"),
    "contents": ("Contents", "目录", "目次"),
    "section_heading": ("Section", "章节", "セクション"),
    "page_heading": ("Page", "页面", "ページ"),
    "related_pages": ("Related pages", "相关页面", "関連ページ"),
    "sources": ("Sources", "来源", "出典"),
    "scope_version": ("Scope and version", "范围与版本", "スコープとバージョン"),
    "scan_mode": ("Scan mode", "扫描模式", "スキャンモード"),
    "git_scope": ("Git corpus", "Git 语料库", "Git コーパス"),
    "git_scope_description": (
        "tracked plus unignored untracked files after the recorded filters",
        "应用已记录过滤器后的已跟踪及未忽略未跟踪文件",
        "記録されたフィルター適用後の追跡済みファイルと無視されていない未追跡ファイル",
    ),
    "include_patterns": ("Include patterns", "包含模式", "包含パターン"),
    "exclude_patterns": ("Exclude patterns", "排除模式", "除外パターン"),
    "default_exclusions": (
        "Default excluded directories",
        "默认排除目录",
        "既定の除外ディレクトリ",
    ),
    "indexed_files": ("Indexed files", "已索引文件", "索引済みファイル"),
    "skipped_files": ("Skipped files", "已跳过文件", "スキップしたファイル"),
    "index_build": ("Index build", "索引构建", "インデックスビルド"),
    "repository_fingerprint": (
        "Repository fingerprint",
        "代码库指纹",
        "リポジトリ指紋",
    ),
    "source_commit": ("Source commit", "源提交", "ソースコミット"),
    "source_state": ("Source state", "源状态", "ソース状態"),
    "source_state_clean": ("clean", "干净", "クリーン"),
    "source_state_dirty": ("dirty", "有未提交更改", "変更あり"),
    "source_state_non_git": ("non-Git", "非 Git", "Git 以外"),
    "source_commit_none": ("none", "无", "なし"),
    "patterns_none": ("none", "无", "なし"),
    "generated_at": ("Generated at", "生成时间", "生成日時"),
}

_LABEL_OVERRIDES = {
    "command_reference_page": ("Command reference", "命令参考", "コマンドリファレンス"),
    "cli_installation_page": ("CLI installation", "CLI 安装", "CLI インストール"),
    "cli_configuration_page": ("CLI configuration", "CLI 配置", "CLI 設定"),
    "execution_flow_page": ("Execution flow", "执行流程", "実行フロー"),
    "cli_extension_points_page": (
        "CLI extension points",
        "CLI 扩展点",
        "CLI 拡張ポイント",
    ),
    "errors_exit_codes_page": (
        "Errors and exit codes",
        "错误与退出码",
        "エラーと終了コード",
    ),
}

_ZH_TOKENS = {
    "architecture": "架构",
    "runtime": "运行时",
    "installation": "安装",
    "reference": "参考",
    "configuration": "配置",
    "flow": "流程",
    "extension": "扩展",
    "points": "点",
    "errors": "错误",
    "exit": "退出",
    "codes": "码",
    "security": "安全",
    "operations": "运维",
    "testing": "测试",
    "data": "数据",
    "pipeline": "管道",
    "evaluation": "评估",
    "artifacts": "产物",
    "distribution": "分发",
    "compatibility": "兼容性",
    "workflow": "工作流",
    "component": "组件",
    "catalog": "目录",
    "contracts": "契约",
    "interfaces": "接口",
    "state": "状态",
    "persistence": "持久化",
    "deployment": "部署",
    "section": "章节",
    "page": "页面",
}

_JA_TOKENS = {
    "architecture": "アーキテクチャ",
    "runtime": "ランタイム",
    "installation": "インストール",
    "reference": "リファレンス",
    "configuration": "設定",
    "flow": "フロー",
    "extension": "拡張",
    "points": "ポイント",
    "errors": "エラー",
    "exit": "終了",
    "codes": "コード",
    "security": "セキュリティ",
    "operations": "運用",
    "testing": "テスト",
    "data": "データ",
    "pipeline": "パイプライン",
    "evaluation": "評価",
    "artifacts": "成果物",
    "distribution": "配布",
    "compatibility": "互換性",
    "workflow": "ワークフロー",
    "component": "コンポーネント",
    "catalog": "カタログ",
    "contracts": "契約",
    "interfaces": "インターフェース",
    "state": "状態",
    "persistence": "永続化",
    "deployment": "デプロイ",
    "section": "セクション",
    "page": "ページ",
}

# Labels are generated from stable logical IDs, but every displayed token still has
# an explicit translation. Keeping this vocabulary closed prevents an untranslated
# identifier fragment from silently leaking into a localized contract.
_ZH_TOKENS.update(
    {
        "activation": "激活",
        "adoption": "采用",
        "analysis": "分析",
        "assets": "素材",
        "assurance": "保障",
        "authoring": "编写",
        "build": "构建",
        "change": "变更",
        "command": "命令",
        "components": "组件",
        "constraints": "约束",
        "content": "内容",
        "contents": "目录",
        "contract": "契约",
        "contribution": "贡献",
        "conventions": "约定",
        "cross": "跨",
        "database": "数据库",
        "delivery": "交付",
        "design": "设计",
        "desktop": "桌面",
        "developer": "开发者",
        "development": "开发",
        "diagnostics": "诊断",
        "discovery": "发现",
        "documentation": "文档",
        "environments": "环境",
        "evolution": "演进",
        "example": "示例",
        "examples": "示例",
        "execution": "执行",
        "experience": "体验",
        "explanation": "说明",
        "facet": "特性",
        "facets": "特性",
        "failure": "故障",
        "features": "特征",
        "firmware": "固件",
        "game": "游戏",
        "gameplay": "玩法",
        "generation": "生成",
        "governance": "治理",
        "hardware": "硬件",
        "heading": "标题",
        "host": "宿主",
        "inference": "推理",
        "information": "信息",
        "infrastructure": "基础设施",
        "inputs": "输入",
        "integration": "集成",
        "integrations": "集成",
        "io": "输入输出",
        "items": "条目",
        "library": "库",
        "lifecycle": "生命周期",
        "loop": "循环",
        "matrix": "矩阵",
        "messaging": "消息传递",
        "microservices": "微服务",
        "mixed": "混合",
        "mobile": "移动端",
        "model": "模型",
        "monorepo": "单体仓库",
        "multi": "多",
        "navigation": "导航",
        "network": "网络",
        "networking": "联网",
        "observability": "可观测性",
        "operationalization": "生产化",
        "orchestration": "编排",
        "os": "操作系统",
        "outputs": "输出",
        "packaging": "打包",
        "pages": "页面",
        "permissions": "权限",
        "platform": "平台",
        "plugin": "插件",
        "process": "进程",
        "project": "项目",
        "protocols": "协议",
        "public": "公共",
        "publishing": "发布",
        "quality": "质量",
        "realtime": "实时",
        "recovery": "恢复",
        "registered": "已注册",
        "related": "相关",
        "reliability": "可靠性",
        "repository": "代码库",
        "reproducibility": "可复现性",
        "request": "请求",
        "resource": "资源",
        "routes": "路由",
        "saas": "软件服务",
        "safety": "安全保障",
        "scene": "场景",
        "service": "服务",
        "shared": "共享",
        "single": "单一",
        "sinks": "接收端",
        "sources": "来源",
        "storage": "存储",
        "subsections": "小节",
        "overview": "概览",
        "implementation": "实现",
        "verification": "验证",
        "comparison": "比较",
        "decisions": "决策",
        "terminology": "术语",
        "boundaries": "边界",
        "canonical": "规范",
        "commands": "命令",
        "diagnostic": "诊断",
        "error": "错误",
        "first": "首次",
        "interpretation": "解读",
        "local": "本地",
        "precedence": "优先级",
        "prerequisites": "前置条件",
        "registration": "注册",
        "release": "发布",
        "run": "运行",
        "scope": "范围",
        "setup": "设置",
        "signals": "信号",
        "syntax": "语法",
        "terms": "术语",
        "systems": "系统",
        "target": "目标",
        "tenancy": "租户",
        "test": "测试",
        "tool": "工具",
        "topology": "拓扑",
        "training": "训练",
        "transformations": "转换",
        "ui": "用户界面",
        "usage": "用法",
        "validation": "校验",
        "web": "网页",
        "wiki": "知识库",
        "workflows": "工作流",
        "world": "世界",
    }
)
_JA_TOKENS.update(
    {
        "activation": "有効化",
        "adoption": "導入",
        "analysis": "分析",
        "assets": "アセット",
        "assurance": "保証",
        "authoring": "執筆",
        "build": "ビルド",
        "change": "変更",
        "command": "コマンド",
        "components": "コンポーネント",
        "constraints": "制約",
        "content": "コンテンツ",
        "contents": "目次",
        "contract": "契約",
        "contribution": "コントリビューション",
        "conventions": "規約",
        "cross": "横断",
        "database": "データベース",
        "delivery": "デリバリー",
        "design": "設計",
        "desktop": "デスクトップ",
        "developer": "開発者",
        "development": "開発",
        "diagnostics": "診断",
        "discovery": "探索",
        "documentation": "ドキュメント",
        "environments": "環境",
        "evolution": "進化",
        "example": "例",
        "examples": "例",
        "execution": "実行",
        "experience": "体験",
        "explanation": "説明",
        "facet": "ファセット",
        "facets": "ファセット",
        "failure": "障害",
        "features": "特徴",
        "firmware": "ファームウェア",
        "game": "ゲーム",
        "gameplay": "ゲームプレイ",
        "generation": "生成",
        "governance": "ガバナンス",
        "hardware": "ハードウェア",
        "heading": "見出し",
        "host": "ホスト",
        "inference": "推論",
        "information": "情報",
        "infrastructure": "インフラストラクチャ",
        "inputs": "入力",
        "integration": "統合",
        "integrations": "統合",
        "io": "入出力",
        "items": "項目",
        "library": "ライブラリ",
        "lifecycle": "ライフサイクル",
        "loop": "ループ",
        "matrix": "マトリクス",
        "messaging": "メッセージング",
        "microservices": "マイクロサービス",
        "mixed": "混合",
        "mobile": "モバイル",
        "model": "モデル",
        "monorepo": "モノレポ",
        "multi": "マルチ",
        "navigation": "ナビゲーション",
        "network": "ネットワーク",
        "networking": "ネットワーキング",
        "observability": "可観測性",
        "operationalization": "運用化",
        "orchestration": "オーケストレーション",
        "os": "オペレーティングシステム",
        "outputs": "出力",
        "packaging": "パッケージング",
        "pages": "ページ",
        "permissions": "権限",
        "platform": "プラットフォーム",
        "plugin": "プラグイン",
        "process": "プロセス",
        "project": "プロジェクト",
        "protocols": "プロトコル",
        "public": "公開",
        "publishing": "公開",
        "quality": "品質",
        "realtime": "リアルタイム",
        "recovery": "復旧",
        "registered": "登録済み",
        "related": "関連",
        "reliability": "信頼性",
        "repository": "リポジトリ",
        "reproducibility": "再現性",
        "request": "リクエスト",
        "resource": "リソース",
        "routes": "ルート",
        "saas": "サービス型ソフトウェア",
        "safety": "安全性",
        "scene": "シーン",
        "service": "サービス",
        "shared": "共有",
        "single": "単一",
        "sinks": "シンク",
        "sources": "出典",
        "storage": "ストレージ",
        "subsections": "小見出し",
        "overview": "概要",
        "implementation": "実装",
        "verification": "検証",
        "comparison": "比較",
        "decisions": "判断",
        "terminology": "用語",
        "boundaries": "境界",
        "canonical": "標準",
        "commands": "コマンド",
        "diagnostic": "診断",
        "error": "エラー",
        "first": "初回",
        "interpretation": "解釈",
        "local": "ローカル",
        "precedence": "優先順位",
        "prerequisites": "前提条件",
        "registration": "登録",
        "release": "リリース",
        "run": "実行",
        "scope": "スコープ",
        "setup": "セットアップ",
        "signals": "シグナル",
        "syntax": "構文",
        "terms": "用語",
        "systems": "システム",
        "target": "対象",
        "tenancy": "テナンシー",
        "test": "テスト",
        "tool": "ツール",
        "topology": "トポロジー",
        "training": "学習",
        "transformations": "変換",
        "ui": "ユーザーインターフェース",
        "usage": "使用法",
        "validation": "検証",
        "web": "ウェブ",
        "wiki": "ウィキ",
        "workflows": "ワークフロー",
        "world": "ワールド",
    }
)

# Topic-owned outline vocabulary. These translations are deliberately closed: a new
# Subsection word must be registered in every locale rather than falling back to an ID.
_ZH_TOKENS.update(
    {
        "acceptance": "验收",
        "accessibility": "无障碍",
        "application": "应用",
        "artifact": "产物",
        "asset": "素材",
        "authorization": "授权",
        "billing": "计费",
        "boundary": "边界",
        "cases": "情况",
        "common": "常见",
        "communication": "通信",
        "composition": "组合",
        "conditions": "条件",
        "consistency": "一致性",
        "consumer": "消费者",
        "contributions": "贡献",
        "controls": "控制",
        "coordination": "协调",
        "coverage": "覆盖率",
        "customer": "客户",
        "dependencies": "依赖",
        "dependency": "依赖",
        "device": "设备",
        "edge": "边界",
        "environment": "环境",
        "feature": "特征",
        "frame": "帧",
        "generated": "生成的",
        "graph": "图",
        "handlers": "处理器",
        "handling": "处理",
        "handoffs": "交接",
        "identity": "身份",
        "ingestion": "摄取",
        "interaction": "交互",
        "interactions": "交互",
        "interface": "接口",
        "internal": "内部",
        "inventory": "清单",
        "isolation": "隔离",
        "lineage": "血缘",
        "management": "管理",
        "mechanisms": "机制",
        "metrics": "指标",
        "migration": "迁移",
        "migrations": "迁移",
        "mitigation": "缓解",
        "models": "模型",
        "modes": "模式",
        "monitoring": "监控",
        "operational": "运维",
        "ownership": "所有权",
        "package": "包",
        "paths": "路径",
        "permission": "权限",
        "producer": "生产者",
        "profile": "概况",
        "protocol": "协议",
        "reproduction": "复现",
        "requirements": "要求",
        "resources": "资源",
        "responses": "响应",
        "result": "结果",
        "retries": "重试",
        "rollback": "回滚",
        "route": "路由",
        "rules": "规则",
        "scheduling": "调度",
        "serving": "服务",
        "sink": "接收端",
        "source": "来源",
        "stages": "阶段",
        "steps": "步骤",
        "strategy": "策略",
        "structure": "结构",
        "supported": "支持的",
        "surfaces": "表面",
        "system": "系统",
        "tenant": "租户",
        "timing": "时序",
        "transformation": "转换",
        "transition": "转换",
        "trust": "信任",
        "versions": "版本",
        "window": "窗口",
        "workspace": "工作区",
    }
)
_JA_TOKENS.update(
    {
        "acceptance": "受け入れ",
        "accessibility": "アクセシビリティ",
        "application": "アプリケーション",
        "artifact": "成果物",
        "asset": "アセット",
        "authorization": "認可",
        "billing": "請求",
        "boundary": "境界",
        "cases": "ケース",
        "common": "共通",
        "communication": "通信",
        "composition": "構成",
        "conditions": "条件",
        "consistency": "整合性",
        "consumer": "コンシューマー",
        "contributions": "コントリビューション",
        "controls": "制御",
        "coordination": "協調",
        "coverage": "カバレッジ",
        "customer": "顧客",
        "dependencies": "依存関係",
        "dependency": "依存関係",
        "device": "デバイス",
        "edge": "境界",
        "environment": "環境",
        "feature": "特徴",
        "frame": "フレーム",
        "generated": "生成済み",
        "graph": "グラフ",
        "handlers": "ハンドラー",
        "handling": "処理",
        "handoffs": "引き継ぎ",
        "identity": "識別子",
        "ingestion": "取り込み",
        "interaction": "操作",
        "interactions": "相互作用",
        "interface": "インターフェース",
        "internal": "内部",
        "inventory": "一覧",
        "isolation": "分離",
        "lineage": "系譜",
        "management": "管理",
        "mechanisms": "仕組み",
        "metrics": "指標",
        "migration": "移行",
        "migrations": "移行",
        "mitigation": "緩和",
        "models": "モデル",
        "modes": "モード",
        "monitoring": "監視",
        "operational": "運用",
        "ownership": "所有権",
        "package": "パッケージ",
        "paths": "パス",
        "permission": "権限",
        "producer": "プロデューサー",
        "profile": "プロファイル",
        "protocol": "プロトコル",
        "reproduction": "再現",
        "requirements": "要件",
        "resources": "リソース",
        "responses": "レスポンス",
        "result": "結果",
        "retries": "再試行",
        "rollback": "ロールバック",
        "route": "ルート",
        "rules": "規則",
        "scheduling": "スケジューリング",
        "serving": "サービング",
        "sink": "シンク",
        "source": "ソース",
        "stages": "段階",
        "steps": "手順",
        "strategy": "戦略",
        "structure": "構造",
        "supported": "対応済み",
        "surfaces": "表面",
        "system": "システム",
        "tenant": "テナント",
        "timing": "タイミング",
        "transformation": "変換",
        "transition": "遷移",
        "trust": "信頼",
        "versions": "バージョン",
        "window": "ウィンドウ",
        "workspace": "ワークスペース",
    }
)


def _localized_label(logical_id: str, locale_index: int) -> str:
    if logical_id in _SHELL_LABELS:
        return _SHELL_LABELS[logical_id][locale_index]
    if logical_id in _LABEL_OVERRIDES:
        return _LABEL_OVERRIDES[logical_id][locale_index]
    words = logical_id.split("_")
    if locale_index == 0:
        return " ".join(words).replace(" api ", " API ").replace(" ml ", " ML ").title()
    tokens = _ZH_TOKENS if locale_index == 1 else _JA_TOKENS
    try:
        translated = [
            word.upper() if word in {"api", "ml", "cli"} else tokens[word]
            for word in words
        ]
    except KeyError as error:
        raise ValueError(
            f"localized label token is unregistered: {error.args[0]}"
        ) from error
    separator = "" if locale_index == 1 else "・"
    return separator.join(translated)


def _catalogs(
    primaries: tuple[Contribution, ...],
    topologies: tuple[Contribution, ...],
    facets: tuple[Contribution, ...],
    shell: FrameworkShell,
) -> tuple[LocaleCatalog, ...]:
    ids = {node.logical_id for node in shell.nodes}
    for primary in primaries:
        ids.update(node.logical_id for root in primary.nodes for node in root.walk())
    for overlay in (*topologies, *facets):
        ids.update(
            node.logical_id
            for operation in overlay.operations
            if operation.node is not None
            for node in operation.node.walk()
        )
    catalogs: list[LocaleCatalog] = []
    for index, locale in enumerate(SUPPORTED_LOCALES):
        copy = dict(load_subsection_copy(locale))
        if set(copy) != _INTENTIONAL_SUBSECTION_IDS:
            raise ValueError(
                "localized Subsection copy must exactly match the contract registry"
            )
        labels = {logical_id: _localized_label(logical_id, index) for logical_id in ids}
        labels.update({logical_id: item.title for logical_id, item in copy.items()})
        catalogs.append(
            LocaleCatalog(
                locale,
                tuple(sorted(labels.items())),
                tuple(
                    (logical_id, item.description)
                    for logical_id, item in sorted(copy.items())
                ),
            )
        )
    return tuple(catalogs)


@dataclass(frozen=True, slots=True)
class TemplateRegistry:
    """A validated, closed registry of contracts, locales, and resources."""

    primaries: tuple[Contribution, ...]
    topologies: tuple[Contribution, ...]
    facets: tuple[Contribution, ...]
    catalogs: tuple[LocaleCatalog, ...]
    resource_names: tuple[str, ...]
    framework_shell: FrameworkShell = FrameworkShell(())
    schema_version: str = TEMPLATE_SCHEMA_VERSION
    registry_version: str = TEMPLATE_REGISTRY_VERSION
    validate_resources: bool = True

    def __post_init__(self) -> None:
        for contributions, dimension in (
            (self.primaries, "primary"),
            (self.topologies, "topology"),
            (self.facets, "facet"),
        ):
            if any(item.dimension != dimension for item in contributions):
                raise ValueError(
                    "contribution dimension does not match registry position"
                )
            ids = tuple(item.id for item in contributions)
            if len(ids) != len(set(ids)):
                raise ValueError("contribution ids must be unique per dimension")
        shell_ids = {
            node.logical_id
            for root in self.framework_shell.nodes
            for node in root.walk()
        }
        for primary in self.primaries:
            contribution_ids = {
                node.logical_id for root in primary.nodes for node in root.walk()
            }
            if shell_ids & contribution_ids:
                raise ValueError("framework shell and contribution logical ids collide")
            for topology in self.topologies:
                validate_composition_operations(
                    primary.nodes,
                    (
                        *topology.operations,
                        *(
                            operation
                            for facet in self.facets
                            for operation in facet.operations
                        ),
                    ),
                )
        expected_keys = self._expected_locale_keys()
        for catalog in self.catalogs:
            if set(dict(catalog.labels)) != expected_keys:
                raise ValueError("locale keys must exactly match the contract registry")
            if (
                self.validate_resources
                and set(dict(catalog.subsection_descriptions))
                != _INTENTIONAL_SUBSECTION_IDS
            ):
                raise ValueError(
                    "Subsection description keys must exactly match the registry"
                )
        if len(self.locale_ids) != len(set(self.locale_ids)):
            raise ValueError("locale ids must be unique")
        if self.validate_resources:
            expected = _resource_names(
                self.primaries, self.topologies, self.facets, self.locale_ids
            )
            if (
                self.resource_names != expected
                or enumerate_resource_names() != expected
            ):
                raise ValueError(
                    "registered template resources are incomplete or extra"
                )
            self._validate_guidance_resources()

    @property
    def primary_ids(self) -> tuple[str, ...]:
        return tuple(item.id for item in self.primaries)

    @property
    def topology_ids(self) -> tuple[str, ...]:
        return tuple(item.id for item in self.topologies)

    @property
    def facet_ids(self) -> tuple[str, ...]:
        return tuple(item.id for item in self.facets)

    @property
    def locale_ids(self) -> tuple[str, ...]:
        return tuple(item.locale for item in self.catalogs)

    def compose(
        self, primary_id: str, topology_id: str, facet_ids: tuple[str, ...], locale: str
    ) -> ComposedContract:
        return compose_registry(self, primary_id, topology_id, facet_ids, locale)

    def guidance_sources(
        self,
        primary: Contribution,
        topology: Contribution,
        facets: tuple[Contribution, ...],
        locale: str,
    ) -> tuple[str, ...]:
        if not self.validate_resources:
            return ()
        selected = (primary, topology, *facets)
        return tuple(
            _read_resource(locale, item.dimension, item.id) for item in selected
        )

    def _expected_locale_keys(self) -> set[str]:
        keys = {
            node.logical_id
            for root in self.framework_shell.nodes
            for node in root.walk()
        }
        for primary in self.primaries:
            keys.update(
                node.logical_id for root in primary.nodes for node in root.walk()
            )
        for overlay in (*self.topologies, *self.facets):
            keys.update(
                node.logical_id
                for operation in overlay.operations
                if operation.node is not None
                for node in operation.node.walk()
            )
        return keys

    def _validate_guidance_resources(self) -> None:
        catalogs = {catalog.locale: dict(catalog.labels) for catalog in self.catalogs}
        for resource_name in self.resource_names:
            source = read_guidance_resource(resource_name)
            locale, dimension, filename = resource_name.split("/")
            contribution_id = filename.removesuffix(".md")
            contribution = next(
                item
                for item in (*self.primaries, *self.topologies, *self.facets)
                if item.id == contribution_id and item.dimension == dimension
            )
            pages = _contribution_pages(contribution)
            metadata = _parse_guidance_metadata(source, contribution_id, locale)
            expected = tuple((page.logical_id, _node_shape(page)) for page in pages)
            if metadata != expected:
                raise ValueError(
                    f"guidance metadata does not match contract: {resource_name}"
                )
            placeholders = tuple(
                re.findall(r"\{\{repo_dive:([a-z][a-z0-9_]*)\}\}", source)
            )
            page_ids = tuple(page.logical_id for page in pages)
            if placeholders != page_ids or any(
                placeholder not in catalogs[locale] for placeholder in placeholders
            ):
                raise ValueError(
                    f"guidance placeholders do not match contract: {resource_name}"
                )


def _contribution_pages(contribution: Contribution) -> tuple[ContractNode, ...]:
    if contribution.dimension == "primary":
        return tuple(
            node
            for root in contribution.nodes
            for node in root.walk()
            if node.node_type == "page"
        )
    return tuple(
        operation.node
        for operation in contribution.operations
        if operation.node is not None and operation.node.node_type == "page"
    )


def _node_shape(page: ContractNode) -> str:
    subsection_children = tuple(
        grandchild
        for child in page.children
        if child.node_type == "subsection"
        for grandchild in child.children
    )
    if subsection_children:
        return ",".join(
            ("heading", *(child.node_type for child in subsection_children))
        )
    return ",".join(child.node_type for child in page.children)


def _parse_guidance_metadata(
    source: str, contribution_id: str, locale: str
) -> tuple[tuple[str, str], ...]:
    header = re.search(
        r"<!-- repo-dive:contribution=([a-z][a-z0-9_]*); locale=([^;]+); -->",
        source,
    )
    if header is None or header.groups() != (contribution_id, locale):
        raise ValueError("guidance contribution metadata is missing or incorrect")
    matches = re.findall(
        r"<!-- repo-dive:page=([a-z][a-z0-9_]*); order=(\d+); "
        r"cardinality=1; shape=([a-z_,]+); purpose=.+?; evidence=.+?; "
        r"constraints=.+?; -->",
        source,
    )
    if tuple(int(order) for _, order, _ in matches) != tuple(
        range(1, len(matches) + 1)
    ):
        raise ValueError("guidance page order metadata is invalid")
    return tuple((page_id, shape) for page_id, _, shape in matches)


def _resource_names(
    primaries: tuple[Contribution, ...],
    topologies: tuple[Contribution, ...],
    facets: tuple[Contribution, ...],
    locales: tuple[str, ...],
) -> tuple[str, ...]:
    return tuple(
        f"{locale}/{item.dimension}/{item.id}.md"
        for locale in locales
        for item in (*primaries, *topologies, *facets)
    )


def expected_resource_names() -> tuple[str, ...]:
    return tuple(
        f"{locale}/{dimension}/{id_}.md"
        for locale in SUPPORTED_LOCALES
        for dimension, ids in (
            ("primary", PRIMARY_IDS),
            ("topology", TOPOLOGY_IDS),
            ("facet", FACET_IDS),
        )
        for id_ in ids
    )


def enumerate_resource_names() -> tuple[str, ...]:
    root = files("repo_dive.wiki.templates.resources")
    discovered = set(_walk_markdown_resources(root))
    expected = expected_resource_names()
    registered = tuple(name for name in expected if name in discovered)
    extras = tuple(sorted(discovered - set(expected)))
    return (*registered, *extras)


def _walk_markdown_resources(
    directory: Traversable, prefix: str = ""
) -> tuple[str, ...]:
    names: list[str] = []
    for entry in directory.iterdir():
        relative = f"{prefix}/{entry.name}" if prefix else entry.name
        if entry.is_dir():
            names.extend(_walk_markdown_resources(entry, relative))
        elif entry.is_file() and entry.name.endswith(".md"):
            names.append(relative)
    return tuple(names)


def _read_resource(locale: str, dimension: str, id_: str) -> str:
    return read_guidance_resource(f"{locale}/{dimension}/{id_}.md")


def load_builtin_registry() -> TemplateRegistry:
    primaries = tuple(_primary(item) for item in PRIMARY_IDS)
    topologies = tuple(_overlay(item, "topology") for item in TOPOLOGY_IDS)
    facets = tuple(_overlay(item, "facet") for item in FACET_IDS)
    shell = _shell()
    registry = TemplateRegistry(
        primaries,
        topologies,
        facets,
        _catalogs(primaries, topologies, facets, shell),
        expected_resource_names(),
        shell,
    )
    if (
        registry.primary_ids != PRIMARY_IDS
        or registry.topology_ids != TOPOLOGY_IDS
        or registry.facet_ids != FACET_IDS
        or registry.locale_ids != SUPPORTED_LOCALES
    ):
        raise ValueError(
            "built-in template registry drifted from classification taxonomy"
        )
    return registry
