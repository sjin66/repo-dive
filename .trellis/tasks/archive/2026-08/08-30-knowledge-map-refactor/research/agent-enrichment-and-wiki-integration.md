# Research: Agent enrichment validation and Wiki integration

- **Query**: Inspect agent enrichment validation and Wiki integration relevant to a deterministic fact graph and semantic layer; identify reusable contracts and absent capabilities.
- **Scope**: internal
- **Date**: 2026-08-30

## Update: Active Trellis Specs

Update: active Trellis backend specs were added after this research snapshot.
The current active specs listed below supersede the earlier “not found” observation.

- `.trellis/spec/backend/index.md` identifies the active backend contracts.
- `.trellis/spec/backend/repository-classification.md` constrains deterministic published-index evidence used before Agent semantics.
- `.trellis/spec/backend/wiki-template-contracts.md` is the explicit negative boundary: Knowledge Map Agent claims cannot create Wiki nodes, change `wiki init`, or alter Wiki Schema 2.0 ownership.
- `.trellis/spec/backend/tooling-integration-contracts.md` applies to final clean-snapshot validation and forbids incomplete Host/plugin ownership.

The current plan reuses strict Wiki Evidence patterns but does not add a Knowledge Map dependency to Wiki.

## Findings

### Files Found

| File Path | Description |
|---|---|
| `src/repo_dive/wiki/models.py` | Strict immutable Wiki, page, subsection, Evidence, snapshot, and metadata contracts. |
| `src/repo_dive/wiki/submission.py` | Strict Schema 2.0 agent page-submission decoder and content/citation validation. |
| `src/repo_dive/wiki/service.py` | Classification/template initialization, evidence collection, page submission, validation, and build orchestration. |
| `src/repo_dive/wiki/validation.py` | Evidence freshness checks against the current index. |
| `src/repo_dive/wiki/assembler.py` | Pure deterministic Markdown assembly from validated Wiki state. |
| `src/repo_dive/wiki/store.py` | Strict read and atomic persistence for Wiki artifacts. |
| `src/repo_dive/context/packer.py` | Stable evidence IDs and bounded complete-chunk selection. |
| `src/repo_dive/commands/wiki.py` | Public non-interactive Wiki command/input boundary. |
| `tests/integration/test_wiki_page.py` | Agent input, citation, encoding, state, and stale-Evidence behavior. |
| `tests/integration/test_wiki_evidence.py` | Persisted page Evidence and direct-source behavior. |
| `tests/integration/test_wiki_workflow.py` | Complete build, idempotence, stale state, concurrency, and atomic publication. |
| `tests/integration/test_governed_wiki_quality.py` | Template-governed direct Evidence and extension-page gating. |

### Code Patterns

#### What “agent enrichment” currently means

There is no generic graph-enrichment input. The current validated agent-owned input is Wiki page Markdown split by governed subsections:

```python
@dataclass(frozen=True, slots=True)
class PageSubmission:
    page_id: str
    subsections: tuple[SubsectionContent, ...]
    schema_version: str = "2.0"
```

(`src/repo_dive/wiki/submission.py:14-24`). The decoder requires exactly `page_id`, `schema_version`, and `subsections`, rejects unknown/missing fields, requires Schema `2.0`, nonempty unpadded page ID, and nonempty subsection list (`src/repo_dive/wiki/submission.py:27-49`). It does not accept semantic nodes, edges, labels, clusters, flows, architecture claims, or reading-order claims.

`SubsectionContent` requires a lower-snake-case subsection ID, nonblank body, at least one citation, and unique Evidence IDs (`src/repo_dive/wiki/models.py:222-243`).

#### Reusable validation chain

The current page boundary validates all of the following before persistence:

