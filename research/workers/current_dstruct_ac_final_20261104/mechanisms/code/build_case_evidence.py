"""Bind frozen illustrative cases to saved native traces and current metadata.

No scoring or fusion is executed here. Every endpoint core remains the original
saved endpoint; only independently verified native diagnostics are attached.
"""
from __future__ import annotations
import collections, json, sys
from pathlib import Path
import pandas as pd
from mechanism_core import ROOT, OUT, COMMIT, clean, read_json, save_json, save_csv, sha, ws, diagnose_pair, endpoint_ring_summary

OLD = ROOT/'research/workers/personnel_ac_v21_20261030'
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(OLD/'stage06_cases/code'))
sys.path.insert(0, str(OLD/'stage02_engine/code'))
from export_ac_mechanisms import diagnose_case
import ac_endpoint_runtime as runtime
from tools.thesis_main.analysis.fixed_identity_location_20261007 import median_pair

LABELS=ROOT/'research/data/releases/v2.1/admitted_space_extension/image_difficulty_20261030/classification/LABELS_ALL_LOBO.csv.gz'
METRICS=OUT.parent/'analysis/PHYSICAL_PAIRS_AUTOMATIC.csv.gz'
LABOR=OUT.parent/'analysis/CURRENT_RECORD_LABOR_INDEX.csv.gz'
ABC=ROOT/'research/workers/mixture_patterns_and_c13_half_20261104/c13_half/analysis/ILLUSTRATIVE_CASES.json.gz'
APPROVED=ROOT/'research/fusion/manual_order_impact_20261104/endpoints/ENDPOINT_SCORES.csv'

