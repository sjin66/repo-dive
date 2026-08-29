# Research: Deterministic repository classification contract

- **Query**: Design candidate deterministic contracts for repository classification and composed built-in Wiki templates.
- **Scope**: mixed
- **Date**: 2026-08-29

## Findings

### Files Found

| File Path | Description |
|---|---|
| `src/repo_dive/scanner/candidates.py:47-76` | Produces a sorted, repository-relative candidate path set from Git or the filesystem. |
| `src/repo_dive/scanner/service.py:74-105` | Produces an ordered inventory and repository fingerprint. |
| `src/repo_dive/scanner/service.py:108-114` | Existing deterministic path-only language classification. |
| `src/repo_dive/scanner/service.py:257-289` | Fingerprint inputs and canonical sort behavior. |
| `src/repo_dive/indexing/manifest.py:118-157` | Published index identity, sorted file paths, build parameters, and repository fingerprint. |
| `src/repo_dive/indexing/schema.sql:3-11` | Persisted file path, detected language, status, and hash evidence. |
| `src/repo_dive/indexing/store.py:100-115` | Read-only validated index access boundary. |
| `src/repo_dive/wiki/service.py:171-221` | Existing structure operation is already tied to a validated published index. |
| `tests/unit/scanner/test_service.py:87-107` | Tests stable path-based language detection. |
| `.trellis/tasks/08-29-wiki-template-governance/prd.md:27-47` | Required compositional taxonomy and deterministic fallback behavior. |

### Existing Evidence Boundary

Candidate discovery is deterministic and sorted (`scanner/candidates.py:69-76`). The scanner records path, detected language, status, content hash, encoding, and size (`scanner/service.py:159-168`) and includes those fields in the repository fingerprint (`scanner/service.py:257-289`). The published Manifest retains sorted paths, status, and hashes but not language (`indexing/manifest.py:61-76,130-157`); language remains in the validated SQLite `files` table (`indexing/schema.sql:3-11`). Consequently, classification from the current published index can audit path/hash/status directly and obtain language through read-only index storage; classification from the Manifest alone cannot reproduce language-based signals.

### Candidate Classification Document

Use one closed, versioned result whose arrays are registry-ordered rather than set-ordered:

```json
{
  "schema_version": "1.0",
  "classifier_id": "builtin-repository-classifier",
  "classifier_version": "1",
  "taxonomy_version": "1",
  "repository_fingerprint": "<sha256>",
  "index_build_id": "<id>",
  "selection_source": "automatic",
  "primary": {"id": "cli_tool", "score": 140, "confidence": "high"},
  "topology": {"id": "single_project", "score": 0},
  "facets": [{"id": "api", "score": 40}],
  "matched_signals": [
    {"id": "python.console-script", "weight": 100, "paths": ["pyproject.toml"]}
  ],
  "template_override": null
}
```

Closed enum values for `selection_source`: `automatic`, `fallback`, `override`. An override changes only `primary.id` and source; topology/facet detection remains auditable unless the command contract explicitly offers separate topology/facet overrides. Unknown IDs are invocation errors, matching the PRD (`prd.md:42-47`).

### Candidate Signal and Selection Rules

1. Evaluate only the validated current published index. Use readable indexed files for content signals and all indexed paths for path-presence signals. Never inspect ignored/unindexed files; this keeps classification tied to `repository_fingerprint` and `index_build_id`.
2. Define signals in a bundled registry with stable IDs, integer weights, target dimension, target ID, matcher kind, and bounded matcher parameters. Matcher kinds should be finite: `exact_path`, `path_glob`, `language_count`, `language_ratio`, and `manifest_key_value`. Content matching is limited to named manifest/config files and parsed key/value locations, not arbitrary prose.
3. A matched signal records only stable signal ID, configured weight, and sorted repository-relative matching paths. This is sufficient to audit the decision without emitting source contents.
4. Sum integer weights independently for primary archetypes, topology overlays, and facets. Sort candidates by descending score, then registry ordinal, then ASCII ID. Registry ordinal is presentation order only and must not break a score tie for automatic primary selection.
5. Select a primary automatically only when its score meets a declared threshold and exceeds the runner-up by a declared margin. Otherwise select `general_mixed` with `selection_source: fallback`. This directly realizes the weak/absent/tied rule at `prd.md:45-47`.
6. Select exactly one topology. `monorepo` and `microservices` require structural path evidence (for example multiple registered workspace roots or multiple independently deployable service manifests); otherwise use `single_project`.
7. Select every facet meeting its own threshold, then emit facets in taxonomy-registry order. A facet does not alter the chosen primary.
8. Hash/version the classifier registry. A stable result requires the same classifier version, taxonomy version, index identity, override, and sorted signal result.

The required primary IDs can directly use the PRD registry: `web_application`, `service_api`, `cli_tool`, `library_sdk`, `data_science`, `data_pipeline`, `ai_ml`, `mobile_application`, `desktop_application`, `embedded_firmware`, `infrastructure`, `developer_tool`, `plugin_extension`, `game`, `documentation_content`, `general_mixed` (`prd.md:27-34`). Topology and facets remain separate dimensions, avoiding an unbounded cross-product.

### Determinism Details

- Signal IDs and taxonomy IDs are ASCII lowercase snake case; matching is byte/case sensitive unless a specific matcher declares ASCII case folding.
- Paths use the repository-relative POSIX representation already guaranteed by discovery and Wiki models (`scanner/candidates.py:69-76`; `wiki/models.py:525-535`).
- Ratios use integer numerator/denominator comparisons (`matched * threshold_denominator >= total * threshold_numerator`) rather than floating point.
- Missing, skipped, malformed, or oversized config files produce no positive content signal and may emit a stable non-secret observation code; they never trigger heuristic guessing.
- Classification timestamps are excluded from identity and equality. The repository already uses timestamp-free deterministic assembly (`wiki/assembler.py:20-53`).

### External References

- [RFC 8785 JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785.txt) — canonical JSON requires deterministic property sorting, preserved array order, and UTF-8 output. The repository's serializer already sorts object keys and emits UTF-8-compatible JSON (`schema.py:76-86`), but it is not declared as full JCS (notably number serialization).

### Related Specs

- No `.trellis/spec/**/*.md` files were found.
- `.trellis/tasks/08-29-wiki-template-governance/prd.md:20-47` — governing taxonomy and classifier requirements.

## Caveats / Not Found

- No repository classifier, taxonomy registry, classification command, or template registry exists in current product source.
- The published Manifest omits file language, so a Manifest-only classifier would lose an existing signal available in SQLite.
- Concrete signal weights and thresholds require fixture calibration; the contract above fixes how they are evaluated, not their final values.
