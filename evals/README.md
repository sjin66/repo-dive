# Evaluation Cases

Evaluation cases record observable agent/CLI contracts and executable retrieval
quality expectations. Cases are JSON Lines files under `evals/cases/` so reviews
can identify one scenario per line and the Runner can stream large sets.

Required fields:

- `id`: globally unique stable identifier.
- `category`: grouping such as `cli`, `io_contract`, or `artifact_contract`.
- `prompt`: situation presented to the calling agent.
- `expected_behavior`: concise observable outcome.
- `mode`: exactly `executable` or `specification`.

Optional fields:

- `command`: documented command boundary; it is never executed as arbitrary Shell.
- `assertions`: additional human-readable outcomes.
- `evaluation`: required only for executable cases.

Specification cases are reported as `specification` and never count as passed.
Executable cases use a structured `evaluation` object with:

- `operation`: `search` or `context`;
- `repository`, `query`, `max_results`, and `token_budget` for Context;
- `expected.paths`, `expected.symbols`, and `expected.citations` ground truth;
- `minimums`: optional per-metric thresholds from 0 through 1.

The Runner copies each repository Fixture to a temporary directory, removes any
previous `.repo-dive` state, builds a fresh offline index, and invokes the typed
Search/Context services. It does not interpret the `command` string or score
Markdown prose.

Run the complete corpus with:

```bash
.venv/bin/python -m repo_dive.evaluation.runner evals/cases --format json
```

The versioned report includes every case's mode, status, metrics, safe
diagnostics, and source line. Aggregates contain a mean and applicable-case
count for Recall@k, MRR, path hit rate, symbol hit rate, budget compliance, and
citation coverage. `null` means the metric is not applicable; it is never
silently treated as zero. The process exits `1` when any executable case fails
its thresholds and `2` when the corpus is invalid.

Metric definitions are intentionally small and auditable:

- Recall@k is unique relevant identities retrieved in the first k ranks divided
  by all relevant identities.
- MRR is the reciprocal rank of the first relevant identity.
- Path, symbol, and citation coverage divide observed required identities by
  all required identities.
- Budget compliance is 1 only when estimated tokens do not exceed the positive
  budget.

Add an executable case before changing a retrieval or context heuristic. Keep
Fixtures small, ground expectations in repository evidence, and avoid scoring
prose style when source correctness is the real requirement.
