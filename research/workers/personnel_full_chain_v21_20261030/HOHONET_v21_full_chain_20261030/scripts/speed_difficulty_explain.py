#!/usr/bin/env python3
"""Build support bridges, metric-support checks and representative raw cases."""
from __future__ import annotations
import gzip, hashlib, json, math, os
from pathlib import Path
import numpy as np
import pandas as pd
import speed_difficulty as m

OUT=m.OUT

def bridge():
    p=m.read(OUT/'CURRENT_MATCHED_PAIRS.csv.gz')
    old=m.read(OUT/'V2_FIXED_PAIR_CURRENT_RESULTS.csv.gz')
    fine=old[old.tier.eq('fine_label')]
    exact=set(fine.object_fast+'|'+fine.object_slow)
    people=set(zip(fine.condition,fine.origin,fine.worker_fast,fine.worker_slow))
    p['same_exact_v2_fine_pair_picture']=p.physical_pair_key.isin(exact)
    p['same_v2_fine_directed_people_pair']=[tuple(v) in people for v in p[['condition','origin','worker_fast','worker_slow']].to_numpy()]
    z=p[p.same_exact_v2_fine_pair_picture].copy()
    m.save(z,'CURRENT_ON_V2_FINE_PAIR_PICTURES.csv.gz')
    m.summarize(z,m.METRICS,'CURRENT_ON_V2_FINE_PAIR_PICTURES')
    m.same_people(z,m.METRICS,'CURRENT_ON_V2_FINE_PAIR_SAME_PEOPLE')
    counts=[]
    for key,g in p.groupby(m.KEYS):
        for scope,gg in [('all_current',g),('same_exact_v2_fine_pair_picture',g[g.same_exact_v2_fine_pair_picture]),
                        ('same_v2_fine_people_pair',g[g.same_v2_fine_directed_people_pair])]:
            counts.append(dict(zip(m.KEYS,key))|dict(scope=scope,rows=len(gg),images=gg.image_id.nunique(),
                buildings=gg.building_id.nunique(),directed_people_pairs=gg[['worker_fast','worker_slow']].drop_duplicates().shape[0],
                workers=len(set(gg.worker_fast)|set(gg.worker_slow))))
    m.save(pd.DataFrame(counts),'OLD_NEW_MATCHING_BRIDGE_SUPPORT.csv')
    attrition=[]
    masks={'v2_original':pd.Series(True,index=old.index),'currently_legal':old.both_current_legal,
        'Q_common_support':old.both_current_legal&old.both_v2_quality&old.both_current_quality,
        'newly_Q_scorable':old.both_current_legal&~old.both_v2_quality&old.both_current_quality,
        'current_class_same':old.both_current_legal&old.current_same_class,
        'current_near_Q':old.both_current_legal&old.current_history_q_gap.abs().le(3),
        'current_full_matching':old.current_matching_still_holds}
    for scope,mask in masks.items():
        for key,g in old[mask].groupby(m.KEYS):
            attrition.append(dict(zip(m.KEYS,key))|dict(scope=scope,rows=len(g),images=g.image_id.nunique(),
                buildings=g.building_id.nunique(),directed_people_pairs=g[['worker_fast','worker_slow']].drop_duplicates().shape[0],
                workers=len(set(g.worker_fast)|set(g.worker_slow))))
    m.save(pd.DataFrame(attrition),'V2_PAIRS_CURRENT_SUPPORT_AND_MATCHING.csv')
    # Original rule counts >=2 images per difficulty before metric-wise NA removal.
    # Report a stricter metric-wise >=2 rule without silently changing old identity.
    rows=[]
    for file in ['V2_FROZEN_SAME_PEOPLE','V21_FIXED_V2_SAME_PEOPLE','CURRENT_SAME_PEOPLE']:
        d=m.read(OUT/(file+'.csv.gz'))
        for key,g in d.groupby(m.KEYS+['metric']):
            g=g[g.easy_images.ge(2)&g.hard_images.ge(2)].dropna(subset=['hard_minus_easy'])
            rows.append(dict(zip(m.KEYS+['metric'],key))|dict(dataset=file,pairs=len(g),
                workers=len(set(g.worker_fast)|set(g.worker_slow)),mean=g.hard_minus_easy.mean(),
                positive=int(g.hard_minus_easy.gt(m.EPS).sum()),negative=int(g.hard_minus_easy.lt(-m.EPS).sum()),
                zero=int(g.hard_minus_easy.abs().le(m.EPS).sum())))
    m.save(pd.DataFrame(rows),'STRICT_TWO_VALID_IMAGES_PER_DIFFICULTY.csv')
    return p

