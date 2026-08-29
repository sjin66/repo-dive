# Wiki Template Contracts

## 1. Scope / Trigger

Use this contract when defining, composing, localizing, serializing, or consuming the
built-in Wiki templates under `repo_dive.wiki.templates`. Templates are a closed,
deterministic contract over the repository classification taxonomy; they do not load
user plugins or fall back between locales.

## 2. Signatures

```python
load_builtin_registry() -> TemplateRegistry

compose_template(
    primary_id: str,
    topology_id: str,
    facet_ids: tuple[str, ...],
    locale: str,
) -> ComposedContract

TemplateRegistry.compose(
    primary_id: str,
    topology_id: str,
    facet_ids: tuple[str, ...],
    locale: str,
) -> ComposedContract
```

The template schema is `1.0`. It is independent from the persisted Wiki state schema.
The registry version and every contribution version are separate identity fields.

## 3. Contracts

- Exactly one primary, one topology, and zero or more unique facets are composed.
- Facets are normalized to `FACET_IDS` registry order, regardless of caller order.
- The framework shell exclusively owns `wiki`, `contents`, section/page headings,
  related pages, and sources. Contribution IDs must be recursively disjoint from shell
  IDs.
- Primary contributions define ordered sections and pages. Topology and facet
  contributions use only `insert_before`, `insert_after`, `append_to_slot`, or
  `refine_existing`; refinements may only narrow constraints.
- Contract nodes use stable lower-snake-case IDs and explicit owner, node type,
  cardinality, heading levels, children, and allowed extension-slot child types.
- Supported locale IDs are exactly `en`, `zh-CN`, and `ja`. Catalog key sets must
  exactly match all registered shell and contribution node IDs.
- Every resource declares its contribution, locale, ordered page IDs, cardinality, and
  AST shape. Placeholders are `{{repo_dive:<logical_id>}}` and must resolve exactly.
- `annotated_guidance` retains resolved HTML instruction comments for the calling
  agent. `compiled_guidance` removes comments, template headings, and all placeholder
  syntax so comments cannot become Wiki output nodes.
- `contract_sha256` hashes the canonical language-neutral shell, nodes, contribution
  identities, and versions. `localized_sha256` hashes that digest together with the
  selected labels and both resolved guidance forms.

The strict JSON projection is `ComposedContract.to_document()`. Semantic arrays retain
their order; object keys are canonicalized only when hashing.

## 4. Validation & Error Matrix

| Condition | Behavior |
|---|---|
| Unknown primary, topology, facet, or locale | Raise `ValueError`; no fallback |
| Duplicate facet selection | Raise `ValueError` |
| Missing operation target or dependency cycle | Reject registry/composition |
| Duplicate or shell-colliding logical ID | Reject registry/composition recursively |
| Extension-slot child type or capacity violation | Reject the operation |
| Refinement widens requiredness, cardinality, or heading levels | Raise `ValueError` |
| Missing, extra, or mismatched locale key/resource | Reject built-in registry load |
| Resource metadata, page order, shape, or placeholder drift | Reject built-in registry load |
| Unknown or residual placeholder syntax | Raise `ValueError` during compilation |

## 5. Good / Base / Bad Cases

- Good: composing `cli_tool`, `monorepo`, `("database", "api")`, and `zh-CN`
  stores facets as `("api", "database")`, retains Chinese annotated instructions, and
  produces comment-free compiled guidance.
- Base: composing one primary and `single_project` with no facets still inserts the
  registered topology page into the explicit topology slot.
- Bad: defining another `wiki` node in a primary, relying on translated heading text as
  an operation target, silently accepting `EN`, or hashing only compiled guidance.

## 6. Tests Required

- Assert taxonomy IDs and order exactly match the classification registry.
- Resolve every primary/topology/facet resource in all three locales and assert exact
  locale key and node-ID parity.
- Assert all primary archetypes have intentional, distinct page signatures and that
  representative contracts exercise heading, paragraph, list, table, code-block, and
  extension-slot constraints.
- Assert caller facet order does not affect normalized documents or hashes.
- Assert annotated guidance contains localized comments while compiled guidance has no
  comments, template placeholders, or template-owned heading nodes.
- Assert missing targets, cycles, collisions, widening refinements, locale drift,
  resource drift, and arbitrary placeholder syntax fail closed.
- Assert the serialized projection includes both guidance forms and template schema
  `1.0`.

## 7. Wrong vs Correct

### Wrong

```python
facets = tuple(requested_facets)
localized_hash = canonical_sha256(compiled_guidance)
```

This makes identity depend on caller order and fails to bind the instructions shown to
the generating agent.

### Correct

```python
contract = compose_template(
    "cli_tool", "monorepo", ("database", "api"), "zh-CN"
)
assert contract.identity.facets == ("api", "database")
assert "<!--" in contract.annotated_guidance
assert "<!--" not in contract.compiled_guidance
```

The registry controls semantic ordering, and the localized digest binds both guidance
representations plus the selected labels and language-neutral contract digest.
