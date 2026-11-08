"""当前同房原答结构重复性；复用正式参考与直接关系，不重跑融合或分类。"""
from pathlib import Path
import gzip
import json
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from .same_room_structure_transfer_20261020 import geometry_features
from .same_room_local_features_20261021 import MAPS, local_assign, history_prediction, prediction_tables

ROOT = Path(__file__).resolve().parents[3]
V = ROOT / 'research/data/releases/v2.1'
BASE = ROOT / 'research/workers/personnel_full_chain_v21_20261030/HOHONET_v21_full_chain_20261030/stage02_same_room/prediction'
OUT = V / 'same_room_structure_20261108'
METRICS = ['turn_n', 'turn_deficit', 'simplified', 'short_turn_edges', 'near_straight_nodes_5deg',
           'corner_delta', 'unmatched_ref_9', 'bottom_bias_9', 'omission', 'B8L2']

def read(path):
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rt', encoding='utf-8') as f:
        return json.load(f)

def save(name, value):
    if isinstance(value, pd.DataFrame):
        value.to_csv(OUT/name, index=False, encoding='utf-8-sig')
    else:
        (OUT/name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')

def peer_center(frame, metric):
    group = frame.groupby('image_id')[metric]
    n = group.transform('count')
    return frame[metric] - (group.transform('sum')-frame[metric])/(n-1).where(n>1)

def paired_identity(a, b):
    """同一个人与所有非本人配对的差距；双方人员集合完全相同。"""
    a, b = np.asarray(a, float), np.asarray(b, float)
    assert len(a)==len(b) and len(a)>1 and np.isfinite(a).all() and np.isfinite(b).all()
    gaps = np.abs(a[:,None]-b[None,:])
    equal = a[:,None]==b[None,:]
    off = ~np.eye(len(a), dtype=bool)
    return dict(same_person_abs_gap=float(np.diag(gaps).mean()), other_person_abs_gap=float(gaps[off].mean()),
                same_person_exact=float(np.diag(equal).mean()), other_person_exact=float(equal[off].mean()),
                spearman=float(spearmanr(a,b).statistic) if np.ptp(a)>0 and np.ptp(b)>0 else np.nan)

def interval(values):
    a=np.asarray(values,float); a=a[np.isfinite(a)]
    if not len(a): return [None,None]
    rng=np.random.default_rng(20261108)
    boot=a[rng.integers(len(a),size=(5000,len(a)))].mean(axis=1)
    return np.quantile(boot,[.025,.975]).tolist()

def inputs():
    d=pd.read_csv(V/'difficulty_computable_comparison/INPUT_RECORDS.csv.gz')
    formal=pd.read_csv(BASE/'CURRENT_FORMAL_RECORDS.csv.gz')
    check=d.merge(formal[['object_id','reference_id','reference_version','B8L2']],on='object_id',validate='one_to_one',suffixes=('','_formal'))
    assert len(check)==len(d)==6512 and d.image_id.nunique()==206
    assert (check.reference_id==check.reference_id_formal).all()
    assert (check.reference_version==check.reference_version_formal).all()
    assert (check.B8L2-check.B8L2_formal).abs().max()<1e-10
    conditions=pd.read_csv(V/'admitted_space_extension/image_difficulty_20261030/POOL_TARGET_CONDITIONS.csv')
    grades=conditions[['image_id','official_difficulty']].drop_duplicates()
    assert grades.image_id.is_unique
    d=d.drop(columns=['difficulty']).merge(grades,on='image_id',validate='many_to_one').rename(columns={'official_difficulty':'difficulty'})
    pairs=pd.read_csv(BASE/'v21_all/DIRECT_PAIRS.csv')
    pairs=pairs[(pairs.condition=='manual')&(pairs.origin=='all')&(pairs.metric=='B8L2')&
                (pairs.layer=='ordinary')&pairs.scope_comparable&~pairs.substantive_conflict&~pairs.oos_pending].copy()
    assert len(pairs)==128 and pairs.pair_id.is_unique
    assert len(set(pairs.image_a)|set(pairs.image_b))==65 and pairs.building_id.nunique()==13
    pools=read(V/'pools/INPUT_SNAPSHOT.json')['images']; refs={r['target_id']:r for r in read(V/'reference_catalog.json')}
    raw={r['object_id']:(r,p['meta']) for p in pools for r in p['records']}
    diagnostics=[]
    for r in d.itertuples():
        obj,meta=raw[r.object_id]
        assert meta['reference_id']==r.reference_id and obj['worker_id']==r.worker_id
        diagnostics.append(geometry_features(obj['points'],refs[r.reference_id]['points_1024x512']))
    diag=pd.DataFrame(diagnostics,index=d.index)
    diffs={m:float((d[m]-diag[m]).abs().max()) for m in ['unmatched_ref_9','bottom_bias_9','omission']}
    assert max(diffs.values())<1e-8,diffs
    d['corner_delta']=diag.corner_delta;d['corners']=diag.corners
    d['turn_deficit']=(d.ref_turn5-d.turn_n).clip(lower=0)
    d['simplified']=(d.turn_n<d.ref_turn5).astype(int)
    for metric in METRICS: d[metric+'_relative']=peer_center(d,metric)
    save('INPUT_RECORDS.csv.gz',d);save('DIRECT_PAIRS.csv',pairs)
    save('INPUT_CHECKS.json',dict(records=len(d),images=d.image_id.nunique(),people=d.worker_id.nunique(),
        pairs=len(pairs),pair_images=65,pair_buildings=13,recomputed_geometry_max_abs_differences=diffs,
        reference_binding_checked=True,formal_quality_checked=True,classification_refit=False,fusion_rerun=False))
    return d,pairs,raw,refs

def comparisons(d,pairs):
    records=[]; pair_rows=[]
    by_image={k:v.set_index('worker_id') for k,v in d.groupby('image_id')}
    for pair in pairs.itertuples():
        a,b=by_image[pair.image_a],by_image[pair.image_b]; common=a.index.intersection(b.index)
        assert len(common)==pair.n_common
        for metric in METRICS:
            x=a.loc[common,metric];y=b.loc[common,metric]; valid=x.notna()&y.notna();workers=common[valid]
            if len(workers)<2: continue
            stats=paired_identity(x.loc[workers],y.loc[workers])
            rel_a=a.loc[workers,metric+'_relative'];rel_b=b.loc[workers,metric+'_relative']
            meaningful=(rel_a!=0)&(rel_b!=0)
            row=dict(pair_id=pair.pair_id,building=pair.building_id,code_a=pair.code_a,code_b=pair.code_b,
                metric=metric,workers=len(workers),same_ref_turns=int(a.ref_turn5.iloc[0]==b.ref_turn5.iloc[0]),
                both_have_short=int(a.ref_short_edges.iloc[0]>0 and b.ref_short_edges.iloc[0]>0),**stats)
            row['identity_abs_advantage']=stats['other_person_abs_gap']-stats['same_person_abs_gap']
            row['identity_exact_advantage']=stats['same_person_exact']-stats['other_person_exact']
            row['nonzero_relative_workers']=int(meaningful.sum())
            row['relative_same_sign']=float(((rel_a[meaningful]>0)==(rel_b[meaningful]>0)).mean()) if meaningful.any() else np.nan
            pair_rows.append(row)
            for w in workers:
                records.append(dict(pair_id=pair.pair_id,building=pair.building_id,code_a=pair.code_a,code_b=pair.code_b,
                    worker_id=w,metric=metric,value_a=float(x[w]),value_b=float(y[w]),relative_a=float(rel_a[w]),relative_b=float(rel_b[w])))
    per=pd.DataFrame(pair_rows); people=pd.DataFrame(records)
    save('PAIR_STRUCTURE_RESULTS.csv',per);save('PERSON_PAIR_VALUES.csv.gz',people)
    save('PAIR_EXCEPTIONS.csv',per[(per.spearman<0)|(per.identity_abs_advantage< -1e-12)])
    binary=people[people.metric=='simplified'].copy()
    binary['both_simplified']=((binary.value_a==1)&(binary.value_b==1)).astype(int)
    binary['neither_simplified']=((binary.value_a==0)&(binary.value_b==0)).astype(int)
    binary['changed']=(binary.value_a!=binary.value_b).astype(int)
    worker=binary.groupby('worker_id').agg(pairs=('pair_id','size'),buildings=('building','nunique'),
        both_simplified=('both_simplified','sum'),neither_simplified=('neither_simplified','sum'),changed=('changed','sum'))
    save('WORKER_SIMPLIFICATION_COUNTS.csv',worker.reset_index())
    save('CASE_PEOPLE.csv',d[d.image_code.isin(['VFuaQ6m2Qom-01','VFuaQ6m2Qom-04','VFuaQ6m2Qom-07','VFuaQ6m2Qom-10'])][
        ['object_id','worker_id','image_code','reference_id','difficulty','corners','ref_vertices','turn_n','ref_turn5','short_turn_edges','simplified']])
    summaries=[]
    for metric, part in per.groupby('metric',sort=False):
        for scope, sub in [('all_pairs',part),('same_reference_turns',part[part.same_ref_turns==1]),('both_short_opportunities',part[part.both_have_short==1])]:
            if sub.empty: continue
            building=sub.groupby('building').identity_abs_advantage.mean()
            lo,hi=interval(building)
            summaries.append(dict(metric=metric,scope=scope,pairs=len(sub),buildings=sub.building.nunique(),
                valid_rank_pairs=int(sub.spearman.notna().sum()),positive_rank_pairs=int((sub.spearman>0).sum()),
                same_person_gap_pair_equal=sub.same_person_abs_gap.mean(),other_person_gap_pair_equal=sub.other_person_abs_gap.mean(),
                identity_advantage_pair_equal=sub.identity_abs_advantage.mean(),identity_advantage_building_equal=building.mean(),
                advantage_buildings=int((building>0).sum()),bootstrap_low=lo,bootstrap_high=hi,
                exact_same_pair_equal=sub.same_person_exact.mean(),exact_other_pair_equal=sub.other_person_exact.mean(),
                relative_same_sign_pair_equal=sub.relative_same_sign.mean()))
    save('PAIR_STRUCTURE_SUMMARY.csv',pd.DataFrame(summaries))
    return by_image

def predictions(d,pairs,by_image):
    neighbors={}
    for r in pairs.itertuples():
        neighbors.setdefault(r.image_a,set()).add(r.image_b);neighbors.setdefault(r.image_b,set()).add(r.image_a)
    rows=[]
    for building in pairs.building_id.unique():
        train=d[d.building!=building]
        # 每个人先楼内均值、再楼等权；目标楼完全不进入人员历史。
        hist=train.groupby(['worker_id','building'])[METRICS+[m+'_relative' for m in METRICS]].mean().groupby('worker_id').mean()
        for image in [i for i in neighbors if by_image[i].building.iloc[0]==building]:
            target=by_image[image]
            for worker,r in target.iterrows():
                if worker not in hist.index: continue
                for metric in METRICS:
                    sources=[s for s in sorted(neighbors[image]) if worker in by_image[s].index and pd.notna(by_image[s].at[worker,metric])]
                    if not sources or pd.isna(r[metric]) or pd.isna(hist.at[worker,metric]):continue
                    own=[];other=[]
                    for source in sources:
                        assert source!=image
                        sf=by_image[source];peers=sf.loc[sf.index!=worker,metric].dropna()
                        if peers.empty:continue
                        own.append(float(sf.at[worker,metric]));other.append(float(peers.mean()))
                    if len(own)!=len(sources):continue
                    public=float(np.mean(other));self_mean=float(np.mean(own));theta=float(hist.at[worker,metric+'_relative'])
                    row=dict(building=building,image=image,image_code=r.image_code,worker_id=worker,object_id=r.object_id,
                        metric=metric,actual=float(r[metric]),history_images=len(sources),source_images='|'.join(sources),
                        outside_person=float(hist.at[worker,metric]),source_other=public,source_self=self_mean,
                        public_plus_stable=public+theta,half_personal=(self_mean+public+theta)/2)
                    if metric=='simplified':
                        for k in ['public_plus_stable','half_personal']:row[k]=float(np.clip(row[k],0,1))
                    rows.append(row)
    pred=pd.DataFrame(rows);assert not pred.duplicated(['image','worker_id','metric']).any()
    methods=['outside_person','source_other','source_self','public_plus_stable','half_personal']
    for method in methods:
        pred[method+'_loss']=np.where(pred.metric=='simplified',(pred.actual-pred[method])**2,(pred.actual-pred[method]).abs())
    save('STRUCTURE_PREDICTIONS.csv.gz',pred)
    rows=[];builds=[]
    for metric,sub in pred.groupby('metric',sort=False):
        cols=[m+'_loss' for m in methods]
        im=sub.groupby(['building','image'])[cols].mean();bd=im.groupby('building').mean()
        for b,r in bd.iterrows():builds.append(dict(metric=metric,building=b,**r.to_dict()))
        for method in methods:
            gain=bd.source_other_loss-bd[method+'_loss'];lo,hi=interval(gain)
            rows.append(dict(metric=metric,method=method,loss='Brier' if metric=='simplified' else 'MAE',
                records=len(sub),images=sub.image.nunique(),people=sub.worker_id.nunique(),buildings=sub.building.nunique(),
                image_equal_loss=im[method+'_loss'].mean(),building_equal_loss=bd[method+'_loss'].mean(),
                gain_vs_source_other=gain.mean(),gain_buildings=int((gain>1e-12).sum()),loss_buildings=int((gain< -1e-12).sum()),
                bootstrap_low=lo,bootstrap_high=hi,leave_one_building_min=min(gain.drop(b).mean() for b in gain.index),
                leave_one_building_max=max(gain.drop(b).mean() for b in gain.index)))
    save('STRUCTURE_PREDICTION_SUMMARY.csv',pd.DataFrame(rows));save('STRUCTURE_PREDICTION_BUILDINGS.csv',pd.DataFrame(builds))

def local(d,raw,refs,pairs):
    edges={frozenset((r.code_a,r.code_b)) for r in pairs.itertuples()}
    for m in MAPS:
        views=list(m['views'])
        assert all(frozenset((a,b)) in edges for i,a in enumerate(views) for b in views[i+1:])
    old=read(ROOT/'research/statistics/v2_evidence_audit_20261019/records.json.gz')['records']
    old_by_code={r['image_code']:r for r in old if r['quality_usable']}
    codes={c for m in MAPS for c in m['views']}; observations=[];bridges=[]
    for code in sorted(codes):
        sub=d[d.image_code==code];rid=sub.reference_id.unique();assert len(rid)==1
        ref=refs[rid[0]]['points_1024x512']; prior=old_by_code[code]['reference_evidence']['points_1024x512']
        assert ref==prior, f'Local physical correspondence needs re-review: {code}'
        bridges.append(dict(image_code=code,reference_id=rid[0],reference_version=sub.reference_version.iloc[0],
            old_reference_coordinates_equal=True,current_formal_people=len(sub)))
        for r in sub.itertuples():
            points=raw[r.object_id][0]['points']
            for tol in [3,6,9]:
                matches=local_assign(points,ref,tol)
                for m in MAPS:
                    if code not in m['views']:continue
                    match=matches.get(m['views'][code]-1)
                    observations.append(dict(room=m['room'],feature=m['feature'],image_code=code,image_id=r.image_id,
                        worker_id=r.worker_id,object_id=r.object_id,reference_id=rid[0],tolerance_deg=tol,
                        hit=int(match is not None),dx=match['dx'] if match else np.nan,
                        correspondence_status='user_confirmed' if m['room']=='G046' else 'image_supported_not_human_confirmed'))
    frame=pd.DataFrame(observations);save('LOCAL_REFERENCE_BRIDGE.csv',pd.DataFrame(bridges));save('LOCAL_BEHAVIOR.csv',frame)
    rates=frame.groupby(['room','feature','image_code','tolerance_deg']).hit.agg(['size','sum','mean']).reset_index()
    save('LOCAL_VIEW_RATES.csv',rates)
    predicted=[];paired=[]
    for (room,feat,tol),sub in frame.groupby(['room','feature','tolerance_deg']):
        for r in sub.itertuples():
            p=history_prediction(sub,r.worker_id,r.image_code)
            if p is None:continue
            own,other,n=p
            for method,prob in [('own_other_views',own),('others_same_source_views',other),('equal_blend',(own+other)/2)]:
                predicted.append(dict(room=room,feature=feat,tolerance_deg=tol,image=r.image_code,worker_id=r.worker_id,
                    history_images=n,y=r.hit,method=method,probability=prob,brier=(r.hit-prob)**2,absolute_error=abs(r.hit-prob)))
        views=sorted(sub.image_code.unique())
        for i,a in enumerate(views):
            for b in views[i+1:]:
                x=sub[sub.image_code==a].set_index('worker_id').hit;y=sub[sub.image_code==b].set_index('worker_id').hit
                common=x.index.intersection(y.index);stats=paired_identity(x.loc[common],y.loc[common])
                paired.append(dict(room=room,feature=feat,tolerance_deg=tol,code_a=a,code_b=b,people=len(common),
                    both_hit=int(((x.loc[common]==1)&(y.loc[common]==1)).sum()),neither_hit=int(((x.loc[common]==0)&(y.loc[common]==0)).sum()),
                    changed=int((x.loc[common]!=y.loc[common]).sum()),**stats))
    pred,summary=prediction_tables(pd.DataFrame(predicted))
    save('LOCAL_PREDICTIONS.csv',pred);save('LOCAL_PREDICTION_SUMMARY.csv',summary);save('LOCAL_PAIR_REPETITION.csv',pd.DataFrame(paired))

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    d,pairs,raw,refs=inputs();by_image=comparisons(d,pairs);predictions(d,pairs,by_image);local(d,raw,refs,pairs)
    print('Completed:',OUT)

if __name__=='__main__':main()
