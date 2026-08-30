from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from repo_dive.classification import (
    BUILTIN_REGISTRY,
    FACET_IDS,
    PRIMARY_IDS,
    TOPOLOGY_IDS,
    ClassificationError,
    ClassificationService,
    IndexedFile,
    IndexSnapshot,
)
from repo_dive.classification.models import (
    MAX_MANIFEST_BYTES,
    Taxon,
    classification_result_from_document,
)
from repo_dive.classification.registry import (
    ExactPath,
    NamedManifestKeyValue,
    RuleRegistry,
    SignalRule,
)
from repo_dive.schema import serialize_json_document


def snapshot(*files: IndexedFile) -> IndexSnapshot:
    return IndexSnapshot(
        repository_fingerprint="fingerprint-1",
        index_build_id="build-1",
        files=tuple(reversed(files)),
    )


def file(path: str, *, language: str = "text", text: str | None = None) -> IndexedFile:
    return IndexedFile(
        path=path,
        language=language,
        readable=text is not None,
        size_bytes=len(text.encode("utf-8")) if text is not None else 0,
        text=text,
    )


@pytest.mark.parametrize(
    ("expected", "files"),
    [
        (
            "web_application",
            (
                file("package.json", text="{}"),
                file("src/pages/home.tsx", language="typescript", text="x"),
            ),
        ),
        ("service_api", (file("openapi.yaml", text="openapi: 3.1.0"),)),
        (
            "cli_tool",
            (file("pyproject.toml", text='[project.scripts]\nexample = "pkg:main"\n'),),
        ),
        (
            "library_sdk",
            (file("src/example_sdk/__init__.py", language="python", text=""),),
        ),
        (
            "data_science",
            (file("notebooks/analysis.ipynb", language="json", text="{}"),),
        ),
        ("data_pipeline", (file("dags/daily.py", language="python", text="x"),)),
        ("ai_ml", (file("models/model.onnx", text=None),)),
        (
            "mobile_application",
            (file("android/app/src/main/AndroidManifest.xml", text="<manifest />"),),
        ),
        (
            "desktop_application",
            (file("package.json", text='{"devDependencies":{"electron":"1"}}'),),
        ),
        ("embedded_firmware", (file("platformio.ini", text="[env:test]"),)),
        ("infrastructure", (file("main.tf", language="hcl", text="resource {}"),)),
        ("developer_tool", (file(".pre-commit-hooks.yaml", text="- id: tool"),)),
        ("plugin_extension", (file("plugin.json", text="{}"),)),
        ("game", (file("project.godot", text="[application]"),)),
        ("documentation_content", (file("mkdocs.yml", text="site_name: Docs"),)),
        ("general_mixed", (file("README.md", language="markdown", text="# Example"),)),
    ],
)
def test_builtin_registry_covers_every_primary_archetype(
    expected: str, files: tuple[IndexedFile, ...]
) -> None:
    result = ClassificationService().classify(snapshot(*files))

    assert result.detected_primary.id == expected
    assert result.effective_primary.id == expected


def test_taxonomy_registry_contains_every_required_id() -> None:
    assert set(PRIMARY_IDS) == {
        "web_application",
        "service_api",
        "cli_tool",
        "library_sdk",
        "data_science",
        "data_pipeline",
        "ai_ml",
        "mobile_application",
        "desktop_application",
        "embedded_firmware",
        "infrastructure",
        "developer_tool",
        "plugin_extension",
        "game",
        "documentation_content",
        "general_mixed",
    }
    assert set(TOPOLOGY_IDS) == {"single_project", "monorepo", "microservices"}
    assert set(FACET_IDS) == {
        "saas",
        "multi_tenancy",
        "ui",
        "api",
        "database",
        "messaging",
        "infrastructure",
        "model_training_inference",
    }
    assert {taxon.id for taxon in BUILTIN_REGISTRY.primaries} == set(PRIMARY_IDS)


