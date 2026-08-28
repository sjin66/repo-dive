# ADR-002: Store explicit float32 embeddings and use brute-force cosine

## Status

Accepted

## Date

2026-08-28

## Context

Semantic retrieval is an optional third evidence channel. The offline baseline
must remain usable without an embedding runtime, network access, or a native
vector database. Persisted embeddings also become invalid when their provider,
model, dimensions, or source Chunk content changes.

The first implementation needs reproducible results and a small dependency
surface more than approximate-nearest-neighbor throughput. Query result size
must be bounded, and equal scores must not inherit database or iteration order.

## Decision

Index Schema 4 stores one vector per Chunk in SQLite. Every row records the
provider, model, dimensions, Chunk content hash, and a fixed-length
little-endian float32 BLOB. The Store validates finite float32 values, a single
embedding identity, current Chunk hashes, and duplicate Chunk IDs before
atomically replacing the vector table. Reading requires the caller to provide
the exact same embedding identity.

Vector retrieval performs an exact brute-force cosine scan using the Python
standard library. Query and stored values are evaluated at persisted float32
precision. Results are ordered by descending cosine score, then ascending
Chunk ID, and truncated to `max_results`. An empty vector table returns no
vector hits and does not alter BM25, structural retrieval, or indexed Chunks.

## Alternatives Considered

### Add FAISS or another ANN index immediately

Rejected because it adds a native dependency, platform-specific packaging,
and approximate ordering before repository-scale measurements demonstrate a
need. Exact scanning is the correctness baseline future ANN implementations
must match within a documented recall tolerance.

### Store JSON arrays or Python float64 values

Rejected because the representation is larger and less explicit. Fixed-size
float32 BLOBs make dimensions enforceable in SQLite and match common embedding
provider output.

### Store model identity only in the index Manifest

Rejected because row-level identity and Chunk hashes let the Store detect mixed
or stale records at the persistence boundary. The Manifest may additionally
summarize the configured provider when vector indexing is integrated.

## Consequences

- Default installation and empty-vector operation remain dependency-free and
  offline.
- Scores and tie ordering are reproducible across input and SQLite row order.
- Changing provider, model, dimensions, or Chunk content requires replacement
  or re-embedding before the record is accepted.
- Exact retrieval is linear in the number of stored vectors. ANN remains a
  future, measurement-driven replacement behind the same typed boundary.
