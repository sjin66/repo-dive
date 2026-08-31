"""Strict untrusted-input decoder for claim-level map enrichment."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import cast

from repo_dive.errors import InvocationError
from repo_dive.knowledge_map.models import EnrichmentRecord, SemanticClaim

ENRICHMENT_READER_CEILING = 10_000_000
_TOP_FIELDS = {"schema_version", "scope_id", "expected_artifact_revision", "records"}
_RECORD_FIELDS = {"id", "kind", "claims"}
_CLAIM_FIELDS = {
    "kind",
    "text",
    "fact_node_ids",
    "related_node_ids",
    "evidence_ids",
}


@dataclass(frozen=True, slots=True)
class EnrichmentSubmission:
    schema_version: str
    scope_id: str
    expected_artifact_revision: int
    records: tuple[EnrichmentRecord, ...]
    raw_input_bytes: int


def decode_enrichment_submission(payload: bytes) -> EnrichmentSubmission:
    """Decode exactly one UTF-8 JSON object; all failures share one safe code."""
    try:
        if type(payload) is not bytes or len(payload) > ENRICHMENT_READER_CEILING:
            raise ValueError("input exceeds reader ceiling")
        document = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
        value = _object(document, _TOP_FIELDS, "submission")
        if value["schema_version"] != "1.0":
            raise ValueError("unsupported schema version")
        scope_id = _trimmed(value["scope_id"], "scope ID")
        revision = value["expected_artifact_revision"]
        if type(revision) is not int or revision < 1:
            raise ValueError("expected artifact revision must be positive")
        records_value = value["records"]
        if type(records_value) is not list or not records_value:
            raise ValueError("records must be a non-empty array")
        records: list[EnrichmentRecord] = []
        for record_document in records_value:
            record_value = _object(record_document, _RECORD_FIELDS, "record")
            record_id = _trimmed(record_value["id"], "record ID")
            claims_value = record_value["claims"]
            if type(claims_value) is not list:
                raise ValueError("claims must be an array")
            claims: list[SemanticClaim] = []
            for claim_document in claims_value:
                claim_value = _object(claim_document, _CLAIM_FIELDS, "claim")
                claims.append(
                    SemanticClaim(
                        kind=cast(str, claim_value["kind"]),
                        text=_trimmed(claim_value["text"], "claim text"),
                        fact_node_ids=_string_array(
                            claim_value["fact_node_ids"], "fact node IDs", nonempty=True
                        ),
                        related_node_ids=_string_array(
                            claim_value["related_node_ids"], "related node IDs"
                        ),
                        evidence_ids=_string_array(
                            claim_value["evidence_ids"], "Evidence IDs", nonempty=True
                        ),
                    )
                )
            records.append(
                EnrichmentRecord(
                    id=record_id,
                    kind=cast(str, record_value["kind"]),
                    claims=tuple(claims),
                )
            )
        if len({item.id for item in records}) != len(records):
            raise ValueError("record IDs must be unique")
        return EnrichmentSubmission(
            "1.0", scope_id, revision, tuple(records), len(payload)
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
        TypeError,
        KeyError,
    ) as error:
        raise InvocationError(
            "knowledge_map_enrichment_invalid",
            "Knowledge Map enrichment input is invalid.",
            details={
                "recovery_action": "correct_submission",
                "retry_mode": "after_recovery",
            },
        ) from error


def _object(value: object, fields: set[str], name: str) -> dict[str, object]:
    if type(value) is not dict or set(value) != fields:
        raise ValueError(f"{name} fields are invalid")
    return cast(dict[str, object], value)


def _trimmed(value: object, name: str) -> str:
    if type(value) is not str or not value or value.strip() != value:
        raise ValueError(f"{name} must be non-empty trimmed text")
    return value


def _string_array(
    value: object, name: str, *, nonempty: bool = False
) -> tuple[str, ...]:
    if type(value) is not list:
        raise ValueError(f"{name} must be an array")
    result = tuple(_trimmed(item, name) for item in value)
    if (nonempty and not result) or len(result) != len(set(result)):
        raise ValueError(f"{name} must be unique and satisfy cardinality")
    return result


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant: {value}")


__all__ = [
    "ENRICHMENT_READER_CEILING",
    "EnrichmentSubmission",
    "decode_enrichment_submission",
]
