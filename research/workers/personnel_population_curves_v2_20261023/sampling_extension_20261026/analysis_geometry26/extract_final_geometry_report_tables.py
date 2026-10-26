"""Read completed geometry outputs and save report-sized selections only."""
from pathlib import Path
import argparse,hashlib,json
import pandas as pd
from safe_io import atomic_bytes,install_safe_csv_writer
install_safe_csv_writer()
COHORTS=['old48','stage1_104','stage2_104','new208','pooled256']

def selected_panel(d):
    return ((d.layer.eq('ordinary_manual')&d.panel.isin(['fixed_N_ge_30','fixed_N_ge_35']))|
        (d.layer.eq('doorway_manual')&d.panel.isin(['fixed_N_ge_27','fixed_N_ge_30'])&d.difficulty.eq('单列')))

def main(root):
    gate=json.loads((root/'GEOMETRY_FINALIZATION_COMPLETE.json').read_text());assert gate['complete'] and gate['pools']==194
    source=root/'results_stage2';out=source/'final_report_readout';out.mkdir(exist_ok=True)
    receipts=[]
    for filename,outname,select in [
      ('GEOMETRY_STRICT_COMMON_CURVE_SUMMARY.csv.gz','KEY_COMPLETE_CURVES.csv',lambda d:selected_panel(d)&d.cohort.isin(COHORTS)&d.k.isin([1,3,6,10,20,27,30,34,35])),
      ('GEOMETRY_FIXED_SUPPORT_INTERVALS.csv.gz','KEY_PAIRED_INTERVALS.csv',lambda d:selected_panel(d)&d.cohort.isin(COHORTS)&pd.Series([(a,b) in [(3,6),(6,10),(10,20),(20,30),(30,35)] for a,b in zip(d.k_from,d.k_to)],index=d.index)),
      ('GEOMETRY_TO_ACTUAL_FULL_SUMMARY.csv','KEY_TO_ACTUAL_FULL.csv',lambda d:selected_panel(d)&d.cohort.isin(COHORTS)&d.k_from.isin([20,30])),
      ('GEOMETRY_SINGLE_IMAGE_PRECISION_CHANGES.csv.gz','KEY_SINGLE_IMAGE_PRECISION.csv',lambda d:selected_panel(d)&d.comparison.isin(['old48_vs_new208','old48_vs_pooled256','stage1_104_vs_stage2_104'])&d.k.isin([1,3,6,10,20,30])),
      ('GEOMETRY_COMMON_SUPPORT_BATCH_CHANGES.csv.gz','KEY_BATCH_POINT_CHANGES.csv',lambda d:selected_panel(d)&d.comparison.isin(['old48_vs_new208','stage1_104_vs_stage2_104'])&d.k.isin([1,3,6,10,20,30]))]:
        d=pd.read_csv(source/filename);s=d[select(d)].copy();s.to_csv(out/outname,index=False);assert len(pd.read_csv(out/outname))==len(s)
        receipts.append(dict(source=filename,output=outname,rows=len(s)))
    d=pd.read_csv(source/'GEOMETRY_DISTANCE_COMPUTE_ACCOUNTING.csv.gz');actual=int(d.distinct_polygon_pair_evaluations.sum());baseline=int(d.team_pair_evaluations_without_footprint_dedup.sum())
    cost=dict(pools=d.pool_id.nunique(),pool_k_rows=len(d),distinct_polygon_pair_evaluations=actual,
        team_pairs_without_exact_footprint_dedup=baseline,logical_pair_evaluations_saved=baseline-actual,
        logical_saving_fraction=(baseline-actual)/baseline,
        description='logical saved polygon-distance evaluations, once per pool/k; not physical hardware time, process rerun accounting or new independent samples',
        exact_coordinate_byte_dedup=True,path_frequency_weights_unchanged=True)
    atomic_bytes(out/'LOGICAL_DISTANCE_COMPUTE_SAVING.json',json.dumps(cost,ensure_ascii=False,indent=2).encode())
    # Finite display case: existing complete saved path rows, no new geometry.
    case=root/'low_k_cases/yqstnuAEVhm-31__manual__7b26e5d3cd__k5';d=pd.read_csv(case/'CASE_ALL_PATHS_AND_ENDPOINTS.csv.gz')
    batches={'old48':{'old24','prior_new24'},'stage1_104':{'extension_stage1_104'},'stage2_104':{'extension_stage2_104'},
        'new208':{'extension_stage1_104','extension_stage2_104'},'pooled256':{'old24','prior_new24','extension_stage1_104','extension_stage2_104'}}
    rows=[]
    for cohort,bb in batches.items():
        a=d[d.batch.isin(bb)];rows.append(dict(pool_id=a.pool_id.iloc[0],k=5,cohort=cohort,paths=len(a),scoreable=int(a.B8L2.notna().sum()),
            Q_lt10_count=int(a.B8L2.lt(10).sum()),Q_lt20_count=int(a.B8L2.lt(20).sum()),IoU2D_lt0p2_count=int(a.iou_2d.lt(.2).sum()),
            nodes_le5_count=int(a.nodes.le(5).sum()),node_histogram=json.dumps(a.nodes.value_counts().sort_index().to_dict()),
            threshold_role='posthoc descriptive display counts, not selection/training or registered hypothesis',new_fusions=0))
    pd.DataFrame(rows).to_csv(case/'CASE_DISPLAY_FREQUENCY_COUNTS.csv',index=False)
    result=dict(complete_input_gate=gate,readout_tables=receipts,logical_distance_accounting=cost,
        case_display_frequency_rows=len(rows),new_fusions=0,new_paths=0,new_bootstrap=0)
    atomic_bytes(out/'READOUT_RECEIPT.json',json.dumps(result,ensure_ascii=False,indent=2).encode());print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args();main(a.root.resolve())
