# Frozen direct-block family: internal outcome check

## Recommendation
Neither direct-m2 K2 nor K3 passed the historical building-fold comparison against original Rnew2 and Q. That negative selection remains frozen. Both candidates are reported here to close the entire prespecified family; no assessment-based reselection is permitted. These are reused internal assessment images, not new external validation.

## Exact endpoint and denominator contract
Each candidate is recategorized on the identical 63,476 raw endpoint pairs (152 anchors, 11 images, 6 buildings), using complete exchanged-block class-count vectors. Every candidate-versus-Rnew2 metric uses the intersection of anchors having finite observations in all four cells (two methods × same/changed composition). Risk metrics instead retain all attempted comparisons on their common observed anchors. Distances are conditional on valid corner correspondence, never zero-imputed for failures. Equal anchors within image, images within building, and buildings determine reported averages.

The common subset is candidate-specific: pairwise matched estimates for K2 and K3 must not be compared as though their m5 populations were identical. Pure-class sensitivity is separate and may exclude classes too small for two disjoint m-worker blocks.

## m2 primary transfer check
K2 has larger same-composition mean BEV distance and a smaller between-minus-within gap than Rnew2 at every tested n. K3 is mixed: n9 improves the conditional mean/gap, n5 and n13 worsen them, and n17 has a slightly lower within mean with essentially unchanged gap. This does not reverse the failed historical CV recommendation.

| Candidate | n | Common anchors | Within BEV h | Rnew2 within h | Gap h | Rnew2 gap h |
|---|---:|---:|---:|---:|---:|---:|
| K2 | 5 | 21 | 0.181094 | 0.167142 | -0.002350 | 0.019288 |
| K2 | 9 | 21 | 0.124429 | 0.116943 | -0.002769 | 0.009957 |
| K2 | 13 | 21 | 0.078672 | 0.071667 | -0.002799 | 0.009051 |
| K2 | 17 | 20 | 0.059713 | 0.059079 | 0.002340 | 0.003356 |
| K3 | 5 | 21 | 0.173234 | 0.167142 | 0.008052 | 0.019288 |
| K3 | 9 | 21 | 0.113475 | 0.116943 | 0.011803 | 0.009957 |
| K3 | 13 | 21 | 0.075838 | 0.071667 | 0.001663 | 0.009051 |
| K3 | 17 | 20 | 0.058604 | 0.059079 | 0.003256 | 0.003356 |

m2 distance support is 21 anchors at n5/9/13 and 20 at n17; all-attempt risks use 22 anchors, all across six buildings. K2 within verified count mismatch exceeds Rnew2 at each n. K3 is slightly worse at n5 and slightly better at n9/13/17; risk and distance remain separate outcomes.

## m5 extrapolation
m5 was not the fitted turnover. Its frozen library contains only 12 candidate blocks per anchor. K2 has 11–12 metric-common anchors over 4–5 buildings, while K3 has 6–7 over four buildings; this sparse support is partly a sampling-library limitation. Conditional means vary with n and do not establish a usable m5 role. At n17, within verified corner-count mismatch is 8% for K2 versus 0% for its Rnew2 subset, and 6.25% for K3 versus 0% on its own subset. Do not extrapolate n5 apparent gains to other n or use them to select a winner.

## Artifacts and reproduction
FULL_FAMILY_SUMMARY.csv retains all raw-h, pair-scale, local-radius, angle-sensitivity and risk summaries. Each candidate directory retains raw pair outcomes, exact members and class-count vectors, method arms, common-anchor ledgers, building estimates and hashed receipt. The frozen training labels and negative selection are in audit_learning/block_fit.

Run `python audit_corner/evaluate_direct_block_family.py --root WORK_ROOT`. This reuses common_library/COMMON_ENDPOINT_PAIRS.csv.gz and requires no new native fusion. No human similarity threshold is inferred.

## Independent verification
Independent audit in `audit_statistics/direct_block_assessment` verified all 63,476 pair identities, worker sets, class-count vectors, arm assignments, pure-class flags and failure types for each candidate. All 3,456 aggregate values per candidate matched within 2.22e-16. Building-bootstrap intervals for K3's apparently favorable n9 mean-BEV within/gap comparison span zero. This reinforces retaining the frozen negative selection rather than promoting that isolated result.
