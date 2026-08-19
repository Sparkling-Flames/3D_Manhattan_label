# Persistent disagreement diagnostic v1

Development-only, task-level description. “Persistent” means disagreement remains at the largest observed eligible support; it does not mean infinitely many additional workers could never resolve the task.

## Formal 0.95 geometry threshold

- PreScreen C1-eligible combined: 29 tasks, k=21–23; supported multimodal 14/29 (48.3%), strong persistent split 10/29 (34.5%), non-evaluable partition 2/29 (6.9%).
- Calibration high-support subset: 12 tasks, k=22–22; supported multimodal 6/12 (50.0%), strong persistent split 5/12 (41.7%), non-evaluable partition 3/12 (25.0%).
- Stage-stratified descriptive total: 41 disjoint tasks; strong persistent lower bound 36.6%, upper bound if every non-evaluable partition were persistent 48.8%.
- Threshold-robust subset: PreScreen 6/29, Calibration 2/12; combined 8/41 (19.5%) remain strong splits at all three thresholds.
- Calibration cap-5-only subset: 66 tasks. Its 12 strong splits are “unresolved at five,” not evidence that additional workers would fail to resolve them.

## Definitions

- `supported_multimodal`: frozen complete-link geometry partition has a second cluster with support at least two.
- `strong_persistent_split`: supported multimodal and the largest cluster contains less than 80% of the full eligible support. The 80% boundary is a proportional diagnostic derived from the existing 4:1 k=5 rule; it is not a new formal stop rule.
- `severe_persistent_split`: supported multimodal and the largest cluster contains less than two thirds of support; sensitivity only.
- `not_evaluable_partition`: the frozen complete-link partition is non-unique or otherwise not evaluable. It is uncertainty, not silently counted as either resolved or persistent.

Thresholds 0.90 and 0.925 are reported as lenient clustering sensitivities. PreScreen and Calibration remain separate strata because they have different recruitment/selection roles and overlapping buildings.

No protocol, worker profile, routing policy, or Main-launch state is changed.
