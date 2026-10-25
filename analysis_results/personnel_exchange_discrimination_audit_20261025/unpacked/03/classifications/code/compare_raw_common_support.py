#!/usr/bin/env python3
"""Common-person original-answer comparison against Q2 and old structure.

Uses only saved original-answer distances and frozen LOBO labels. No new
candidate, fusion endpoint, quality score or reference is calculated.
"""
import argparse,json,warnings
from pathlib import Path
import numpy as np
import pandas as pd
from build_condition_response_classes import save_csv,save_json
from describe_candidate_support import METRICS

def distances(g,mapping):
    ca=g.worker_a.map(mapping).to_numpy();cb=g.worker_b.map(mapping).to_numpy()
    answer={}
    for subset in ['all_pairs','same_corner_count']:
        pick=np.ones(len(g),bool) if subset=='all_pairs' else g.same_corner_count.to_numpy(bool)
        wmask=pick&(ca==cb);cmask=pick&(ca!=cb)
        if wmask.sum()<4 or cmask.sum()<4:continue
        within_keys=np.unique(ca[wmask])
        pairkeys=np.array(['|'.join(sorted([a,b])) for a,b in zip(ca,cb)])
        cross_keys=np.unique(pairkeys[cmask])
        data=g[METRICS].to_numpy(float)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore',RuntimeWarning)
            w=np.nanmean(np.vstack([np.nanmean(data[wmask&(ca==cl)],axis=0) for cl in within_keys]),axis=0)
            c=np.nanmean(np.vstack([np.nanmean(data[cmask&(pairkeys==cl)],axis=0) for cl in cross_keys]),axis=0)
        for i,metric in enumerate(METRICS):
            if not np.isfinite(w[i]) or not np.isfinite(c[i]):continue
            answer[(subset,metric)]=dict(within=float(w[i]),cross=float(c[i]),contrast=float(c[i]-w[i]),
              within_pair_n=int(np.isfinite(data[wmask,i]).sum()),cross_pair_n=int(np.isfinite(data[cmask,i]).sum()),
              within_classes=len(within_keys),cross_class_pairs=len(cross_keys))
    return answer

