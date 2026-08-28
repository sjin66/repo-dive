# ADR-001: Publish index artifacts as atomic generations

## Status

Accepted

## Date

2026-08-28

## Context

One repository index consists of three artifacts: SQLite data, a versioned
Manifest, and public metadata. Publishing those files independently creates a
failure window where readers can observe files from different builds. A failed
incremental build must also leave the previous index fully usable.

The documented read path remains `.repo-dive/index/`, so callers should not
need to know an internal generation identifier.

## Decision

Build and validate every artifact in a new directory under
`.repo-dive/index-generations/`. After SQLite integrity checks and Manifest
round-trip validation pass, create a relative symlink for that generation and
atomically replace `.repo-dive/index` with the new symlink.

Never modify the currently published generation. Unchanged files may reuse
their typed parse records while the next generation is assembled, but BM25 is
rebuilt over the complete new Chunk corpus before publication.

Reject pointers or parent directories that resolve outside the selected
repository. If the host cannot create directory symlinks, publication fails
without replacing the current generation; it does not fall back to a
multi-file in-place update.

## Alternatives Considered

### Replace the three stable files independently

Rejected because a failure after replacing one file can destroy the last
internally consistent index.

### Rename the old directory away, then rename the new directory into place

Rejected because ordinary portable directory rename does not atomically
exchange two populated directories. Readers can observe a missing index, and a
process crash requires additional recovery state.

### Publish a separate pointer JSON file

Technically sound, but rejected because it changes the documented stable path
and requires every consumer to implement pointer resolution. A directory
symlink preserves the existing path for SQLite and JSON consumers.

## Consequences

- Readers observe one complete generation through a stable path.
- Parse, write, validation, or publication failures retain the old generation.
- Previous generations remain available for recovery and require a later
  bounded cleanup policy.
- Publication depends on directory symlink support. Cross-platform release
  testing must verify this explicitly and document unsupported environments.
