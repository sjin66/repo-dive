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

SUPPORTED_LOCALES = ("en", "zh-CN", "ja")
TEMPLATE_SCHEMA_VERSION = "1.0"
TEMPLATE_REGISTRY_VERSION = "1"

PageProfile = Literal["narrative", "reference", "procedure", "matrix"]
PageSpec: TypeAlias = tuple[str, PageProfile]
SectionSpec: TypeAlias = tuple[str, tuple[PageSpec, ...]]

_ONE = NodeConstraints(True, 1, 1)
_PAGE = NodeConstraints(True, 1, 1, (3,))
_BODY_HEADING = NodeConstraints(True, 1, 4, (4, 5))
_PARAGRAPHS = NodeConstraints(True, 2, 8)
_LISTS = NodeConstraints(True, 1, 4)
_TABLES = NodeConstraints(True, 1, 4)
_CODE_BLOCKS = NodeConstraints(True, 1, 6)
_SLOT = NodeConstraints(False, 0, 32, (3,))


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
        ),
        _spec(
            "tool_delivery_section",
            ("tool_diagnostics_page", "reference"),
            ("tool_distribution_page", "procedure"),
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
    return ContractNode(
        page_id,
        "page",
        "contract",
        _PAGE,
        tuple(_body_node(page_id, node_type) for node_type in _PROFILE_TYPES[profile]),
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
    return Contribution(
        primary_id, "primary", "1", nodes=(*sections, *overlay_sections)
    )


def _overlay(id_: str, dimension: ContributionDimension) -> Contribution:
    suffix = "topology" if dimension == "topology" else "facet"
    target = "topology_pages" if dimension == "topology" else "facet_pages"
    node = _page(f"{id_}_{suffix}_page", "narrative")
    return Contribution(
        id_,
        dimension,
        "1",
        operations=(MergeOperation("append_to_slot", target, node),),
    )


_SHELL_LABELS = {
    "wiki": ("Repository Wiki", "代码库 Wiki", "リポジトリ Wiki"),
    "contents": ("Contents", "目录", "目次"),
    "section_heading": ("Section", "章节", "セクション"),
    "page_heading": ("Page", "页面", "ページ"),
    "related_pages": ("Related pages", "相关页面", "関連ページ"),
    "sources": ("Sources", "来源", "出典"),
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
    return tuple(
        LocaleCatalog(
            locale,
            tuple(
                sorted(
                    (logical_id, _localized_label(logical_id, index))
                    for logical_id in ids
                )
            ),
        )
        for index, locale in enumerate(SUPPORTED_LOCALES)
    )


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
