# Topology sequential preflight v4 audit

This is an append-only development audit. It does not overwrite or silently repair v3.

## Medoid reproducibility

- exact historical k=5 tasks: 66
- cluster-status mismatches: 0
- cluster-membership mismatches: 0
- medoid mismatches: 9
- current-minus-frozen public-GT quality among evaluable mismatches: mean=-0.013223285007844601, min=-0.10366288623413433, max=0.15498174669002274

## TG-EF5

TG-EF5 uses the v3 k=3/k=4 conservative gate and, whenever it reaches k=5, uses the identical corrected F0 terminal output.

- stop@3: 0.43085897435897436
- incremental stop@4: 0.2007179487179487
- reach5: 0.3684230769230769
- mean K: 3.9375641025641026
- frozen-geometry saving versus fixed k=5: 1.0624358974358974
- public-GT paired delta versus corrected F0: -0.0008903714918769612
- task-level paired-delta SD: 0.008568075346888629
- expert escalation introduced by TG-EF5: 0.0

The public-GT result is diagnostic. Actual expert-validated harm and a scientifically justified NI margin remain absent.

## Paper A reference semantics

Paper A retains one frozen operational reference for every in-scope geometry-evaluable task. A second materially different, protocol-consistent interpretation is a scope-contract failure (`scope-unresolved`), not an additional acceptable Main reference. Set-valued references remain a possible future re-annotation contract, not the current confirmatory Main contract.

## Reliable reviewer

The reviewer files assess profile ordering and candidate availability only. Historical independent annotations cannot identify the effect of a worker seeing and verifying other annotations. A reviewer mechanism therefore requires a separately randomised, blinded review study before it can affect production delivery.
