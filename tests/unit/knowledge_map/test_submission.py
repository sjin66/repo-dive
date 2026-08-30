from __future__ import annotations

import json
from typing import cast

import pytest

from repo_dive.errors import InvocationError
from repo_dive.knowledge_map.submission import decode_enrichment_submission


def _payload() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "scope_id": "flow:one",
        "expected_artifact_revision": 4,
        "records": [
            {
                "id": "flow-explanation:one",
                "kind": "flow_explanation",
                "claims": [
                    {
                        "kind": "flow_explanation",
                        "text": "The entrypoint invokes the service.",
                        "fact_node_ids": ["symbol:one"],
                        "related_node_ids": [],
                        "evidence_ids": ["evidence:one"],
                    }
                ],
            }
        ],
    }


def test_submission_strictly_decodes_claim_owned_references() -> None:
    submission = decode_enrichment_submission(json.dumps(_payload()).encode("utf-8"))

    assert submission.scope_id == "flow:one"
    assert submission.records[0].claims[0].evidence_ids == ("evidence:one",)
    assert submission.raw_input_bytes > 0


@pytest.mark.parametrize(
    "payload",
    [
        b"\xff",
        b'{"schema_version":"1.0","schema_version":"1.0"}',
        b'{"schema_version":"1.0","scope_id":"x","expected_artifact_revision":1,"records":[],"fact_edges":[]}',
    ],
)
def test_submission_rejects_encoding_duplicates_unknown_fields_and_empty_records(
    payload: bytes,
) -> None:
    with pytest.raises(InvocationError) as exc_info:
        decode_enrichment_submission(payload)

    assert exc_info.value.code == "knowledge_map_enrichment_invalid"


def test_submission_rejects_record_level_citations() -> None:
    payload = _payload()
    records = cast(list[object], payload["records"])
    record = cast(dict[str, object], records[0])
    record["evidence_ids"] = ["evidence:one"]

    with pytest.raises(InvocationError):
        decode_enrichment_submission(json.dumps(payload).encode("utf-8"))
