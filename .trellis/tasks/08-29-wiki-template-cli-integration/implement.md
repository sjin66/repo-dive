# Implementation

1. Add red CLI contract tests for classify/init/validate and error-envelope exit status.
2. Implement thin command adapters and additive evidence/status/build projections.
3. Implement exact total/sub-budget accounting and deprecated absent-state-only strict
   `wiki structure` compatibility behavior.
4. Add exact persisted/external validation, structure-field matching, guidance-first
   accounting, pre-mutation failure, and Schema activation regressions.
5. Activate Schema `2.0` for the complete Wiki command family in one change.
6. Add complete workflow, I/O bound, JSON isolation, package, and evaluation tests.
7. Update English/Chinese docs, AGENTS/help, then run fresh full verification.

Risky files: Wiki command adapters, global CLI error behavior, package metadata/smoke,
and matched documentation. Final review must compare executable help and JSON examples.
Rollback removes additive adapters only; persisted Schema `2.0` remains untouched.
