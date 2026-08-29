"""Versioned bounded signal registry for built-in classification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from repo_dive.classification.models import Dimension, Taxon
from repo_dive.schema import JsonScalar

PRIMARY_IDS = (
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
)
TOPOLOGY_IDS = ("single_project", "monorepo", "microservices")
FACET_IDS = (
    "saas",
    "multi_tenancy",
    "ui",
    "api",
    "database",
    "messaging",
    "infrastructure",
    "model_training_inference",
)


class _UnsetComparison:
    pass


_UNSET_COMPARISON = _UnsetComparison()


@dataclass(frozen=True, slots=True)
class ExactPath:
    path: str

    def __post_init__(self) -> None:
        if not _is_repository_path(self.path) or any(
            character in self.path for character in "*?["
        ):
            raise ValueError("exact path must be a repository-relative POSIX path")


@dataclass(frozen=True, slots=True)
class PathGlob:
    pattern: str
    min_count: int = 1

    def __post_init__(self) -> None:
        if not _is_repository_path(self.pattern) or self.min_count <= 0:
            raise ValueError("path glob parameters must be valid")


@dataclass(frozen=True, slots=True)
class LanguageCount:
    language: str
    minimum: int

    def __post_init__(self) -> None:
        if not self.language or self.minimum <= 0:
            raise ValueError("language count parameters must be positive")


@dataclass(frozen=True, slots=True)
class LanguageRatio:
    language: str
    numerator: int
    denominator: int
    minimum_files: int = 1

    def __post_init__(self) -> None:
        if (
            not self.language
            or self.numerator <= 0
            or self.denominator <= 0
            or self.numerator > self.denominator
            or self.minimum_files <= 0
        ):
            raise ValueError("language ratio parameters must be valid")


@dataclass(frozen=True, slots=True)
class NamedManifestKeyValue:
    path: str
    key: tuple[str, ...]
    equals: JsonScalar | _UnsetComparison = _UNSET_COMPARISON
    present: bool = False
    contains: str | None = None

    def __post_init__(self) -> None:
        modes = (
            int(self.present)
            + int(self.contains is not None)
            + int(self.equals is not _UNSET_COMPARISON)
        )
        if (
            not _is_repository_path(self.path)
            or any(character in self.path for character in "*?[")
            or not self.key
            or any(not part for part in self.key)
            or modes != 1
        ):
            raise ValueError(
                "manifest matcher must declare exactly one bounded comparison"
            )


Matcher: TypeAlias = (
    ExactPath | PathGlob | LanguageCount | LanguageRatio | NamedManifestKeyValue
)


@dataclass(frozen=True, slots=True)
class SignalRule:
    id: str
    dimension: Dimension
    target_id: str
    weight: int
    matcher: Matcher

    def __post_init__(self) -> None:
        valid_id = (
            bool(self.id)
            and self.id[0].isascii()
            and self.id[0].islower()
            and all(
                character.isascii()
                and (character.islower() or character.isdigit() or character == "_")
                for character in self.id
            )
        )
        if not valid_id or self.dimension not in {"primary", "topology", "facet"}:
            raise ValueError("signal id and dimension must be valid")
        if self.weight <= 0:
            raise ValueError("signal id and weight must be positive")


@dataclass(frozen=True, slots=True)
class RuleRegistry:
    primaries: tuple[Taxon, ...]
    topologies: tuple[Taxon, ...]
    facets: tuple[Taxon, ...]
    signals: tuple[SignalRule, ...]
    primary_margin: int = 20

    def __post_init__(self) -> None:
        if self.primary_margin < 0:
            raise ValueError("primary margin must not be negative")
        dimensions = {
            "primary": {item.id for item in self.primaries},
            "topology": {item.id for item in self.topologies},
            "facet": {item.id for item in self.facets},
        }
        if (
            "general_mixed" not in dimensions["primary"]
            or len(dimensions["primary"]) < 2
            or "single_project" not in dimensions["topology"]
        ):
            raise ValueError("registry fallback taxa are required")
        signal_ids = [rule.id for rule in self.signals]
        if len(signal_ids) != len(set(signal_ids)):
            raise ValueError("registry signal ids must be unique")
        if any(
            rule.target_id not in dimensions[rule.dimension] for rule in self.signals
        ):
            raise ValueError("registry signal target is unknown")
        for taxa in (self.primaries, self.topologies, self.facets):
            ids = [item.id for item in taxa]
            if len(ids) != len(set(ids)):
                raise ValueError("registry taxon ids must be unique per dimension")


def _signal(
    id: str, dimension: Dimension, target: str, weight: int, matcher: Matcher
) -> SignalRule:
    return SignalRule(id, dimension, target, weight, matcher)


def _is_repository_path(value: str) -> bool:
    parts = value.split("/")
    return (
        bool(value)
        and not value.startswith("/")
        and "\\" not in value
        and all(part not in {"", ".", ".."} for part in parts)
    )


BUILTIN_REGISTRY = RuleRegistry(
    primaries=tuple(
        Taxon(item, 100 if item != "general_mixed" else 0) for item in PRIMARY_IDS
    ),
    topologies=(
        Taxon("single_project", 0),
        Taxon("monorepo", 100),
        Taxon("microservices", 100),
    ),
    facets=tuple(Taxon(item, 40) for item in FACET_IDS),
    signals=(
        _signal(
            "web_package", "primary", "web_application", 40, ExactPath("package.json")
        ),
        _signal("web_pages", "primary", "web_application", 80, PathGlob("src/pages/*")),
        _signal(
            "service_openapi", "primary", "service_api", 120, ExactPath("openapi.yaml")
        ),
        _signal(
            "cli_python_scripts",
            "primary",
            "cli_tool",
            120,
            NamedManifestKeyValue(
                "pyproject.toml", ("project", "scripts"), present=True
            ),
        ),
        _signal(
            "library_python_package",
            "primary",
            "library_sdk",
            120,
            PathGlob("src/*/__init__.py"),
        ),
        _signal(
            "data_science_notebook",
            "primary",
            "data_science",
            120,
            PathGlob("notebooks/*.ipynb"),
        ),
        _signal(
            "data_pipeline_dag", "primary", "data_pipeline", 120, PathGlob("dags/*.py")
        ),
        _signal("ai_ml_model", "primary", "ai_ml", 120, PathGlob("models/*.onnx")),
        _signal(
            "mobile_android_manifest",
            "primary",
            "mobile_application",
            120,
            ExactPath("android/app/src/main/AndroidManifest.xml"),
        ),
        _signal(
            "desktop_electron",
            "primary",
            "desktop_application",
            120,
            NamedManifestKeyValue(
                "package.json", ("devDependencies", "electron"), present=True
            ),
        ),
        _signal(
            "embedded_platformio",
            "primary",
            "embedded_firmware",
            120,
            ExactPath("platformio.ini"),
        ),
        _signal(
            "embedded_c_sources",
            "primary",
            "embedded_firmware",
            30,
            LanguageCount("c", 5),
        ),
        _signal(
            "infrastructure_terraform",
            "primary",
            "infrastructure",
            100,
            PathGlob("*.tf"),
        ),
        _signal(
            "developer_tool_pre_commit",
            "primary",
            "developer_tool",
            120,
            ExactPath(".pre-commit-hooks.yaml"),
        ),
        _signal(
            "plugin_manifest",
            "primary",
            "plugin_extension",
            120,
            ExactPath("plugin.json"),
        ),
        _signal("game_godot", "primary", "game", 120, ExactPath("project.godot")),
        _signal(
            "documentation_mkdocs",
            "primary",
            "documentation_content",
            120,
            ExactPath("mkdocs.yml"),
        ),
        _signal(
            "documentation_markdown_ratio",
            "primary",
            "documentation_content",
            100,
            LanguageRatio("markdown", 4, 5, 5),
        ),
        _signal(
            "topology_monorepo",
            "topology",
            "monorepo",
            120,
            PathGlob("packages/*/package.json", min_count=2),
        ),
        _signal(
            "facet_saas",
            "facet",
            "saas",
            40,
            NamedManifestKeyValue(
                "package.json", ("repoDive", "facets"), contains="saas"
            ),
        ),
        _signal(
            "facet_multi_tenancy",
            "facet",
            "multi_tenancy",
            40,
            NamedManifestKeyValue(
                "package.json", ("repoDive", "facets"), contains="multi_tenancy"
            ),
        ),
        _signal("facet_ui", "facet", "ui", 40, PathGlob("src/ui/*")),
        _signal("facet_api", "facet", "api", 40, ExactPath("openapi.yaml")),
        _signal("facet_database", "facet", "database", 40, PathGlob("migrations/*")),
        _signal("facet_messaging", "facet", "messaging", 40, PathGlob("config/kafka*")),
        _signal(
            "facet_infrastructure", "facet", "infrastructure", 40, PathGlob("*.tf")
        ),
        _signal(
            "facet_model",
            "facet",
            "model_training_inference",
            40,
            PathGlob("models/*.onnx"),
        ),
        _signal(
            "topology_microservices",
            "topology",
            "microservices",
            120,
            PathGlob("services/*/service.yaml", min_count=2),
        ),
    ),
)
