"""Hypothetical pool restrictions; never edit eligibility or source votes.

Retain each target building's original LOBO labels, without rebalancing or
retraining. Restrict precomputed 4-person subset scores to those that do not
contain the specified people, and compare survivors in the restricted pool.
This is distinct from removing people only as comparison candidates while
retaining them in the 3-person backgrounds.
"""
from pathlib import Path
import argparse,json
import numpy as np
import pandas as pd
from explore_replacements import design,analyze_scores,lobo_train,aggregate_frame,POLICIES,METHODS,EPS


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-dir',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    if args.out.exists():raise ValueError('fresh output directory required')
    src=args.source_dir;r=json.loads((src/'rosters.json').read_text());workers=np.array(r['workers']);groups=r['groups']
    buildings=np.array([g['building'] for g in groups]);z=np.load(src/'subsets.npz',allow_pickle=False);members=z['members']
    x=np.zeros((len(members),24));x[np.arange(len(members))[:,None],members]=1
    matrix={q:pd.read_csv(src/f'matrix_{q}_iou.csv',float_precision='round_trip').iloc[:,2:].to_numpy() for q in POLICIES}
    omit_sets=[()]+[(w,) for w in workers]+[('P017','P002')]
    rows=[];checks=[]
    for omit in omit_sets:
        keep=~np.isin(workers,omit);n=int(keep.sum());included=np.sum(x[:,~keep],axis=1)==0;xr=x[included][:,keep]
        restricted_workers=workers[keep].tolist()
        # Only the focal pre-identified two-person sensitivity enumerates full
        # context distributions; every leave-one effect mean is still exact.
        focal=omit==('P017','P002')
        if focal:
            remap={old:new for new,old in enumerate(np.flatnonzero(keep))}
            newmembers=np.array([[remap[int(j)] for j in row] for row in members[included]])
            d=design(newmembers,n)
            assert d['ia'].shape==(231,1140)
        for gi,g in enumerate(groups):
            for method in METHODS:
                for ep in POLICIES:
                    version='manual_revision' if ep=='revised_where_available' and f"{g['key']}_{method}_manual_revision" in z else 'original'
                    scores=z[f"{g['key']}_{method}_{version}"][included];mu=scores.mean()
                    inc=xr.T@scores/xr.sum(0);beta=(n-1)/(n-4)*(inc-mu)
                    if focal:
                        analysis=analyze_scores(d,scores)
                        assert np.max(abs(beta-analysis['beta']))<2e-14
                    for cp in POLICIES:
                        _,fullhigh=lobo_train(matrix[cp],buildings,g['building']);high=fullhigh[keep]
                        contrast=float(beta[high].mean()-beta[~high].mean())
                        row=dict(image=g['image'],building=g['building'],method=method,evaluation_policy=ep,calibration_policy=cp,
                            excluded_from_candidates_and_backgrounds='|'.join(omit) or 'none',
                            hypothetical_pool_n=n,subset_n=len(scores),higher_n=int(high.sum()),lower_n=int((~high).sum()),
                            higher_minus_lower_replacement=contrast,
                            mean_iou_over_surviving_subsets=float(mu),original_lobo_labels_unchanged=True)
                        if focal:
                            cross=high[d['pairs'][:,0]]!=high[d['pairs'][:,1]]
                            orientation=np.where(high[d['pairs'][:,0]],1.,-1.)
                            delta=analysis['delta'][cross]*orientation[cross,None]
                            error=abs(contrast-delta.mean());assert error<2e-13;checks.append(float(error))
                            row.update(common_background_n=1140,cross_pair_n=int(cross.sum()),
                                higher_wins_fraction=float(np.mean(delta>EPS)),lower_wins_fraction=float(np.mean(delta< -EPS)),
                                tie_fraction=float(np.mean(abs(delta)<=EPS)),
                                cross_pairs_both_signs=int(np.sum((delta.max(1)>EPS)&(delta.min(1)<-EPS))))
                        rows.append(row)
    f=pd.DataFrame(rows);summary=[]
    for scheme in ['equal_image','equal_building']:
        a=aggregate_frame(f,['method','evaluation_policy','calibration_policy','excluded_from_candidates_and_backgrounds'],
            ['higher_minus_lower_replacement','higher_wins_fraction','lower_wins_fraction','tie_fraction','cross_pairs_both_signs'],scheme)
        a['weighting']=scheme;summary.append(a)
    args.out.mkdir(parents=True)
    f.to_csv(args.out/'restricted_pool_by_image.csv',index=False,float_format='%.17g')
    pd.concat(summary).to_csv(args.out/'restricted_pool_aggregate.csv',index=False,float_format='%.17g')
    (args.out/'validation.json').write_text(json.dumps(dict(max_focal_mean_identity_error=max(checks),rows=len(f),
        no_gt_or_source_eligibility_edits=True,original_labels_preserved=True,scope='all 24 single-person restrictions and one pre-identified double restriction'),indent=2)+'\n')
    print('Completed',len(f),'rows; focal identity max error',max(checks))
if __name__=='__main__':main()