1. Requested page exists and submitted page ID matches (`src/repo_dive/wiki/service.py:659-678`).
2. Page lifecycle is evidence-ready/failed/generated, with generated content immutable except byte-equivalent replay (`src/repo_dive/wiki/service.py:679-702`).
3. Persisted Evidence still matches current indexed chunk ID, hash, path, and line range (`src/repo_dive/wiki/validation.py:33-72`).
4. Submission includes every governed subsection in exact order (`src/repo_dive/wiki/submission.py:52-61`).
5. Combined UTF-8 body is at most 200,000 bytes (`src/repo_dive/wiki/submission.py:62-77`).
6. Markdown contains no NUL, raw HTML, or H1-H4 headings (`src/repo_dive/wiki/submission.py:109-139`).
7. Every cited ID belongs to the page’s Evidence snapshot (`src/repo_dive/wiki/submission.py:80-92`).
8. Every non-documentation subsection cites at least one `direct` Evidence item assigned to that subsection (`src/repo_dive/wiki/submission.py:93-106`).

The generated page persists ordered subsection content and a deduplicated citation order; the CLI, not the agent, owns page status and lifecycle fields (`src/repo_dive/wiki/service.py:1508-1526`).

This is a strong reusable **validation pattern**—strict versioned input, immutable server-owned state, evidence ownership, source freshness, bounded content, and no unknown fields—but it is specific to Wiki prose.

#### Evidence identity and provenance

Evidence IDs are deterministic SHA-256 values derived from chunk IDs (`src/repo_dive/context/packer.py:227-229`). Each persisted `EvidenceRef` carries Evidence ID, chunk ID, repository-relative path, one-based inclusive range, content hash, role, subsection coverage, and direct paths (`src/repo_dive/wiki/models.py:139-187`). Direct Evidence must declare matching subsection/path coverage; supplemental Evidence cannot declare it (`src/repo_dive/wiki/models.py:153-174`).

`EvidenceSnapshot` binds the query, repository fingerprint, SQLite schema version, index build ID, Git identity, token accounting, retrieval parameters, and collection timestamp (`src/repo_dive/wiki/models.py:84-136`). Retrieval parameters persist max results, strategy, RRF `k`, channel weights, and overlap threshold (`src/repo_dive/wiki/models.py:44-81`).

Evidence collection builds a deterministic query from page/subsection text and declared paths, runs repository search, verifies the index did not change, injects mandatory direct-path chunks, packs complete chunks under budget, persists snapshot/references, and only then returns source text to the caller (`src/repo_dive/wiki/service.py:526-657,1351-1438`).

#### Wiki integration

Governed Wiki initialization is deterministic classification plus built-in template composition (`src/repo_dive/wiki/service.py:396-425`). Template pages/subsections are converted to direct-source contracts by deterministic chunk relevance and stable tie breakers (`src/repo_dive/wiki/service.py:949-1098`). Relevant/direct paths must exist in the current manifest (`src/repo_dive/wiki/service.py:1205-1226`).

Wiki state is an ordered section/page/subsection model with four page states: `pending`, `evidence_ready`, `generated`, and `failed` (`src/repo_dive/wiki/models.py:25-41,247-418`). Metadata binds the Wiki to repository, index, source-control, classification, template, and locale identity (`src/repo_dive/wiki/models.py:421-504`).

`wiki validate` rechecks every generated page’s Evidence and submission contract, verifies current index identity, and dry-runs assembly without publication (`src/repo_dive/wiki/service.py:764-802`). `wiki build` requires every page generated, rejects stale Evidence/current-index mismatch, assembles deterministically, rechecks concurrent index replacement, and atomically writes Markdown (`src/repo_dive/wiki/service.py:713-762`).

The assembler owns shell headings, stable hashed anchors, TOC, related-page links, source links, and scope metadata; caller Markdown fills only subsection bodies (`src/repo_dive/wiki/assembler.py:33-86,139-191,223-232`).

### Claim Verification

| Claim implied by task wording | Verified status | Evidence |
|---|---|---|
| A validated agent semantic layer already exists. | **Partly correct.** A validated agent prose-and-citation layer exists for Wiki subsections. No generic semantic fact/edge enrichment layer exists. | `src/repo_dive/wiki/submission.py:14-106` |
| Agent output is grounded to deterministic repository facts. | **Correct for Wiki pages.** Citations must reference the current page snapshot; direct subsection Evidence is mandatory and freshness is rechecked. | `src/repo_dive/wiki/submission.py:80-106`; `src/repo_dive/wiki/validation.py:33-72` |
| The agent can alter graph facts or lifecycle state. | **Incorrect.** Page submission accepts only subsection bodies/citations; service-owned state transitions are applied after validation. | `src/repo_dive/wiki/submission.py:27-49`; `src/repo_dive/wiki/service.py:1508-1526` |
| Wiki currently derives architecture, flow, and reading paths from a fact graph. | **Incorrect.** Templates define requested prose topics and deterministic direct-source paths, but the CLI does not derive structured architecture/flow/reading-path views. | `src/repo_dive/wiki/service.py:949-1098`; global source search |
| Wiki persistence is resumable and validates stale Evidence. | **Correct.** Page lifecycle, snapshots, status, stale checks, validation, and build gates are implemented. | `src/repo_dive/wiki/models.py:25-41,247-354`; `src/repo_dive/wiki/service.py:493-802` |

