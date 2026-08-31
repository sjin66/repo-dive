# Knowledge Map Integration Corrections

## Goal

Resolve the blocking findings from the parent Knowledge Map P3/P4 review without
changing approved product scope, deterministic heuristics, semantic ownership, Wiki
ownership, or the six-command public surface.

## Dependencies

- All four original Knowledge Map children are completed and archived.
- The parent PRD/design, `.trellis/spec/backend/knowledge-map-contracts.md`, and the
  independent parent review findings are authoritative for this correction.
- This child returns to the parent for a fresh P3/P4 review; it does not archive the
  parent automatically.

## Requirements

### IC-R1 JSON Invocation Contract

- Every Map invocation failure, including unsupported `--format`, must emit exactly one
  Schema 1.0 error document to stdout, a safe diagnostic to stderr, no ANSI, and exit
  `2`.
- Preserve existing non-Map CLI behavior unless a shared parser correction is proven
  compatible by existing tests.
- Malformed enrichment payloads remain `knowledge_map_enrichment_invalid`, not generic
  `invalid_invocation`.

### IC-R2 Strict Scope Ownership

- `KnowledgeMapArtifact.create` and `from_document` must reject every enrichment
  `fact_node_id` and `related_node_id` outside its persisted scope contract, even when
  the document has internally consistent hashes.
- Rejection must occur in strict artifact validation as well as submission validation.
- Invalid artifacts remain unreadable and are never rewritten by read-only commands.

### IC-R3 Real Public Error Paths

- Every checked parent command/error applicability cell must execute the real Map
  command adapter and root CLI envelope; replacing `MAP_COMMAND.handler` with a direct
  raising stub is insufficient.
- Tests may inject failures at the owning service/store/filesystem boundary when an OS
  race or atomic failure cannot be produced portably, but must still exercise argument
  parsing, command dispatch, output serialization, and no-write checks.
- Each cell asserts stable code, exit, exactly one JSON document, stderr safety, no
  ANSI, exact closed `retry_mode`/`recovery_action`, precedence, and artifact bytes.

### IC-R4 Concurrency, Capacity, And Performance Evidence

- Add coordinated writer tests spanning build, Evidence, enrichment, and reset that
  prove one shared lock/CAS protocol, equivalence-before-CAS, no lost successful
  update, and last-valid preservation.
- Cover the portable Windows lock branch without requiring Windows CI.
- Add bounded-work tests for artifact serialization, flow/tour limits, Evidence
  reference capacity, and repeated semantic growth without fixed latency assertions.
- Do not add another writer, lock, store, cache, dependency, or algorithm.

### IC-R5 Documentation Parity

- Correct matched English/Chinese architecture and Wiki generation-flow constants to
  current executable index Schema `5` and Wiki Schema `2.0`.
- Recheck Knowledge Map help, budgets, errors, recovery, and workflow examples against
  executable behavior with equivalent paired headings and constants.
- Keep Wiki behavior and the existing Wiki workflow unchanged.

### IC-R6 Historical Comparison Material

- Do not delete or modify `docs/superpowers` comparison proposals.
- Record in parent traceability that commit `d2535dc` created them during parent
  planning before the final scope freeze; the parent PRD/design, executable behavior,
  tests, and active specs supersede them.
- They must not be staged by this correction, cited as implementation authority, or
  counted as Child 4 implementation output.

## Acceptance Criteria

- **IC-AC1:** Invalid Map format and flags satisfy the JSON/exit/stderr/ANSI contract
  through a real subprocess; no test pins plain argparse output.
- **IC-AC2:** A correctly rehashed artifact with a wrong-scope related/fact node is
  rejected by both construction and strict decode.
- **IC-AC3:** The parent applicability matrix is covered through real command dispatch,
  including actual adapter/service/store precedence and no-write assertions.
- **IC-AC4:** Coordinated writer, portable lock, capacity, and bounded-growth tests close
  KM-AC4/KM-AC8/KM-AC11 without timing promises.
- **IC-AC5:** EN/zh-CN docs use index Schema `5`, Wiki Schema `2.0`, and Map constants
  matching executable help.
- **IC-AC6:** Comparison proposals remain byte-unchanged and explicitly non-authoritative.
- **IC-AC7:** `make check`, `make test-unit`, `make test-all`, all Map help smoke tests,
  and exact staged clean-snapshot Ruff checks pass under Python 3.11+.

## Out Of Scope

- New Map commands, deterministic heuristics, fact kinds, claim kinds, Wiki
  integration, plugins, implicit model calls, or dependency additions.
- Deleting/rewording historical `docs/superpowers` proposals.
- Broad cleanup of existing CLI parser behavior unrelated to Map.

## Open Questions

None.
