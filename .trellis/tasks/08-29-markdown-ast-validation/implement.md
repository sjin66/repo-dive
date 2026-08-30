# Implementation

1. Add parser-profile and token-normalization tests, then the pinned dependency.
2. Add red tests for all node/ordering/cardinality/slot/content constraints.
3. Implement one pure validator and stable bounded diagnostic projection.
4. Add adversarial, disclosure-safety, source-location, and complexity fixtures.
5. Run focused tests, package smoke, `make check`, and `make test-all`.

Risky areas: parser token normalization, line maps, complexity bounds, and disclosure.
Review adversarial fixtures before the state child starts. Rollback removes the core
dependency only while no persisted Schema `2.0` state references its profile.
