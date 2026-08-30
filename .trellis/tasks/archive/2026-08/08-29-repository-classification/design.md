# Design

Implement immutable classification models, a versioned rule registry, bounded matcher
adapters over `PublishedIndex`, and one pure scoring/selection service in a dedicated
domain package. Registry order controls output presentation only; score ties fall back
to `general_mixed`. Ratios use integer arithmetic, paths are repository-relative POSIX,
and timestamps are excluded from identity. Public projection follows the parent
`research/classification-contract.md` Schema `1.0` candidate.

Detected and effective primary values are separate fields so overrides do not erase
automatic evidence. The package does not import Wiki or CLI rendering modules.
Malformed bounded manifests contribute stable observations but no positive signal.
Rollback is additive: removing the package before CLI integration leaves existing
commands and artifacts unchanged.
