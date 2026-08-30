# Relationship Provenance Index Schema Design

## Boundary

`parsing` owns occurrence creation; `indexing` owns persistence; `indexing.graph` owns unique adjacency; `retrieval.structural` consumes adjacency without rank changes. No Knowledge Map package imports are introduced.

## Relationship Model

```text
Relationship(
  id,
  source_id,
  target_id,
  kind,
  confidence,
  provenance,
  path,
  start_line,
  end_line,
  occurrence_discriminator,
)
```

The stable ID is a length-prefixed hash of all fields except `id`. The occurrence discriminator is derived from parser-reported byte/column span plus a zero-based ordinal only among otherwise identical occurrences. Identical source bytes produce the same discriminator; database insertion order is never used.

Exact ranges:

- Python `contains`: complete child declaration node.
- Python `imports`: individual alias occurrence where AST position permits; stable alias ordinal supplements shared statement ranges.
- Python `calls`: complete call expression.
- Python `inherits`: individual base expression.
- Tree-sitter `contains`: complete child declaration node.

The model validates confidence, POSIX path, ordered one-based lines, non-empty provenance/kind/IDs, and non-negative discriminator components.

## Normalization

`ParseResult` may contain multiple endpoint-equivalent relationships. Pipeline deduplication key is relationship ID only. Sort key is path, start/end line, occurrence discriminator, source ID, target ID, kind, provenance, ID.

## SQLite Contract

Schema 5 replaces the old composite relationship primary key with relationship `id`. Columns include owner `file_path`, ordinal, endpoints, kind, confidence, provenance, path, range, and discriminator. Foreign keys still target symbols. Store validation requires relationship path to equal the replaced document path.

No migration is attempted. `INDEX_SCHEMA_VERSION` and `PARSER_VERSION` increment, and exact `BuildParameters` compatibility causes old generations to rebuild through the existing index service.

## Reader Contracts

Two distinct reads are supported:

- Occurrence read: returns every relationship in stable occurrence order under an explicit limit.
- Adjacency read: groups by `(source_id, target_id, kind)` for traversal. The representative uses highest confidence, then provenance/path/range/discriminator/ID stable order.

Traversal node/edge budgets count unique adjacencies, not occurrence rows. This preserves graph expansion behavior.

Structural retrieval continues to receive one adjacency per endpoint/kind and uses the existing confidence/path-length formula. Tests pin complete score/order/explanation output before and after the Schema change. If provenance output field names are public, serialization preserves the existing field contract while internal naming becomes explicit.

## Compatibility And Rollback

Parser model, schema SQL, store, parser version, and index schema version are one compatibility unit. Rollback reverts all together. Existing published old generations remain untouched until a successful rebuild atomically publishes a new generation. Build failure leaves the old generation available to the old code and never publishes a partial Schema 5 generation.

## Risks

- Same-line AST aliases may share line ranges: the parser-owned discriminator prevents identity collapse.
- Occurrence rows can increase storage: indexes already bound files; future consumers must use explicit limits.
- Grouping could change confidence: representative selection and structural retrieval regression fixtures pin behavior.
- Field rename can leak: graph/retrieval serialization tests protect observable compatibility.
