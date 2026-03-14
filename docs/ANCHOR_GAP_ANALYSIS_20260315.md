# ANCHOR SET GAP ANALYSIS & SUPPLEMENTATION PLAN (2026-03-15)

## 1. Overview
User requires:
- **Manual Anchor Set**: 20-22 images, covering difficulty options and glass interference.
- **Semi Anchor Set**: 18 images, covering typical errors (natural failures) and potentially synthetic errors (future).

## 2. Manual Anchor Set Analysis
Current bank (`manual_anchor_bank_index_v1.csv`) has 24 unique base tasks.
However, it **misses** key difficulty types mentioned in the user's `trap集` audit.

### Missing Critical Cases (To Be Added):
| Task ID | Type | Basename | Justification |
| :--- | :--- | :--- | :--- |
| **task497** | Occlusion (遮挡明显) | `uNb9QFRL6hY_d02f87bbb0414146a7a15070110a0384` | User requirement: "cover all options". GT=4, stable closure despite occlusion. |
| **task462** | Seam/Stretch (拼接缝) | `UwV83HsGsw3_8e9c912f525744eeaea21083a20a1596` | User requirement: "cover all options". GT=4, difficult manual case. |
| **task509** | Glass (玻璃) | `wc2JMjhGNzB_dc4a9f470b834de1983c7e605ff06b2e` | User requirement: "glass interference". Critical for checking reflection handling. |
| **task510** | Seam/Stretch (拼接缝) | `B6ByNegPMKs_b8e1ecf1bd044e7292581a66683e7993` | Additional coverage for distortion/seam issues. |

### Proposed Manual Set Structure (Target: ~24):
We will add these 4 tasks to the existing 24. Total = 28.
We can label the new ones as `prescreen_manual` (since they are difficult cases suitable for screening expert capability).
*Action*: Append these 4 rows to `manual_anchor_bank_index_v1.csv`.

**Note**: Since these tasks are not in the current `merged_all_v0.csv` (based on grep check), we will mark their `registry_uids` as `manual_supplement` or leave blank if they are purely from the `trap集` file system.

## 3. Semi Anchor Set Analysis
Current bank (`natural_failure_bank_index_v1.csv`) has 15 entries.
Target: 18.
Gap: 3 images.

### Strategy:
- **Keep existing 15**: They cover typical natural failures well (Good Model, Model Fail, Over Parsing, Drift, Duplicate, Overextend, OOS).
- **Reserve 3 slots for Synthetic Traps**: User mentioned "wait for script to generate error corners".
- **Conclusion**: The current set of 15 is sufficient for *Natural Failures*. The remaining 3 to reach 18 will be filled by *Synthetic Failures* later. No need to force-add manual cases as semi traps now unless we find specifically "semi-initialized but wrong" cases in the `trap集`.

### Verification of Semi Candidates in `trap集`:
- `task474`, `task477`, `task493`, `task499`, `task505`, `task475` are already in the bank.
- `task492`, `task501` are already in the bank.
- `task526`, `task529`, `task533`, `task459`, `task476`, `task495`, `task496` are in the bank (mostly as OOS gates).
- **Result**: We have utilized the `trap集` well for Semi/Natural Failures.

## 4. Action Items
1.  **Update `manual_anchor_bank_index_v1.csv`**: Add `task497`, `task462`, `task509`, `task510`.
    -   Role: `prescreen_manual` (likely).
    -   Source: `trap_collection`.
2.  **Report**: Confirm to user that Manual set is expanded to cover all difficulty options (including Glass), and Semi set stands at 15 natural failures + 3 pending synthetic slots.

## 5. CSV Update Content (Draft)
```csv
base_task_id,planned_stage,dataset_group,condition,source_pools,registry_uids,registry_row_count,has_expert_ref,init_type
...[existing 24 rows]...
uNb9QFRL6hY_d02f87bbb0414146a7a15070110a0384,prescreen_manual,PreScreen_manual,manual,trap_collection,,0,True,
UwV83HsGsw3_8e9c912f525744eeaea21083a20a1596,prescreen_manual,PreScreen_manual,manual,trap_collection,,0,True,
wc2JMjhGNzB_dc4a9f470b834de1983c7e605ff06b2e,prescreen_manual,PreScreen_manual,manual,trap_collection,,0,True,
B6ByNegPMKs_b8e1ecf1bd044e7292581a66683e7993,prescreen_manual,PreScreen_manual,manual,trap_collection,,0,True,
```
