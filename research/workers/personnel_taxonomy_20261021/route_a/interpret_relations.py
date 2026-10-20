#!/usr/bin/env python3
"""Describe A partitions and test Q/source-matched original-answer relations."""
import gzip,json
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.metrics import normalized_mutual_info_score,adjusted_rand_score
from check_route_b_relations import q_source_match
from run_route_a import eval_crossfit

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]

def main():
    pairs=pd.read_csv(HERE/'pair_observations.csv.gz')
    labels=pd.read_csv(HERE/'worker_labels.csv')
    allfinal=labels[labels.stage.eq('all_data_descriptive')&labels.class_id.ne('unknown')]
    matched=[]
    for (c,m),l in allfinal.groupby(['condition','method']):
        cross=pd.read_csv(HERE/f'crossfit_pairs_{c}_{m}.csv.gz')
        p=pairs.merge(cross,on=['pool_id','image_id','building_id','worker_a','worker_b'],validate='one_to_one')
        out=q_source_match(p,c,'A')
        for r in out:r['method']=m;r['k']=int(l.k.iloc[0])
        matched+=out
    pd.DataFrame(matched).to_csv(HERE/'A_Q_source_matched_validation.csv',index=False)
    source=ROOT/'research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/clusters'
    rec=pd.read_csv(source/'records_geometry.csv.gz')
    api=json.load(gzip.open(source/'CLUSTER_API.json.gz','rt',encoding='utf-8'))
    rr=[]
    for pool in api['pools']:
        for g in pool['geometries']:
            p=np.asarray(g['points']);floor=np.asarray(g['floor']) if g['floor'] is not None else None
            rr.append(dict(object_id=g['object_id'],bottom_mean_deg=float(p[1::2,1].mean()*180/512-90),
                top_mean_deg=float(p[::2,1].mean()*180/512-90),
                log_mean_radius=float(np.log(np.linalg.norm(floor,axis=1).mean())) if floor is not None else np.nan))
    rec=rec.merge(pd.DataFrame(rr),on='object_id',validate='one_to_one')
    for v in ['bottom_mean_deg','top_mean_deg','log_mean_radius']:
        # Compared against the same image, reference and corner-count peers.
        rec[v+'_equalcount_peer_delta']=rec[v]-rec.groupby(['pool_id','pair_count'])[v].transform('median')
    expr=pd.read_csv(ROOT/'research/workers/personnel_marking_patterns_20261020/record_expression.csv')
    expr=expr[[c for c in expr if c=='object_id' or c.endswith('_peer_delta')]]
    rec=rec.merge(expr,on='object_id',validate='one_to_one',how='left')
    fields=[c for c in rec if c.endswith('_peer_delta')]+['B8L2','D10','source_time_seconds']
    summary=[];workers=[];assocs=[]
    bfinal=pd.read_csv(HERE.parent/'route_b/final_labels.csv')
    for (cond,method),l in allfinal.groupby(['condition','method']):
        r=rec[rec.layer.eq('ordinary_'+cond)].merge(l[['worker_id','class_id']],on='worker_id',validate='many_to_one')
        wp=r.groupby(['worker_id','building_id'])[fields].mean().groupby('worker_id').mean().reset_index()
        wp=wp.merge(l[['worker_id','class_id','origin']],on='worker_id');wp['condition']=cond;wp['method']=method
        workers+=wp.to_dict('records')
        for cl,g in wp.groupby('class_id'):
            z=dict(condition=cond,method=method,class_id=cl,n_workers=len(g),members='|'.join(g.worker_id),new_workers=int(g.origin.eq('new').sum()))
            z.update({f:float(g[f].mean()) for f in fields});summary.append(z)
        b=bfinal[bfinal.condition.eq(cond)&bfinal.label_status.eq('assigned')]
        z=l.merge(b[['worker_id','coarse_class','fine_class']],on='worker_id')
        q=l.merge(wp[['worker_id','B8L2']],on='worker_id')
        q['Qtertile']=pd.qcut(q.B8L2,3,labels=False,duplicates='drop')
        assocs.append(dict(condition=cond,method=method,n_workers=len(l),source_NMI=normalized_mutual_info_score(l.origin,l.class_id),
            B_coarse_NMI=normalized_mutual_info_score(z.coarse_class,z.class_id),B_fine_NMI=normalized_mutual_info_score(z.fine_class,z.class_id),
            Q_tertiles_NMI=normalized_mutual_info_score(q.Qtertile,q.class_id)))
    pd.DataFrame(summary).to_csv(HERE/'A_expression_class_descriptions.csv',index=False)
    pd.DataFrame(workers).to_csv(HERE/'A_expression_worker_descriptions.csv',index=False)
    pd.DataFrame(assocs).to_csv(HERE/'A_associations.csv',index=False)
    lobo=pd.read_csv(HERE/'worker_labels_lobo.csv')
    stable=[]
    for (c,m),g in lobo.groupby(['condition','method']):
        ref=allfinal[allfinal.condition.eq(c)&allfinal.method.eq(m)].set_index('worker_id').class_id.to_dict()
        g=g[g.class_id.ne('unknown')].copy();g['agrees']=g.aligned_class_id.eq(g.worker_id.map(ref))
        s=g.groupby('worker_id').agg(n_buildings=('target_building','size'),agreement=('agrees','mean')).reset_index()
        s['condition']=c;s['method']=m;s['class_id']=s.worker_id.map(ref);stable+=s.to_dict('records')
    pd.DataFrame(stable).to_csv(HERE/'A_lobo_member_stability.csv',index=False)
    pair_summary=[]
    for cond in ['manual','semi']:
        z=lobo[lobo.condition.eq(cond)&lobo.method.eq('A2_samecount_source_residual')&lobo.class_id.ne('unknown')]
        mp=z.set_index(['target_building','worker_id']).aligned_class_id.to_dict()
        t=pairs[pairs.layer.eq('ordinary_'+cond)].copy()
        t['class_a']=[mp.get((b,w)) for b,w in zip(t.building_id,t.worker_a)]
        t['class_b']=[mp.get((b,w)) for b,w in zip(t.building_id,t.worker_b)]
        t=t.dropna(subset=['class_a','class_b'])
        t['class_pair']=['|'.join(sorted([a,b])) for a,b in zip(t.class_a,t.class_b)]
        for panel,q in [('all',t),('same_count',t[t.same_count.eq(1)])]:
            s=q.groupby(['class_pair','building_id','image_id'])[['bound_deg','same9','same12','bottom_deg','top_deg','floor_iou']].mean()
            s=s.groupby(['class_pair','building_id']).mean().groupby('class_pair').mean().reset_index()
            support=q.groupby('class_pair').agg(n_pairs=('image_id','size'),n_images=('image_id','nunique'),n_buildings=('building_id','nunique')).reset_index()
            s=s.merge(support,on='class_pair');s['condition']=cond;s['panel']=panel
            pair_summary+=s.to_dict('records')
    pd.DataFrame(pair_summary).to_csv(HERE/'A2_class_pair_geometry.csv',index=False)
    lm=lobo[lobo.condition.eq('manual')&lobo.method.eq('A2_samecount_source_residual')&lobo.class_id.ne('unknown')]
    mp=lm.set_index(['target_building','worker_id']).class_id.to_dict()
    door=pairs[pairs.layer.eq('doorway_manual')].copy()
    door['class_a']=[mp.get((b,w)) for b,w in zip(door.building_id,door.worker_a)]
    door['class_b']=[mp.get((b,w)) for b,w in zip(door.building_id,door.worker_b)]
    door=door.dropna(subset=['class_a','class_b']);door['within']=door.class_a.eq(door.class_b)
    dr=eval_crossfit(door,'A2_samecount_source_residual',3,'manual')
    dm=q_source_match(door,'manual','A2')
    for r in dm:r['method']='A2_samecount_source_residual';r['k']=3
    for r in dr+dm:r['layer']='doorway_manual'
    pd.DataFrame(dr+dm).to_csv(HERE/'A2_doorway_validation.csv',index=False)
    print(pd.DataFrame(matched).query("metric in ['same9','bound_deg','floor_iou']")[['condition','method','metric','n_images','n_buildings','within','between','within_minus_between','ci_lo','ci_hi']].to_string(index=False))
    print(pd.DataFrame(summary).query("method == 'A2_samecount_source_residual'").to_string(index=False))

if __name__=='__main__':main()
