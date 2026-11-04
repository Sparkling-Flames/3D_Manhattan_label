"""Measure fixed events and aggregate backgrounds -> blocks -> images.

All inferential resampling is over buildings, not repeated overlapping teams.
The shared 6/3 contrast requires four valid endpoints; three-endpoint support
is retained as a separately labelled sensitivity, never silently substituted.
"""
from __future__ import annotations
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import collections, gzip, importlib.util, json, math, sys
from pathlib import Path
import numpy as np
import pandas as pd
from design import ROOT,OUT,SEED,COMMIT,csv,digest,sha,write_json
from run_native import read_gz

sys.path.insert(0,str(ROOT/'research/workers/personnel_v21_reselection_20261029/analysis'))
from measure_registered_events import measure

BOOTSTRAP=10000
METRICS=['Q_W','Q_cross','Q_GA','Q_GS','Q_CA','Q_CB','Q_class_shift','Q_A','Q_B','Q_C',
         'Q_CA_positive','Q_CB_positive','Q_GS_positive','Q_CA_loss10','Q_CB_loss10',
         'IoU3D100_CA_ABC','iou_2d_CA_ABC','S_bottom_deg_CA_ABC','dir_CA_ABC','Hmean_CA_ABC','Hcenter_CA_ABC',
         'omission_CA_ABC','extension_CA_ABC','nodes_CA_ABC','fusion_turn_n_CA_ABC','fusion_short_turn_edges_CA_ABC',
         'fusion_redundancy_n_CA_ABC','ref_node_recall_9_CA_ABC','ref_edge_recall_9_CA_ABC','diag_wall_coverage_05_CA_ABC',
         'geometry_bev_distance_AB','geometry_bev_distance_AC','geometry_bev_distance_BC','geometry_bev_distance_gap',
         'geometry_pair_angle_AB','geometry_pair_angle_AC','geometry_pair_angle_BC','geometry_pair_angle_gap']
TIME_METRICS=['time_CA_seconds_single_source','time_CB_seconds_single_source','time_CA_pct_single_source','time_CB_pct_single_source',
              'block_time_CA_seconds_same_source','block_time_CB_seconds_same_source','block_time_CA_pct_same_source','block_time_CB_pct_same_source']
IDCOLS=['study','direction','pool_id','image','building','official_difficulty','room_type']

def safe_mean(v):
    a=np.asarray(v,float);return float(np.nanmean(a)) if np.isfinite(a).any() else None

def time_info(row):
    x=json.loads(row.get('record_time_by_kind_json') or '{}')
    good=bool(x) and all(v.get('known_n')==v['n'] and v.get('total_seconds') is not None and v['total_seconds']>0 for v in x.values())
    sig=tuple(sorted((k,v['n']) for k,v in x.items()))
    return x,good,sig

def endpoint_rows():
    return {r['team_key']:r for p in sorted((OUT/'endpoints/pools').glob('*.json.gz')) for r in read_gz(p)['teams']}

