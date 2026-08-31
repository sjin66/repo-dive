# Knowledge Map Review Corrections Implementation Plan

## Parent Role

The parent owns planning, task ordering, cross-child acceptance, and final release
review only. It must not contain direct product implementation.

## Child Order

1. `08-31-map-edge-budget-closure`
2. `08-31-map-flow-omission-accounting`
3. `08-31-map-evidence-planning-corrections`

The first child establishes algorithm version `2`. The Flow and Evidence corrections
are source-independent after planning but must validate against the algorithm-2
integrated snapshot before archival.

## P1: Review Child Plans

- Verify each child has converged PRD/design/implement artifacts and curated manifests.
- Confirm exact file ownership and no second Store/writer/lock.
- Confirm the unavailable-Evidence code and recovery action match across parent,
  Evidence child, tests, specs, and paired docs.
- Confirm no child edits Wiki product code or historical `docs/superpowers` files.

## P2: Child Execution Gates

- Start, implement, independently check, commit, and archive one child at a time.
- Require red-green behavior tests before implementation changes.
- Re-run adjacent high-budget, lifecycle, process-error, security, recovery, and
  performance suites for every child.
- A newly exposed public-contract mismatch returns the owning child to planning.

## P3: Integrated Acceptance

- Map KMC-AC1 through KMC-AC7 to concrete test and commit evidence.
- Verify algorithm-1 artifacts fail closed and algorithm-2 rebuild succeeds.
- Verify constrained build, Flow coverage, Evidence collection, validate, reset, and
  rebuild workflows end to end.
- Verify `knowledge_map_evidence_unavailable` precedence before supplemental retrieval
  and capacity/token checks, while preserving map/source/scope and stale-existing-
  snapshot precedence and no-write behavior.

## P4: Exact Release Snapshot

Run from the exact allowlisted clean Python 3.11+ snapshot:

```bash
make setup PYTHON=/path/to/python3.11+
make check
make test-unit
make test-all
.venv/bin/python -m ruff format --check --no-respect-gitignore .
.venv/bin/python -m ruff check --no-respect-gitignore .
git diff --cached --check
```

Smoke-test root, `map`, and all six subcommand help documents. Confirm `.codegraph/`,
ignored Host integrations, Wiki product code, and `docs/superpowers` are absent from the
staged allowlist.

## Completion Gate

- All three children are independently reviewed and archived.
- KMC-AC1 through KMC-AC7 pass with direct evidence.
- A fresh full-scope review reports no unresolved correctness, performance, budget,
  provenance, concurrency, security, compatibility, or documentation finding.
- The parent may then record evidence and archive without product-code commits.
