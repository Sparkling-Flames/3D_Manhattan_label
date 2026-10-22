#!/usr/bin/env python3
"""Group/case, uncertain-label and algebraic finite-family diagnostics.

Scenarios are possibilities, never sampling probabilities. No scenario chooses
parameters or changes the received labels. No unused holdout is consulted.
"""
from __future__ import annotations
import argparse,csv,itertools,json,sys,math
from pathlib import Path
import numpy as np
from candidate_functions import PRIMARY_METHODS,DIAGNOSTIC_METHODS,top_weight_score
from run_candidates import readcsv,csvwrite,dump

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path.cwd());ar=ap.parse_args();r=ar.root.resolve();p=r/'top_structure_20261012';o=p/'analysis/sensitivity';o.mkdir(parents=True,exist_ok=True)
    rows=json.loads((p/'analysis/results/candidate_scores_39.json').read_text());rs={x['record_id']:x for x in rows}
    old=json.loads((r/'study_borderline/results/old24_evidence.json').read_text());labels=np.array([x['quality_ordinal_original'] for x in old]);methods=PRIMARY_METHODS+DIAGNOSTIC_METHODS
    q=np.array([[rs[x['record_id']][m] for x in old] for m in methods]);pair=np.array(list(itertools.combinations(range(24),2)));ia,ib=pair.T
    qsign=np.sign(q[:,ia]-q[:,ib]);
    def inv(y,keep=None):
        ls=np.sign(y[ib]-y[ia]);mask=ls!=0
        if keep is not None:mask &= keep[ia]&keep[ib]
        return ((qsign[:,mask]*ls[mask])<0).sum(axis=1),int(mask.sum())
    base,den=inv(labels);assert den==164
    # Preserve the prior four-grade adjacency convention: an originally
    # obvious (2) case may provisionally move to severe (3). The unobserved
    # severe grade is not used to fit the old24 two-cutpoint comparison.
    options={i:[v for v in [int(labels[i])-1,int(labels[i])+1] if 0<=v<=3] for i in range(24)}
    scenarios=[]
    for k in [1,2]:
        for inds in itertools.combinations(range(24),k):
            for vals in itertools.product(*(options[i] for i in inds)):
                y=labels.copy();y[list(inds)]=vals;iv,n=inv(y)
                x={'changed_count':k,'case_ids':';'.join(old[i]['case_id'] for i in inds),'alternate_grades':';'.join(map(str,vals)),'pairs':n}
                x.update({m:int(v) for m,v in zip(methods,iv)});scenarios.append(x)
    csvwrite(o/'adjacent_label_scenarios.csv',scenarios)
    comparisons=[(m,'Q_v11') for m in methods if m!='Q_v11']+[(m,'Q_no_topS') for m in ['Q_top_1_16','Q_max_quarter','Q_split_equal','Q_split_local025','Q_no_top_Xrms8','Q_no_top_Xmax8']]
    summaries=[]
    for m,b in comparisons:
        for k in [1,2]:
            ss=[x for x in scenarios if x['changed_count']==k];ds=[x[m]-x[b] for x in ss]
            summaries.append({'method':m,'baseline':b,'changed_count':k,'scenarios':len(ss),'inversion_difference_min':min(ds),'inversion_difference_max':max(ds),'base_inversion_difference':int(base[methods.index(m)]-base[methods.index(b)]),'scenarios_are_probabilities':False})
    csvwrite(o/'adjacent_label_sensitivity_summary.csv',summaries)
    omissions=[]
    for unit,key in [('case','case_id'),('image','image_code'),('building','building_id')]:
        for value in sorted({x[key] for x in old}):
            keep=np.array([x[key]!=value for x in old]);iv,n=inv(labels,keep)
            for m,v in zip(methods,iv):omissions.append({'omitted_unit':unit,'omitted_id':value,'remaining_records':int(keep.sum()),'pairs':n,'method':m,'inversions':int(v),'removal_is_sensitivity_not_new_exclusion':True})
    csvwrite(o/'group_case_omissions.csv',omissions)
    blocks=[]
    ls=np.sign(labels[ib]-labels[ia]);group={}
    for j,(a,b) in enumerate(pair):
        if ls[j]==0:continue
        key=tuple(sorted((old[a]['image_code'],old[b]['image_code'])));group.setdefault(key,[]).append(j)
    for m_i,m in enumerate(methods):
        allrates=[]
        for (a,b),ix in group.items():
            bad=int(((qsign[m_i,ix]*ls[ix])<0).sum());rate=bad/len(ix);allrates.append(rate)
            blocks.append({'method':m,'image_a':a,'image_b':b,'pairs':len(ix),'inversions':bad,'inversion_fraction':rate,'same_image':a==b})
    csvwrite(o/'image_pair_block_rates.csv',blocks)
    block_summary=[{'method':m,'image_pair_blocks':len(group),'macro_mean_inversion_fraction':float(np.mean([x['inversion_fraction'] for x in blocks if x['method']==m])),'blocks_still_share_images_not_independent_samples':True} for m in methods]
    dump(o/'image_pair_macro_summary.json',block_summary)
    roots=[];changed_pairs=[]
    for x,y in itertools.combinations(rows,2):
        def terms(z):
            d,f=z['dir'],z['flat'];aa=100*z['iou_2d']*(1-.075*(d*d/(d*d+25)+f*f/(f*f+4)))
            return aa,1+z['S_bottom_deg']**2/32+(z['Hstar']/.5)**2,z['S_top_deg']**2/32
        a,da,ta=terms(x);b,db,tb=terms(y);bot=a*tb-b*ta;gamma=(b*da-a*db)/bot if abs(bot)>1e-12 else None
        if gamma is not None and 0<=gamma<=1:
            residual=top_weight_score(x,gamma)-top_weight_score(y,gamma);assert abs(residual)<1e-7
            roots.append({'case_a':x['old_case_id'] or x['new_case_id'],'case_b':y['old_case_id'] or y['new_case_id'],'record_a':x['record_id'],'record_b':y['record_id'],'same_image':x['image_id']==y['image_id'],'gamma_equal_score':gamma,'residual':residual,'root_is_human_threshold':False})
        for m in methods:
            if m=='Q_v11':continue
            oldsign=np.sign(x['Q_v11']-y['Q_v11']);newsign=np.sign(x[m]-y[m])
            if oldsign!=newsign:
                changed_pairs.append({'method':m,'case_a':x['old_case_id'] or x['new_case_id'],'case_b':y['old_case_id'] or y['new_case_id'],'same_image':x['image_id']==y['image_id'],'old_delta':x['Q_v11']-y['Q_v11'],'new_delta':x[m]-y[m],'rank_change_not_automatic_improvement':True})
    csvwrite(o/'top_weight_pair_roots_39.csv',roots);csvwrite(o/'candidate_pair_order_changes_39.csv',changed_pairs)
    fixed=[]
    for g in [0,.0625,.25,1]:
        vals=np.array([top_weight_score(rs[x['record_id']],g) for x in old]);sg=np.sign(vals[ia]-vals[ib]);mask=ls!=0
        fixed.append({'gamma':g,'old24_inversions':int(((sg[mask]*ls[mask])<0).sum()),'pairs':int(mask.sum()),'T20':top_weight_score(next(x for x in rows if x['old_case_id']=='T20'),g)})
    dump(o/'finite_gamma_summary.json',fixed)
    dump(o/'summary.json',{'old_quality_records':24,'images':len({x['image_code'] for x in old}),'buildings':len({x['building_id'] for x in old}),'old_cross_grade_pairs':164,'independent_pairs':False,'adjacent_scenarios':len(scenarios),'all_24_allowed_to_vary':True,'roots_within_gamma_0_1':len(roots),'unique_records_in_roots':len({x[k] for x in roots for k in ['record_a','record_b']}),'finite_gamma_grid':[0,.0625,.25,1],'parameters_chosen_from_scenarios':False,'grade_cutpoints_frozen':False})
    print(json.dumps({'finite_gamma':fixed,'new_methods_vs_noTop_adjacent':[x for x in summaries if x['baseline']=='Q_no_topS']},ensure_ascii=False))
if __name__=='__main__':main()
