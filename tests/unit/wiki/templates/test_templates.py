from __future__ import annotations

import json
import re
from dataclasses import replace
from pathlib import Path

import pytest

from repo_dive.classification.registry import FACET_IDS, PRIMARY_IDS, TOPOLOGY_IDS
from repo_dive.wiki.templates import (
    SUPPORTED_LOCALES,
    ConstraintRefinement,
    ContractNode,
    Contribution,
    LocaleCatalog,
    MergeOperation,
    NodeConstraints,
    TemplateRegistry,
    compose_template,
    enumerate_resource_names,
    expected_resource_names,
    load_builtin_registry,
)
from repo_dive.wiki.templates import subsection_copy as subsection_copy_module
from repo_dive.wiki.templates.models import template_identity_from_document
from repo_dive.wiki.templates.resources import read_guidance_resource
from repo_dive.wiki.templates.subsection_copy import load_subsection_copy

_CJK_OR_KANA = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")


def test_subsection_copy_rejects_duplicate_json_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    resource_root = tmp_path / "resources"
    locale_root = resource_root / "en"
    locale_root.mkdir(parents=True)
    (locale_root / "subsections.json").write_text(
        '{"schema_version":"1.0","locale":"en","locale":"en","subsections":{}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(subsection_copy_module, "files", lambda _: resource_root)
    load_subsection_copy.cache_clear()

    try:
        with pytest.raises(ValueError, match="duplicate keys"):
            load_subsection_copy("en")
    finally:
        load_subsection_copy.cache_clear()


def test_builtin_registry_covers_taxonomy_and_every_locale_resource() -> None:
    registry = load_builtin_registry()

    assert tuple(item.id for item in registry.primaries) == PRIMARY_IDS
    assert tuple(item.id for item in registry.topologies) == TOPOLOGY_IDS
    assert tuple(item.id for item in registry.facets) == FACET_IDS
    assert SUPPORTED_LOCALES == ("en", "zh-CN", "ja")
    assert enumerate_resource_names() == expected_resource_names()


def test_every_contribution_resolves_in_every_locale_with_detailed_safe_guidance() -> (
    None
):
    for resource_name in expected_resource_names():
        source = read_guidance_resource(resource_name)
        minimum_comments = 6 if "/primary/" in resource_name else 4
        assert source.count("<!--") >= minimum_comments
        assert source.count("<!--") == source.count("-->")
        assert source.count("{{repo_dive:") >= 1

    for primary_id in PRIMARY_IDS:
        for topology_id in TOPOLOGY_IDS:
            contracts = tuple(
                compose_template(primary_id, topology_id, FACET_IDS, locale)
                for locale in SUPPORTED_LOCALES
            )
            node_ids = tuple(
                node.logical_id for root in contracts[0].nodes for node in root.walk()
            )
            assert len({contract.compiled_guidance for contract in contracts}) == 3
            contents_labels = {
                dict(contract.labels)["contents"] for contract in contracts
            }
            assert len(contents_labels) == 3
            for contract in contracts:
                assert (
                    tuple(
                        node.logical_id
                        for root in contract.nodes
                        for node in root.walk()
                    )
                    == node_ids
                )
                assert "<!--" not in contract.compiled_guidance
                assert "{{repo_dive:" not in contract.compiled_guidance
                assert not any(
                    line.startswith("#")
                    for line in contract.compiled_guidance.splitlines()
                )


def test_composition_orders_facets_by_taxonomy_and_has_stable_separate_hashes() -> None:
    first = compose_template("cli_tool", "monorepo", ("database", "api"), "zh-CN")
    second = compose_template("cli_tool", "monorepo", ("api", "database"), "zh-CN")
    english = compose_template("cli_tool", "monorepo", ("api", "database"), "en")

    assert first.identity.facets == ("api", "database")
    assert first.to_document() == second.to_document()
    assert first.identity.contract_sha256 == english.identity.contract_sha256
    assert first.identity.localized_sha256 != english.identity.localized_sha256
    assert json.loads(json.dumps(first.to_document())) == first.to_document()
    assert "<!--" not in first.compiled_guidance
    assert "{{repo_dive:" not in first.compiled_guidance


def test_template_identity_is_version_1_and_serializes_both_guidance_forms() -> None:
    contract = compose_template("cli_tool", "single_project", (), "en")
    document = contract.to_document()

    assert contract.identity.schema_version == "1.0"
    assert contract.identity.to_document()["template_schema_version"] == "1.0"
    assert document["annotated_guidance"] == contract.annotated_guidance
    assert document["compiled_guidance"] == contract.compiled_guidance
    assert "<!--" in contract.annotated_guidance
    assert "<!--" not in contract.compiled_guidance
    assert "{{repo_dive:" not in contract.annotated_guidance
    assert "{{repo_dive:" not in contract.compiled_guidance
    assert (
        template_identity_from_document(contract.identity.to_document())
        == contract.identity
    )


def test_localized_hash_covers_both_canonical_guidance_forms() -> None:
    from repo_dive.wiki.templates.composition import canonical_sha256

    contract = compose_template("cli_tool", "single_project", (), "en")
    document = contract.to_document()

    localized_projection = {
        "annotated_guidance": document["annotated_guidance"],
        "compiled_guidance": document["compiled_guidance"],
        "contract_sha256": contract.identity.contract_sha256,
        "labels": document["labels"],
        "locale": "en",
        "subsection_descriptions": document["subsection_descriptions"],
    }
    assert contract.identity.localized_sha256 == canonical_sha256(localized_projection)


def test_compiler_rejects_unregistered_placeholder_syntax() -> None:
    from repo_dive.wiki.templates.composition import compile_guidance

    with pytest.raises(ValueError, match="placeholder"):
        compile_guidance("Do not emit {{unregistered}}.", {})


def test_framework_shell_and_composed_contribution_ids_never_collide() -> None:
    for primary_id in PRIMARY_IDS:
        contract = compose_template(primary_id, "microservices", FACET_IDS, "en")
        shell_ids = {node.logical_id for node in contract.framework_shell.nodes}
        composed_ids = {
            node.logical_id for root in contract.nodes for node in root.walk()
        }
        assert shell_ids.isdisjoint(composed_ids)


def test_all_primary_archetypes_have_intended_distinct_page_signatures() -> None:
    expected = {
        "web_application": (
            "web_runtime_architecture_page",
            "routes_interfaces_page",
            "web_state_persistence_page",
            "web_security_page",
            "web_deployment_operations_page",
            "web_testing_page",
        ),
        "service_api": (
            "service_runtime_architecture_page",
            "api_contracts_page",
            "request_validation_page",
            "service_persistence_page",
            "service_security_page",
            "service_operations_page",
        ),
        "cli_tool": (
            "cli_installation_page",
            "command_reference_page",
            "cli_configuration_page",
            "execution_flow_page",
            "cli_extension_points_page",
            "errors_exit_codes_page",
            "terminology_reference_page",
        ),
        "library_sdk": (
            "library_installation_page",
            "public_api_page",
            "usage_examples_page",
            "library_extension_page",
            "compatibility_page",
        ),
        "data_science": (
            "data_sources_page",
            "analysis_workflow_page",
            "reproducibility_page",
            "analysis_evaluation_page",
            "analysis_artifacts_page",
            "analysis_operationalization_page",
        ),
        "data_pipeline": (
            "pipeline_sources_sinks_page",
            "pipeline_orchestration_page",
            "pipeline_transformations_page",
            "data_quality_page",
            "pipeline_failure_recovery_page",
            "pipeline_operations_page",
        ),
        "ai_ml": (
            "ml_data_features_page",
            "training_pipeline_page",
            "inference_architecture_page",
            "model_evaluation_page",
            "model_artifacts_page",
            "ml_operations_page",
        ),
        "mobile_application": (
            "mobile_runtime_architecture_page",
            "mobile_navigation_page",
            "mobile_state_storage_page",
            "platform_integration_page",
            "mobile_security_page",
            "mobile_distribution_testing_page",
        ),
        "desktop_application": (
            "desktop_process_architecture_page",
            "desktop_ui_lifecycle_page",
            "desktop_state_storage_page",
            "os_integration_page",
            "desktop_security_page",
            "desktop_distribution_testing_page",
        ),
        "embedded_firmware": (
            "target_hardware_page",
            "firmware_architecture_page",
            "realtime_lifecycle_page",
            "io_protocols_page",
            "safety_constraints_page",
            "firmware_testing_distribution_page",
        ),
        "infrastructure": (
            "resource_topology_page",
            "environments_state_page",
            "network_security_page",
            "infrastructure_change_page",
            "observability_recovery_page",
            "infrastructure_testing_page",
        ),
        "developer_tool": (
            "developer_workflow_page",
            "tool_architecture_page",
            "tool_configuration_page",
            "tool_integrations_page",
            "tool_extension_points_page",
            "tool_diagnostics_page",
            "tool_distribution_page",
            "terminology_reference_page",
        ),
        "plugin_extension": (
            "host_contract_page",
            "plugin_activation_page",
            "contribution_points_page",
            "plugin_permissions_page",
            "plugin_compatibility_page",
            "plugin_packaging_testing_page",
        ),
        "game": (
            "game_runtime_loop_page",
            "scene_world_page",
            "gameplay_systems_page",
            "assets_content_page",
            "game_persistence_networking_page",
            "game_build_testing_page",
        ),
        "documentation_content": (
            "information_architecture_page",
            "authoring_conventions_page",
            "documentation_generation_page",
            "documentation_validation_page",
            "navigation_discovery_page",
            "documentation_publishing_page",
        ),
        "general_mixed": (
            "component_catalog_page",
            "shared_contracts_page",
            "cross_component_workflows_page",
            "build_test_matrix_page",
            "mixed_operations_page",
        ),
    }
    signatures: dict[str, tuple[str, ...]] = {}
    for primary_id in PRIMARY_IDS:
        contract = compose_template(primary_id, "single_project", (), "en")
        signatures[primary_id] = tuple(
            node.logical_id
            for root in contract.nodes
            for node in root.walk()
            if node.node_type == "page"
            and node.logical_id
            not in {f"{topology_id}_topology_page" for topology_id in TOPOLOGY_IDS}
        )
    assert signatures == expected
    assert len(set(signatures.values())) == len(PRIMARY_IDS)


def test_representative_contracts_express_distinct_ast_shapes() -> None:
    cli = compose_template("cli_tool", "single_project", (), "en")
    data = compose_template("data_pipeline", "single_project", (), "en")
    node_types = {
        node.node_type for root in (*cli.nodes, *data.nodes) for node in root.walk()
    }
    assert {"subsection", "paragraph", "list", "table", "code_block"} <= node_types
    assert any(
        node.node_type == "extension_slot" for root in cli.nodes for node in root.walk()
    )


def test_every_builtin_page_owns_explicit_ordered_localized_subsections() -> None:
    generic_suffixes = {
        "overview",
        "implementation",
        "contract",
        "examples",
        "workflow",
        "verification",
        "comparison",
        "decisions",
    }
    observed_page_ids: set[str] = set()
    english_signatures: dict[str, tuple[str, ...]] = {}

    for primary_id in PRIMARY_IDS:
        contracts = tuple(
            compose_template(
                primary_id,
                "microservices",
                FACET_IDS,
                locale,
            )
            for locale in SUPPORTED_LOCALES
        )
        pages = tuple(
            node
            for root in contracts[0].nodes
            for node in root.walk()
            if node.node_type == "page"
        )
        labels_by_locale = tuple(dict(contract.labels) for contract in contracts)
        for page in pages:
            observed_page_ids.add(page.logical_id)
            assert len(page.children) == 2
            stem = page.logical_id.removesuffix("_page")
            subsection_ids = tuple(child.logical_id for child in page.children)
            assert len(set(subsection_ids)) == 2
            assert not {f"{stem}_{suffix}" for suffix in generic_suffixes}.intersection(
                subsection_ids
            )
            previous = english_signatures.setdefault(page.logical_id, subsection_ids)
            assert previous == subsection_ids
            for labels in labels_by_locale:
                assert all(labels[subsection_id] for subsection_id in subsection_ids)
            descriptions = tuple(
                tuple(
                    dict(contract.subsection_descriptions)[subsection_id]
                    for subsection_id in subsection_ids
                )
                for contract in contracts
            )
            assert all(
                all(description for description in items) for items in descriptions
            )
            for labels in labels_by_locale[1:]:
                assert all(
                    _CJK_OR_KANA.search(labels[subsection_id])
                    for subsection_id in subsection_ids
                )

    expected_overlay_ids = {
        *(f"{topology_id}_topology_page" for topology_id in TOPOLOGY_IDS),
        *(f"{facet_id}_facet_page" for facet_id in FACET_IDS),
    }
    for topology_id in TOPOLOGY_IDS:
        contracts = tuple(
            compose_template("cli_tool", topology_id, (), locale)
            for locale in SUPPORTED_LOCALES
        )
        page_id = f"{topology_id}_topology_page"
        page = next(
            node
            for root in contracts[0].nodes
            for node in root.walk()
            if node.logical_id == page_id
        )
        observed_page_ids.add(page_id)
        assert len(page.children) == 2
        for contract in contracts[1:]:
            labels = dict(contract.labels)
            assert all(
                _CJK_OR_KANA.search(labels[child.logical_id]) for child in page.children
            )
    assert expected_overlay_ids <= observed_page_ids


def test_subsection_copy_is_focused_explicit_and_not_synthesized() -> None:
    expected = {
        "en": (
            "Prerequisites",
            "Identify required runtimes, packages, and repository setup commands "
            "before CLI installation begins.",
        ),
        "zh-CN": (
            "前置条件",
            "在开始安装 CLI 前，识别必需的运行时、软件包和代码库设置命令。",
        ),
        "ja": (
            "前提条件",
            "CLI のインストール前に必要なランタイム、パッケージ、"
            "リポジトリ設定コマンドを特定します。",
        ),
    }
    generic_prefixes = (
        "Document ",
        "使用代码库证据说明",
        "リポジトリの根拠に基づいて",
    )

    for locale in SUPPORTED_LOCALES:
        contract = compose_template("cli_tool", "single_project", FACET_IDS, locale)
        labels = dict(contract.labels)
        descriptions = dict(contract.subsection_descriptions)
        subsection_ids = tuple(
            child.logical_id
            for root in contract.nodes
            for node in root.walk()
            if node.node_type == "page"
            for child in node.children
            if child.node_type == "subsection"
        )
        assert set(descriptions) == set(subsection_ids)
        assert len(descriptions.values()) == len(set(descriptions.values()))
        assert all(
            not description.startswith(generic_prefixes)
            for description in descriptions.values()
        )
        subsection_id = "cli_installation_prerequisites"
        assert (labels[subsection_id], descriptions[subsection_id]) == expected[locale]


def test_subsection_copy_resources_fail_closed_on_drift_or_generic_copy() -> None:
    resources = {
        locale: dict(load_subsection_copy(locale)) for locale in SUPPORTED_LOCALES
    }
    expected_ids = set(resources["en"])
    banned_generic_copy = (
        "Document {title}",
        "Document this Subsection",
        "使用代码库证据说明标题",
        "リポジトリの根拠に基づいてタイトル",
    )

    assert expected_ids
    assert all(set(copy) == expected_ids for copy in resources.values())
    for locale, copy in resources.items():
        descriptions = tuple(item.description for item in copy.values())
        assert len(descriptions) == len(set(descriptions))
        assert all(
            generic not in description
            for description in descriptions
            for generic in banned_generic_copy
        )
        if locale != "en":
            assert all(_CJK_OR_KANA.search(item.title) for item in copy.values())
            assert all(_CJK_OR_KANA.search(item.description) for item in copy.values())

    with pytest.raises(ValueError, match="locale"):
        load_subsection_copy("EN")

    registry = load_builtin_registry()
    english = registry.catalogs[0]
    missing = replace(
        english,
        subsection_descriptions=english.subsection_descriptions[:-1],
    )
    with pytest.raises(ValueError, match="description keys"):
        replace(registry, catalogs=(missing, *registry.catalogs[1:]))

    first_id, _ = english.subsection_descriptions[0]
    second_id, _ = english.subsection_descriptions[1]
    with pytest.raises(ValueError, match="unique sorted copy"):
        replace(
            english,
            subsection_descriptions=((first_id, "duplicate"), (second_id, "duplicate")),
        )


def test_cli_template_uses_topic_specific_subsection_order() -> None:
    contract = compose_template("cli_tool", "single_project", (), "en")
    pages = {
        node.logical_id: tuple(child.logical_id for child in node.children)
        for root in contract.nodes
        for node in root.walk()
        if node.node_type == "page"
    }

    assert pages["cli_installation_page"] == (
        "cli_installation_prerequisites",
        "cli_installation_first_run",
    )
    assert pages["cli_extension_points_page"] == (
        "cli_extension_points_extension_contracts",
        "cli_extension_points_registration_workflow",
    )
    assert pages["errors_exit_codes_page"] == (
        "errors_exit_codes_error_contracts",
        "errors_exit_codes_recovery_workflows",
    )


def test_annotated_guidance_is_resolved_and_really_localized() -> None:
    english = compose_template("cli_tool", "single_project", (), "en")
    chinese = compose_template("cli_tool", "single_project", (), "zh-CN")
    japanese = compose_template("cli_tool", "single_project", (), "ja")

    assert "Command reference" in english.annotated_guidance
    assert "命令参考" in chinese.annotated_guidance
    assert "コマンドリファレンス" in japanese.annotated_guidance
    assert "必需证据" in chinese.annotated_guidance
    assert "必須の根拠" in japanese.annotated_guidance


def test_every_non_english_catalog_label_is_localized() -> None:
    registry = load_builtin_registry()

    for catalog in registry.catalogs:
        if catalog.locale == "en":
            continue
        assert all(_CJK_OR_KANA.search(value) for _, value in catalog.labels)


@pytest.mark.parametrize(
    ("primary", "topology", "facets", "locale"),
    [
        ("unknown", "single_project", (), "en"),
        ("cli_tool", "unknown", (), "en"),
        ("cli_tool", "single_project", ("unknown",), "en"),
        ("cli_tool", "single_project", (), "EN"),
        ("cli_tool", "single_project", ("api", "api"), "en"),
    ],
)
def test_composition_rejects_unknown_or_duplicate_selection(
    primary: str, topology: str, facets: tuple[str, ...], locale: str
) -> None:
    with pytest.raises(ValueError):
        compose_template(primary, topology, facets, locale)


def test_contract_models_are_strict_and_refinements_only_tighten() -> None:
    constraints = NodeConstraints(required=False, min_count=0, max_count=3)
    node = ContractNode("entry", "paragraph", "caller", constraints)
    refined = node.refine(ConstraintRefinement(required=True, min_count=1, max_count=2))
    assert refined.constraints == NodeConstraints(True, 1, 2)

    with pytest.raises(ValueError, match="tighten"):
        refined.refine(ConstraintRefinement(required=False))
    with pytest.raises(ValueError, match="logical"):
        ContractNode("Not.Valid", "paragraph", "caller", constraints)
    with pytest.raises(ValueError, match="extension slot"):
        ContractNode("slot", "extension_slot", "contract", constraints)
    with pytest.raises(ValueError, match="operation"):
        MergeOperation("move", "entry", node)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="immutable tuple"):
        NodeConstraints(False, 0, 1, [2])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="immutable tuple"):
        ContractNode("root", "root", "cli", constraints, [node])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="heading levels"):
        NodeConstraints(False, 0, 1, (True,))
    with pytest.raises(ValueError, match="node children"):
        ContractNode(
            "root",
            "root",
            "cli",
            constraints,
            ("not-a-node",),  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="canonical"):
        LocaleCatalog("EN", (("entry", "Entry"),))