def main():
    selected=pd.read_csv(OUT/'CASE_SELECTION.csv',keep_default_na=False).to_dict('records')
    pools={p['pool_id']:p for p in read_json(OUT/'source/DIAGNOSTIC_POOLS.json.gz')['images']}
    labels=pd.read_csv(LABELS,keep_default_na=False)
    labels=labels[labels.method.eq('TARGET_DSTRUCT_K3')]
    metrics=pd.read_csv(METRICS,low_memory=False).set_index('canonical_physical_pair_id')
    labor=pd.read_csv(LABOR,keep_default_na=False)
    origins=pd.read_csv(OUT/'source/SAVED_LEGACY_ENDPOINT_ORIGINS.csv',keep_default_na=False).set_index('team_key')
    approved=pd.read_csv(APPROVED,keep_default_na=False)
    save_csv(OUT/'source/APPROVED_MANUAL_ORDER_IDENTITY_INDEX.csv',approved[['team_key','pool_id','reference_id','reference_version','review_id','group_id']])
    rows=collections.defaultdict(list); summaries=[]; manifests=[]; all_links=[]; compact=[]; manual_checks=[]
    for selection in selected:
        event=dict(selection)
        event.update(method='当前 DSTRUCT K3', equal_team_size=True,
                     source_class=selection['source_class_current'],target_class=selection['target_class_current'])
        pool=pools[event['pool_id']]
        arms={a:read_json(OUT/'trace_endpoints'/(selection[a+'_team_key']+'.json.gz')) for a in ('A','C')}
        for arm in arms.values():
            assert arm['trace_replay_parity']['full_geometry_json_hash_identical']
            assert arm['reference_id']==pool['meta']['reference_id']
        case_manual={}
        for name,arm in arms.items():
            exact=approved[approved.team_key.eq(arm['team_key']) & approved.pool_id.eq(arm['pool_id']) & approved.reference_id.eq(arm['reference_id']) & approved.reference_version.eq(arm['reference_version'])]
            c=dict(case_id=event['case_id'],arm=name,team_key=arm['team_key'],pool_id=arm['pool_id'],reference_id=arm['reference_id'],reference_version=arm['reference_version'],
                   exact_team_pool_reference_match=not exact.empty,approved_result_available=not exact.empty,
                   approved_source=str(APPROVED.relative_to(ROOT)),approved_source_sha256=sha(APPROVED),
                   no_forced_connection=True)
            assert exact.empty,'A matching approved result requires an explicit parallel display; do not silently overwrite automatic output.'
            manual_checks.append(c);case_manual[name]=c
        members=set(ws(event['D_workers'])+ws(event['X_workers'])+ws(event['Z_workers']))
        local=labels[labels.heldout_building.eq(event['building']) & labels.worker_id.isin(members)]
        assert local.worker_id.nunique()==len(members) and len(local)==len(members)
        frozen={str(r['worker_id']):r for r in local.to_dict('records')}
        for block,category in [('X',event['source_class_current']),('Z',event['target_class_current'])]:
            assert all(frozen[w]['class_id']==category and frozen[w]['known'] in (True,'True','true') for w in ws(event[block+'_workers']))
        current=clean(metrics.loc[event['canonical_pair_id']].to_dict())
        assert current['A_team_key']==arms['A']['team_key'] and current['C_team_key']==arms['C']['team_key']
        local_labor=labor[labor.pool_id.eq(event['pool_id']) & labor.worker_id.isin(members)].to_dict('records')
        assert len(local_labor)==len(members)
        for rec in local_labor:
            native=next(r for r in pool['records'] if r['worker_id']==rec['worker_id'])
            assert rec['object_id']==native['object_id']
        summary,links=diagnose_pair(event,arms['A'],arms['C'],pool)
        case=dict(case_id=event['case_id'],event=event,selection=selection,pool=pool,reference=pool['reference'],arms=arms,
                  frozen_lobo_labels=frozen,current_metrics=current,current_record_labor=local_labor,
                  metrics=current,mechanisms=summary,D_anchor_links=links,approved_manual_order_match=case_manual,
                  endpoint_ring_summaries={a:endpoint_ring_summary(r) for a,r in arms.items()},
                  provenance=dict(source_commit=COMMIT,labels_path=str(LABELS.relative_to(ROOT)),labels_sha256=sha(LABELS),
                    selected_label_method='TARGET_DSTRUCT_K3',heldout_building=event['building'],
                    physical_pair_origin='legacy_target_stock_current_label_conditional',
                    endpoint_sources={a:origins.loc[r['team_key']].to_dict() for a,r in arms.items()},
                    existing_native_geometry_preserved=True,score_contract_unchanged=True,post_outcome_case_selection=True),
                  interpretation_limits=[
                    'Illustrative cases are selected after observing outcomes; their frequency is not a population estimate.',
                    'All classes are target-image outside-building labels, not descriptive all-building assignments.',
                    'The common D background may be mixed. D is held exactly constant between A and C.',
                    'Cross-arm stable groups require the exact same nonempty set of original D observation IDs and pair indices.',
                    'Local feature IDs are arm-local. Spatial proximity or equal group numbers are not evidence of node identity.',
                    'No detected stable-anchor crossing does not rule out mechanisms in ambiguously regrouped nodes.',
                    'Current recorded labor is from legal same-origin records. Missing time is never zero; labor is not full workflow cost.',
                    'The engine retains source_suggestion / unconfirmed ring metadata even when the geometry can be scored.',
                    'The frozen reference can be an adopted user target; use the displayed reference version, not an assumed universal GT.'
                  ])
        diagnostics=diagnose_case(case,median_pair,runtime)
        for name,data in diagnostics.items():
            for r in data:r['case_id']=event['case_id']
            rows[name].extend(data)
        for r in links:r['case_id']=event['case_id']
        all_links.extend(links)
        summaries.append(dict(case_id=event['case_id'],**summary,
                              official_difficulty=current['official_difficulty'],room_type=current['room_type'],
                              selection_roles=selection['selection_roles']))
        path=OUT/'cases'/(event['case_id']+'.json.gz');save_json(path,case)
        manifests.append(dict(case_id=event['case_id'],event_id=event['event_id'],image=event['image'],path=str(path.relative_to(OUT)),sha256=sha(path),
                              n=event['n'],m=event['m'],class_pair=event['class_pair'],delta_Q=summary['delta_Q']))
        c={k:current[k] for k in ('official_difficulty','room_type','A_B8L2','C_B8L2','dQ','A_iou_2d','C_iou_2d','A_S_bottom_deg','C_S_bottom_deg','A_dir','C_dir','A_Hmean','C_Hmean','A_Hcenter','C_Hcenter','A_nodes','C_nodes','A_fusion_turn_n','C_fusion_turn_n','A_fusion_short_turn_edges','C_fusion_short_turn_edges','A_geometry_area_h2','C_geometry_area_h2','geometry_bev_distance_AC','geometry_centroid_distance_AC','A_matched_ref_top_abs_deg','C_matched_ref_top_abs_deg','A_matched_ref_bottom_abs_deg','C_matched_ref_bottom_abs_deg','A_matched_ref_horizontal_abs_deg','C_matched_ref_horizontal_abs_deg','A_ref_node_recall_9','C_ref_node_recall_9','A_recorded_labor_total','C_recorded_labor_total','dT_whole','time_whole_single_source')}
        c.update(case_id=event['case_id'],image=event['image'],class_pair=event['class_pair'],n=event['n'],m=event['m'])
        c.update({k:summary[k] for k in ('stable_threshold_cross_up','stable_threshold_cross_down','D_partition_changed','A_source_complete_rings','C_source_complete_rings')})
        compact.append(c)
    save_csv(OUT/'CASE_NATIVE_MECHANISMS.csv',summaries)
    save_csv(OUT/'CASE_APPROVED_MANUAL_ORDER_MATCH.csv',manual_checks)
    save_csv(OUT/'CASE_METRIC_EVIDENCE.csv',compact)
    save_csv(OUT/'CASE_D_ANCHOR_LINKS.csv.gz',all_links)
    for name,data in rows.items():save_csv(OUT/'tables'/(name+'.csv.gz'),data)
    # A copied, already published ABC example supplies a boundary to the high-Q
    # explanation. It is never treated as a 249th diagnostic AC pair.
    abc=next(r for r in read_json(ABC) if r['event_id']=='C13_f5da0dd1fdd351c111b27ef5')
    abc.update(appendix_only=True,not_current_AC_sample=True,source_path=str(ABC.relative_to(ROOT)),source_sha256=sha(ABC),
               no_new_fusion=True,no_new_scoring=True,no_recalculated_GS=True,
               note_zh='引用第12批既有严格ABC；GS是原保存逐图均值，本页A/B/C是既有代表事件，两者不可混称同一事件统计。')
    save_json(OUT/'cases/APPENDIX_EXISTING_ABC.json.gz',abc)
    receipt=dict(cases=manifests,case_count=len(manifests),unique_physical_AC_pairs=len(manifests),
                 unique_AC_endpoint_keys=len({c[a+'_team_key'] for c in selected for a in ('A','C')}),
                 diagnostic_sample_unchanged=True,appendix_existing_ABC=1,appendix_in_diagnostic_denominator=False,
                 new_fusions=0,new_scores=0,new_physical_teams=0)
    save_json(OUT/'CASE_EVIDENCE_RECEIPT.json',receipt)
    print(json.dumps(dict(cases=len(manifests),tables=len(rows),all_votes=sum(len(r) for r in rows.values())),ensure_ascii=False))

if __name__=='__main__':main()