### Compatibility-Aligned Boundary Map

| Concern | Existing boundary | Reusable contract |
|---|---|---|
| Deterministic source facts | `parsing`/`indexing` | Stable IDs, path/range/hash, confidence/provenance. |
| Agent input decoding | `wiki.submission` pattern | Exact fields, explicit schema version, bounded payload, safe typed errors. |
| Evidence ownership/freshness | `wiki.models.EvidenceRef`, `EvidenceSnapshot`, `wiki.validation` | Agent references only known current Evidence; content is not trusted by ID alone. |
| Semantic lifecycle | `wiki.models.PageStatus` pattern | CLI owns state transitions; caller cannot submit lifecycle fields. |
| View assembly | `wiki.assembler` | Pure deterministic rendering after validation. |
| Persistence | `wiki.store` | Complete strict documents and atomic replacement. |

For the smallest coherent boundary, current contracts support one validated enrichment round trip only when every agent assertion is represented as bounded, schema-versioned input tied to current Evidence and kept separate from deterministic source facts. Direct Wiki consumption is a later boundary because existing Wiki models consume page/subsection contracts and Evidence references, not arbitrary graph enrichments.

### Likely Test Locations

- `tests/unit/wiki/test_models.py`: strict enrichment model invariants and decoder round trips if represented in Wiki-owned state.
- A unit test adjacent to any new submission decoder, following `tests/integration/test_wiki_page.py` cases for unknown fields, invalid UTF-8, bounds, unknown Evidence, duplicate IDs, and no-mutation failures.
- `tests/integration/test_wiki_evidence.py`: source-fact-to-Evidence provenance and stale behavior.
- `tests/integration/test_wiki_page.py`: agent payload lifecycle, validation, replay, privacy-safe errors, and content restrictions.
- `tests/integration/test_governed_wiki_quality.py`: whether a derived view changes governed page/subsection direct-source contracts.
- `tests/integration/test_wiki_workflow.py`: end-to-end generated-page validation, index concurrency, idempotent build, and old-artifact preservation.
- `evals/cases/wiki_page.jsonl`, `wiki_evidence.jsonl`, and `wiki_workflow.jsonl`: agent/RAG behavior cases.

## External References

None. This request was an internal implementation audit.

## Related Specs

- No `.trellis/spec/**/*.md` files were found.
- `docs/en/wiki-workflow.md:5-15,61-66,102-133,177` documents the governed Evidence-first workflow and recovery errors.
- `docs/en/cli-contract.md:24-28,94-102,267-419` documents the model boundary and Wiki command order.
- `AGENTS.md` requires `wiki evidence`, exact returned Evidence IDs, page submission, validation, and build; generic `context` is not a substitute for persisted Wiki Evidence.

## Caveats / Not Found

- No schema exists for agent-supplied semantic nodes/edges, confidence, claim type, evidence spans per claim, rejection reason, or enrichment version/provider identity.
- Wiki Evidence freshness verifies chunk identity/hash/location, not that generated prose is logically entailed by the cited text; validation establishes citation ownership and direct coverage.
- `generated_at` and metadata timestamps are clock-derived (`src/repo_dive/wiki/service.py:588-610,1533-1534`), so persisted Wiki state includes nondeterministic time metadata even though selection/order/assembly are deterministic for fixed state.
- Governed initialization chooses one direct source path per subsection by chunk relevance unless an extension-specific focused path set applies (`src/repo_dive/wiki/service.py:1065-1098`). This is not graph-based architecture or flow derivation.