def test_framework_shell_rejects_nested_non_cli_and_duplicate_ids() -> None:
    from repo_dive.wiki.templates import FrameworkShell

    constraints = NodeConstraints(True, 1, 1)
    caller_child = ContractNode("body", "paragraph", "caller", constraints)
    with pytest.raises(ValueError, match="CLI owned"):
        FrameworkShell(
            (ContractNode("wiki", "root", "cli", constraints, (caller_child,)),)
        )
    with pytest.raises(ValueError, match="unique"):
        FrameworkShell(
            (
                ContractNode("wiki", "root", "cli", constraints),
                ContractNode("wiki", "contents", "cli", constraints),
            )
        )
    with pytest.raises(ValueError, match="exactly one root"):
        FrameworkShell((ContractNode("contents", "contents", "cli", constraints),))
    with pytest.raises(ValueError, match="exactly one root"):
        FrameworkShell(
            (
                ContractNode("wiki", "root", "cli", constraints),
                ContractNode("other_root", "root", "cli", constraints),
            )
        )


def test_registry_rejects_nested_shell_contribution_id_collision() -> None:
    from repo_dive.wiki.templates import FrameworkShell

    constraints = NodeConstraints(True, 1, 1)
    shell = FrameworkShell(
        (
            ContractNode(
                "wiki",
                "root",
                "cli",
                constraints,
                (ContractNode("nested_shell", "contents", "cli", constraints),),
            ),
        )
    )
    primary = Contribution(
        "cli_tool",
        "primary",
        "1",
        nodes=(ContractNode("nested_shell", "section", "contract", constraints),),
    )
    topology = Contribution(
        "single_project",
        "topology",
        "1",
        operations=(
            MergeOperation(
                "insert_after",
                "nested_shell",
                ContractNode("topology", "section", "contract", constraints),
            ),
        ),
    )
    labels = LocaleCatalog(
        "en",
        (("nested_shell", "Nested shell"), ("topology", "Topology"), ("wiki", "Wiki")),
    )

    with pytest.raises(ValueError, match="collide"):
        TemplateRegistry(
            (primary,),
            (topology,),
            (),
            (labels,),
            (),
            shell,
            validate_resources=False,
        )


