# Research: Governance schema and state invalidation

- **Query**: Design deterministic schema/state invalidation for classification, templates, locale, and Markdown governance.
- **Scope**: internal
- **Date**: 2026-08-29

## Findings

### Files Found

| File Path | Description |
|---|---|
| `src/repo_dive/wiki/models.py:13-15,253-335` | Wiki/metadata Schema `1.0` and exact persisted fields. |
| `src/repo_dive/wiki/models.py:338-385` | Strict root decoders reject unknown/missing fields. |
| `src/repo_dive/wiki/store.py:44-66,98-131` | Distinct invalid-state and unsupported-version repository errors; preserves bytes. |
| `src/repo_dive/wiki/service.py:171-251` | Current initial write, merge, invalidation, and metadata update behavior. |
| `src/repo_dive/wiki/service.py:587-642` | Page preservation depends on structure equality, staleness, and global invalidation. |
| `src/repo_dive/wiki/validation.py:55-72` | Evidence staleness is based on index Schema and exact Chunk identity/hash/path/range. |
| `src/repo_dive/storage/atomic.py:18-53,69-74` | Complete serialized writes through sibling temporary files and atomic replace. |
| `tests/integration/test_wiki_structure.py:110-192` | Byte idempotency and page-local invalidation precedent. |
| `tests/integration/test_recovery.py:241-309` | Stale/corrupt/failing operations preserve last valid Markdown and source bytes. |
| `docs/en/cli-contract.md:494-502` | Public compatibility rule for optional fields versus breaking field/type/path changes. |
| `.trellis/tasks/08-29-wiki-template-governance/prd.md:91-100,123-126` | Governance identity, legacy-state behavior, and preservation requirements. |

### Existing Compatibility Constraint

Persisted Wiki and metadata decoders require exact root key sets (`wiki/models.py:338-385`) and page decoders reject unknown keys outside two historical optionals (`wiki/models.py:399-433`). Adding governance fields to Schema `1.0` would make new state unreadable by old code and legacy state incomplete for new code. The documented compatibility contract says adding optional output fields is compatible, but removing/renaming/changing types or artifact paths requires a schema or command version change (`docs/en/cli-contract.md:500-502`). Governance identity is required state, not an optional response decoration.

### Candidate Version Decision

Use explicit Wiki state Schema `2.0` and metadata Schema `2.0` for governed state. Do not infer governance for Schema `1.0`. On every governance-aware `wiki init`, `wiki evidence`, `wiki page`, `wiki validate`, `wiki build`, and `wiki status` read:

- if both artifacts are valid `1.0`, return repository error `wiki_template_state_missing`, exit `3`, with no writes;
- if either artifact has an unsupported future version, retain existing `wiki_state_version_unsupported` / `wiki_metadata_version_unsupported` behavior;
- if only one artifact exists, retain `wiki_state_incomplete`;
- never rewrite, repair, or delete old bytes on these errors.

This directly implements the explicit legacy rule (`prd.md:94-98`) and follows current byte-preservation behavior (`wiki/store.py:44-66,98-131`; `test_recovery.py:266-283`).

Candidate metadata `2.0` required governance identity:

```json
{
  "schema_version": "2.0",
  "wiki_schema_version": "2.0",
  "repository_classification": {
    "classifier_version": "1",
    "taxonomy_version": "1",
    "selection_source": "automatic",
    "primary_id": "cli_tool",
    "topology_id": "single_project",
    "facet_ids": ["api"],
    "matched_signal_ids": ["python.console-script"]
  },
  "template": {
    "registry_version": "1",
    "primary_id": "cli_tool",
    "primary_version": "1",
    "topology_id": "single_project",
    "topology_version": "1",
    "facets": [{"id": "api", "version": "1"}],
    "contract_sha256": "<hash>",
    "localized_sha256": "<hash>"
  },
  "locale": "en"
}
```

Retain existing repository, fingerprint, source commit, index Schema/build, and timestamps (`wiki/models.py:290-335`). Persist the full matched-signal audit either here or in a separate bounded public governance object referenced by hash; signal IDs alone are insufficient if weights and matching paths must remain inspectable after the classifier registry changes.

Persist each page's exact logical page contract identity (page contract hash/version) in Wiki `2.0`. Evidence output can then return the same exact page contract required by `prd.md:80-83`, and page submission/build can reject contract mismatch without recomposing against a newer installed registry.

### Candidate Invalidation Matrix

| Change | Classification metadata | Structure | Evidence | Generated body | Last valid `wiki.md` |
|---|---|---|---|---|---|
| Index build changes, governance composition unchanged | refresh index identity/audit | preserve stable logical pages | invalidate only pages whose Evidence is stale | reset only stale pages to `pending`; retain old body diagnostically | preserve until successful rebuild |
| Automatic score/signals change but selected primary/topology/facets and hashes are identical | refresh audit | preserve | preserve | preserve | preserve |
| Primary/topology/facet composition or language-neutral contract hash changes | replace governance identity | instantiate new composed structure | invalidate all retained affected pages; removed pages disappear from active structure | affected pages become `pending`; old fields may remain only for retained IDs/diagnosis | preserve |
| Classifier/taxonomy version changes | refresh classification | conservative full governed re-init/invalidation unless exact persisted contract remains explicitly certified compatible | invalidate affected pages | affected pages `pending` | preserve |
| Locale changes or localized contract hash changes | locale/template identity changes | replace all localized framework titles/descriptions | invalidate all pages | all pages `pending` | preserve |
| Parser profile/validation contract changes | template contract hash changes | logical structure may remain | Evidence can remain if query contract unchanged | invalidate pages whose page-contract hash changes | preserve |
| Explicit template override changes selection | selection source becomes `override` | compose selected base with detected overlays/facets | invalidate affected pages | affected pages `pending` | preserve |
| Override text repeats exact current identity | no change | no change | no change | no change | no write |

The narrow stale-Evidence precedent is `_page_is_stale` (`wiki/validation.py:55-72`) and current structure merge preserves unaffected pages by stable IDs and exact structural equality (`wiki/service.py:587-642`). Output-language changes already trigger `invalidate_all` (`wiki/service.py:196-213`).

### Candidate Transaction Ordering

Current initialization writes metadata before Wiki (`wiki/service.py:179-187`) and current updates also perform two independent atomic replacements (`wiki/service.py:233-243`), while readers require both files. Individual files are atomic, but the pair is not transactional. Governance-aware reinitialization must preserve the stated legacy requirement that the last valid Markdown remains untouched; it also needs a defined crash state for the JSON pair.

A deterministic operation sequence is:

1. Read and validate current pair and current index.
2. Compose/validate the entire new governed state in memory.
3. Write new state using a generation/pointer or another pair-atomic publication design.
4. Do not write `wiki.md`; only a later successful build replaces it.

At minimum, a mid-pair failure must continue to surface `wiki_state_incomplete` and never silently repair. The generation/pointer pattern already exists for indexes (`indexing/service.py:46-50,159-192`) and is the repository's strongest precedent for multi-file publication.

### Related Specs

- No `.trellis/spec/**/*.md` files were found.
- `.trellis/tasks/08-29-wiki-template-governance/prd.md:91-100` — required persisted identity and legacy behavior.

## Caveats / Not Found

- Current tests do not exercise an output-language change even though service code invalidates all pages.
- There is no persisted page contract hash, classifier identity, taxonomy identity, template identity, or parser profile.
- Whether classifier-version-only changes can preserve pages is a product compatibility policy. The conservative matrix above treats uncertified classifier governance changes as invalidating, while exact unchanged composition alone is safe only if explicitly declared compatible.
