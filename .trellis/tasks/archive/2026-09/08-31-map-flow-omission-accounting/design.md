# Knowledge Map Flow Omission Accounting Design

## Boundary

The defect is local to `derive_flows`: global work exhaustion exits only the current
queue while the outer root loop continues. Models, build propagation, views, and public
schemas already represent the intended count.

## Correction

Track a local `work_exhausted` boolean. At the first exhaustion check:

1. add `len(queue) + len(roots) - root_index - 1` to `suppressed`;
2. add `candidate_budget` once;
3. mark exhaustion and exit the current queue;
4. immediately exit the outer root loop.

All other candidate generation and normalization remains byte-for-byte equivalent when
the global work budget does not exhaust.

## Count Contract

One discarded frontier state remains one omitted unit. The implementation does not
traverse discarded descendants to estimate terminal candidates. Build-time coverage
counts remain distinct from `map show --max-results` projection counts.

## Tests And Rollback

Unit tests cover 4/5/6 independent roots, a branched queue, and unaffected duplicate,
prefix, utility, and final-limit terms. A build-level test pins coverage propagation.
The one-function change can be reverted independently without artifact migration.