def main(a):
    p=Path(a.classifications);f=Path(a.features)
    labels=pd.read_csv(p/'CANDIDATE_LABELS_COMPLETE_ALL_LOBO.csv.gz');labels=labels[labels.known&labels.heldout_building.ne('ALL')]
    old=pd.read_csv(a.old);old=old[old.known&old.condition.eq('manual')&old.method.eq('V3_BEHAVIOR')]
    pair=pd.read_csv(f/'RAW_ORIGINAL_PAIR_DISTANCES.csv.gz');pair=pair[pair.pool_layer.eq('ordinary_manual')]
    groups={b:g for b,g in pair.groupby('building')}
    lm={(method,b):g.set_index('worker_id').class_id.to_dict() for (method,b),g in labels.groupby(['method','heldout_building'])}
    om={b:g.set_index('worker_id').coarse_label.to_dict() for b,g in old.groupby('heldout_building')}
    cache={};out=[];panels=[];missing=[]
    candidates=sorted(labels.method.unique());candidates=[x for x in candidates if x!='Q_MEDIAN2']
    for candidate in candidates:
        for b,source in groups.items():
            cm=lm.get((candidate,b),{});qm=lm.get(('Q_MEDIAN2',b),{});bm=om.get(b,{})
            common=tuple(sorted(set(cm)&set(qm)&set(bm)))
            d=source[source.worker_a.isin(common)&source.worker_b.isin(common)]
            for poolid,g in d.groupby('pool_id'):
                meta={k:g.iloc[0][k] for k in ['pool_id','image_id','image','condition','building','difficulty','image_layer','pool_layer']}
                members=tuple(sorted(set(g.worker_a)|set(g.worker_b)))
                panels.append(dict(candidate_method=candidate,**meta,common_members='|'.join(members),common_member_n=len(members),raw_pair_n=len(g)))
                cand=distances(g,cm)
                for baseline,mapping in [('Q_MEDIAN2',qm),('OLD_V3_BEHAVIOR_COARSE',bm)]:
                    key=(baseline,poolid,members)
                    if key not in cache:cache[key]=distances(g,mapping)
                    base=cache[key];keys=set(cand)&set(base)
                    if not keys:
                        missing.append(dict(candidate_method=candidate,baseline_method=baseline,**meta,common_member_n=len(members),reason='fewer_than_4_within_or_cross_pairs_in_candidate_or_baseline'))
                    for subset,metric in sorted(keys):
                        c=cand[(subset,metric)];bc=base[(subset,metric)]
                        out.append(dict(candidate_method=candidate,baseline_method=baseline,**meta,common_member_n=len(members),subset=subset,metric=metric,
                          **{'candidate_'+k:v for k,v in c.items()},**{'baseline_'+k:v for k,v in bc.items()},
                          contrast_gain=c['contrast']-bc['contrast']))
        print('saved-computation',candidate,flush=True)
    result=pd.DataFrame(out);save_csv(result,p/'COMMON_SUPPORT_RAW_COMPARISON_BY_IMAGE.csv.gz');save_csv(pd.DataFrame(panels),p/'COMMON_SUPPORT_RAW_PANELS.csv.gz');save_csv(pd.DataFrame(missing),p/'COMMON_SUPPORT_RAW_UNESTIMABLE.csv.gz')
    summary=[]
    for key,g in result.groupby(['candidate_method','baseline_method','subset','metric']):
        for difficulty in ['ALL','简单','中等','困难']:
            z=g if difficulty=='ALL' else g[g.difficulty.eq(difficulty)]
            if z.empty:continue
            bybuilding=z.groupby('building')[['candidate_contrast','baseline_contrast','contrast_gain']].mean()
            row=dict(zip(['candidate_method','baseline_method','subset','metric'],key))
            row.update(difficulty=difficulty,images=z.image_id.nunique(),buildings=len(bybuilding),
                candidate_within=z.candidate_within.mean(),candidate_cross=z.candidate_cross.mean(),
                baseline_within=z.baseline_within.mean(),baseline_cross=z.baseline_cross.mean(),
                candidate_contrast=z.candidate_contrast.mean(),baseline_contrast=z.baseline_contrast.mean(),
                contrast_gain=z.contrast_gain.mean(),images_gain_positive=int(z.contrast_gain.gt(0).sum()),
                buildings_gain_positive=int(bybuilding.contrast_gain.gt(0).sum()),
                common_member_n_min=int(z.common_member_n.min()),common_member_n_median=float(z.common_member_n.median()))
            row['candidate_ratio']=row['candidate_cross']/row['candidate_within'] if row['candidate_within']>1e-10 else np.nan
            row['baseline_ratio']=row['baseline_cross']/row['baseline_within'] if row['baseline_within']>1e-10 else np.nan
            summary.append(row)
    save_csv(pd.DataFrame(summary),p/'COMMON_SUPPORT_RAW_COMPARISON_SUMMARY.csv')
    save_json(dict(candidates=candidates,baselines=['Q_MEDIAN2','OLD_V3_BEHAVIOR_COARSE'],pool_layer='ordinary_manual',
       common_support='Intersection of candidate, Q_MEDIAN2 and old V3_BEHAVIOR coarse known workers, separately per heldout building and actual image.',
       no_new_fusion=True,no_new_candidates=True,labels_unchanged=True,
       aggregation='Equal class means within and unordered class-pair means across; same image and common exact person pool; then equal image/building.',
       interpretation='Descriptive separation comparison; candidates differ in class count and class balance. Not a causal gain or proof of better fused quality.',
       image_comparison_rows=len(result),panels=len(panels),unestimable_panels=len(missing)),p/'COMMON_SUPPORT_RAW_RECEIPT.json')
    print('Finished',len(result),'common-support rows')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--classifications',required=True);ap.add_argument('--features',required=True);ap.add_argument('--old',required=True);main(ap.parse_args())
