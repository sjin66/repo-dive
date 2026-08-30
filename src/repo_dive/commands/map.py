"""Public non-interactive `repo-dive map` command family."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import cast

from repo_dive.commands import Command, CommandOutput
from repo_dive.commands.retrieval_arguments import positive_token_budget, result_limit
from repo_dive.errors import (
    InternalOperationError,
    InvocationError,
    RepoDiveError,
    RepositoryError,
)
from repo_dive.knowledge_map.build import KnowledgeMapBuildService
from repo_dive.knowledge_map.enrichment_service import KnowledgeMapEnrichmentService
from repo_dive.knowledge_map.evidence_service import KnowledgeMapEvidenceService
from repo_dive.knowledge_map.models import MapBuildBudgets
from repo_dive.knowledge_map.store import MapStore
from repo_dive.knowledge_map.submission import ENRICHMENT_READER_CEILING
from repo_dive.knowledge_map.views import (
    project_architecture,
    project_flows,
    project_tour,
)
from repo_dive.schema import JsonObject
from repo_dive.storage.paths import resolve_repository, resolve_within_repository

MAX_BUDGET_INPUT_BYTES = 1_000_000


def configure(parser: argparse.ArgumentParser) -> None:
    """Configure the closed Knowledge Map command set."""
    subparsers = parser.add_subparsers(dest="map_command", required=True)

    build = subparsers.add_parser("build", help="build the deterministic Knowledge Map")
    build.add_argument("repository", help="local repository directory")
    build.add_argument(
        "--source-fact-budget", required=True, type=_positive_integer, metavar="COUNT"
    )
    build.add_argument(
        "--artifact-byte-budget",
        required=True,
        type=_positive_integer,
        metavar="BYTES",
    )
    build.add_argument(
        "--budget-file",
        required=True,
        metavar="PATH",
        help="repository-relative strict UTF-8 JSON budget file",
    )
    _add_format(build)
    build.set_defaults(_map_handler=_handle_build)

    show = subparsers.add_parser("show", help="show one bounded deterministic view")
    show.add_argument("repository", help="local repository directory")
    show.add_argument(
        "--view", required=True, choices=("architecture", "flows", "tour")
    )
    show.add_argument(
        "--max-results", required=True, type=result_limit, metavar="COUNT"
    )
    _add_format(show)
    show.set_defaults(_map_handler=_handle_show)

    evidence = subparsers.add_parser(
        "evidence", help="collect and persist Evidence for one map scope"
    )
    evidence.add_argument("repository", help="local repository directory")
    evidence.add_argument("--scope", required=True, type=_scope_id, metavar="SCOPE_ID")
    evidence.add_argument(
        "--token-budget",
        required=True,
        type=positive_token_budget,
        metavar="TOKENS",
    )
    _add_format(evidence)
    evidence.set_defaults(_map_handler=_handle_evidence)

    enrich = subparsers.add_parser(
        "enrich", help="validate and replace one scope's semantic claims"
    )
    enrich.add_argument("repository", help="local repository directory")
    enrich.add_argument(
        "--input",
        required=True,
        metavar="PATH|-",
        help="repository-relative UTF-8 JSON input, or - for stdin",
    )
    _add_format(enrich)
    enrich.set_defaults(_map_handler=_handle_enrich)

    reset = subparsers.add_parser(
        "reset", help="remove one scope's Evidence and enrichment"
    )
    reset.add_argument("repository", help="local repository directory")
    reset.add_argument("--scope", required=True, type=_scope_id, metavar="SCOPE_ID")
    _add_format(reset)
    reset.set_defaults(_map_handler=_handle_reset)

    validate = subparsers.add_parser(
        "validate", help="validate map structure and Evidence freshness"
    )
    validate.add_argument("repository", help="local repository directory")
    _add_format(validate)
    validate.set_defaults(_map_handler=_handle_validate)


def handle(args: argparse.Namespace) -> CommandOutput:
    """Dispatch one already parsed map operation."""
    handler = getattr(args, "_map_handler", None)
    if handler is None:
        raise InvocationError("invalid_invocation", "A map subcommand is required.")
    return cast(CommandOutput, handler(args))


def _handle_build(args: argparse.Namespace) -> CommandOutput:
    repository = resolve_repository(args.repository)
    document = _read_budget_document(repository, args.budget_file)
    try:
        budgets = MapBuildBudgets.from_budget_document(
            document,
            source_fact_budget=args.source_fact_budget,
            artifact_byte_budget=args.artifact_byte_budget,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise _invalid_budget() from error
    try:
        result = KnowledgeMapBuildService().build(repository, budgets=budgets)
    except RepoDiveError:
        raise
    except Exception as error:
        raise InternalOperationError(
            "knowledge_map_derivation_failed",
            "Knowledge Map derivation failed.",
            details={
                "recovery_action": "inspect_safe_diagnostic",
                "retry_mode": "after_cause_clears",
            },
        ) from error
    artifact = result.artifact
    output: JsonObject = {
        "artifact_revision": artifact.artifact_revision,
        "changed": result.changed,
        "content_hash": artifact.content_hash,
        "deterministic_revision": artifact.deterministic_revision,
        "discarded_enrichments": result.discarded_enrichments,
        "discarded_evidence_snapshots": result.discarded_evidence_snapshots,
        "enrichment_count": len(artifact.enrichments),
        "evidence_snapshot_count": len(artifact.evidence_snapshots),
        "semantic_revision": artifact.semantic_revision,
        "unchanged": not result.changed,
    }
    return _output("map build", repository, output)


def _handle_show(args: argparse.Namespace) -> CommandOutput:
    repository = resolve_repository(args.repository)
    # Load the index first to preserve the documented stale-index precedence.
    from repo_dive.indexing.service import load_published_index

    published = load_published_index(repository)
    artifact = MapStore(repository).read_artifact()
    _require_current_map(
        artifact.source.index_build_id,
        artifact.source.repository_fingerprint,
        published.manifest.build_id,
        published.manifest.repository_fingerprint,
    )
    projectors = {
        "architecture": project_architecture,
        "flows": project_flows,
        "tour": project_tour,
    }
    result = projectors[args.view](artifact, max_results=args.max_results)
    result["content_hash"] = artifact.content_hash
    result["view"] = args.view
    return _output("map show", repository, result)


def _handle_evidence(args: argparse.Namespace) -> CommandOutput:
    repository = resolve_repository(args.repository)
    result = KnowledgeMapEvidenceService().collect(
        repository, scope_id=args.scope, token_budget=args.token_budget
    )
    output: JsonObject = {
        "artifact_revision": result.artifact.artifact_revision,
        "changed": result.changed,
        "omitted_references": result.omitted_references,
        "scope_id": result.snapshot.scope_id,
        "snapshot": result.snapshot.to_document(),
        "sources": [
            {**source.reference.to_document(), "text": source.text}
            for source in result.sources
        ],
        "unchanged": not result.changed,
    }
    return _output("map evidence", repository, output)


def _handle_enrich(args: argparse.Namespace) -> CommandOutput:
    repository = resolve_repository(args.repository)
    payload = _read_enrichment_input(repository, args.input)
    result = KnowledgeMapEnrichmentService().enrich(repository, payload=payload)
    output: JsonObject = {
        "artifact_revision": result.artifact.artifact_revision,
        "changed": result.changed,
        "scope_id": result.scope_id,
        "semantic_revision": result.artifact.semantic_revision,
        "unchanged": not result.changed,
    }
    return _output("map enrich", repository, output)


def _handle_reset(args: argparse.Namespace) -> CommandOutput:
    repository = resolve_repository(args.repository)
    result = KnowledgeMapEnrichmentService().reset(repository, scope_id=args.scope)
    output: JsonObject = {
        "artifact_revision": result.artifact.artifact_revision,
        "changed": result.changed,
        "scope_id": result.scope_id,
        "semantic_revision": result.artifact.semantic_revision,
        "unchanged": not result.changed,
    }
    return _output("map reset", repository, output)


def _handle_validate(args: argparse.Namespace) -> CommandOutput:
    repository = resolve_repository(args.repository)
    result = KnowledgeMapEnrichmentService().validate(repository)
    output: JsonObject = {
        "artifact_revision": result.artifact_revision,
        "checked_claims": result.checked_claims,
        "checked_scopes": result.checked_scopes,
        "semantic_entailment_checked": result.semantic_entailment_checked,
        "valid": result.valid,
        "validation_scope": list(result.validation_scope),
    }
    return _output("map validate", repository, output)


def _read_budget_document(repository: Path, input_path: str) -> JsonObject:
    path = resolve_within_repository(repository, input_path, must_exist=True)
    try:
        with path.open("rb") as stream:
            payload = stream.read(MAX_BUDGET_INPUT_BYTES + 1)
        if len(payload) > MAX_BUDGET_INPUT_BYTES:
            raise _invalid_budget()
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
        if type(value) is not dict:
            raise ValueError("budget document must be an object")
        return cast(JsonObject, value)
    except InvocationError:
        raise
    except (UnicodeError, json.JSONDecodeError, ValueError, TypeError) as error:
        raise _invalid_budget() from error
    except OSError as error:
        raise _unavailable_input(input_path) from error


def _read_enrichment_input(repository: Path, input_path: str) -> bytes:
    if input_path == "-":
        stream = getattr(sys.stdin, "buffer", sys.stdin)
        raw = stream.read(ENRICHMENT_READER_CEILING + 1)
        return raw.encode("utf-8") if isinstance(raw, str) else raw
    path = resolve_within_repository(repository, input_path, must_exist=True)
    try:
        with path.open("rb") as stream:
            return stream.read(ENRICHMENT_READER_CEILING + 1)
    except OSError as error:
        raise _unavailable_input(input_path) from error


def _require_current_map(
    map_build_id: str,
    map_fingerprint: str,
    index_build_id: str,
    index_fingerprint: str,
) -> None:
    if (map_build_id, map_fingerprint) != (index_build_id, index_fingerprint):
        raise RepositoryError(
            "knowledge_map_stale",
            "Knowledge Map does not match the current published index.",
            details={"recovery_action": "rebuild_map", "retry_mode": "after_recovery"},
        )


def _output(command: str, repository: Path, result: JsonObject) -> CommandOutput:
    return CommandOutput(
        command=command, format="json", result=result, repository=str(repository)
    )


def _add_format(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--format",
        choices=("json",),
        default="json",
        help="result output format (default: json)",
    )


def _positive_integer(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("value must be a positive integer") from error
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def _scope_id(value: str) -> str:
    if not value or value.strip() != value:
        raise argparse.ArgumentTypeError("scope ID must be non-empty trimmed text")
    return value


def _invalid_budget() -> InvocationError:
    return InvocationError(
        "invalid_invocation",
        "Knowledge Map budget input is invalid.",
        details={
            "recovery_action": "correct_invocation",
            "retry_mode": "after_recovery",
        },
    )


def _unavailable_input(path: str) -> RepositoryError:
    return RepositoryError(
        "repository_path_unavailable",
        "Requested repository input is not available.",
        details={
            "path": path,
            "recovery_action": "wait_for_input",
            "retry_mode": "after_cause_clears",
        },
    )


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant: {value}")


MAP_COMMAND = Command(
    name="map",
    help="build, inspect, and optionally enrich the repository Knowledge Map",
    configure=configure,
    handler=handle,
)

__all__ = ["MAP_COMMAND", "MAX_BUDGET_INPUT_BYTES"]