def same_building_summary():
    sb=m.read(OUT/'CURRENT_SAME_PEOPLE_SAME_BUILDING.csv.gz')
    sb=sb.dropna(subset=['hard_minus_easy'])
    bs=sb.groupby(m.KEYS+['metric','building_id']).agg(
        pair_contexts=('hard_minus_easy','size'),difference=('hard_minus_easy','mean')).reset_index()
    m.save(bs,'SAME_PEOPLE_SAME_BUILDING_BUILDING_EFFECTS.csv')
    rows=[]
    for key,g in bs.groupby(m.KEYS+['metric']):
        rows.append(dict(zip(m.KEYS+['metric'],key))|dict(buildings=len(g),pair_contexts=int(g.pair_contexts.sum()),
            building_equal_mean=g.difference.mean(),building_median=g.difference.median(),
            positive_buildings=int(g.difference.gt(m.EPS).sum()),negative_buildings=int(g.difference.lt(-m.EPS).sum()),
            zero_buildings=int(g.difference.abs().le(m.EPS).sum())))
    m.save(pd.DataFrame(rows),'SAME_PEOPLE_SAME_BUILDING_BUILDING_SUMMARY.csv')
    return bs

def floor(points):
    a=np.asarray(points,float)[1::2]; lon=(a[:,0]/1024-.5)*2*np.pi
    r=1/np.tan((a[:,1]/512-.5)*np.pi)
    return np.c_[np.sin(lon)*r,-np.cos(lon)*r]

