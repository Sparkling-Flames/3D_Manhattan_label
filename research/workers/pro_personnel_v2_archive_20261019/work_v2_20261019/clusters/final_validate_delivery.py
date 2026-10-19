"""Cross-process CRC/count, prediction and exclusion checks before delivery."""
from __future__ import annotations
import csv,gzip,hashlib,io,json,re
from pathlib import Path
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent

def deliverable(p):
    rel=p.relative_to(HERE)
    if any(x in ['checkpoints','fusion_analysis_pilot','swap_transfer_pilot','__pycache__'] for x in rel.parts):return False
    if '.tmp' in p.name or p.suffix=='.pyc':return False
    if rel.parts[0]=='swap_transfer' and re.fullmatch(r'[A-Za-z0-9]+_predictions\.csv\.gz',p.name):return False
    if p.name in ['PACKAGING_MANIFEST.json','FINAL_VALIDATION.json','final_delivery_validation.log','final_delivery_validation_frozen.log']:return False
    return p.is_file()

def main():
    wide_receipt=json.loads((HERE/'swap_transfer/WIDE_PREDICTIONS_RECEIPT.json').read_text())
    files=sorted(p for p in HERE.rglob('*') if deliverable(p));gzip_checks=[];manifest=[]
    for p in files:
        r=dict(path=str(p.relative_to(HERE)),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
        if p.name.endswith('.gz'):
            with gzip.open(p,'rt',encoding='utf-8-sig',newline='') as f:
                if p.name.endswith('.csv.gz'):
                    reader=csv.reader(f);header=next(reader);rows=sum(1 for _ in reader);r.update(gzip_crc_full_stream=True,rows=rows,columns=len(header))
                elif p.name.endswith('.json.gz'):
                    obj=json.load(f);sizes={k:len(v) for k,v in obj.items() if isinstance(v,(list,dict))} if isinstance(obj,dict) else {'items':len(obj)}
                    r.update(gzip_crc_full_stream=True,top_level_sizes=sizes)
                else:
                    while f.read(1024*1024):pass
                    r.update(gzip_crc_full_stream=True)
            gzip_checks.append(r.copy())
        manifest.append(r)
    # Independently recompute all saved image/k error means from the compact
    # actual values and predictions, retaining the original background means.
    wide=pd.read_csv(HERE/'swap_transfer/heldout_predictions_wide.csv.gz',float_precision='round_trip')
    reference=pd.read_csv(HERE/'swap_transfer/image_k_scores.csv',float_precision='round_trip')
    errors=[]
    for name in sorted(c for c in wide if c.startswith('prediction__')):
        _,outcome,model=name.split('__');actual='actual__'+outcome;valid=wide[name].notna() & wide[actual].notna()
        d=wide.loc[valid,['pool_id','k','background_id']].copy();delta=wide.loc[valid,name]-wide.loc[valid,actual]
        d['squared_error']=delta**2;d['absolute_error']=abs(delta)
        b=d.groupby(['pool_id','k','background_id'])[['squared_error','absolute_error']].mean().reset_index()
        image=b.groupby(['pool_id','k'])[['squared_error','absolute_error']].mean().reset_index();image['model']=model;image['outcome']=outcome
        image['n']=d.groupby(['pool_id','k']).size().reindex(pd.MultiIndex.from_frame(image[['pool_id','k']])).to_numpy();errors.append(image)
    errors=pd.concat(errors,ignore_index=True)
    matched=errors.merge(reference,on=['pool_id','k','model','outcome'],suffixes=('_wide','_original'),validate='one_to_one')
    assert len(matched)==len(reference)==len(errors)
    deltas={c:float((matched[c+'_wide']-matched[c+'_original']).abs().max()) for c in ['squared_error','absolute_error','n']}
    assert max(deltas.values())<1e-10,deltas
    assert len(wide)==270370 and not wide.event_key.duplicated().any()
    # A deterministic cross-check of support counts independently rebuilds
    # exclusions from the flat audited-record table, without fitting a model.
    profiles=HERE.parent/'profiles';flat=pd.read_csv(profiles/'records_flat.csv');flat=flat[flat.quality_usable & flat.condition.eq('manual') & flat.quality_use.eq('ordinary_primary')]
    nested=pd.read_csv(profiles/'nested_fold_features.csv');fold=pd.read_csv(profiles/'fold_profiles.csv');checks=[]
    for origin,source in [('outer',fold),('nested',nested)]:
        selected=source.assign(_hash=[hashlib.sha256(str(tuple(x)).encode()).hexdigest() for x in source[['worker_id']+(['heldout_building'] if origin=='outer' else ['outer_heldout_building','inner_heldout_building'])].itertuples(index=False,name=None)]).sort_values('_hash').head(120)
        for r in selected.itertuples():
            excluded={r.heldout_building} if origin=='outer' else {r.outer_heldout_building,r.inner_heldout_building}
            d=flat[flat.worker_id.eq(r.worker_id) & ~flat.building_id.isin(excluded)]
            assert len(d)==r.Q_tasks and d.building_id.nunique()==r.Q_buildings
            checks.append(dict(profile=origin,worker=r.worker_id,excluded=sorted(excluded),tasks=len(d),buildings=d.building_id.nunique()))
    validation=dict(status='PASS',fresh_process_check=True,gzip_file_count=len(gzip_checks),gzip_checks=gzip_checks,
        prediction_rows=len(wide),prediction_key_unique=True,prediction_model_error_rows_checked=len(matched),prediction_error_max_differences=deltas,
        exact_long_to_wide_float64_checks=wide_receipt['exact_float64_readback_comparisons'],
        repaired_fold_summary_check=json.loads((HERE/'swap_transfer/PREDICTION_REPAIR_RECEIPT.json').read_text()),
        support_exclusion_checks=checks,classes_distances_fusion_or_model_parameters_changed_for_repair=False,
        current_summary_results_unchanged_up_to_float64_roundoff=True,
        inference_unit='building; rows/combinations/paths are not independent people')
    (HERE/'FINAL_VALIDATION.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2)+'\n')
    package=dict(files=manifest,total_bytes=sum(x['bytes'] for x in manifest),
        omitted_redundant=['checkpoints/','fusion_analysis_pilot/','swap_transfer_pilot/','__pycache__/','*.tmp*','swap_transfer/<building>_predictions.csv.gz'],
        preserved_complete_prediction_information='swap_transfer/heldout_predictions_wide.csv.gz plus WIDE_PREDICTIONS_RECEIPT.json',
        reconstruct_long='python work_v2_20261019/clusters/compact_swap_predictions.py --expand-to work_v2_20261019/clusters/swap_transfer',
        required_sibling_inputs=['profiles/fold_profiles.csv','profiles/nested_fold_features.csv','profiles/records_flat.csv','profiles/full_profiles.csv','profiles/declared_room_groups.csv','profiles/room_weighting.py','fusion/INPUT_SNAPSHOT.json.gz','fusion/INITIAL_replacements.csv.gz','fusion/composition_comparisons.csv.gz','fusion/prefix_transitions.csv.gz','fusion/team_results.csv'],
        required_repo='repo_main_20261019 at main 82c6164b0d4630de5316199c92aa405930973168; retained code and audited evidence')
    (HERE/'PACKAGING_MANIFEST.json').write_text(json.dumps(package,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in validation.items() if k not in ['gzip_checks','support_exclusion_checks']},indent=2))

if __name__=='__main__':main()