def test_overlays_are_ordered_and_override_does_not_hide_detection() -> None:
    result = ClassificationService().classify(
        snapshot(
            file("openapi.yaml", text="openapi: 3.1.0"),
            file("packages/app/package.json", text="{}"),
            file("packages/shared/package.json", text="{}"),
            file("src/ui/app.tsx", language="typescript", text="x"),
            file("migrations/001.sql", language="sql", text="create table x"),
            file("main.tf", language="hcl", text="resource {}"),
        ),
        override="library_sdk",
    )

    assert result.detected_primary.id == "service_api"
    assert result.effective_primary.id == "library_sdk"
    assert result.selection_source == "override"
    assert result.template_override == "library_sdk"
    assert result.topology.id == "monorepo"
    assert [item.id for item in result.facets] == [
        "ui",
        "api",
        "database",
        "infrastructure",
    ]


def test_builtin_registry_detects_every_facet_in_taxonomy_order() -> None:
    result = ClassificationService().classify(
        snapshot(
            file(
                "package.json",
                text='{"repoDive":{"facets":["multi_tenancy","saas"]}}',
            ),
            file("src/ui/app.tsx", language="typescript", text="x"),
            file("openapi.yaml", text="openapi: 3.1.0"),
            file("migrations/001.sql", language="sql", text="x"),
            file("config/kafka.yaml", text="brokers: []"),
            file("main.tf", language="hcl", text="resource {}"),
            file("models/model.onnx"),
        )
    )

    assert [item.id for item in result.facets] == list(FACET_IDS)


def test_language_count_and_integer_ratio_signals_are_auditable() -> None:
    c_result = ClassificationService().classify(
        snapshot(
            *(file(f"src/{index}.c", language="c", text="x") for index in range(5))
        )
    )
    docs_result = ClassificationService().classify(
        snapshot(
            *(
                file(f"docs/{index}.md", language="markdown", text="# X")
                for index in range(4)
            ),
            file("docs/data.json", language="json", text="{}"),
        )
    )

    assert "embedded_c_sources" in {item.id for item in c_result.matched_signals}
    assert docs_result.detected_primary.id == "documentation_content"
    assert "documentation_markdown_ratio" in {
        item.id for item in docs_result.matched_signals
    }


def test_microservices_requires_multiple_service_manifests() -> None:
    one = ClassificationService().classify(
        snapshot(file("services/api/service.yaml", text="name: api"))
    )
    two = ClassificationService().classify(
        snapshot(
            file("services/worker/service.yaml", text="name: worker"),
            file("services/api/service.yaml", text="name: api"),
        )
    )

    assert one.topology.id == "single_project"
    assert two.topology.id == "microservices"
    assert two.matched_signals[-1].paths == (
        "services/api/service.yaml",
        "services/worker/service.yaml",
    )


def test_monorepo_requires_multiple_workspace_roots_not_only_a_marker() -> None:
    marker_only = ClassificationService().classify(
        snapshot(file("pnpm-workspace.yaml", text="packages: []"))
    )
    workspaces = ClassificationService().classify(
        snapshot(
            file("packages/app/package.json", text="{}"),
            file("packages/shared/package.json", text="{}"),
        )
    )

    assert marker_only.topology.id == "single_project"
    assert workspaces.topology.id == "monorepo"


def test_tied_and_weak_primary_scores_fall_back_stably() -> None:
    tied = ClassificationService().classify(
        snapshot(
            file("openapi.yaml", text="openapi: 3.1.0"),
            file("project.godot", text="[application]"),
        )
    )
    weak = ClassificationService().classify(snapshot(file("package.json", text="{}")))

    assert tied.detected_primary.id == "general_mixed"
    assert tied.fallback_reason == "tied"
    assert weak.detected_primary.id == "general_mixed"
    assert weak.fallback_reason == "below_threshold"


def test_primary_score_with_insufficient_margin_is_ambiguous() -> None:
    registry = RuleRegistry(
        primaries=(Taxon("alpha", 100), Taxon("beta", 100), Taxon("general_mixed", 0)),
        topologies=(Taxon("single_project", 0),),
        facets=(),
        signals=(
            SignalRule("alpha_signal", "primary", "alpha", 110, ExactPath("alpha")),
            SignalRule("beta_signal", "primary", "beta", 100, ExactPath("beta")),
        ),
        primary_margin=20,
    )

    result = ClassificationService(registry).classify(
        snapshot(file("alpha", text="x"), file("beta", text="x"))
    )

    assert result.detected_primary.id == "general_mixed"
    assert result.fallback_reason == "ambiguous"


