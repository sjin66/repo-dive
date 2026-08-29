# Repository Classification

## 1. Scope / Trigger

Use this contract whenever code classifies a published repository index into a primary
archetype, topology, and facets. Classification is deterministic local evidence
processing; it must not inspect ignored files, arbitrary prose, or model output.

## 2. Signatures

```python
snapshot_from_published_index(
    published: PublishedIndex,
    *,
    registry: RuleRegistry = BUILTIN_REGISTRY,
) -> IndexSnapshot

ClassificationService(registry).classify(
    snapshot: IndexSnapshot,
    *,
    override: str | None = None,
) -> ClassificationResult
```

## 3. Contracts

- `IndexSnapshot` is immutable, timestamp-free, sorted by repository-relative POSIX
  path, and tied to `repository_fingerprint` plus `index_build_id`.
- Signals are limited to exact paths, bounded path globs, integer language counts or
  ratios, and registered key paths in named JSON/TOML manifests.
- Manifest audit output may contain only stable observation/signal IDs, integer
  weights, and sorted paths. It must not contain source text or parsed values.
- Results keep `detected_primary` separate from `effective_primary`; an override changes
  only the effective primary and selection source.
- Weak, tied, or insufficient-margin primary scores select `general_mixed`.

## 4. Validation & Error Matrix

| Condition | Behavior |
|---|---|
| Unknown primary override | `ClassificationError` with `classification_override_unknown` |
| Manifest/database status, hash, membership, or Chunk mismatch | `RepositoryError` with `index_manifest_database_mismatch` |
| Named manifest exceeds 65,536 actual UTF-8 bytes | Ignore content and emit `manifest_oversized` |
| Malformed TOML/JSON, duplicate JSON key, non-standard JSON constant, recursion failure | Ignore content and emit `manifest_malformed` |
| Missing/unreadable registered manifest | No positive content signal and no source disclosure |

## 5. Good / Base / Bad Cases

- Good: two `packages/*/package.json` roots select `monorepo`; a template override
  preserves detected scores, topology, facets, and matched signals.
- Base: no strong signal selects `general_mixed` plus `single_project`.
- Bad: trusting Manifest size metadata while parsing oversized reconstructed text, or
  using registry order to break an equal primary score.

## 6. Tests Required

- Assert every registered primary, topology, facet, and matcher kind has behavioral
  coverage.
- Assert weak, tied, ambiguous, malformed, oversized, and unknown-override behavior.
- Assert serialized output is byte-stable across input order and contains no source
  text or timestamp.
- Assert the adapter rejects Manifest/database identity and Chunk-membership drift.

## 7. Wrong vs Correct

### Wrong

```python
document = json.loads(file_text)
primary = max(scores, key=scores.get)
```

This accepts duplicate/non-standard JSON and makes ties depend on incidental ordering.

### Correct

```python
document = json.loads(
    file_text,
    object_pairs_hook=_unique_json_object,
    parse_constant=_reject_json_constant,
)
result = ClassificationService().classify(snapshot)
```

The bounded parser rejects ambiguous manifests, and the service applies explicit
threshold, margin, and fallback rules.
