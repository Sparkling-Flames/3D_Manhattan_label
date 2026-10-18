"""Repair lost measurement payloads on saved v1 geometry; preserve tables and provenance."""
import gzip
import io
import json
import zipfile

import numpy as np
import pandas as pd

from .wall_consensus_v1_process_20261017 import OUT, ROOT, ENGINE, save, read, aggregate, measurement_context
from .wall_consensus_quality_20261015 import measured
from .scope_quality_scoring_20261016 import scoring_engine
from .wall_consensus_v1_summary_20261017 import run as summarize

REVISION='v1_complete_measurement_cache_main_panel_r2_20261017'
KEY=['pool_id','subset']
CORE=['WQ','IoU3D100','iou_2d','S_bottom_deg','dir','Hmean','Hcenter','omission','extension','diagnostic_B8L2','diagnostic_D10']
NUMERIC_AUX=['floor_WQ_upper_bound','iou_3d_corner_mean','height_mean_ratio','floor_WQ','boundary_loss','direction_loss',
     'global_height_loss','local_height_loss','height_loss','height_drop_WQ','height_drop_current','WQ_no_D','WQ_no_B','WQ_no_H','iou2d100']
AUX=NUMERIC_AUX+['reasons']


def same_core(current,source):
    for field in ['reference_id','reference_version','member_records','score_status']:
        assert current[field].equals(source[field]),field
    for field in CORE:
        assert np.allclose(current[field],source[field],rtol=1e-12,atol=1e-12,equal_nan=True),field


