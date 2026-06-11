# Task 533 / GT row 75 Single-image Assist Summary

Expert-side diagnostic only. The source GT row has two annotation results; this report does not adjudicate which one is final GT.

| candidate | annotation_id | preview_status | n_pairs | align_x eligible | align_x review_only | height applicable | height review_only | height suppress | report |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| candidate_a_annotation_2226 | 2226 | compatible | 8 | 0 | 8 | 8 | 0 | 0 | analysis_results/paper_a_manhattan/single_image_manual_test/task533_gt75/candidate_a_annotation_2226_report.md |
| candidate_b_annotation_3425 | 3425 | compatibility_failure_duplicate | 0 | 0 | 0 | 0 | 0 | 0 | analysis_results/paper_a_manhattan/single_image_manual_test/task533_gt75/candidate_b_annotation_3425_report.md |

## Interpretation

- candidate A / annotation 2226: preview-compatible, 8 ordered pairs. No Align Pair X row is eligible because each pair already has vertical_x_residual=0; height applicability is eligible for all 8 pairs. There is no x micro-adjustment to apply from this tool.
- candidate B / annotation 3425: preview-incompatible with `compatibility_failure_duplicate` / `near_duplicate_corner_pair`. Do not use the manual edit table; inspect or simplify duplicated/extra keypoints manually first.

## Generated files

- `candidate_a_annotation_2226`:
  - input: `analysis_results\paper_a_manhattan\single_image_manual_test\task533_gt75\candidate_a_annotation_2226_input.json`
  - output: `analysis_results/paper_a_manhattan/single_image_manual_test/task533_gt75/candidate_a_annotation_2226_output.json`
  - report: `analysis_results/paper_a_manhattan/single_image_manual_test/task533_gt75/candidate_a_annotation_2226_report.md`
- `candidate_b_annotation_3425`:
  - input: `analysis_results\paper_a_manhattan\single_image_manual_test\task533_gt75\candidate_b_annotation_3425_input.json`
  - output: `analysis_results/paper_a_manhattan/single_image_manual_test/task533_gt75/candidate_b_annotation_3425_output.json`
  - report: `analysis_results/paper_a_manhattan/single_image_manual_test/task533_gt75/candidate_b_annotation_3425_report.md`
