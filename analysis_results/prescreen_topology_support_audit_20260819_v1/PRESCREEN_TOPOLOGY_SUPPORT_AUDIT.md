# PreScreen topology support audit v1

Development-only diagnostic. It does not change P1/C1 eligibility, repair raw submissions, freeze a policy, or authorize Main.

## Denominator finding

- Frozen C1 manual high-k inventory remains 78 images. PreScreen contributes 29 additional, disjoint, final-in-scope manual images; the two stages must remain separate analysis strata.
- C1-admitted PreScreen support: 662 valid rows across 29 images, valid k=21–23; all 29 reach k>=5.
- Current-20 sensitivity: 576 valid rows, valid k=19–20; all 29 reach k>=5.
- Therefore the earlier 47-task figure is not the total historical high-k inventory. It is a C1-only current-roster/dual-validity sensitivity denominator.

## Filter audit

- Exactly 5 C1-admitted in-scope manual rows fail the current calculation normalizer.
- No row satisfies the unique-orphan repair rule. Ambiguous single-point deletions remain invalid; two out-of-range rows contain the same raw y=761.1879% source artifact and cannot be silently decimal-corrected.
- Restoring all five rows would not add a k>=5 task because every affected task already has much more than five valid candidates.
- The 86 in-scope rows from workers 19, 21 and 26 are excluded by frozen worker admission, not by geometry filtering. The all-completed result is retained only as an inadmissible sensitivity.
- Semi and OOS records are retained in separate lanes; they are not discarded, but are not pooled into the manual topology replay.

## Conservative M1 replay (1,000 permutations per image)

- C1-admitted combined: stop@3=0.5457, incremental stop@4=0.1473, reach5=0.3070, mean valid k=3.7613.
- Current-20: stop@3=0.5401, incremental stop@4=0.1510, reach5=0.3089, mean valid k=3.7688.
- Chinese and English cohorts are reported separately because they differ materially; pooling without a cohort stratum would conceal transportability risk.
- Prefix/full-k5 selected annotation mismatch is a stability diagnostic, not delivery harm. No expert-acceptable topology or actual delivery-harm label exists here, so safety and quality remain unidentified.

## Valid interpretation

The audit supports using the 29 PreScreen images as a stage-stratified development sensitivity alongside, not merged into, the 78-image frozen C1 replay. PreScreen selected the workers, so it is resubstitution evidence and cannot independently validate the policy. The 29 images span 11 buildings, all already represented in C1, so they add image-level support but no new building domain.