def run():
    history=OUT/'history'/REVISION;history.mkdir(parents=True,exist_ok=True)
    archive=history/'pre_revision_tables.zip'
    source_stat=ROOT/'research/statistics/v1_integrated_analysis_20261017/inputs/fusion_states.csv'
    if not archive.exists():
        paths=list(OUT.glob('*.csv'))+list(OUT.glob('*.json'))+list(OUT.glob('*.md'))+list(OUT.glob('process_comparison.*'))
        paths+=list((OUT/'pools').glob('*/observations.csv'))
        paths.append(OUT/'random_baseline/trajectory_scores.csv')
        with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
            for path in paths:z.write(path,str(path.relative_to(OUT)).replace('\\','/'))
            z.write(source_stat,'source_statistics/fusion_states.csv')
    def table(z,name):return pd.read_csv(io.BytesIO(z.read(name)),low_memory=False,float_precision='round_trip')
    with zipfile.ZipFile(archive) as z:
        before=table(z,'trajectory_scores.csv')
        snapshot=json.loads(z.read('input_snapshot.json'))
        baseline=table(z,'random_baseline/trajectory_scores.csv')
        statistics=table(z,'source_statistics/fusion_states.csv')
    current=before.drop_duplicates(KEY).set_index(KEY)
    current['reasons']=current['reasons'].astype(object)
    sources=[('random_baseline/trajectory_scores.csv',baseline),
             ('research/statistics/v1_integrated_analysis_20261017/inputs/fusion_states.csv',statistics)]
    # Recover only from matching source subsets and references; main scores are checked, not replaced.
    restored=[];contexts=[]
    for source_path,frame in sources:
        other=frame.drop_duplicates(KEY).set_index(KEY);common=current.index.intersection(other.index)
        same_core(current.loc[common],other.loc[common])
        contexts.append(dict(source=source_path,matching_unique_subsets=len(common),core_and_reference_equal=True))
        for field in AUX:
            mask=current.loc[common,field].isna() & other.loc[common,field].notna()
            for key in common[mask]:
                restored.append(dict(pool_id=key[0],subset=key[1],field=field,source=source_path,value=other.loc[key,field]))
            current.loc[common,field]=current.loc[common,field].fillna(other.loc[common,field])
    remaining=current[(current.score_status.eq('complete_conditional') & current[NUMERIC_AUX].isna().any(axis=1)) |
        (current.iou_2d.notna() & current.floor_WQ_upper_bound.isna())]
    images={im['pool_id']:im for im in snapshot['images']}
    raw_fields=set();probes=[];remeasured=0
    with scoring_engine(ENGINE/'measurement_engine.zip',ENGINE/'working_models.py') as (engine,_):
        # Discover the frozen engine's complete payload schema, including unavailable-status fields.
        for pool,g in before.groupby('pool_id'):
            wanted=remaining.loc[remaining.index.get_level_values(0)==pool]
            statuses=set(before.score_status)-{p['status'] for p in probes}
            selected=g.drop_duplicates('score_status');selected=selected[selected.score_status.isin(statuses)]
            need=set(wanted.index.get_level_values(1))|set(selected.subset)
            if not need:continue
            im=images[pool];ref=im['reference'];reference=dict(floor=ref['floor_xz_h'],
                points=ref['points_1024x512'] if ref['full_reference_available'] else None)
            payload=json.load(gzip.open(OUT/'pools'/pool/'states.json.gz','rt',encoding='utf-8'))
            for e in payload['states']:
                if e['subset'] not in need:continue
                raw=measured(engine,e['automatic'],reference);raw_fields.update(raw)
                key=(pool,e['subset']);row=current.loc[key]
                for field in CORE:
                    if field.startswith('diagnostic_'):continue
                    old=row.get(field,np.nan);value=raw.get(field)
                    assert (pd.isna(old) and value is None) or np.isclose(old,value,rtol=1e-12,atol=1e-12), (key,field)
                if key in remaining.index:
                    remeasured+=1
                    for field,value in raw.items():
                        if field in CORE or field=='score_status' or value is None:continue
                        if field not in current:current[field]=np.nan
                        if pd.isna(current.loc[key,field]):
                            current.loc[key,field]=value
                            restored.append(dict(pool_id=pool,subset=e['subset'],field=field,source='remeasured_saved_geometry',value=value))
                probes.append(dict(pool_id=pool,subset=e['subset'],status=row.score_status,fields=sorted(raw)))
    assert not current[current.score_status.eq('complete_conditional')][NUMERIC_AUX].isna().any().any()
    assert not current.loc[current.iou_2d.notna(),'floor_WQ_upper_bound'].isna().any()
    by_pool={pool:g for pool,g in current.reset_index().groupby('pool_id')}
    with zipfile.ZipFile(archive) as z:
        for pool,values in by_pool.items():
            path=OUT/'pools'/pool/'observations.csv';frame=table(z,str(path.relative_to(OUT)).replace('\\','/'))
            lookup=values.set_index('subset')
            for field in AUX:frame[field]=frame['subset'].map(lookup[field])
            frame.to_csv(path,index=False,encoding='utf-8-sig')
            measured_fields=sorted(raw_fields|{'diagnostic_B8L2','diagnostic_D10'})
            measurements={}
            for subset,row in lookup.iterrows():
                measurements[subset]={k:(None if pd.isna(row.get(k)) else row[k]) for k in measured_fields}
            save(path.parent/'score_cache.json',dict(context=measurement_context(images[pool]),measurements=measurements))
    pd.DataFrame(restored).to_csv(OUT/'measurement_field_recovery.csv',index=False,encoding='utf-8-sig')
    save(OUT/'MEASUREMENT_CACHE_SCHEMA.json',dict(analysis_revision=REVISION,fields=sorted(raw_fields),
        runtime='score_cache.json persists the complete measured dictionary; no field allowlist at reuse',
        restored_from_flat_table_schema='frozen measured schema verified on representative saved states',probes=probes))
    aggregate();summarize()
    after=pd.read_csv(OUT/'trajectory_scores.csv',low_memory=False,float_precision='round_trip')
    key=['pool_id','path_id','k'];a=before.set_index(key).sort_index();b=after.set_index(key).sort_index()
    assert a.index.equals(b.index) and len(after)==41859
    for field in ['subset','member_workers','member_records','reference_id','reference_version','quality_allowed','main_comparison_allowed','nodes']:
        assert a[field].equals(b[field]),field
    maxima={}
    for field in ['B8L2','D10',*CORE]:
        assert np.allclose(a[field],b[field],rtol=1e-12,atol=1e-12,equal_nan=True),field
        maxima[field]=float((a[field]-b[field]).abs().max())
    witness=statistics.set_index(key);common=a.index.intersection(witness.index);known={}
    for field in AUX:
        mask=witness.loc[common,field].notna()&a.loc[common,field].isna()
        assert b.loc[common[mask],field].notna().all()
        known[field]=int(mask.sum())
    record=dict(analysis_revision=REVISION,data_release='v1',archive=str(archive.relative_to(OUT)).replace('\\','/'),
        source_checks=contexts,recovered_unique_subsets=len({(r['pool_id'],r['subset']) for r in restored}),
        recovered_field_cells=len(restored),known_review_window_restored_rows=known,
        unique_subsets_remeasured=remeasured,schema_probe_measurements=len(probes),fusion_rerun=False,
        members_references_eligibility_unchanged=True,main_score_maximum_absolute_difference=maxima,
        states=len(after),unique_subsets=len(current),pools=after.pool_id.nunique(),images=after.image.nunique())
    save(OUT/'REVISION_CHECKS.json',record)
    for name in ['CHECKS.json','STATUS.json']:
        data=read(OUT/name);data['analysis_revision']=REVISION;save(OUT/name,data)
    manifest=read(OUT/'MANIFEST.json');manifest['analysis_revision']=REVISION
    manifest['files'].update(main_random_changes='random_matched_changes_main.csv',
        descriptive_8to16='random_8to16_descriptive_panel.csv',main_8to16='random_8to16_main_panel.csv',
        main_strict_V='random_8to16_main_strict_V.csv',random_panel_summary='random_8to16_panel_summary.csv',
        field_recovery='measurement_field_recovery.csv',revision_checks='REVISION_CHECKS.json',measurement_schema='MEASUREMENT_CACHE_SCHEMA.json')
    manifest['previous_tables_archive']=record['archive'];save(OUT/'MANIFEST.json',manifest)
    save(OUT/'CURRENT.json',dict(data_release='v1',analysis_revision=REVISION,manifest='MANIFEST.json',
        active_tables_root='.',previous_tables_archive=record['archive'],geometry_unchanged=True))
    print(record,flush=True)


if __name__=='__main__':run()
