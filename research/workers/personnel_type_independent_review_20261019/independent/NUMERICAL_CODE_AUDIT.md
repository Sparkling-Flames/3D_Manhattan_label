# Independent numerical and code audit, 2026-10-19

## Delivery integrity
All three ZIPs pass complete CRC reading. 2,957 data-package member size/SHA256 checks pass; 824 frozen scientific-source files and 519 retained prior-core logical files pass SHA256. Sixteen analysis-key file checks and 83 forward-delivery member hashes also pass. This is not a hash claim for every byte of the original Pro working directory: 22 reverse prediction long tables are intentionally omitted, and full regeneration was not performed. The 136 data-packaging omissions are runtime bytecode/locks, superseded download copies and one temporary write. See COMPLETENESS_AUDIT.json. The root separately checks public checksum manifest and wrapper readiness.

## Independent computations
- Recomputed every one of 286,666 joint-stability flags from completeness, |B8 change|<=2, footprint difference<=.05, same node count and cyclic boundary shift<=3 degrees: zero mismatch. This preserves 7,715 event rows with at least one incomplete endpoint as unstable.
- Reimplemented building/image-weighted leave-building calibrators without importing Pro calibration code. Four methods (old QT, selected forward, selected geometry reverse, selected replacement reverse), every event and all 22 held-out buildings: probabilities agree within 4.45e-16.
- Independently reaggregated new k=16 reverse-vs-QT Brier gain: .000724813, building bootstrap 95% [.000334052,.001156586], 4,080 events/170 images/22 buildings. Common known support reduces this to .000673154 on 3,990 events. Among Q-near common events: .000012005 [-.000898648,.000904457], 1,290 events/169 images/22 buildings.
- Independently reaggregated origin-controlled new k=16 gain: -.000098649 [-.000718584,.000690358], so incremental evidence beyond source cohort is unresolved.
- Recomputed all 69 selected QT-only forward partitions from their frozen training feature matrices (4,140 assignments): exact labels. This is a partition replay, not all 69 fresh feature fits.
- Freshly recomputed all numeric features for one 21-building outer fold and one nested 14-building subset; every field agrees within 1e-9, missing masks match. Poisoned excluded-building Q/time/points/scope and recomputed: unchanged features. Only these two subsets were freshly feature-refitted.
- Recomputed main reverse geometry partition from local training geometry for FULL and one outer fold: exact 60 worker labels each. Does not rerun all reverse candidate/selection chains.

## Code and interpretation findings
1. Training filters are applied before feature effects, scaling and pair aggregation in inspected implementations. Unknown workers use baseline probabilities, not a joint unknown class. These inspected and tested boundaries are sound; no broad proof of absence of all leakage is claimed.
2. Both search grids are K=4,6,8,10. Thus K=4 everywhere cannot establish the natural number of types: K=1,2,3 were never eligible, and the registered one-standard-error rule explicitly favors the smallest candidate. Add simple/no-class controls before claiming discovered four archetypes.
3. Selected forward method is QT-only K4 in every one of 23 FULL/outer contexts. Full multivariable candidates were actually fitted but were not selected. This does not establish that all extra variables are useless.
4. Reverse pair support flags are reported, but unsupported pair distances fall back to the common training prior and still enter clustering. This is a modeling assumption, not observed similarity. Sensitivity to pair support/cohort and disconnected evidence deserves further testing.
5. New-panel background IDs each support only one pair relation, so no new-panel background has both within-class and cross-class comparison opportunities for selected methods. Same-event Brier comparisons are valid predictive comparisons, but do not themselves establish matched-background within/cross replacement effects.
6. The reported k16 matched-background gap comes from the OLD panel: between minus within = -1.0574 percentage points, CI[-4.0330,+1.7775], 253 backgrounds/139 images/22 buildings. Event/background equal weighting gives -3.2178pp; image equal -3.1063pp. Preserve all weighting targets.
7. Current evidence supports keeping continuous quality/time portraits and conditional compatibility as exploratory research, not production interchangeable personnel classes. No significance does not mean equivalence.

## Reproduction
Run recompute_metrics.py, replay_partitions.py, and check_origin_and_contrasts.py in this directory against the unchanged extracted three-part layout. They write only audit outputs here, not scientific inputs. They assume the current local path in their R/P constants; change those to relocate. Source code/receipts are small and do not require republishing the large original inputs. Broader native-fusion spot checks are recorded separately by the parent audit.