def test_registry_rejects_locale_drift_and_unregistered_resources() -> None:
    registry = load_builtin_registry()
    catalog = registry.catalogs[0]
    missing = LocaleCatalog(catalog.locale, catalog.labels[:-1])
    with pytest.raises(ValueError, match="locale keys"):
        TemplateRegistry(
            registry.primaries,
            registry.topologies,
            registry.facets,
            (missing, *registry.catalogs[1:]),
            registry.resource_names,
        )

    with pytest.raises(ValueError, match="resources"):
        TemplateRegistry(
            registry.primaries,
            registry.topologies,
            registry.facets,
            registry.catalogs,
            registry.resource_names[:-1],
            registry.framework_shell,
        )


def test_composition_rejects_missing_targets_duplicates_and_cycles() -> None:
    base = Contribution(
        "base",
        "primary",
        "1",
        nodes=(
            ContractNode(
                "root",
                "root",
                "cli",
                NodeConstraints(True, 1, 1),
            ),
        ),
    )
    missing = Contribution(
        "single_project",
        "topology",
        "1",
        operations=(
            MergeOperation(
                "insert_after",
                "absent",
                ContractNode("new", "section", "cli", NodeConstraints(True, 1, 1)),
            ),
        ),
    )
    missing_locale = LocaleCatalog("en", (("new", "New"), ("root", "Root")))
    with pytest.raises(ValueError, match="target"):
        TemplateRegistry(
            (base,),
            (missing,),
            (),
            (missing_locale,),
            resource_names=(),
            validate_resources=False,
        )

    cycle = Contribution(
        "single_project",
        "topology",
        "1",
        operations=(
            MergeOperation(
                "insert_after",
                "b",
                ContractNode("a", "section", "cli", NodeConstraints(True, 1, 1)),
            ),
            MergeOperation(
                "insert_after",
                "a",
                ContractNode("b", "section", "cli", NodeConstraints(True, 1, 1)),
            ),
        ),
    )
    cycle_locale = LocaleCatalog("en", (("a", "A"), ("b", "B"), ("root", "Root")))
    with pytest.raises(ValueError, match="cycle"):
        TemplateRegistry(
            (base,),
            (cycle,),
            (),
            (cycle_locale,),
            resource_names=(),
            validate_resources=False,
        )