def build_events():
    ev=pd.read_csv(OUT/'design/EVENTS.csv.gz');rows=endpoint_rows()
    pools={p['pool_id']:p for p in read_gz(OUT/'inputs/SELECTED_POOLS.json.gz')['images']}
    room=pd.read_csv(ROOT/'research/statistics/room_type_similarity_scoping_20261027/IMAGE_TYPE_INDEX.csv')
    assert not room.image_code.duplicated().any()
    rm=room.set_index('image_code').room_type.to_dict();parts=[]
    for pid,g in ev.groupby('pool_id',sort=True):
        needed=set(g.A_team_key)|set(g.B_team_key)|set(g.C_team_key)
        d=measure(g.reset_index(drop=True),{k:rows[k] for k in needed},pools[pid])
        d['room_type']=d.image.map(rm).fillna('未登记')
        for arm in 'ABC':
            d[arm+'_score_status']=d[arm+'_team_key'].map(lambda k:rows[k].get('score_status'))
            d[arm+'_connection_available']=d[arm+'_team_key'].map(lambda k:bool(rows[k].get('connection_available')))
            d[arm+'_geometry_status']=d[arm+'_team_key'].map(lambda k:rows[k].get('geometry_status'))
        alias={'Q_W':'B8L2_within','Q_cross':'B8L2_cross','Q_GA':'B8L2_AC_gap','Q_GS':'B8L2_gap','Q_CA':'B8L2_CA','Q_CB':'B8L2_CB',
               'Q_A':'A_B8L2','Q_B':'B_B8L2','Q_C':'C_B8L2'}
        for dst,src in alias.items():d[dst]=d[src].where(d.ABC_scored)
        d['Q_class_shift']=(d.Q_CA+d.Q_CB)/2
        for k in ['CA','CB','GS']:d['Q_'+k+'_positive']=(d['Q_'+k]>0).astype(float).where(d.ABC_scored)
        for k in ['CA','CB']:d['Q_'+k+'_loss10']=(d['Q_'+k]<-10).astype(float).where(d.ABC_scored)
        for c in METRICS:
            if c.endswith('_CA_ABC'):
                src=c[:-4];d[c]=d[src].where(d.ABC_scored) if src in d else np.nan
        own={r['worker_id']:r for r in pools[pid]['records']};extra=[]
        for e in d.to_dict('records'):
            rr={a:rows[e[a+'_team_key']] for a in 'ABC'};tt={a:time_info(rr[a]) for a in 'ABC'}
            single=all(tt[a][1] and len(tt[a][0])==1 for a in 'ABC') and len({tuple(tt[a][0]) for a in 'ABC'})==1
            out=dict(time_ABC_single_source=single,time_ABC_source_count_matched=all(tt[a][1] for a in 'ABC') and len({tt[a][2] for a in 'ABC'})==1,
                     time_single_source_kind=next(iter(tt['A'][0])) if single else '')
            for c,a in [('CA','A'),('CB','B')]:
                b0=rr[a].get('source_time_total_seconds');b1=rr['C'].get('source_time_total_seconds')
                out['time_'+c+'_seconds_single_source']=b1-b0 if single else np.nan
                out['time_'+c+'_pct_single_source']=100*(b1/b0-1) if single and b0>0 else np.nan
            blocks={a:[own[w] for w in e[a].split('|')] for a in 'DXYZ'}
            types={r['time_source_kind'] for a in 'XYZ' for r in blocks[a]}
            good=len(types)==1 and all(r['source_time_seconds'] is not None and r['source_time_seconds']>0 for a in 'XYZ' for r in blocks[a])
            out['time_replacement_blocks_same_source']=good;out['time_replacement_block_source']=next(iter(types)) if good else ''
            sums={a:sum(r['source_time_seconds'] for r in blocks[a]) if all(r['source_time_seconds'] is not None for r in blocks[a]) else None for a in 'DXYZ'}
            for a in 'DXYZ':out[a+'_record_time_sum_raw']=sums[a]
            for c,a in [('CA','X'),('CB','Y')]:
                out['block_time_'+c+'_seconds_same_source']=sums['Z']-sums[a] if good else np.nan
                out['block_time_'+c+'_pct_same_source']=100*(sums['Z']/sums[a]-1) if good else np.nan
            cv=json.loads(e['D_class_vector'])
            for c in ['C1','C2','C3','unknown']:out['D_'+c+'_n']=cv.get(c,0)
            extra.append(out)
        d=pd.concat([d,pd.DataFrame(extra)],axis=1);parts.append(d)
    d=pd.concat(parts,ignore_index=True)
    bundles=pd.read_csv(OUT/'design/PAIRED_BUNDLES.csv.gz');flags={}
    for e in bundles.to_dict('records'):
        flags[e['bundle_id']]=all(rows[e[a+'_team_key']].get('B8L2') is not None for a in 'PQRS')
    d['all_four_scored']=d.bundle_id.map(flags).fillna(False).astype(bool)
    d['method_identity']='automatic'
    csv(OUT/'analysis/EVENT_METRICS.csv.gz',d)
    scalar=pd.DataFrame([{k:v for k,v in r.items() if not isinstance(v,(list,dict))} for r in rows.values()])
    scalar['room_type']=scalar.image.map(rm).fillna('未登记')
    failure=scalar[scalar.B8L2.isna()].copy()
    touches=[]
    for arm in 'ABC':touches.extend([dict(team_key=k,event_id=e,arm=arm) for k,e in zip(d[arm+'_team_key'],d.event_id)])
    uses=pd.DataFrame(touches).groupby('team_key').agg(event_uses=('event_id','size'),unique_event_uses=('event_id','nunique')).reset_index()
    failure=failure.merge(uses,on='team_key',how='left')
    csv(OUT/'analysis/FAILED_ENDPOINTS.csv.gz',failure)
    return d,rows

