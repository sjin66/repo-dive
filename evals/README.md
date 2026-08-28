# Evaluation Cases

Evaluation cases record observable agent/CLI contracts and, in later phases, retrieval quality expectations. Cases are JSON Lines files under `evals/cases/` so reviews can identify one scenario per line and runners can stream large sets.

Required fields:

- `id`: globally unique stable identifier.
- `category`: grouping such as `cli`, `io_contract`, or `artifact_contract`.
- `prompt`: situation presented to the calling agent.
- `expected_behavior`: concise observable outcome.

Optional fields:

- `command`: executable command when the behavior exists in the current build.
- `assertions`: additional literal outcomes for a future runner.

Cases without `command` are specification cases. They document an approved future contract and must not be reported as passing executable evaluations.

Add a case before changing a retrieval or context heuristic. Keep fixtures small, ground expectations in repository evidence, and avoid scoring prose style when source correctness is the real requirement.

