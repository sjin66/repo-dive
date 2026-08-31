# Database Guidelines

> Executable SQLite persistence contracts for repository indexes.

---

## Scenario: Relationship Occurrence Persistence

### 1. Scope / Trigger

- Apply this contract when parser relationships, relationship queries, or the
  SQLite index schema change.
- A parser model change, `schema.sql`, `INDEX_SCHEMA_VERSION`, and
  `PARSER_VERSION` form one compatibility unit.
- Schema changes use full index rebuilds. Do not add in-place migrations or
  dual-schema reads unless a separate requirement explicitly introduces them.

### 2. Signatures

```python
create_relationship(
    *,
    source_id: str,
    target_id: str,
    kind: str,
    confidence: float,
    provenance: str,
    path: str,
    start_line: int,
    end_line: int,
    occurrence_discriminator: tuple[int, int, int],
) -> Relationship

IndexStore.replace_document(source: SourceFile, parsed: ParseResult) -> None

IndexStore.query_relationships(
    symbol_ids: tuple[str, ...],
    *,
    direction: Literal["outgoing", "incoming", "both"],
    edge_kinds: tuple[str, ...] | None,
    limit: int,
    min_confidence: float = 0.0,
) -> tuple[Relationship, ...]

IndexStore.query_relationship_occurrences(
    symbol_ids: tuple[str, ...],
    *,
    direction: Literal["outgoing", "incoming", "both"],
    edge_kinds: tuple[str, ...] | None,
    limit: int,
    min_confidence: float = 0.0,
) -> tuple[Relationship, ...]
```

The Schema 5 `relationships` row contains `id`, owner `file_path`, file-local
`ordinal`, endpoint IDs, `kind`, `confidence`, `provenance`, exact POSIX `path`,
one-based inclusive lines, zero-based columns, and `occurrence_ordinal`.

The scope-directed complete-Chunk read boundary is:

```python
IndexStore.get_chunks_by_paths(paths: tuple[str, ...]) -> tuple[Chunk, ...]
```

### 3. Contracts

- One syntax occurrence produces one content-addressed relationship ID.
- The discriminator is `(start_column, end_column, occurrence_ordinal)`; the
  ordinal increments only among otherwise-identical relationships.
- `replace_document` writes the file, symbols, chunks, and relationships in one
  transaction. Relationship `path` must equal the owning file path.
- `query_relationship_occurrences` returns every matching occurrence in stable
  source order and always requires a positive `limit`.
- `query_relationships` returns one representative per
  `(source_id, target_id, kind)`. The representative is highest confidence,
  followed by deterministic provenance, location, discriminator, and ID order.
- Graph traversal budgets count unique adjacencies, not occurrence rows.
- `get_chunks_by_paths` accepts at most 256 unique normalized repository-relative POSIX
  paths, rejects invalid, duplicate, or oversized nonempty input before SQL, returns
  `()` for empty input, and returns complete Chunks in `(file_path, ordinal)` order.
  Callers batch larger scope-directed reads rather than widening the SQL parameter
  bound or reconstructing unrelated `ParseResult` values.

### 4. Validation & Error Matrix

| Condition | Required behavior |
|---|---|
| Empty endpoint, kind, or provenance | `ValueError` before persistence |
| Confidence outside `[0.0, 1.0]` | `ValueError` before persistence |
| Absolute, backslash, non-normalized, or parent-traversing path | `ValueError` before persistence |
| Invalid one-based inclusive line range | `ValueError` before persistence |
| Discriminator is not exactly three non-negative integers | `ValueError` before persistence |
| Relationship path differs from owner file | Reject the document before opening the write transaction |
| Duplicate relationship ID or broken foreign key | `InternalOperationError("index_integrity_error", ...)` |
| Invalid direction, non-positive limit, or invalid confidence threshold | `ValueError` from the query boundary |
| Invalid, duplicate, or more than 256 Chunk lookup paths | `ValueError` before SQL; empty input returns `()` |
| Index schema/parser identity is old | Existing compatibility logic rejects or rebuilds the generation; no migration |

### 5. Good/Base/Bad Cases

- Good: two same-line calls with the same endpoints persist as two rows with
  stable, distinct IDs and remain one graph adjacency.
- Base: one occurrence round-trips with identical provenance, exact range, and
  discriminator.
- Bad: deduplicating by endpoints before persistence loses Evidence and violates
  the occurrence contract.
- Bad: applying `LIMIT` to raw occurrence rows before adjacency grouping lets
  duplicates consume traversal capacity.

### 6. Tests Required

- Parser/model unit tests assert repeated-byte stability, same-line duplicate
  distinction, exact ranges, strict tuple validation, and ID-only normalization.
- Store tests assert round-trip equality, path mismatch rejection, duplicate-ID
  integrity errors, stable bounded occurrence reads, and unique adjacency reads.
- Graph tests assert node and edge budgets count unique adjacencies.
- Structural retrieval tests pin complete score, result order, tie-breaking, and
  explanation output when duplicate occurrences exist.
- Integration tests assert old schema/parser identities rebuild and failed
  rebuilds do not publish a partial generation.
- Store tests assert complete-Chunk path batches are bounded, path-confined, stably
  ordered, empty-input safe, and equivalent across fixed-size batches.

### 7. Wrong vs Correct

#### Wrong

```python
# Collapses distinct syntax Evidence before it reaches SQLite.
relationships[(item.source_id, item.target_id, item.kind)] = item
```

#### Correct

```python
# Persist occurrences by identity; collapse only at the traversal read boundary.
relationships[item.id] = item
```