def test_all_closed_operations_preserve_order_and_tighten_in_place() -> None:
    base = Contribution(
        "cli_tool",
        "primary",
        "1",
        nodes=(
            ContractNode(
                "root",
                "root",
                "cli",
                NodeConstraints(True, 1, 1),
                (
                    ContractNode(
                        "cli_tool_body",
                        "paragraph",
                        "caller",
                        NodeConstraints(True, 1, 3),
                    ),
                    ContractNode(
                        "slot",
                        "extension_slot",
                        "contract",
                        NodeConstraints(False, 0, 2),
                        allowed_child_types=("page",),
                    ),
                ),
            ),
        ),
    )
    topology_page = ContractNode(
        "single_project_topology_page",
        "page",
        "cli",
        NodeConstraints(True, 1, 1),
        (
            ContractNode(
                "single_project_topology_body",
                "paragraph",
                "caller",
                NodeConstraints(True, 1, 2),
            ),
        ),
    )
    topology = Contribution(
        "single_project",
        "topology",
        "1",
        operations=(
            MergeOperation(
                "insert_before",
                "cli_tool_body",
                ContractNode(
                    "before", "paragraph", "caller", NodeConstraints(True, 1, 1)
                ),
            ),
            MergeOperation(
                "insert_after",
                "cli_tool_body",
                ContractNode(
                    "after", "paragraph", "caller", NodeConstraints(True, 1, 1)
                ),
            ),
            MergeOperation("append_to_slot", "slot", topology_page),
            MergeOperation(
                "refine_existing",
                "cli_tool_body",
                refinement=ConstraintRefinement(max_count=2),
            ),
        ),
    )
    labels = tuple(
        sorted(
            (key, key.replace("_", " "))
            for key in (
                "after",
                "before",
                "cli_tool_body",
                "root",
                "single_project_topology_body",
                "single_project_topology_page",
                "slot",
            )
        )
    )
    registry = TemplateRegistry(
        (base,),
        (topology,),
        (),
        (LocaleCatalog("en", labels),),
        resource_names=(),
        validate_resources=False,
    )

    contract = registry.compose("cli_tool", "single_project", (), "en")
    children = contract.nodes[0].children
    assert tuple(node.logical_id for node in children) == (
        "before",
        "cli_tool_body",
        "after",
        "slot",
    )
    assert children[1].constraints.max_count == 2
    assert children[3].children == (topology_page,)


