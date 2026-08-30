# Implementation

1. Add red tests for models, registry validation, signal matching, scoring, fallback,
   overlays, overrides, ordering, and safe output.
2. Implement the smallest typed classifier and read-only index adapter.
3. Add representative repository fixtures and integration coverage.
4. Run focused tests, `make check`, and `make test-all`; review taxonomy gaps before
   exposing the service to CLI integration.

Risky areas: manifest parsers, rule precedence, and stable ordering. Do not advance to
the template child until all taxonomy IDs and serialized fields pass review. Rollback
removes the still-unreferenced classifier package and fixtures.