def test_unknown_override_is_typed_domain_validation_error() -> None:
    with pytest.raises(ClassificationError) as exc_info:
        ClassificationService().classify(snapshot(), override="unknown")

    assert exc_info.value.code == "classification_override_unknown"
    assert exc_info.value.details == {"override": "unknown"}


def test_malformed_and_oversized_manifests_are_safe_and_do_not_match() -> None:
    malformed = ClassificationService().classify(
        snapshot(file("package.json", text='{"devDependencies":'))
    )
    oversized = ClassificationService().classify(
        snapshot(file("package.json", text='{"devDependencies":' + " " * 70_000))
    )

    assert malformed.detected_primary.id == "general_mixed"
    assert [item.to_document() for item in malformed.observations] == [
        {"code": "manifest_malformed", "path": "package.json"}
    ]
    assert oversized.detected_primary.id == "general_mixed"
    assert oversized.observations[0].code == "manifest_oversized"
    document = oversized.to_document()
    assert "devDependencies" not in str(document)


@pytest.mark.parametrize(
    "manifest",
    [
        '{"devDependencies":{},"devDependencies":{"electron":"1"}}',
        '{"repoDive":{"facets":[NaN]}}',
        "[" * 2_000 + "]" * 2_000,
    ],
)
def test_ambiguous_or_pathological_json_is_reported_as_malformed(
    manifest: str,
) -> None:
    result = ClassificationService().classify(
        snapshot(file("package.json", text=manifest))
    )

    assert result.detected_primary.id == "general_mixed"
    assert [item.to_document() for item in result.observations] == [
        {"code": "manifest_malformed", "path": "package.json"}
    ]


def test_actual_manifest_text_size_is_bounded_even_if_metadata_is_incorrect() -> None:
    oversized = IndexedFile(
        path="package.json",
        language="json",
        readable=True,
        size_bytes=1,
        text=" " * (MAX_MANIFEST_BYTES + 1),
    )

    result = ClassificationService().classify(snapshot(oversized))

    assert [item.to_document() for item in result.observations] == [
        {"code": "manifest_oversized", "path": "package.json"}
    ]


def test_manifest_matcher_can_compare_an_explicit_json_null() -> None:
    registry = RuleRegistry(
        primaries=(Taxon("example", 10), Taxon("general_mixed", 0)),
        topologies=(Taxon("single_project", 0),),
        facets=(),
        signals=(
            SignalRule(
                "null_license",
                "primary",
                "example",
                10,
                NamedManifestKeyValue("package.json", ("license",), equals=None),
            ),
        ),
        primary_margin=0,
    )

    result = ClassificationService(registry).classify(
        snapshot(file("package.json", text='{"license":null}'))
    )

    assert result.detected_primary.id == "example"
    assert [item.id for item in result.matched_signals] == ["null_license"]


def test_result_is_immutable_and_byte_stable_without_timestamps_or_content() -> None:
    inputs = (
        file("src/pages/z.tsx", language="typescript", text="SECRET z"),
        file("src/pages/a.tsx", language="typescript", text="SECRET a"),
        file("package.json", text="{}"),
    )
    first = ClassificationService().classify(snapshot(*inputs))
    second = ClassificationService().classify(snapshot(*reversed(inputs)))

    with pytest.raises(FrozenInstanceError):
        first.selection_source = "override"  # type: ignore[misc]
    encoded = serialize_json_document(first.to_document())
    assert encoded == serialize_json_document(second.to_document())
    assert "SECRET" not in encoded
    assert "timestamp" not in encoded
    assert first.matched_signals[1].paths == ("src/pages/a.tsx", "src/pages/z.tsx")


def test_classification_persistence_decoder_is_strict_and_round_trips() -> None:
    result = ClassificationService().classify(snapshot(file("src/app.py")))
    document = result.to_document()

    assert classification_result_from_document(document) == result

    document["unexpected"] = True
    with pytest.raises(ValueError, match="fields"):
        classification_result_from_document(document)
