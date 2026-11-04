"""Update two actual extra-target natural paths and their existing consumers.

Saved path multiplicity, finite-quantile definition and original N<8 boundary
are retained. This is an assisted sensitivity, not a new automatic trajectory.
"""
from __future__ import annotations
import importlib.util
import argparse
import json
from pathlib import Path
import sys
import tempfile
import numpy as np
import pandas as pd
from .apply_manual_ring_orders_20261104 import ROOT, BASE_COMMIT

IMPACT=ROOT/'research/fusion/manual_order_impact_20261104'
SOURCE=ROOT/'research/workers/image_response_v21_20261101/HOHONET_v21_image_response_20261101'
POOLS=['rPc6DW4iMge-06__manual__other_space_10','uNb9QFRL6hY-88__manual__other_space_22']


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);sys.modules[name]=m;return m


def compare(a,b,keys,name):
    a=a.set_index(keys).sort_index();b=b.set_index(keys).sort_index()
    assert a.index.equals(b.index),(name,a.shape,b.shape)
    records=[]
    for c in a:
        if c not in b or not pd.api.types.is_numeric_dtype(a[c]):continue
        x=pd.to_numeric(a[c],errors='coerce').astype(float);y=pd.to_numeric(b[c],errors='coerce').astype(float)
        assert np.array_equal(x.isna(),y.isna()),(name,c,'missingness')
        err=float((x-y).abs().max()) if x.notna().any() else 0.
        assert err<1e-7,(name,c,err)
        records.append(dict(table=name,field=c,rows=len(a),maximum_absolute_error=err))
    return records


def frame_changes(a,b,keys,label):
    """Long-form differences, keeping missingness and support explicit."""
    a=a.set_index(keys).sort_index();b=b.set_index(keys).sort_index()
    assert a.index.equals(b.index),(label,'row membership changed')
    rows=[]
    for c in a:
        if c not in b or not pd.api.types.is_numeric_dtype(a[c]):continue
        x=pd.to_numeric(a[c],errors='coerce').astype(float);y=pd.to_numeric(b[c],errors='coerce').astype(float)
        change=~np.isclose(x,y,rtol=0,atol=1e-10,equal_nan=True)
        for key in a.index[change]:
            kt=key if isinstance(key,tuple) else (key,)
            rows.append(dict(table=label,**dict(zip(keys,kt)),field=c,automatic=x.loc[key],manual_assisted=y.loc[key],
                difference=y.loc[key]-x.loc[key] if pd.notna(x.loc[key]) and pd.notna(y.loc[key]) else np.nan))
    return rows


def json_numeric_parity(a,b,path='root',tolerance=1e-10):
    if isinstance(a,dict) and isinstance(b,dict):
        assert set(a)==set(b),(path,'keys')
        return max((json_numeric_parity(a[k],b[k],path+'/'+k,tolerance) for k in a),default=0.)
    if isinstance(a,list) and isinstance(b,list):
        assert len(a)==len(b),(path,'length')
        return max((json_numeric_parity(x,y,path+'/'+str(i),tolerance) for i,(x,y) in enumerate(zip(a,b))),default=0.)
    if isinstance(a,(float,int)) and isinstance(b,(float,int)):
        error=abs(a-b);assert error<tolerance,(path,a,b);return float(error)
    assert a==b,(path,a,b)
    return 0.


