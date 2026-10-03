"""Pro/dot返回的定向复核；只写新审计，不改资格、坐标或旧实验。"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from itertools import combinations
import json
from math import comb, log, sqrt
from pathlib import Path
import warnings
import zlib

import numpy as np
from scipy.stats import rankdata

from .lee_tile_stage1_20261002 import ROOT, METHODS, write_csv, write_json
from .lee_tile_precision_20261003 import integration_basis, measure_masks, subset_mask, exact_ks

B = ROOT/'analysis_results/worker_profiles_20261003'
A = ROOT/'analysis_results/lee_expanded_20261003'
ARCHIVE = ROOT/'research/consensus_reviews_20261003'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def csv_rows(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def keypoints(annotation):
    return [(r['id'], r['value']['x']*r['original_width']/100,
             r['value']['y']*r['original_height']/100)
            for r in annotation['result'] if r['type']=='keypointlabels']


def parent_evidence(task, annotation_id):
    annotations = {a['id']:a for a in task['annotations']}
    if len(annotations) != len(task['annotations']):
        raise ValueError('duplicate_raw_annotation_ids')
    a = annotations[annotation_id]; parent_id = a.get('parent_annotation')
    parent = annotations.get(parent_id); chain=[]; visited={annotation_id}; current=a
    status='resolved'
    while current.get('parent_annotation') is not None:
        p=current['parent_annotation']
        if p in visited:
            raise ValueError('parent_cycle')
        visited.add(p); chain.append(p)
        if p not in annotations:
            status='missing_parent'; break
        current=annotations[p]
    author=lambda a: a['completed_by']['id'] if isinstance(a['completed_by'], dict) else a['completed_by']
    return dict(annotation=annotation_id, author=author(a), parent_annotation=parent_id,
        parent_author=author(parent) if parent is not None else None,
        cross_author_parent=parent is not None and author(parent)!=author(a),
        same_parent_points=parent is not None and keypoints(a)==keypoints(parent),
        same_parent_result=parent is not None and a['result']==parent['result'],
        ancestor_ids=chain, root_annotation=current['id'] if status=='resolved' else None,
        lineage_status=status, created_at=a.get('created_at'), parent_prediction=a.get('parent_prediction'))


def source_audit(out):
    data=read(ROOT/'analysis_results/research_input_20260929/preprocessed_source.json')
    aliases={f'R{j:05d}':o for j,o in enumerate(sorted(data['objects'],key=lambda r:r['object_id']),1)}
    roster=read(B/'rosters.json'); frozen={i['code']:i for i in read(B/'input.json')['images']}
    cache={}; rows=[]; duplicate_rows=[]; image_rows=[]
    for group in roster['groups']:
        objects={}; raw={}; records={r['worker']:r for r in frozen[group['image']]['annotations']}
        for record_id, worker in zip(group['record_ids'], roster['workers']):
            o=aliases[record_id]; s=o['source']; path=s['path']
            if path not in cache:
                tasks=read(ROOT/path); cache[path]={t['id']:t for t in tasks}
                if len(tasks)!=len(cache[path]):raise ValueError('duplicate_raw_task_ids')
            task=cache[path][s['task']]
            a=next(a for a in task['annotations'] if a['id']==s['annotation'])
            evidence=parent_evidence(task,s['annotation'])
            points=np.array([p[1:] for p in keypoints(a)])
            expected=np.array(o['original_export_points'])
            if points.shape!=expected.shape:raise ValueError('raw_point_count_mismatch:'+record_id)
            error=float(np.max(abs(points-expected)))
            if error>1e-9:raise ValueError('raw_point_binding_mismatch:'+record_id)
            if o['image_code']!=group['image'] or s['worker']!=o['worker_id']:
                raise ValueError('source_identity_mismatch:'+record_id)
            rows.append(dict(image=group['image'],worker=worker,record_id=record_id,
                source_path=path,project=s['project'],task=s['task'],**evidence,
                raw_point_binding_max_error=error,existing_independent_flag=o['independent_vote_eligible'],
                interpretation='user_20261003_keep_independent_no_requalification'))
            objects[worker]=o;raw[worker]=a
        unique=len({json.dumps(records[w]['footprint']) for w in roster['workers']})
        image_rows.append(dict(image=group['image'],unique_exact_footprints=unique,
                              candidates=24,cross_author_parent_n=sum(r['cross_author_parent'] for r in rows if r['image']==group['image'])))
        for wa,wb in combinations(roster['workers'],2):
            ra,rb=records[wa],records[wb]
            if ra['footprint']!=rb['footprint'] and (wa,wb)!=('P002','P012'):continue
            oa,ob=objects[wa],objects[wb]
            duplicate_rows.append(dict(image=group['image'],worker_a=wa,worker_b=wb,
                footprint_exact_equal=ra['footprint']==rb['footprint'],prepared_points_equal=ra['points']==rb['points'],
                original_export_points_equal=oa['original_export_points']==ob['original_export_points'],
                raw_points_and_ids_equal=keypoints(raw[wa])==keypoints(raw[wb]),
                raw_result_equal=raw[wa]['result']==raw[wb]['result'],
                direct_parent_link=raw[wa].get('parent_annotation')==raw[wb]['id'] or raw[wb].get('parent_annotation')==raw[wa]['id']))
    write_json(out/'source_evidence.json',rows);write_csv(out/'duplicate_pairs.csv',duplicate_rows)
    write_csv(out/'source_by_image.csv',image_rows)
    return dict(records=len(rows),source_files=len(cache),cross_author_parents=sum(r['cross_author_parent'] for r in rows),
        same_parent_points_and_ids=sum(r['same_parent_points'] for r in rows),
        unresolved_lineage=sum(r['lineage_status']!='resolved' for r in rows),
        raw_point_max_error=max(r['raw_point_binding_max_error'] for r in rows),
        unique_footprints_by_image=[r['unique_exact_footprints'] for r in image_rows],
        user_decision='All records retain independent status; duplicate coordinates remain separate votes. Metadata does not adjudicate observed human behavior.')


def rho(a,b):
    x,y=rankdata(a),rankdata(b)
    return float(np.corrcoef(x,y)[0,1]) if np.std(x) and np.std(y) else None


def relative_skill(y, buildings):
    residual=y-y.mean(1,keepdims=True); prediction=np.empty_like(y)
    for b in set(buildings):
        target=np.array(buildings)==b
        prediction[target]=residual[~target].mean(0)
    return float(1-np.sum((residual-prediction)**2)/np.sum(residual**2))


def half_probability(x):
    cut=np.sort(x)[len(x)//2]; ties=np.isclose(x,cut,atol=1e-12,rtol=0)
    mandatory=x>cut+1e-12
    return mandatory.astype(float)+ties*(len(x)//2-mandatory.sum())/ties.sum()


def profile_audit(out):
    roster=read(B/'rosters.json'); workers=roster['workers'];buildings=[g['building'] for g in roster['groups']]
    results={}; split_rows=[]
    for policy in ('original','revised_where_available'):
        y=np.array([[float(r[w]) for w in workers] for r in csv_rows(B/f'matrix_{policy}_iou.csv')])
        c=np.array([[float(r[w]) for w in workers] for r in csv_rows(B/f'matrix_{policy}_centroid_normalized.csv')])
        ds=[]; unique=sorted(set(buildings))
        for bs in combinations(unique,4):
            if unique[0] not in bs:continue
            mask=np.isin(buildings,bs);x=y[mask].mean(0);z=y[~mask].mean(0)
            px,pz=half_probability(x),half_probability(z)
            ds.append(dict(policy=policy,buildings_a='|'.join(bs),rank_rho=rho(x,z),
                expected_same_half=float(np.mean(px*pz+(1-px)*(1-pz)))))
        split_rows.extend(ds)
        influence={}
        for omitted in ([],['P002'],['P017'],['P017','P002']):
            keep=~np.isin(workers,omitted)
            influence['|'.join(omitted) or 'none']=relative_skill(y[:,keep],buildings)
        results[policy]=dict(relative_skill=influence,loss_centroid_rho=rho(1-y.mean(0),c.mean(0)),
            split_median_rho=float(np.median([d['rank_rho'] for d in ds])),
            split_median_same_half=float(np.median([d['expected_same_half'] for d in ds])),
            largest_three_centroid_share=float(np.sort(c.sum(1))[-3:].sum()/c.sum()))
    write_csv(out/'disjoint_checks.csv',split_rows)
    return results


def replacement_design(members,n):
    if not np.issubdtype(members.dtype,np.integer):raise ValueError('integer_members_required')
    k=members.shape[1];tuples=[tuple(s) for s in members.tolist()]
    if set(tuples)!=set(combinations(range(n),k)) or len(tuples)!=comb(n,k):
        raise ValueError('complete_unique_subset_design_required')
    lookup={s:j for j,s in enumerate(tuples)};pairs=[];ia=[];ib=[];bg=[]
    for a,b in combinations(range(n),2):
        backgrounds=list(combinations([w for w in range(n) if w not in (a,b)],k-1))
        pairs.append((a,b));bg.append(backgrounds)
        ia.append([lookup[tuple(sorted((*t,a)))] for t in backgrounds])
        ib.append([lookup[tuple(sorted((*t,b)))] for t in backgrounds])
    return np.array(pairs),np.array(ia),np.array(ib),np.array(bg)


def replacement_audit(members,y,higher,design=None,omit=()):
    n=len(higher);k=members.shape[1]
    pairs,ia,ib,bg=design if design is not None else replacement_design(members,n)
    if y.shape!=(len(members),) or not np.isfinite(y).all():raise ValueError('invalid_scores')
    inclusion=np.array([y[(members==j).any(1)].mean() for j in range(n)])
    beta=(n-1)/(n-k)*(inclusion-y.mean());fitted=y.mean()+beta[members].sum(1)
    delta=y[ia]-y[ib];identity=float(np.max(abs(delta.mean(1)-(beta[pairs[:,0]]-beta[pairs[:,1]]))))
    cross=higher[pairs[:,0]]!=higher[pairs[:,1]]
    if omit:cross &= ~np.isin(pairs,omit).any(1)
    orientation=np.where(higher[pairs[:,0]],1,-1)
    oriented=delta[cross]*orientation[cross,None]
    if omit:oriented=oriented[~np.isin(bg[cross],omit).any(2)]
    variance=float(np.var(y));residual=float(np.mean((y-fitted)**2))
    return dict(mean_gain=float(oriented.mean()),positive=float(np.mean(oriented>1e-12)),
        negative=float(np.mean(oriented< -1e-12)),tie=float(np.mean(abs(oriented)<=1e-12)),
        pair_identity_max_error=identity,residual_fraction=residual/variance if variance and not omit else None,
        pairs_sign_flip=int(np.sum((delta.max(1)>1e-12)&(delta.min(1)<-1e-12))) if not omit else None,
        evaluated_contrasts=int(oriented.size))


def replacements_audit(out):
    roster=read(B/'rosters.json');archive=np.load(B/'subsets.npz',allow_pickle=False)
    members=archive['members'];workers=roster['workers'];design=replacement_design(members,len(workers))
    ass=csv_rows(B/'lobo_assignments.csv');rows=[]
    for g in roster['groups']:
        for policy in ('original','revised_where_available'):
            higher=np.array([next(r['relative_half']=='higher' for r in ass if r['worker']==w and r['policy']==policy and r['target_building']==g['building']) for w in workers])
            for method in METHODS:
                version='manual_revision' if policy!='original' and f"{g['key']}_{method}_manual_revision" in archive else 'original'
                y=archive[f"{g['key']}_{method}_{version}"]
                for omitted in ((),(workers.index('P017'),workers.index('P002'))):
                    rows.append(dict(image=g['image'],building=g['building'],policy=policy,method=method,
                        omitted='P017|P002' if omitted else 'none',
                        **replacement_audit(members,y,higher,design,omitted)))
    write_csv(out/'replacement_checks.csv',rows)
    summaries=[]
    for policy in ('original','revised_where_available'):
        for method in METHODS:
            for omitted in ('none','P017|P002'):
                rs=[r for r in rows if (r['policy'],r['method'],r['omitted'])==(policy,method,omitted)]
                summaries.append(dict(policy=policy,method=method,omitted=omitted,
                    **{k:float(np.mean([r[k] for r in rs])) if all(r[k] is not None for r in rs) else None
                       for k in ('mean_gain','positive','negative','tie','residual_fraction','pairs_sign_flip')},
                    max_pair_identity_error=max(r['pair_identity_max_error'] for r in rs)))
    write_csv(out/'replacement_summary.csv',summaries)
    return summaries


def area_audit(out):
    data=read(B/'input.json');roster=read(B/'rosters.json');ass=csv_rows(B/'lobo_assignments.csv')
    members=np.load(B/'subsets.npz',allow_pickle=False)['members'];rows=[];notices=[]
    for g in roster['groups']:
        im=next(i for i in data['images'] if i['code']==g['image']);byid={r['id']:r for r in im['annotations']}
        refs={r['version']:r['footprint'] for r in im['references']};rs=[byid[j] for j in g['record_ids']]
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always',RuntimeWarning);basis=integration_basis(rs,refs)
            counts=basis['mesh']['votes'][members].sum(1);area=basis['mesh']['area']
            for policy in ('original','revised_where_available'):
                high=np.array([next(r['relative_half']=='higher' for r in ass if r['worker']==w and r['policy']==policy and r['target_building']==g['building']) for w in roster['workers']])
                hc=high[members].sum(1)
                for method in METHODS:
                    selected=counts>=(2 if method=='mv50' else 3)
                    for h in range(5):
                        q=selected[hc==h].mean(0);v=float(area@(q*(1-q)))
                        for version,gt in basis['references'].items():
                            inter=np.array([t.intersection(gt).area for t in basis['mesh']['tiles']])
                            risk=float(gt.area+area@q-2*inter@q)
                            bias=float(inter@((1-q)**2)+(area-inter)@(q*q)+gt.area-inter.sum())
                            if abs(risk-bias-v)>1e-9:raise ValueError('area_decomposition_mismatch')
                            rows.append(dict(image=g['image'],building=g['building'],policy=policy,method=method,
                                version=version,higher_n=h,R_gt=risk/gt.area,B_gt=bias/gt.area,V_gt=v/gt.area))
            notices.extend(dict(image=g['image'],message=str(w.message)) for w in caught)
            notices.extend(dict(image=g['image'],message=m) for m in basis['warnings'])
    write_csv(out/'area_checks.csv',rows);write_json(out/'area_warnings.json',notices)
    return dict(rows=len(rows),warnings=len(notices),max_identity_residual=max(abs(r['R_gt']-r['B_gt']-r['V_gt']) for r in rows))


def paired_radius(widths,draws):
    return sqrt(log(4/.05)*sum(w*w for w in widths)/(2*draws*len(widths)**2))


def count_contrast_audit(out):
    data=read(A/'input.json');rosters=read(A/'rosters.json');draws=16384;seed=30412027
    rows=[];widths=[];notices=[];sums={m:np.zeros(draws) for m in METHODS}
    for group in rosters:
        n=len(group['record_ids'])
        if n<20:continue
        im=next(i for i in data['images'] if i['code']==group['image'])
        byid={r['id']:r for r in im['annotations']};rs=[byid[r] for r in group['record_ids']]
        refs={r['version']:r['footprint'] for r in im['references'] if r['version']=='original'}
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always',RuntimeWarning);basis=integration_basis(rs,refs)
            rng=np.random.default_rng(seed+zlib.crc32(im['code'].encode()))
            orders=np.array([rng.permutation(n) for _ in range(draws)],dtype=np.uint8)
            masks=np.bitwise_or.accumulate(1<<orders.astype(np.uint32),axis=1)
            exact=20 in exact_ks(n);widths.append(1 if exact else 2)
            m20=np.array([subset_mask(s) for s in combinations(range(n),20)],dtype=np.uint32) if exact else masks[:,19]
            for method in METHODS:
                y8=measure_masks(basis,masks[:,7],8,method)['original']
                y20=measure_masks(basis,m20,20,method)['original']
                delta=(float(y20.mean()) if exact else y20)-y8;sums[method]+=delta
                rows.append(dict(image=im['code'],method=method,n=n,k20_exact=exact,mean_gain=float(delta.mean())))
            notices.extend(dict(image=im['code'],message=str(w.message)) for w in caught)
            notices.extend(dict(image=im['code'],message=m) for m in basis['warnings'])
    summaries=[];radius=paired_radius(widths,draws)
    for method,total in sums.items():
        delta=total/len(widths);mean=float(delta.mean())
        summaries.append(dict(method=method,images=len(widths),draws=draws,seed=seed,mean_gain=mean,
            mc_se=float(delta.std(ddof=1)/sqrt(draws)),hoeffding_radius=radius,lower=mean-radius,upper=mean+radius,
            theoretical_squared_width_sum=sum(w*w for w in widths)))
    write_csv(out/'count_contrast_per_image.csv',rows);write_json(out/'count_contrast_summary.json',summaries)
    write_json(out/'count_contrast_warnings.json',notices)
    return summaries


def compare_returns(out, summary):
    ext=ARCHIVE/'worker_20261003';checks=[]
    def check(label,actual,expected):
        error=abs(actual-expected)
        if error>1e-10:raise ValueError('external_numeric_mismatch:'+label)
        checks.append(dict(check=label,actual=actual,external=expected,absolute_error=error))
    pro=read(ext/'pro/results/profile_analysis_summary.json')
    for policy,r in summary['profiles'].items():
        for key,other in [('loss_centroid_rho','iou_centroid_profile_spearman'),('split_median_rho','disjoint_split_median_rho'),('split_median_same_half','disjoint_split_median_same_half')]:
            check(policy+':'+key,r[key],pro[policy][other])
        for omitted,k in [('none','influence_none'),('P017','influence_P017'),('P017|P002','influence_P017-P002')]:
            check(policy+':skill:'+omitted,r['relative_skill'][omitted],pro[policy][k]['skill'])
    rows=csv_rows(ext/'dot/worker-audit-exploration/results_v2/group_contrasts_aggregate.csv')
    restricted=csv_rows(ext/'dot/worker-audit-exploration/restricted_results/restricted_pool_aggregate.csv')
    for r in summary['replacements']:
        source=rows if r['omitted']=='none' else [t for t in restricted if t['excluded_from_candidates_and_backgrounds']=='P017|P002']
        t=next(t for t in source if t['method']==r['method'] and t['evaluation_policy']==r['policy'] and t['calibration_policy']==r['policy'] and t['weighting']=='equal_image')
        for key,ek in [('mean_gain','higher_minus_lower_replacement'),('positive','higher_wins_fraction'),('negative','lower_wins_fraction'),('tie','tie_fraction')]:
            check(':'.join([r['policy'],r['method'],r['omitted'],key]),r[key],float(t[ek]))
    area=csv_rows(ext/'dot/worker-audit-risk/results/risk_decomposition_all10.csv')
    index={(r['image'],r['calibration_policy'],r['method'],r['version'],r['higher_n']):r for r in area}
    own=csv_rows(out/'area_checks.csv')
    for r in own:
        t=index[r['image'],r['policy'],r['method'],r['version'],r['higher_n']]
        for k in ['R_gt','B_gt','V_gt']:
            check(':'.join([r['image'],r['policy'],r['method'],r['version'],r['higher_n'],k]),float(r[k]),float(t[k]))
    cs=read(ext/'dot/expanded_count_independent_20261003/independent_results/paired_contrast_summary.json')
    for r in summary['count_contrast']:
        t=next(t for t in cs if t['seed']=='new' and t['method']==r['method'])
        for key,ek in [('mean_gain','mean_gain'),('mc_se','mc_se'),('hoeffding_radius','paired_two_rule_family_hoeffding')]:
            check('count:'+r['method']+':'+key,r[key],t[ek])
    write_csv(out/'external_comparisons.csv',checks)
    contrasts=[]
    for method in METHODS:
        for im in sorted({r['image'] for r in own}):
            rs=[r for r in own if r['image']==im and r['policy']=='original' and r['version']=='original' and r['method']==method]
            lo=next(r for r in rs if r['higher_n']=='0');hi=next(r for r in rs if r['higher_n']=='4')
            contrasts.append(dict(image=im,building=lo['building'],method=method,
                **{k:float(hi[k])-float(lo[k]) for k in ['R_gt','B_gt','V_gt']}))
    write_csv(out/'area_contrasts.csv',contrasts)
    return dict(external_numeric_comparisons=len(checks),max_absolute_difference=max(r['absolute_error'] for r in checks))


def next_panel(out):
    roster=read(B/'rosters.json');known={g['building'] for g in roster['groups']};workers=set(roster['workers'])
    images={i['code']:i for i in read(A/'input.json')['images']};rows=[]
    for group in read(A/'rosters.json'):
        im=images[group['image']]
        if im['building'] in known:continue
        common=workers&set(group['workers']);unseen=set(group['workers'])-workers
        rows.append(dict(image=im['code'],building=im['building'],difficulty=im['difficulty'],
            original_roster_n=len(group['workers']),calibrated_worker_n=len(common),
            calibrated_workers='|'.join(sorted(common)),unseen_workers='|'.join(sorted(unseen)),all_workers_calibrated=not unseen))
    write_csv(out/'next_building_panel.csv',rows)
    selected=[r for r in rows if r['all_workers_calibrated'] and r['original_roster_n']>=4]
    return dict(outside_calibration_images=len(rows),outside_calibration_buildings=len({r['building'] for r in rows}),
        full_roster_calibrated_at_least4_images=len(selected),selected_buildings=len({r['building'] for r in selected}),
        selected_difficulty_counts=dict(Counter(r['difficulty'] for r in selected)),
        limitation='Coverage inventory only; these images already appeared in A-line, not a new blind validation sample. Unprofiled people retained in ledger, not silently dropped.')


def main():
    parser=argparse.ArgumentParser(__doc__);parser.add_argument('--out',type=Path,default=ROOT/'analysis_results/worker_review_20261003')
    args=parser.parse_args();out=args.out
    if out.exists():raise ValueError('use_new_output_directory')
    out.mkdir(parents=True)
    write_json(out/'design.json',dict(schema='worker_return_review_v1',status='started',
        user_decision='2026-10-03: no reference to others; duplicate coordinates count as independent annotations; no eligibility change',
        scope='external numerical checks and raw metadata trace, no visual adjudication or independent-person causal inference'))
    summary=dict(source=source_audit(out),profiles=profile_audit(out),replacements=replacements_audit(out),
                 area=area_audit(out),count_contrast=count_contrast_audit(out))
    summary['comparison']=compare_returns(out,summary)
    summary['next_panel']=next_panel(out)
    write_json(out/'summary.json',summary)
    write_json(out/'field_contract.json',dict(schema='worker_return_review_v1',
        source='Raw export linkage and keypoint equality only; parent metadata is not a behavior judgment. User directs all records retain independence and separate votes.',
        replacement='Mean and signs across uniform cross-half person pairs and shared 3-person backgrounds; restricted pool keeps original labels; neither causal nor population CI.',
        additive='Uses target scores only to describe finite-pool non-additivity. Not a deployable or held-out worker model. Restricted-pool residual/sign-flip fields are null; no new restricted additive fit is claimed.',
        area='R=B+V is area symmetric-difference loss. GT-area normalized quantities, not average IoU or person/image variance components.',
        count='Same fixed 33 images, independent PRNG streams per image; simultaneous bound across 2 rules only, conditional on frozen data. Reuses external seed to replicate, not an independent confirmatory dataset.',
        next_panel='Coverage only outside the eight B-line buildings. original_roster_n includes all existing candidates; unseen_workers remain listed. Selected means full roster calibrated and at least four people, not new eligibility or blind validation.',
        frozen='B240 and A1496 retain prior roster, gates and vote rules. Historical results are not overwritten.'))
    design=read(out/'design.json');write_json(out/'design.json',dict(design,status='completed'))
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
