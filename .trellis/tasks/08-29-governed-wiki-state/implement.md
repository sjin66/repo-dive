# Implementation

1. Add Schema `2.0` round-trip/strictness and Schema `1.0` preservation tests.
2. Implement governed initialization, page identity, and no-op semantics.
3. Integrate page/state/final validation and localized assembly.
4. Implement and test every invalidation/recovery/concurrency edge in the parent matrix.
5. Prove existing Schema `1.0` CLI tests remain unchanged and no public handler reaches
   Schema `2.0` before final integration.
6. Run Wiki/recovery integration tests, `make check`, and `make test-all`.

Risky files: Wiki models/store/service/assembler and the new lock adapter. Review
legacy bytes, lock timeout/crash release, concurrent page updates, invalidation, and
partial pair recovery before CLI exposure. Rollback preserves Schema `2.0` bytes and
the last valid Markdown; it never attempts a downgrade.