def test_composition_rejects_duplicate_inserted_logical_ids() -> None:
    registry = load_builtin_registry()
    duplicate = Contribution(
        "single_project",
        "topology",
        "1",
        operations=(
            *registry.topologies[0].operations,
            registry.topologies[0].operations[0],
        ),
    )
    with pytest.raises(ValueError, match="duplicate logical ids"):
        TemplateRegistry(
            (registry.primaries[2],),
            (duplicate,),
            (),
            tuple(
                LocaleCatalog(
                    catalog.locale,
                    tuple(
                        item
                        for item in catalog.labels
                        if item[0]
                        in {
                            node.logical_id
                            for root in registry.primaries[2].nodes
                            for node in root.walk()
                        }
                        | {
                            node.logical_id
                            for node in duplicate.operations[0].node.walk()  # type: ignore[union-attr]
                        }
                    ),
                )
                for catalog in registry.catalogs
            ),
            (),
            validate_resources=False,
        ).compose("cli_tool", "single_project", (), "en")


def test_framework_shell_is_cli_owned_and_page_contract_excludes_shell_headings() -> (
    None
):
    contract = compose_template("cli_tool", "single_project", (), "ja")
    shell = contract.framework_shell

    assert all(node.owner == "cli" for node in shell.nodes)
    assert {
        "wiki",
        "contents",
        "section_heading",
        "page_heading",
        "related_pages",
        "sources",
        "scope_version",
        "source_commit",
        "generated_at",
    } <= {node.logical_id for node in shell.nodes}
    assert "page heading" not in contract.compiled_guidance.lower()
