# Historical C1 proposal identity amendment

The first bridge joined the current ep300 audit to C1 by `base_task_id`. That is useful for
future Test sampling, but it is not sufficient to claim that the current ep300 output is the
proposal workers actually saw.

This audit recovers the proposal shown in the frozen C1 import JSON.

- C1 tasks audited: 25
- Historical/current ep300 pair-count mismatch: 14/25
- Pair-count equality: 11/25; geometry identity remains unproven even in these rows.

Therefore:

1. `C1_HISTORICAL_PROPOSAL_TOPOLOGY_SUMMARY.csv` supersedes the earlier C1 grouping by current ep300 topology relation.
2. Current ep300 continuous metrics must not be attributed to the historical C1 proposal.
3. Historical `U_initial` remains the available continuous outcome for what workers saw, while the present audit supplies the actual historical proposal-vs-GT pair-count relation.
4. Exact geometry identity would require canonical coordinate comparison to the retained current-output files; pair-count mismatch already proves non-identity for the affected rows.