def aggregate(events,metrics):
    metrics=[c for c in metrics if c in events]
    e=events.copy()
    bg=e.groupby(IDCOLS+['block_id','background_id'],dropna=False)[metrics].mean().reset_index()
    block=bg.groupby(IDCOLS+['block_id'],dropna=False)[metrics].mean().reset_index()
    image=block.groupby(IDCOLS,dropna=False)[metrics].mean().reset_index()
    building=image.groupby(['study','direction','building'],dropna=False)[metrics].mean().reset_index()
    return bg,block,image,building

def summary_metric(image,metric,seed):
    z=image[image[metric].notna()];v=z[metric].to_numpy(float);B=z.building.nunique()
    if not len(z):return None
    b=z.groupby('building')[metric].agg(['sum','count','mean']);arr=b['sum'].to_numpy();cnt=b['count'].to_numpy();means=b['mean'].to_numpy()
    rr=np.random.default_rng(seed);ix=rr.integers(0,B,size=(BOOTSTRAP,B))
    boot=arr[ix].sum(axis=1)/cnt[ix].sum(axis=1)
    be=means[ix].mean(axis=1)
    loo=[float((arr.sum()-arr[i])/(cnt.sum()-cnt[i])) for i in range(B)] if B>1 else []
    low,high=np.quantile(boot,[.025,.975]) if B>1 else [np.nan,np.nan]
    blo,bhi=np.quantile(be,[.025,.975]) if B>1 else [np.nan,np.nan]
    return dict(metric=metric,images=len(z),buildings=B,image_equal_mean=float(v.mean()),image_median=float(np.median(v)),
                image_q25=float(np.quantile(v,.25)),image_q75=float(np.quantile(v,.75)),image_min=float(v.min()),image_max=float(v.max()),
                positive_images=int((v>0).sum()),negative_images=int((v<0).sum()),zero_images=int((v==0).sum()),
                positive_image_fraction=float((v>0).mean()),cluster_bootstrap_low=float(low),cluster_bootstrap_high=float(high),
                building_equal_mean=float(means.mean()),building_equal_bootstrap_low=float(blo),building_equal_bootstrap_high=float(bhi),
                leave_one_building_out_min=min(loo) if loo else np.nan,leave_one_building_out_max=max(loo) if loo else np.nan,
                leave_one_building_out_same_sign=all(np.sign(x)==np.sign(v.mean()) for x in loo) if loo else None)

def make_summaries(events):
    images=[];blocks=[];backgrounds=[];buildings=[];summary=[];support=[]
    for (study,direction),base in events.groupby(['study','direction'],sort=True):
        regimes=['ABC_valid']+(['all_four_valid'] if study=='paired_6_3' else [])
        for support_name in regimes:
            mask=base.ABC_scored if support_name=='ABC_valid' else base.all_four_scored
            g=base[mask].copy()
            sup=dict(study=study,direction=direction,support=support_name,registered_events=len(base),usable_events=len(g),
                     registered_images=base.image.nunique(),usable_images=g.image.nunique(),registered_buildings=base.building.nunique(),usable_buildings=g.building.nunique(),
                     registered_blocks=base.block_id.nunique(),usable_blocks=g.block_id.nunique(),registered_backgrounds=base.background_id.nunique(),usable_backgrounds=g.background_id.nunique(),
                     fraction_Q_valid=len(g)/len(base),source='analysis/EVENT_METRICS.csv.gz')
            for arm in 'ABC':sup[arm+'_no_Q_events']=int(base[arm+'_failed'].sum())
            support.append(sup)
            bg,bl,im,bu=aggregate(g,METRICS)
            for df,ls in [(bg,backgrounds),(bl,blocks),(im,images),(bu,buildings)]:df['support']=support_name;ls.append(df)
            strata=[('all','all',im)]+[('difficulty',k,z) for k,z in im.groupby('official_difficulty')]+[('room_type',k,z) for k,z in im.groupby('room_type')]
            for typ,level,z in strata:
                for metric in METRICS:
                    if metric not in z:continue
                    # Reuse the same building draws for all metrics in a cell;
                    # shared 6/3 directions also use identical draws so linked
                    # contrasts remain linked in the uncertainty calculation.
                    draw_group='shared_directions' if study=='paired_6_3' else direction
                    out=summary_metric(z,metric,int(digest([SEED,'bootstrap',study,draw_group,support_name,typ,level])[:8],16))
                    if out:summary.append(dict(study=study,direction=direction,support=support_name,stratum_type=typ,stratum=level,**out))
    for filename,ls in [('BACKGROUND_METRICS',backgrounds),('BLOCK_METRICS',blocks),('IMAGE_METRICS',images),('BUILDING_METRICS',buildings)]:csv(OUT/f'analysis/{filename}.csv.gz',pd.concat(ls,ignore_index=True))
    csv(OUT/'analysis/SUPPORT.csv',pd.DataFrame(support));csv(OUT/'analysis/SUMMARY.csv',pd.DataFrame(summary))
    return pd.concat(images,ignore_index=True),pd.concat(blocks,ignore_index=True),pd.concat(backgrounds,ignore_index=True),pd.DataFrame(summary)

