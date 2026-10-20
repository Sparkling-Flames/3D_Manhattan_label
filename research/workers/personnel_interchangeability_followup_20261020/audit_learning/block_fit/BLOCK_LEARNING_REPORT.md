# Direct m2 block learning: finite negative experiment

## Result

Neither registered candidate is a practical improvement over Q or the original Rnew2. Both slightly beat capacity-matched random labels, but have worse held-out within distance and separation than useful baselines; valid-distance coverage and verified count-change risk also worsen against Rnew2. No winner is nominated, and no additional search is undertaken.

|Candidate|Within|Between−within|Within valid|Within count-change|Within incomplete|
|---|---:|---:|---:|---:|---:|
|B_direct_m2_composition_K2|0.020956|0.000470|85.077%|11.781%|3.142%|
|B_direct_m2_composition_K3|0.020851|0.000447|84.893%|12.088%|3.018%|

|Candidate|Baseline|Δwithin (lower better)|Δgap (higher better)|Δvalid|Δcount-change|
|---|---|---:|---:|---:|---:|
|B_direct_m2_composition_K2|Q_same_capacity|0.000678|-0.001200|-0.605%|0.506%|
|B_direct_m2_composition_K2|original_Rnew2_mixed_refit|0.001528|-0.002719|-1.413%|1.218%|
|B_direct_m2_composition_K2|random_same_capacity|-0.000197|0.000349|0.427%|-0.446%|
|B_direct_m2_composition_K3|Q_same_capacity|0.000617|-0.000877|-1.915%|1.834%|
|B_direct_m2_composition_K3|original_Rnew2_mixed_refit|0.001370|-0.002822|-1.597%|1.526%|
|B_direct_m2_composition_K3|random_same_capacity|-0.000684|0.000785|0.295%|-0.168%|

These are equal-building held-out history estimates on exact common anchors. Conditional distance is .5(BEVmean+topmean)/pairscale; invalid distances never become zero. Structural rates use all-attempt observed common anchors. Random rows average40 fixed capacity permutations, not confidence intervals. Ten buildings limit uncertainty and generalization.

## Frozen membership and meaning

### B_direct_m2_composition_K2
- C01: W100, W101, W104, W106, W107, W108, W113, W114, W116, W120, W121, W122, W124, W125, W126, W127, W128, W129
- C02: W102, W103, W105, W109, W110, W111, W112, W115, W117, W118, W119, W123, W130, W131, W132, W133, W134
### B_direct_m2_composition_K3
- C01: W100, W103, W104, W107, W108, W114, W116, W120, W121, W123, W125, W128, W131, W132
- C02: W101, W105, W106, W111, W113, W117, W124, W133
- C03: W102, W109, W110, W112, W115, W118, W119, W122, W126, W127, W129, W130, W134

All35 new-source workers are known;25 old-source workers remain outside this domain. These unsupported alternative memberships are archived for reproducibility, not recommended replacements for the existing conditional Rnew2 reference. Descriptive Q/T/geometry profiles and full-fit relation tails are separately labeled in-sample, not validation.

## Why this is genuinely block-level

The learner compares the two-person class-count vectors of disjoint replacement blocks and uses their actual final-team geometry distance. It never substitutes summed single-person outcomes for a block outcome. Its fixed registered objective, two K values, two starts and30 accepted-move cap completed without outcome-driven amendments. Registration/design/native/metric hashes and full optimizer trace remain available.

## Stopping decision

Preserve the negative legacy m1→m2 transfer and this independent history-only m2 result. Use the original conditional Rnew2 plus explicit Q/geometry/source/scope qualifications where its empirical domain supports it. There is no evidence here for a universally strong coarse/fine hierarchy. Additional learning would need a new scientific justification and a genuinely new evaluation plan rather than repeated optimization against the same assessment.
