# Relationship Provenance Index Schema

## Goal

Upgrade parser and index facts so every relationship syntax occurrence has a deterministic identity and exact source Evidence, while existing graph traversal and structural retrieval continue to operate on unique reachability rather than duplicated occurrences.

## Parent Requirements

- Owns KM-R1 and the source-fact prerequisite of KM-R2.
- Satisfies KM-AC1 and the relationship portion of KM-AC3/KM-AC11.
- Has no dependency on another child.
- Must complete before `08-30-deterministic-knowledge-map` starts implementation.

## Requirements

### RP-R1 Occurrence Identity

- One parser syntax occurrence equals one `Relationship`, even when source, target, kind, and line are repeated.
- The immutable value contains deterministic ID, endpoints, kind, confidence, provenance, POSIX path, one-based inclusive range, and an occurrence discriminator.
- IDs are stable for repeated parsing of identical bytes and distinguish same-line duplicate calls.

### RP-R2 Exact Parser Evidence

- Python `contains`, `imports`, `calls`, and `inherits` use the exact syntax occurrence range.
- Tree-sitter `contains` uses the exact child declaration range.
- Parser normalization deduplicates only identical occurrence IDs and preserves stable source ordering.
- No enclosing-definition or inferred fallback may be labeled exact.

### RP-R3 Persistence And Compatibility

- SQLite persists relationship ID and every occurrence field and validates the owning file path.
- Parser and SQLite Schema versions increment together; build parameters/manifest identity force supported rebuild behavior.
- Old indexes are rejected by ordinary consumers and rebuilt by the existing index command; no in-place migration is added.

### RP-R4 Consumer Semantics

- Graph traversal exposes one adjacency per `(source_id, target_id, kind)` and does not expand repeated occurrences.
- Structural retrieval preserves current path scoring, result order, and tie-breaking for existing fixtures.
- Aggregate/occurrence APIs retain all occurrence IDs for future Knowledge Map use, subject to caller limits.
- Public retrieval provenance remains compatible even if the internal model field is renamed from `source` to `provenance`.

## Acceptance Criteria

- **RP-AC1:** Two same-line calls from one symbol to one target produce two stable relationship IDs and two persisted rows with exact ranges/discriminators.
- **RP-AC2:** Repeated Python and Tree-sitter parsing produces byte-equivalent ordered relationship documents.
- **RP-AC3:** SQLite round-trip preserves all occurrence fields, rejects path mismatch/duplicate ID corruption, and passes foreign-key/integrity checks.
- **RP-AC4:** Graph traversal returns one reachable adjacency for repeated occurrences while an occurrence query returns both IDs.
- **RP-AC5:** Existing structural retrieval scores, explanations, and result order remain unchanged on pinned fixtures.
- **RP-AC6:** Schema-old indexes follow existing rejection/rebuild behavior and a failed rebuild preserves the previous valid generation.
- **RP-AC7:** Focused parser/index/graph/retrieval/integration tests and `make check` pass.

## Out Of Scope

- Knowledge Map models, artifact, lock, commands, lifting, analysis, flows, or Agent semantics.
- New JS/TS import/call/inheritance extraction.
- Cross-file reference resolution.
- Structural retrieval ranking improvements.
- In-place SQLite migration or dual-schema compatibility.

## Open Questions

None.
