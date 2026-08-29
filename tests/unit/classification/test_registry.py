from __future__ import annotations

from collections.abc import Callable

import pytest

from repo_dive.classification.models import Taxon
from repo_dive.classification.registry import (
    ExactPath,
    LanguageCount,
    LanguageRatio,
    NamedManifestKeyValue,
    PathGlob,
    RuleRegistry,
    SignalRule,
)


def test_registry_rejects_duplicate_signal_ids_and_unknown_targets() -> None:
    taxon = Taxon("general_mixed", threshold=0)
    primaries = (Taxon("example", threshold=100), taxon)
    rule = SignalRule("same", "primary", "general_mixed", 10, ExactPath("x"))
    with pytest.raises(ValueError, match="signal ids"):
        RuleRegistry(primaries, (Taxon("single_project", 0),), (), (rule, rule))

    unknown = SignalRule("unknown", "facet", "missing", 10, ExactPath("x"))
    with pytest.raises(ValueError, match="target"):
        RuleRegistry(primaries, (Taxon("single_project", 0),), (), (unknown,))

    with pytest.raises(ValueError, match="signal id"):
        SignalRule("not.valid", "primary", "general_mixed", 10, ExactPath("x"))

    with pytest.raises(ValueError, match="fallback"):
        RuleRegistry((Taxon("example", 100),), (Taxon("single_project", 0),), (), ())


@pytest.mark.parametrize(
    "factory",
    [
        lambda: ExactPath("../pyproject.toml"),
        lambda: ExactPath("src\\package.json"),
        lambda: PathGlob("/services/*/service.yaml"),
        lambda: NamedManifestKeyValue("../package.json", ("private",), equals=True),
        lambda: NamedManifestKeyValue("package.json", ("",), equals=True),
    ],
)
def test_registry_rejects_paths_outside_repository_and_empty_manifest_keys(
    factory: Callable[[], object],
) -> None:
    with pytest.raises(ValueError):
        factory()


@pytest.mark.parametrize(
    "matcher",
    [
        ExactPath("pyproject.toml"),
        PathGlob("services/*/service.yaml", min_count=2),
        LanguageCount("python", minimum=2),
        LanguageRatio("markdown", numerator=4, denominator=5, minimum_files=5),
        NamedManifestKeyValue("package.json", ("private",), equals=True),
        NamedManifestKeyValue("package.json", ("license",), equals=None),
    ],
)
def test_registry_accepts_every_bounded_matcher_kind(matcher: object) -> None:
    primary = (Taxon("example", threshold=100), Taxon("general_mixed", threshold=0))
    topology = (Taxon("single_project", threshold=0),)
    rule = SignalRule("bounded", "primary", "general_mixed", 10, matcher)  # type: ignore[arg-type]

    assert RuleRegistry(primary, topology, (), (rule,)).signals == (rule,)