def time_summary(events):
    bg,bl,im,bu=aggregate(events,TIME_METRICS)
    out=[]
    for (study,direction),z in im.groupby(['study','direction']):
        for metric in TIME_METRICS:
            q=summary_metric(z,metric,int(digest([SEED,'time',study,direction,metric])[:8],16))
            if q:
                e=events[(events.study==study)&(events.direction==direction)]
                out.append(dict(study=study,direction=direction,usable_events=int(e[metric].notna().sum()),registered_events=len(e),**q))
    csv(OUT/'analysis/TIME_IMAGE_METRICS.csv.gz',im);csv(OUT/'analysis/TIME_SUMMARY.csv',pd.DataFrame(out))

def support_by_image(events):
    out=[]
    for key,g in events.groupby(IDCOLS,dropna=False):
        z=dict(zip(IDCOLS,key));z.update(events=len(g),blocks=g.block_id.nunique(),backgrounds=g.background_id.nunique(),ABC_Q_valid=int(g.ABC_scored.sum()),
              all_four_valid_events=int(g.all_four_scored.sum()),time_ABC_single_source=int(g.time_ABC_single_source.sum()),time_XYZ_same_source=int(g.time_replacement_blocks_same_source.sum()))
        for a in 'ABC':
            z[a+'_Q_missing']=int(g[a+'_failed'].sum());z[a+'_no_connection']=int(g[a+'_score_status'].eq('no_connection').sum())
        out.append(z)
    csv(OUT/'analysis/IMAGE_SUPPORT.csv',pd.DataFrame(out))

def background_stability(bg):
    out=[]
    for key,g in bg.groupby(['study','direction','support','pool_id','image','building','block_id'],dropna=False):
        if len(g)!=2:continue
        r=dict(zip(['study','direction','support','pool_id','image','building','block_id'],key))
        for m in ['Q_GS','Q_class_shift','Q_W','Q_cross']:
            v=g[m].dropna().to_numpy()
            if len(v)==2:r[m+'_background_absolute_difference']=float(abs(v[1]-v[0]));r[m+'_background_sign_flip']=bool(v[0]*v[1]<0)
        out.append(r)
    d=pd.DataFrame(out);csv(OUT/'analysis/FIXED_BLOCK_TWO_BACKGROUNDS.csv.gz',d)
    im=d.groupby(['study','direction','support','pool_id','image','building']).mean(numeric_only=True).reset_index()
    csv(OUT/'analysis/BACKGROUND_STABILITY_IMAGE.csv',im)

