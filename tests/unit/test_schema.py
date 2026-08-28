import json

import pytest

from repo_dive.schema import (
    ErrorBody,
    ErrorEnvelope,
    JsonObject,
    ResultEnvelope,
    serialize_json_document,
)


def test_result_envelope_serializes_one_versioned_document() -> None:
    result: JsonObject = {"items": [], "truncated": False}
    envelope: ResultEnvelope[JsonObject] = ResultEnvelope(
        command="context",
        repository="/tmp/example",
        result=result,
        warnings=("index reused",),
    )

    document = envelope.to_document()

    assert document == {
        "schema_version": "1.0",
        "command": "context",
        "repository": "/tmp/example",
        "result": {"items": [], "truncated": False},
        "warnings": ["index reused"],
    }


def test_error_envelope_omits_unknown_repository_and_details() -> None:
    envelope = ErrorEnvelope(
        command="index",
        error=ErrorBody(
            code="repository_not_found",
            message="Repository path does not exist.",
        ),
    )

    assert envelope.to_document() == {
        "schema_version": "1.0",
        "command": "index",
        "error": {
            "code": "repository_not_found",
            "message": "Repository path does not exist.",
        },
    }


def test_json_document_is_stable_utf8_and_has_one_trailing_newline() -> None:
    first = serialize_json_document({"message": "仓库", "count": 1})
    second = serialize_json_document({"count": 1, "message": "仓库"})

    assert first == second
    assert first.endswith("\n")
    assert not first.endswith("\n\n")
    assert json.loads(first) == {"count": 1, "message": "仓库"}
    assert "仓库" in first


def test_json_serialization_fails_before_returning_partial_output() -> None:
    with pytest.raises(TypeError):
        serialize_json_document({"unsupported": object()})


def test_json_serialization_rejects_non_finite_numbers() -> None:
    with pytest.raises(ValueError):
        serialize_json_document({"score": float("nan")})
