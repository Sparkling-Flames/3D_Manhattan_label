#!/usr/bin/env python3
"""Read saved completed results, preserve exact u64 seed strings, make receipts.

No new bootstrap, fusion, score, or estimate. This also finalizes a completed
policy-only restart without rerunning already saved numerical results.
"""
from pathlib import Path
import argparse,csv,gzip,hashlib,json
import numpy as np
import pandas as pd
from rebuild_path_stability import seed_for

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);ap.add_argument('--seed',type=int,default=2026102307);ap.add_argument('--replicates',type=int,default=2000);a=ap.parse_args();r=a.root/'results'
    for fname,axis in [('NATURAL_CURVE_STABILITY.csv','k'),('NATURAL_INTERVAL_STABILITY.csv','interval'),('POLICY_EARLY_STABILITY.csv','phase')]:
        d=pd.read_csv(r/fname,low_memory=False);assert d.bootstrap_replicates.eq(a.replicates).all()
        seeds=[]
        for row in d.to_dict('records'):
            scope={k:row[k] for k in ['condition','layer','difficulty']}
            if axis=='phase':scope.update({k:row[k] for k in ['policy','policy_support']})
            scope['axis']=axis
            s=seed_for(a.seed,'building',json.dumps(scope,sort_keys=True,ensure_ascii=False))
            seeds.append('u64:'+str(s) if row['resampling']=='building_resampling_fixed_paths' else '')
        d['building_seed']=seeds;d.to_csv(r/fname,index=False)
    curves=pd.read_csv(r/'NATURAL_IMAGE_CURVES_REBUILT.csv.gz');meta=curves[['pool_id','building']].drop_duplicates();phase=pd.read_csv(r/'POLICY_EARLY_IMAGE_REBUILT.csv');design=pd.read_csv(a.root/'inputs/EXACT_ORDER_DESIGN.csv.gz',low_memory=False)
    seedtable=pd.read_csv(r/'EXACT_BOOTSTRAP_SEEDS.csv',dtype={'seed':str});assert len(seedtable)==2*len(meta)
    for x in seedtable.to_dict('records'):
        kind='natural_path' if x['kind']=='natural_whole_paths' else 'paired_base_path';assert int(x['seed'])==seed_for(a.seed,kind,x['pool_id'])
    common=phase.groupby('pool_id').policy.nunique();common=int(common.eq(4).sum())
    receipt=dict(operation='fixed_saved_design_new_bootstrap_implementation',source_commit='e92abe8631d7f01dc192ee796b46f295ece37a6d',new_fusion=0,new_team_design=0,new_member_orders=0,new_scoring=0,replicates=a.replicates,master_seed=a.seed,natural_paths_per_main_pool=24,paired_base_paths_per_main_pool=8,natural_N20_pools=len(meta),natural_N20_buildings=int(meta.building.nunique()),policy_pools_by_policy=phase.groupby('policy').pool_id.nunique().to_dict(),policy_common_four_pools=common,natural_k=list(range(1,21)),intervals=[[3,6],[6,10],[10,20],[3,20]],policy_phase='3<=k<=floor(N/2)',q_p10='within_image_valid_path_quantile_numpy_linear',q_sd='within_image_valid_path_sample_standard_deviation_ddof1',failure_denominator='all_attempted_paths_k2_policy_defer_separate',quality_missing='remain_nan_never_zero_score',strategy_quality_support='natural_and_priority_both_scored_at_same_k',time='legacy_known_n_only_columns_retained; authoritative_QT_uses_single_known_kind_per_team_and_same_kind_per_pair; see results/time_semantics/CORRECTION_RECEIPT.json',bootstrap_types=['whole_paths_within_each_fixed_image','whole_buildings_with_observed_paths_fixed'],interval_type='pointwise_percentile_95_not_simultaneous_band',path_and_building_uncertainty_not_combined=True,completion_note='Natural outputs completed first; identical-seed policy restart after vectorizing linear quantiles; no analysis rule or budget changed.')
    correction=r/'time_semantics/CORRECTION_RECEIPT.json'
    if correction.exists():receipt['targeted_time_semantics_correction']=json.loads(correction.read_text())
    (r/'ANALYSIS_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    files=[]
    for directory in [a.root/'inputs',r]:
        for p in sorted(directory.rglob("*")):
            if not p.is_file():continue
            data=p.read_bytes();rec=dict(path=p.relative_to(a.root).as_posix(),bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),read_to_eof=True)
            if p.name.endswith(('.csv','.csv.gz')):
                if p.suffix=='.gz':plain=gzip.decompress(data).decode('utf-8-sig')
                else:plain=data.decode('utf-8-sig')
                import io
                reader=csv.DictReader(io.StringIO(plain,newline=''));n=0
                for row in reader:assert None not in row;n+=1
                rec.update(rows=n,fields=reader.fieldnames)
            elif p.suffix=='.json':json.loads(data)
            files.append(rec)
    (a.root/'READ_TO_EOF_RECEIPT.json').write_text(json.dumps(dict(status='passed',operation='read_final_actual_input_and_output_files',files=files),ensure_ascii=False,indent=2)+'\n');print(json.dumps(receipt,ensure_ascii=False))

if __name__=='__main__':main()