def paired_four(rows):
    bundles=pd.read_csv(OUT/'design/PAIRED_BUNDLES.csv.gz');out=[]
    for b in bundles.to_dict('records'):
        q={a:rows[b[a+'_team_key']].get('B8L2') for a in 'PQRS'}
        r={k:b[k] for k in ['bundle_id','block_id','background_id','pool_id','image','building']};r['all_four_scored']=all(x is not None for x in q.values())
        if r['all_four_scored']:
            w1=abs(q['P']-q['Q']);w3=abs(q['R']-q['S']);cross=np.mean([abs(q[a]-q[b]) for a in 'PQ' for b in 'RS'])
            r.update(C1_within=w1,C3_within=w3,cross=float(cross),GS_C1_to_C3=float(cross-w1),GS_C3_to_C1=float(cross-w3),
                     C3_minus_C1_mean_Q=float((q['R']+q['S']-q['P']-q['Q'])/2),C3_within_minus_C1_within=float(w3-w1))
            assert abs((r['GS_C1_to_C3']-r['GS_C3_to_C1'])-r['C3_within_minus_C1_within'])<1e-9
        out.append(r)
    z=pd.DataFrame(out);csv(OUT/'analysis/PAIRED_FOUR_ENDPOINT_METRICS.csv.gz',z)
    cols=['C1_within','C3_within','cross','GS_C1_to_C3','GS_C3_to_C1','C3_minus_C1_mean_Q','C3_within_minus_C1_within']
    block=z[z.all_four_scored].groupby(['pool_id','image','building','block_id'])[cols].mean().reset_index()
    image=block.groupby(['pool_id','image','building'])[cols].mean().reset_index();csv(OUT/'analysis/PAIRED_FOUR_IMAGE.csv',image)
    # Exactly the same shared building draws as the main all-four summary.
    shared_seed=int(digest([SEED,'bootstrap','paired_6_3','shared_directions','all_four_valid','all','all'])[:8],16)
    sums=[summary_metric(image,m,shared_seed) for m in cols]
    csv(OUT/'analysis/PAIRED_FOUR_SUMMARY.csv',pd.DataFrame(sums))

def main():
    d,rows=build_events();im,bl,bg,summ=make_summaries(d);time_summary(d);support_by_image(d);background_stability(bg);paired_four(rows)
    r=read_gz(OUT/'inputs/SELECTED_POOLS.json.gz');assert len(rows)==4992 and len(d)==3200
    assert d[['A_team_key','B_team_key','C_team_key']].notna().all().all()
    # Every event endpoint is bound to the same official reference and actual pool.
    for e in d.to_dict('records'):
        for a in 'ABC':
            z=rows[e[a+'_team_key']]
            assert z['pool_id']==e['pool_id'] and z['reference_id']==e['reference_id'] and z['reference_version']==e['reference_version']
    report=dict(completed=True,source_commit=COMMIT,event_rows=len(d),endpoint_rows=len(rows),primary='main_8_4 / ABC_valid; paired_6_3 / all_four_valid',
                aggregation='Target slots -> D -> blocks -> images; equal image mean. Equal building mean and cluster bootstrap are sensitivity.',
                bootstrap=dict(replicates=BOOTSTRAP,unit='building; all observed images move with their building',seed=SEED,interval='percentile 2.5 / 97.5',paired_directions_share_draws=True,
                               scope='Descriptive uncertainty within the observed feasible support; no population random sampling claim'),
                missing_scores_never_zero=True,no_Q_based_design_updates=True,no_new_human_orders=True,
                time='Main T comparison requires all ABC endpoints entirely the same logging source, all recorded values known and positive; same-source XYZ blocks reported separately, D cancels in absolute block differences',
                pair_supplement='Four common endpoints ensure each direction has its own disjoint same-class control; target block average removes a special anchor. Opposite signed class-mean differences are algebraically linked, not independent reverse replications.',
                limitations=['8/4 directions have disjoint image support; their means cannot establish symmetry','6/3 is a smaller-block common-domain supplement; it does not estimate 8/4 or14/7 effects','Finite-Q contrasts condition on evaluable ABC/four endpoints; failures and full registered support are separate','Repeated events overlap workers and share images; events are not independent sample units'],
                files={str(p.relative_to(OUT)):sha(p) for p in sorted((OUT/'analysis').glob('*.csv*'))})
    write_json(OUT/'audit/ANALYSIS_RECEIPT.json',report)
    selected=summ[(summ.stratum_type=='all')&summ.metric.isin(['Q_W','Q_GA','Q_GS','Q_class_shift'])]
    print(selected.to_string(index=False))

if __name__=='__main__':main()
