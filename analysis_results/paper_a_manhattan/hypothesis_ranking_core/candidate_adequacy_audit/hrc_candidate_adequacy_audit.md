# HRC C6.4 Candidate Adequacy Audit

- Schema: `hrc_candidate_adequacy_audit_v1`
- Adequate for C6.3e bucket audit: `False`
- Adequate for hard-case fix claim: `False`
- Recommended next step: `collect/materialize missing real candidate source for ordinary_compatible`
- Accepted: `False`
- Downstream recommendation: `False`

## Case summaries

- `task218_ann3741`: status=`available`, candidates=91, actions={'vertical_column_align_x': 1, 'endpoint_anchor_align_x': 2, 'azimuth_translate_keep_top_bottom_delta': 24, 'edge_6_7_azimuth_open_close': 8, 'edge_6_7_floor_depth_balance': 16, 'edge_6_7_normal_slide_proxy': 8, 'preserve_5_6_short_wall_block_x': 8, 'preserve_5_6_length_with_6_7_fix': 8, 'height_outlier_pull_top_y': 16}
- `task218_ann2369`: status=`available`, candidates=8, actions={'fixed_bottom_top_y_reproject': 8}
- `task238_ann2389`: status=`available`, candidates=6, actions={'fixed_bottom_top_y_reproject': 6}
- `gt75_task533`: status=`available`, candidates=10, actions={'fixed_bottom_top_y_reproject': 10}
- `ordinary_compatible`: status=`unavailable`, candidates=0, actions={}

## Missing candidate dimensions

- `gt75_task533:floor_depth_change`
- `gt75_task533:global_layout_change`
- `gt75_task533:topology_change`
- `gt75_task533:x_change`
- `ordinary_compatible:floor_depth_change`
- `ordinary_compatible:global_layout_change`
- `ordinary_compatible:topology_change`
- `ordinary_compatible:x_change`
- `ordinary_compatible_real_candidate_source`
- `task218_ann2369:floor_depth_change`
- `task218_ann2369:global_layout_change`
- `task218_ann2369:topology_change`
- `task218_ann2369:x_change`
- `task218_ann3741:topology_change`
- `task238_ann2389:floor_depth_change`
- `task238_ann2389:global_layout_change`
- `task238_ann2389:topology_change`
- `task238_ann2389:x_change`