def cases(p):
    longitudinal=m.read(OUT/'CURRENT_SAME_PEOPLE.csv.gz')
    z=longitudinal[(longitudinal.method=='TARGET_DSTRUCT_K3')&(longitudinal.condition=='manual')&(longitudinal.origin=='new')]
    w=z.pivot(index=['worker_fast','worker_slow'],columns='metric',values='hard_minus_easy')
    specs=[('more_turns_Q_down',(w.turn_n>.2)&(w.B8L2<-1)),
           ('more_turns_Q_up',(w.turn_n>.2)&(w.B8L2>1)),
           ('same_turns_small_Q',(w.turn_n.abs()<=.1)&(w.B8L2.abs()<=2))]
    snapshot=m.SRC/'pools/INPUT_SNAPSHOT.json'
    content=snapshot.read_bytes();sha=hashlib.sha1(b'blob '+str(len(content)).encode()+b'\0'+content).hexdigest()
    assert sha=='fa42df06d5cf0990d5e3bbd99f68c9f517b349b9'
    pools=json.loads(content)['images'];lookup={r['object_id']:(pool,r) for pool in pools for r in pool['records']}
    currentrefs={r['target_id']:r for r in json.loads((m.SRC/'reference_catalog.json').read_text()) if r.get('current_target')}
    rec=m.read(OUT/'RECORDS_CURRENT_WITH_PROVENANCE.csv.gz').set_index('object_id')
    selected=[];case_events=[];manifest=[]
    for caseid,mask in specs:
        g=w[mask].copy();center=g[['turn_n','B8L2']].median();scale=(g[['turn_n','B8L2']].quantile(.75)-g[['turn_n','B8L2']].quantile(.25)).replace(0,1)
        g['selection_distance']=((g[['turn_n','B8L2']]-center).abs()/scale).sum(axis=1)
        for (fast,slow),candidate in g.sort_values(['selection_distance']).iterrows():
            events=p[(p.method=='TARGET_DSTRUCT_K3')&(p.condition=='manual')&(p.worker_fast==fast)&(p.worker_slow==slow)]
            events=events[events.object_fast.isin(lookup)&events.object_slow.isin(lookup)&events.current_difficulty.isin(['简单','困难'])]
            avail=events.groupby(['building_id','current_difficulty']).size().unstack(fill_value=0)
            if not {'简单','困难'}<=set(avail.columns):continue
            avail=avail[avail['简单'].gt(0)&avail['困难'].gt(0)]
            if avail.empty:continue
            combinations=[]
            for building in sorted(avail.index):
                ev=events[events.building_id.eq(building)]
                for ei,e in ev[ev.current_difficulty.eq('简单')].iterrows():
                    for hi,h in ev[ev.current_difficulty.eq('困难')].iterrows():
                        if caseid=='more_turns_Q_down':
                            valid=h.turn_n_difference>0 and h.B8L2_difference<0 and h.turn_n_difference>e.turn_n_difference and h.B8L2_difference<e.B8L2_difference
                        elif caseid=='more_turns_Q_up':
                            valid=h.turn_n_difference>0 and h.B8L2_difference>0 and h.turn_n_difference>e.turn_n_difference and h.B8L2_difference>e.B8L2_difference
                        else:
                            valid=abs(h.turn_n_difference)<1e-9 and abs(e.turn_n_difference)<1e-9 and abs(h.B8L2_difference)<2 and abs(e.B8L2_difference)<2
                        if valid:combinations.append(dict(building=building,ei=ei,hi=hi,
                            hard_turn=h.turn_n_difference,hard_Q=h.B8L2_difference,easy_Q=e.B8L2_difference,
                            quality_change=h.B8L2_difference-e.B8L2_difference))
            if not combinations:continue
            comb=pd.DataFrame(combinations);fields=['hard_turn','hard_Q','easy_Q','quality_change']
            med=comb[fields].median();iqr=(comb[fields].quantile(.75)-comb[fields].quantile(.25)).replace(0,1)
            comb['distance']=((comb[fields]-med).abs()/iqr).sum(axis=1)
            take=comb.sort_values(['distance','building','ei','hi']).iloc[0];building=take.building
            chosen_rows={'简单':events.loc[int(take.ei)],'困难':events.loc[int(take.hi)]}
            chosen=[]
            for difficulty in ['简单','困难']:
                row=chosen_rows[difficulty]
                pool,rf=lookup[row.object_fast];pool_s,rs=lookup[row.object_slow]
                assert pool['pool_id']==pool_s['pool_id']
                target=row.reference_id;reference=currentrefs[target]
                assert np.allclose(np.asarray(pool['reference']['points_1024x512']),np.asarray(reference['points_1024x512']))
                detail=dict(case_id=caseid,difficulty=difficulty,image_code=row.image_code,image_id=row.image_id,
                    building=building,reference_id=target,method=row.method,class_id=row.class_id,
                    worker_fast=fast,worker_slow=slow,object_fast=row.object_fast,object_slow=row.object_slow,
                    history_q_fast=row.history_q_fast,history_q_slow=row.history_q_slow,
                    history_time_log_slow_minus_fast=row.history_time_log_slow_minus_fast,
                    reference=reference,raw_fast=rf,raw_slow=rs,
                    metrics_fast=rec.loc[row.object_fast,m.METRICS].to_dict(),
                    metrics_slow=rec.loc[row.object_slow,m.METRICS].to_dict())
                chosen.append(detail)
                case_events.append(row.to_dict()|dict(case_id=caseid))
            selected.extend(chosen)
            manifest.append(dict(case_id=caseid,worker_fast=fast,worker_slow=slow,
                overall_hard_minus_easy_turns=candidate.turn_n,overall_hard_minus_easy_Q=candidate.B8L2,
                selected_building=building,selected_images='|'.join(r['image_code'] for r in chosen),
                selection='person pair nearest its predefined overall effect-stratum median; same-building easy/hard actual pairs matching the stated local sign; nearest median among eligible picture combinations'))
            break
    m.save(pd.DataFrame(case_events),'CASES_EXACT_PAIRS.csv')
    m.save(pd.DataFrame(manifest),'CASE_INDEX.csv')
    def clean(v):
        if isinstance(v,dict):return {k:clean(z) for k,z in v.items()}
        if isinstance(v,list):return [clean(z) for z in v]
        if isinstance(v,(float,np.floating)):return float(v) if np.isfinite(v) else None
        if isinstance(v,(np.integer,)):return int(v)
        if isinstance(v,(np.bool_,)):return bool(v)
        return v
    data=clean(dict(source_snapshot_blob=sha,selection=manifest,cases=selected))
    (OUT/'CASES_MINIMUM_RAW_GEOMETRY.json.gz').write_bytes(gzip.compress(json.dumps(data,ensure_ascii=False).encode(),mtime=0))
    # Scientific diagram from exact geometry, not a generated illustration.
    os.environ.setdefault('MPLCONFIGDIR','/tmp/hohonet_speed_matplotlib')
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    for caseid,items in pd.DataFrame(selected).groupby('case_id',sort=False):
        fig,axes=plt.subplots(1,len(items),figsize=(10,5),squeeze=False)
        for ax,(_,r) in zip(axes[0],items.iterrows()):
            for obj,color,label in [(r.reference,'#4c566a','Reference'),(r.raw_fast,'#168aad',r.worker_fast+' fast'),(r.raw_slow,'#d1495b',r.worker_slow+' slow')]:
                pts=obj.get('points',obj.get('points_1024x512'));f=floor(pts);f=np.vstack([f,f[0]])
                ax.plot(f[:,0],f[:,1],'-o',lw=1.5,ms=3,color=color,label=label)
            ax.scatter([0],[0],marker='x',color='black',s=30)
            ax.set_aspect('equal',adjustable='datalim');ax.grid(alpha=.2);ax.set_xlabel('x / camera height');ax.set_ylabel('z / camera height')
            ax.set_title(r.image_code+' ('+('easy' if r.difficulty=='简单' else 'hard')+')\n'+
                f'Q fast {r.metrics_fast["B8L2"]:.2f}, slow {r.metrics_slow["B8L2"]:.2f}')
        axes[0][0].legend(fontsize=8);fig.tight_layout()
        fig.savefig(OUT/(caseid+'.png'),dpi=150);fig.savefig(OUT/(caseid+'.svg'));plt.close(fig)
    m.js('CASE_VALIDATION.json',dict(source_snapshot_blob=sha,cases=len(manifest),pair_pictures=len(selected),
        exact_workers_and_objects_verified=True,current_reference_points_verified=True,
        semantic_correctness='reference-relative diagnostics; no new human judgement inferred'))
    return manifest

def main():
    p=bridge();same_building_summary();spec=cases(p)
    print(json.dumps(dict(current_rows=len(p),cases=spec),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
