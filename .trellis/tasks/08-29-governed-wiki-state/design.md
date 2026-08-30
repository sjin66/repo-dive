# Design

Extend immutable Wiki models and strict decoders to Schema `2.0`, persisting complete
governance identity in metadata and normalized composed/page contract snapshots in
Wiki state. Add initialization and identity-aware merge logic to `WikiService`.
Mutations and builds hold a bounded repository-local exclusive OS file lock across
read, validation, and publication. Compose and validate complete documents in memory
before existing atomic file replacements; partial pairs remain detectable and only
successful final validation may replace `wiki.md`. Rollback never rewrites Schema
`2.0`; it preserves the last built Markdown for older binaries.

Schema `2.0` models/services remain behind new typed internal entry points in this
child. Existing Schema `1.0` CLI dispatch and persisted decoders are not switched or
removed here, so the repository remains usable if the final integration child is
deferred. The final child performs the one public activation after all adapters exist.