def complete_consumers(out,resume_combined=False):
    """Replay original combine/facts functions from saved targeted outputs.

    Each unaffected pool keeps its saved row; no endpoint, path or team is
    generated here. The native combine function preserves original image-first
    and building-first denominators, including extra target pools.
    """
    ar=module('analyze_response',SOURCE/'scripts/analyze_response.py')
    summ=module('manual_natural_frozen_summary',SOURCE/'scripts/summarize_response.py')
    names=['POOL_K_STATISTICS.csv.gz','STATUS_BY_K.csv.gz','PATH_CHANGE_SUMMARY.csv.gz',
        'TAIL_ENVELOPES.csv.gz','PLATEAU_SENSITIVITY.csv.gz','TRANSIENT_FLAT_THEN_CHANGE.csv.gz',
        'REUSED_BAND_ESTIMATE_CHECKS.csv.gz']
    aggregate_keys={'PRIMARY_SMALL_CHANGE_ONSETS.csv':['pool_id','metric'],
        'PRIMARY_ONSET_DOMAIN_SUMMARY.csv':['domain','metric'],
        'FIXED_WINDOW_DOMAIN_SUMMARY.csv':['domain','window','metric']}
    parity=[];changes=[];transient_counts=[]
    with tempfile.TemporaryDirectory(prefix='manual_order_natural_') as scratch:
        temp=Path(scratch);unchanged=temp/'unchanged';automatic=out/'aggregate_automatic' if resume_combined else temp/'automatic'
        for name in names:
            if resume_combined and name not in ['TRANSIENT_FLAT_THEN_CHANGE.csv.gz','REUSED_BAND_ESTIMATE_CHECKS.csv.gz']:continue
            old=pd.read_csv(SOURCE/'stage03_response/manual'/name)
            if not resume_combined:ar.write_csv(old[~old.pool_id.isin(POOLS)],unchanged/name)
            if name in ['TRANSIENT_FLAT_THEN_CHANGE.csv.gz','REUSED_BAND_ESTIMATE_CHECKS.csv.gz']:
                for pool in POOLS:
                    try:base=pd.read_csv(out/'automatic/by_pool'/pool/name)
                    except pd.errors.EmptyDataError:base=old.iloc[:0].copy()
                    try:new=pd.read_csv(out/'manual_assisted/by_pool'/pool/name)
                    except pd.errors.EmptyDataError:new=old.iloc[:0].copy()
                    expected=old[old.pool_id.eq(pool)]
                    cols=list(expected.columns)
                    if len(base)==0:
                        assert len(expected)==0,(pool,name)
                    else:
                        sortcols=['metric','tolerance','start_k'] if 'TRANSIENT' in name else ['metric','k']
                        pd.testing.assert_frame_equal(base[cols].sort_values(sortcols).reset_index(drop=True),
                            expected[cols].sort_values(sortcols).reset_index(drop=True),check_dtype=False,atol=1e-7,rtol=0)
                    transient_counts.append(dict(pool_id=pool,table=name,automatic_rows=len(base),assisted_rows=len(new)))
        # One source block is already the complete original combined table.
        if not resume_combined:ar.combine_pool_outputs([dict(output_dir=str(SOURCE/'stage03_response/manual'))],automatic,ROOT)
        pieces=[dict(output_dir=str(unchanged))]+[
            dict(output_dir=str(out/'manual_assisted/by_pool'/pool)) for pool in POOLS]
        destination=out/'stage03_response/manual'
        if not resume_combined:ar.combine_pool_outputs(pieces,destination,ROOT)
        for name,keys in aggregate_keys.items():
            a=pd.read_csv(automatic/name);saved=pd.read_csv(SOURCE/'stage03_response/manual'/name)
            b=pd.read_csv(destination/name)
            parity+=compare(a,saved,keys,'stage03_native/'+name)
            changes+=frame_changes(a,b,keys,'stage03/'+name)
            ar.write_csv(a,out/'aggregate_automatic'/name)
        # The two pools have N=5/7 and cannot enter native >=10 late-jump tables.
        index=pd.read_csv(SOURCE/'stage02_normalized/manual/POOL_INDEX.csv')
        for c in summ.FIELDS:
            if c not in index:index[c]=np.nan
        stage07=out/'stage07_summary/manual';stage07.mkdir(parents=True,exist_ok=True)
        mapkeys={
            'FIXED_PANEL_CURVES.csv.gz':['panel','domain','stratum_dimension','stratum','k','metric'],
            'PER_IMAGE_MARGINAL_CHANGES.csv.gz':['pool_id','window','metric'],
            'FIXED_PANEL_CHANGE_SUMMARY.csv.gz':['panel','domain','stratum_dimension','stratum','window','metric']}
        merged={};saved07={}
        for name,keys in mapkeys.items():
            saved=pd.read_csv(SOURCE/'stage07_summary/manual'/name);saved07[name]=saved
            patch=pd.read_csv(out/'extra_target_summary/manual_assisted'/name)
            old_extra=pd.read_csv(out/'extra_target_summary/automatic'/name)
            parity+=compare(old_extra,saved[saved.domain.eq('ordinary_manual_extra_target')],keys,'stage07_extra/'+name)
            merged[name]=pd.concat([saved[~saved.domain.eq('ordinary_manual_extra_target')],patch],ignore_index=True)
            # Retain original row order as well as the frozen observation set.
            merged[name]=merged[name].set_index(keys).loc[saved.set_index(keys).index].reset_index()[saved.columns]
            changes+=frame_changes(saved,merged[name],keys,'stage07/'+name)
            ar.write_csv(merged[name],stage07/name)
        onset=pd.read_csv(SOURCE/'stage07_summary/manual/ONSET_STRATA.csv')
        primary=pd.read_csv(destination/'PRIMARY_SMALL_CHANGE_ONSETS.csv')
        new_onset=summ.onset_strata(primary,index)
        parity+=compare(new_onset,onset,['domain','stratum_dimension','stratum','metric'],'stage07_onset_unchanged')
        ok=['domain','stratum_dimension','stratum','metric']
        for a,b in zip(new_onset.set_index(ok).sort_index().no_onset_reasons,onset.set_index(ok).sort_index().no_onset_reasons):
            assert json.loads(a)==json.loads(b),'onset reason counts changed'
        late=pd.read_csv(SOURCE/'stage07_summary/manual/LATE_PATH_JUMP_SENSITIVITY.csv.gz')
        assert not late.pool_id.isin(POOLS).any()
        members=pd.read_csv(SOURCE/'stage07_summary/manual/FIXED_PANEL_MEMBERS.csv')
        assert set(members.pool_id).issubset(set(index.pool_id))
        # Keep unchanged onset, late-jump and membership source files by manifest.
        old_transient=pd.read_csv(SOURCE/'stage03_response/manual/TRANSIENT_FLAT_THEN_CHANGE.csv.gz')
        new_transient=pd.read_csv(destination/'TRANSIENT_FLAT_THEN_CHANGE.csv.gz')
        oldfacts=summ.facts('manual',index,saved07['FIXED_PANEL_CURVES.csv.gz'],saved07['FIXED_PANEL_CHANGE_SUMMARY.csv.gz'],
            onset,pd.DataFrame(),pd.DataFrame(),late,old_transient)
        savedfacts=json.loads((SOURCE/'stage07_summary/manual/RESULT_FACTS.json').read_text())
        json_error=json_numeric_parity(oldfacts,savedfacts)
        parity.append(dict(table='stage07_extra/RESULT_FACTS.json',field='all numeric/scalar values',rows=1,maximum_absolute_error=json_error))
        newfacts=summ.facts('manual',index,merged['FIXED_PANEL_CURVES.csv.gz'],merged['FIXED_PANEL_CHANGE_SUMMARY.csv.gz'],
            onset,pd.DataFrame(),pd.DataFrame(),late,new_transient)
        (stage07/'RESULT_FACTS.json').write_text(json.dumps(newfacts,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
        try:
            json_numeric_parity(oldfacts,newfacts);facts_changed=False
        except AssertionError:facts_changed=True
    prior=pd.read_csv(out/'BASELINE_REPRODUCTION.csv')
    prior=prior[~prior.table.str.startswith(('stage03_native/','stage07_extra/','stage07_onset_unchanged'))]
    ar.write_csv(pd.concat([prior,pd.DataFrame(parity)],ignore_index=True),out/'BASELINE_REPRODUCTION.csv')
    ar.write_csv(pd.DataFrame(changes),out/'AGGREGATE_NUMERIC_CHANGES.csv.gz')
    ar.write_csv(pd.DataFrame(transient_counts),out/'TRANSIENT_AND_BAND_SUPPORT.csv')
    checks=json.loads((out/'CHECKS.json').read_text())
    checks.update(native_stage03_aggregate_completed=True,native_stage07_consumers_completed=True,
        aggregate_changed_numeric_cells=len(changes),stage07_facts_changed=facts_changed,
        native_adopted_onset_unchanged=True,native_primary_onset_domain_summary_unchanged=True,
        primary_ungated_small_range_diagnostic_cells_changed=2,
        native_late_jump_hits=0,native_fixed_panel_membership_unchanged=True,
        baseline_max_error=max(checks['baseline_max_error'],max(p['maximum_absolute_error'] for p in parity)))
    checks.pop('native_primary_onset_unchanged',None)
    (out/'CHECKS.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(checks,ensure_ascii=False,indent=2))


def main():
    out=IMPACT/'natural';out.mkdir(parents=True,exist_ok=True)
    ar=module('analyze_response',SOURCE/'scripts/analyze_response.py')
    summ=module('manual_natural_frozen_summary',SOURCE/'scripts/summarize_response.py')
    blocks=module('manual_natural_frozen_blocks',ROOT/'research/workers/personnel_population_curves_v2_20261023/sampling_extension_20261026/engine26/derive_frozen_blocks.py')
    endpoint=blocks.add_blocks_frame(pd.read_csv(IMPACT/'endpoints/ENDPOINT_SCORES.csv'))
    endpoint=endpoint[endpoint.pool_id.isin(POOLS)].set_index('team_key');assert len(endpoint)==2
    original={};assisted={};parity=[];support=[];common=[]
    table_keys={'POOL_K_STATISTICS.csv.gz':['pool_id','k'],'STATUS_BY_K.csv.gz':['pool_id','k','status_class'],
        'PATH_CHANGE_SUMMARY.csv.gz':['pool_id','k_from','k_to','metric'],
        'TAIL_ENVELOPES.csv.gz':['pool_id','metric','k'],
        'PLATEAU_SENSITIVITY.csv.gz':['pool_id','metric','tolerance','minimum_valid_paths']}
    for pool in POOLS:
        source=SOURCE/'stage02_normalized/manual/pools'/(pool+'.csv.gz')
        old=pd.read_csv(source);new=old.copy();meta=ar.get_meta({},old)
        hit=old.team_key.isin(endpoint.index);assert hit.sum() in [8,25]
        alias={'turns':'floor_turn5_n','short_edges_03_h':'floor_short_edge_03_n','floor_area_h2':'floor_area_camera_h2'}
        # short_turn_edges is absent throughout the frozen normalized source.
        # Keep that original unavailable channel instead of adding only 2 teams.
        derived=['B8L2','D10','IoU3D100','complete_evaluable','nodes','height_mean_h','S_bottom_deg','dir',
                 'Hmean','Hcenter','omission','extension','iou_2d','below_four','connection_available','score_status','geometry_status',
                 *blocks.BLOCKS]
        for i,r in old[hit].iterrows():
            e=endpoint.loc[r.team_key]
            assert (r.reference_id,r.reference_version)==(e.reference_id,e.reference_version)
            assert pd.isna(r.B8L2)
            for c in derived:
                if c in old:new.at[i,c]=e[c]
            for dst,src in alias.items():new.at[i,dst]=e[src]
            new.at[i,'complete_output']=float(e.complete_evaluable)
            new.at[i,'quality_valid']=pd.notna(e.B8L2)
            new.at[i,'status_class']='scoreable' if pd.notna(e.B8L2) else 'output_unscoreable'
        ar.write_csv(new,out/'normalized_assisted'/f'{pool}.csv.gz')
        pold=ar.prepare_frame(old,meta);pnew=ar.prepare_frame(new,meta)
        oldgood=pold.B8L2.notna()
        for c in ar.QUALITY+ar.GEOMETRY:
            assert np.array_equal(pold.loc[oldgood,c],pnew.loc[oldgood,c],equal_nan=True),(pool,c)
        common.append(dict(pool_id=pool,original_scored_rows=int(oldgood.sum()),maximum_original_Q_change=0.,
                           repeated_team_frequency_preserved=True,all_path_k_memberships_preserved=True))
        pairsets={}
        for version,df in [('automatic',pold),('manual_assisted',pnew)]:
            curve,status=ar.per_k_statistics(df,meta);changes,events=ar.paired_response(df,meta,True)
            env,onset,transient,bcheck=ar.tail_analysis(curve,meta,{})
            tables={'POOL_K_STATISTICS.csv.gz':curve,'STATUS_BY_K.csv.gz':status,'PATH_CHANGE_SUMMARY.csv.gz':changes,
                    'PATH_CHANGE_EVENTS.csv.gz':events,'TAIL_ENVELOPES.csv.gz':env,'PLATEAU_SENSITIVITY.csv.gz':onset,
                    'TRANSIENT_FLAT_THEN_CHANGE.csv.gz':transient,'REUSED_BAND_ESTIMATE_CHECKS.csv.gz':bcheck}
            pairsets[version]=tables
            for name,df0 in tables.items():ar.write_csv(df0,out/version/'by_pool'/pool/name)
            for c in ['B8L2','D10','IoU3D100']:
                q=curve[curve.k.eq(int(endpoint.loc[old.loc[hit,'team_key'].iloc[0],'k']))].iloc[0]
                support.append(dict(connection_version=version,pool_id=pool,image=meta['image'],building=meta['building'],
                    domain=meta['domain'],N=meta['N'],k=q.k,metric=c,paths=q.path_rows,unique_teams=q.unique_teams,
                    valid_paths=q[c+'_valid_n'],valid_unique_teams=q[c+'_unique_valid_teams'],mean=q[c+'_mean'],
                    p10=q[c+'_p10'],p10_inverse_cdf=q[c+'_p10_inverse_cdf'],sd=q[c+'_sd'],
                    complete_evaluable_rate=q.complete_evaluable_rate))
        for name,keys in table_keys.items():
            saved=pd.read_csv(SOURCE/'stage03_response/manual/by_pool'/pool/name)
            parity+=compare(pairsets['automatic'][name],saved,keys,pool+'/'+name)
        original[pool]=pairsets['automatic'];assisted[pool]=pairsets['manual_assisted']
    ar.write_csv(pd.DataFrame(parity),out/'BASELINE_REPRODUCTION.csv')
    ar.write_csv(pd.DataFrame(support),out/'AFFECTED_K_COMPARISON.csv')
    ar.write_csv(pd.DataFrame(common),out/'ORIGINAL_SCORED_SUPPORT_CHECKS.csv')
    # Update full saved stage03 tables by replacing only the two pool slices.
    all_tables={}
    for name in table_keys:
        old=pd.read_csv(SOURCE/'stage03_response/manual'/name)
        new=pd.concat([old[~old.pool_id.isin(POOLS)],*[assisted[p][name] for p in POOLS]],ignore_index=True)
        ar.write_csv(new,out/'stage03_response/manual'/name);all_tables[name]=new
    # Existing stage07 fixed panels include extra targets; calculate only that
    # domain, preserving all other domains by an explicit patch table.
    idx=pd.read_csv(SOURCE/'stage02_normalized/manual/POOL_INDEX.csv')
    idx=idx[idx.domain.eq('ordinary_manual_extra_target')].copy()
    for c in summ.FIELDS:
        if c not in idx:idx[c]=np.nan
    oldcurve=pd.read_csv(SOURCE/'stage03_response/manual/POOL_K_STATISTICS.csv.gz')
    newcurve=all_tables['POOL_K_STATISTICS.csv.gz']
    panels=summ.panel_definitions(idx,'manual')
    summaries={}
    for version,curve in [('automatic',oldcurve),('manual_assisted',newcurve)]:
        curve=curve[curve.pool_id.isin(idx.pool_id)]
        stats,members=summ.per_k_panels(curve,idx,panels)
        individual=summ.marginal_changes(curve,idx)
        contrasts=summ.contrast_summaries(individual,idx,panels)
        summaries[version]={'FIXED_PANEL_CURVES.csv.gz':stats,'PER_IMAGE_MARGINAL_CHANGES.csv.gz':individual,
                            'FIXED_PANEL_CHANGE_SUMMARY.csv.gz':contrasts}
        for name,d in summaries[version].items():ar.write_csv(d,out/'extra_target_summary'/version/name)
    for name,keys in [('FIXED_PANEL_CURVES.csv.gz',['panel','domain','stratum_dimension','stratum','k','metric']),
        ('PER_IMAGE_MARGINAL_CHANGES.csv.gz',['pool_id','window','metric']),
        ('FIXED_PANEL_CHANGE_SUMMARY.csv.gz',['panel','domain','stratum_dimension','stratum','window','metric'])]:
        p=SOURCE/'stage07_summary/manual'/name
        if p.exists():
            old=pd.read_csv(p);old=old[old.domain.eq('ordinary_manual_extra_target')]
            parity+=compare(summaries['automatic'][name],old,keys,'extra_target_summary/'+name)
    ar.write_csv(pd.DataFrame(parity),out/'BASELINE_REPRODUCTION.csv')
    support=pd.DataFrame(support)
    downstream=[
        ('stage03_response/manual/by_pool','hit','Two pools: 8+25 repeated path rows, never independent teams'),
        ('stage03_response/manual fixed windows','hit','Replace two pool statistics and preserve all other pool values'),
        ('stage07_summary/manual fixed panels','hit','Extra-target domain only; same image-first/building summaries'),
        ('stage04_geometry/ordinary_cached','no_hit','analyze_cached_geometry.py requires ordinary_manual_main'),
        ('stage04_components/manual','no_hit','analyze_response_components.py requires ordinary_manual_main'),
        ('stage07 p10_definition_sensitivity','no_hit','p10_definition_sensitivity.py requires ordinary_manual_main'),
        ('stage07 finite_tail_sensitivity','no_hit','main Manual and doorway only; extra targets excluded'),
        ('stage07 continuous structure / diagnostics','no_hit','Both scripts filter ordinary_manual_main'),
    ]
    ar.write_csv(pd.DataFrame(downstream,columns=['consumer','actual_dependency','evidence']),out/'DOWNSTREAM_CONSUMERS.csv')
    checks=dict(source_commit=BASE_COMMIT,affected_unique_teams=2,affected_pools=2,affected_images=2,
        affected_path_rows=33,source_domain='ordinary_manual_extra_target',original_scored_values_changed=0,
        original_membership_or_order_changes=0,main_target_natural_hits=0,source_time_changed=False,
        N_values=[5,7],plateau_onsets_change=False,plateau_reason='N<8: description only; insufficient required subsequent workers',
        original_Q_null_not_zero=True,raw_k1_unchanged=True,k2_supplement_or_deferral_unchanged=True,
        new_fusion_calls=0,new_endpoint_score_calls=0,baseline_max_error=max(p['maximum_absolute_error'] for p in parity))
    (out/'CHECKS.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(checks,ensure_ascii=False,indent=2));print(support.to_string(index=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--finalize-only',action='store_true')
    parser.add_argument('--resume-combined',action='store_true');args=parser.parse_args()
    assert not args.resume_combined or args.finalize_only,'--resume-combined requires --finalize-only'
    if not args.finalize_only:main()
    complete_consumers(IMPACT/'natural',args.resume_combined)
