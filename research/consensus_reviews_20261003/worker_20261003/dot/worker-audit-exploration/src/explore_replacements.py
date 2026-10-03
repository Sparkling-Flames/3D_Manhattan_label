"""Exact fixed-pool k=4 replacement diagnostics; no geometry or eligibility edits.

The score function on the complete k-subset design is projected onto additive
person terms. Pair mean effects are necessarily differences of those terms;
context dependence is assessed separately by the full paired difference array.
No sampling/human confidence intervals or causal/person-ability claims are made.
"""
from __future__ import annotations
import argparse
import hashlib
from itertools import combinations
import json
import math
from pathlib import Path
import platform
import sys

import numpy as np
import pandas as pd
from scipy.stats import rankdata, spearmanr

POLICIES = ('original', 'revised_where_available')
METHODS = ('mv50', 'mv_strict')
EPS = 1e-12


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tolerant_rank(values, epsilon=EPS):
    # Adjacent values within epsilon share an average rank. This prevents
    # algebraically equal conditional means from being split by roundoff.
    values=np.asarray(values,dtype=float)
    order=np.argsort(values,kind='stable'); result=np.zeros(len(values))
    start=0
    while start<len(values):
        stop=start+1
        while stop<len(values) and values[order[stop]]-values[order[start]]<=epsilon:
            stop+=1
        result[order[start:stop]]=(start+stop+1)/2
        start=stop
    return result


def correlation(a, b):
    a,b=tolerant_rank(a),tolerant_rank(b)
    if np.ptp(a)==0 or np.ptp(b)==0:
        return None
    return float(np.corrcoef(a,b)[0,1])


def design(members, n):
    members = np.asarray(members, dtype=int)
    if members.ndim != 2:
        raise ValueError('members must be a two-dimensional array')
    k = members.shape[1]
    expected = list(combinations(range(n), k))
    if not 0 < k < n:
        raise ValueError('subset size must be between zero and n')
    tuples = [tuple(sorted(row)) for row in members.tolist()]
    if len(tuples) != math.comb(n, k) or set(tuples) != set(expected):
        raise ValueError('the complete distinct subset design is required')
    lookup = {v: j for j, v in enumerate(tuples)}
    x = np.zeros((len(members), n), dtype=float)
    x[np.arange(len(members))[:, None], members] = 1
    pair, index_a, index_b, backgrounds = [], [], [], []
    for a, b in combinations(range(n), 2):
        bg = list(combinations([j for j in range(n) if j not in (a, b)], k-1))
        pair.append((a, b))
        index_a.append([lookup[tuple(sorted((*t, a)))] for t in bg])
        index_b.append([lookup[tuple(sorted((*t, b)))] for t in bg])
        backgrounds.append(bg)
    return dict(members=members, n=n, k=k, x=x, pairs=np.array(pair),
                ia=np.array(index_a, dtype=np.int32), ib=np.array(index_b, dtype=np.int32),
                backgrounds=np.array(backgrounds, dtype=np.int16))


def analyze_scores(d, scores):
    y = np.asarray(scores, dtype=float)
    if y.shape != (len(d['members']),) or not np.isfinite(y).all():
        raise ValueError('invalid scores')
    x, n, k = d['x'], d['n'], d['k']
    mu = float(y.mean())
    inclusion = x.T @ y / x.sum(axis=0)
    beta = (n-1)/(n-k)*(inclusion-mu)
    # Uses target reference scores for a descriptive/oracle decomposition only.
    # These terms are not calibration profiles or deployed fusion weights.
    fitted = mu+x@beta
    residual = y-fitted
    delta = y[d['ia']]-y[d['ib']]
    predicted_pair = beta[d['pairs'][:,0]]-beta[d['pairs'][:,1]]
    identity_error = float(np.max(np.abs(delta.mean(axis=1)-predicted_pair)))
    orthogonality = float(np.max(np.abs(x.T@residual / len(y))))
    variance = float(np.mean((y-mu)**2))
    additive_variance = float(np.mean((fitted-mu)**2))
    residual_variance = float(np.mean(residual**2))
    if identity_error > 2e-13 or orthogonality > 2e-13:
        raise AssertionError((identity_error, orthogonality))
    if abs(variance-additive_variance-residual_variance) > 2e-13:
        raise AssertionError('projection variance did not add up')
    return dict(mu=mu, inclusion=inclusion, beta=beta, fitted=fitted, residual=residual,
                delta=delta, identity_error=identity_error, orthogonality=orthogonality,
                score_variance=variance, additive_variance=additive_variance,
                residual_variance=residual_variance,
                additive_explained_fraction=additive_variance/variance if variance else None)


def delta_rows(delta, pairs, workers, meta):
    out=[]
    q=np.quantile(delta,[.1,.5,.9],axis=1)
    for z,(a,b) in enumerate(pairs):
        v=delta[z]; mean=float(v.mean())
        out.append(dict(**meta, worker_a=workers[a],worker_b=workers[b],
            common_background_n=len(v), mean_a_minus_b=mean,
            sd_a_minus_b=float(v.std()), min_a_minus_b=float(v.min()), max_a_minus_b=float(v.max()),
            p10=float(q[0,z]),median=float(q[1,z]),p90=float(q[2,z]),
            a_better_fraction=float(np.mean(v>EPS)),b_better_fraction=float(np.mean(v< -EPS)),
            tie_fraction=float(np.mean(np.abs(v)<=EPS)),
            both_signs=bool(v.max()>EPS and v.min()< -EPS),
            both_signs_gt_001=bool(v.max()>.001 and v.min()<-.001),
            both_signs_gt_005=bool(v.max()>.005 and v.min()<-.005),
            mean_winner_loses_fraction=float(np.mean(v*np.sign(mean)< -EPS)) if abs(mean)>EPS else None,
            mean_and_majority_disagree=bool(abs(mean)>EPS and np.mean(v>EPS)-np.mean(v< -EPS) != 0
                                          and mean*(np.mean(v>EPS)-np.mean(v< -EPS))<0)))
    return out


def lobo_train(matrix, buildings, target):
    train = np.asarray(buildings) != target
    if not train.any():
        raise ValueError('no training images')
    means = matrix[train].mean(axis=0)
    ordered=np.sort(means)
    if ordered[len(means)//2]-ordered[len(means)//2-1] < EPS:
        raise ValueError('LOBO cutoff is tied; do not resolve using worker IDs')
    high=means>np.median(means)
    return means,high


def aggregate_frame(frame, keys, metrics, scheme):
    if scheme == 'equal_image':
        return frame.groupby(keys, dropna=False)[metrics].mean().reset_index()
    building=frame.groupby(keys+['building'],dropna=False)[metrics].mean().reset_index()
    return building.groupby(keys,dropna=False)[metrics].mean().reset_index()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    if args.out.exists():
        raise ValueError('output directory already exists; use a fresh destination')
    src=args.source_dir
    roster=json.loads((src/'rosters.json').read_text())
    workers=roster['workers']; groups=roster['groups']; n=len(workers)
    if n!=24 or len(groups)!=10 or len({g['building'] for g in groups})!=8:
        raise AssertionError('the specified 24-person, 10-image, 8-building panel is required')
    matrices={}; paths=['subsets.npz','rosters.json','lobo_assignments.csv']
    for policy in POLICIES:
        name=f'matrix_{policy}_iou.csv';paths.append(name)
        f=pd.read_csv(src/name,float_precision='round_trip')
        if list(f.columns[2:])!=workers or list(f.image)!=[g['image'] for g in groups]:
            raise AssertionError('matrix order does not match roster')
        matrices[policy]=f.iloc[:,2:].to_numpy(float)
    buildings=np.array([g['building'] for g in groups])
    assignments=pd.read_csv(src/'lobo_assignments.csv',float_precision='round_trip')
    train_profiles={}; assignment_check=0.
    for policy in POLICIES:
        for b in sorted(set(buildings)):
            mean,high=lobo_train(matrices[policy],buildings,b)
            saved=assignments[(assignments.policy==policy)&(assignments.target_building==b)].set_index('worker').loc[workers]
            err=float(np.max(np.abs(mean-saved.calibration_mean_iou.to_numpy())))
            assignment_check=max(assignment_check,err)
            if err>2e-14 or not np.array_equal(high,saved.relative_half.to_numpy()=='higher'):
                raise AssertionError('independently reconstructed LOBO assignment differs')
            # Leakage diagnostic: target values cannot enter train profiles.
            changed=matrices[policy].copy();changed[buildings==b]=-999.
            mean2,high2=lobo_train(changed,buildings,b)
            if not np.array_equal(mean,mean2) or not np.array_equal(high,high2):
                raise AssertionError('target leakage in calibration')
            train_profiles[(policy,b)]=(mean,high)
    archive=np.load(src/'subsets.npz',allow_pickle=False)
    d=design(archive['members'],n)
    if d['k']!=4 or d['ia'].shape!=(276,1540):
        raise AssertionError('wrong replacement design')
    args.out.mkdir(parents=True)
    pair_rows=[];proj_rows=[];person_rows=[];group_rows=[];influence=[];background_rows=[]
    sensitivity=[];utility={};delta_cache={};score_cache={};projection_checks=[]
    revisions=[]
    for gi,g in enumerate(groups):
        if f"{g['key']}_mv50_manual_revision" in archive:
            revisions.append(g['image'])
        for method in METHODS:
            for policy in POLICIES:
                version='manual_revision' if policy=='revised_where_available' and f"{g['key']}_{method}_manual_revision" in archive else 'original'
                key=f"{g['key']}_{method}_{version}"
                if key not in archive:
                    raise AssertionError(f'missing expected score array {key}')
                y=archive[key]; a=analyze_scores(d,y)
                meta=dict(image=g['image'],building=g['building'],method=method,evaluation_policy=policy,actual_reference=version)
                pair_rows.extend(delta_rows(a['delta'],d['pairs'],workers,meta))
                utility[(gi,method,policy)]=a['beta']
                delta_cache[(gi,method,policy)]=a['delta']
                score_cache[(gi,method,policy)]=y
                p=dict(**meta,mean_iou=a['mu'],score_sd=math.sqrt(a['score_variance']),
                    additive_explained_fraction=a['additive_explained_fraction'],
                    score_variance=a['score_variance'],additive_variance=a['additive_variance'],residual_variance=a['residual_variance'],
                    residual_fraction=1-a['additive_explained_fraction'],
                    residual_rmse=math.sqrt(a['residual_variance']),
                    additive_sd=math.sqrt(a['additive_variance']),
                    pair_identity_max_error=a['identity_error'],
                    projection_orthogonality_max_error=a['orthogonality'])
                delta=a['delta']
                p.update(pairs_both_signs=int(np.sum((delta.max(1)>EPS)&(delta.min(1)<-EPS))),
                    pairs_both_signs_gt_001=int(np.sum((delta.max(1)>.001)&(delta.min(1)<-.001))),
                    pairs_both_signs_gt_005=int(np.sum((delta.max(1)>.005)&(delta.min(1)<-.005))),
                    median_pair_background_sd=float(np.median(delta.std(1))))
                proj_rows.append(p)
                for j,w in enumerate(workers):
                    person_rows.append(dict(**meta,worker=w,conditional_inclusion_mean=float(a['inclusion'][j]),
                        additive_utility=float(a['beta'][j]),target_single_iou=float(matrices[policy][gi,j]),
                        target_descriptive_fusion_utility_rank=float(tolerant_rank(-a['beta'])[j])))
                for cal in POLICIES:
                    mean,high=train_profiles[(cal,g['building'])]
                    cross=high[d['pairs'][:,0]]!=high[d['pairs'][:,1]]
                    orientation=np.where(high[d['pairs'][:,0]],1.,-1.)
                    oriented=delta[cross]*orientation[cross,None]
                    count_high=d['x']@high
                    contrast=float(a['beta'][high].mean()-a['beta'][~high].mean())
                    if abs(contrast-oriented.mean())>2e-13:
                        raise AssertionError('cross-group mean contrast mismatch')
                    gm=dict(**meta,calibration_policy=cal)
                    group_rows.append(dict(**gm,higher_minus_lower_replacement=contrast,
                        all_higher_minus_all_lower=float(y[count_high==4].mean()-y[count_high==0].mean()),
                        positive_cross_pair_fraction=float(np.mean(oriented.mean(1)>EPS)),
                        higher_wins_fraction=float(np.mean(oriented>EPS)),lower_wins_fraction=float(np.mean(oriented<-EPS)),
                        tie_fraction=float(np.mean(np.abs(oriented)<=EPS)),
                        cross_pairs_both_signs=int(np.sum((oriented.max(1)>EPS)&(oriented.min(1)<-EPS))),
                        training_single_vs_target_utility_rho=correlation(mean,a['beta']),
                        target_single_vs_target_utility_rho=correlation(matrices[policy][gi],a['beta']),
                        training_single_vs_target_single_rho=correlation(mean,matrices[policy][gi])))
                    # Candidate-contrast influence only. Keep the same 24-person scores,
                    # original high/low labels, and all paired backgrounds, even if they
                    # contain an omitted comparison candidate. No vote or geometry is removed.
                    omissions=[()] + [(w,) for w in workers] + [('P017','P002')]
                    for omit in omissions:
                        eligible=~np.isin(workers,omit)
                        h=high&eligible;l=(~high)&eligible
                        value=float(a['beta'][h].mean()-a['beta'][l].mean())
                        influence.append(dict(**gm,omitted_from_candidate_contrast='|'.join(omit) or 'none',
                            higher_candidates=int(h.sum()),lower_candidates=int(l.sum()),
                            fixed_24_person_background_pool=True,
                            higher_minus_lower_replacement=value,
                            change_from_all_candidates=value-contrast))
                    # Non-overlapping background strata clarify dependence on current
                    # calibration composition; these do not change target assignments.
                    cross_bg_high=high[d['backgrounds'][cross]].sum(2)
                    for hnum in range(4):
                        vals=oriented[cross_bg_high==hnum]
                        background_rows.append(dict(**gm,common_background_higher_n=hnum,
                            comparison_n=len(vals),mean_higher_minus_lower=float(vals.mean()),
                            sd_higher_minus_lower=float(vals.std()),
                            higher_wins_fraction=float(np.mean(vals>EPS)),lower_wins_fraction=float(np.mean(vals<-EPS))))
    # Aggregate candidate-contrast sensitivity; equal-building means first average
    # the two repeated-building image pairs, then give each building weight 1/8.
    pairdf=pd.DataFrame(pair_rows);projdf=pd.DataFrame(proj_rows);groupdf=pd.DataFrame(group_rows)
    influencedf=pd.DataFrame(influence);persondf=pd.DataFrame(person_rows);bgdf=pd.DataFrame(background_rows)
    grouped=[];influence_agg=[];proj_agg=[];bg_agg=[]
    gm=['higher_minus_lower_replacement','all_higher_minus_all_lower','positive_cross_pair_fraction',
        'higher_wins_fraction','lower_wins_fraction','tie_fraction','cross_pairs_both_signs',
        'training_single_vs_target_utility_rho','target_single_vs_target_utility_rho','training_single_vs_target_single_rho']
    for scheme in ('equal_image','equal_building'):
        keys=['method','evaluation_policy','calibration_policy']
        z=aggregate_frame(groupdf,keys,gm,scheme);z['weighting']=scheme;grouped.append(z)
        z=aggregate_frame(influencedf,keys+['omitted_from_candidate_contrast'],
                          ['higher_minus_lower_replacement','change_from_all_candidates'],scheme)
        z['weighting']=scheme;influence_agg.append(z)
        z=aggregate_frame(projdf,['method','evaluation_policy'],
                          ['additive_explained_fraction','residual_fraction','residual_rmse','score_variance','additive_variance','residual_variance','pairs_both_signs',
                           'pairs_both_signs_gt_001','pairs_both_signs_gt_005','median_pair_background_sd'],scheme)
        z['pooled_additive_fraction']=z.additive_variance/z.score_variance
        z['weighting']=scheme;proj_agg.append(z)
        z=aggregate_frame(bgdf,keys+['common_background_higher_n'],
                          ['mean_higher_minus_lower','higher_wins_fraction','lower_wins_fraction'],scheme)
        z['weighting']=scheme;bg_agg.append(z)
    # Pool each identical a,b,T contrast over the selected panel, rather than
    # pooling unrelated score observations; this still describes the fixed pool.
    agg_pairs=[];person_agg=[];pair_crossbuilding=[]
    for method in METHODS:
        for policy in POLICIES:
            arrays=np.stack([delta_cache[(i,method,policy)] for i in range(len(groups))])
            betas=np.stack([utility[(i,method,policy)] for i in range(len(groups))])
            building_delta=np.stack([arrays[buildings==b].mean(0) for b in sorted(set(buildings))])
            building_beta=np.stack([betas[buildings==b].mean(0) for b in sorted(set(buildings))])
            bmeans=building_delta.mean(2)
            for pi,(a,b) in enumerate(d['pairs']):
                v=bmeans[:,pi]
                pair_crossbuilding.append(dict(method=method,evaluation_policy=policy,worker_a=workers[a],worker_b=workers[b],
                    positive_buildings=int(np.sum(v>EPS)),negative_buildings=int(np.sum(v<-EPS)),tie_buildings=int(np.sum(abs(v)<=EPS)),
                    both_building_signs=bool(v.max()>EPS and v.min()<-EPS),
                    min_building_mean=float(v.min()),max_building_mean=float(v.max())))
            for scheme,avg,meanbeta in [('equal_image',arrays.mean(0),betas.mean(0)),
                                        ('equal_building',building_delta.mean(0),building_beta.mean(0))]:
                agg_pairs.extend(delta_rows(avg,d['pairs'],workers,dict(method=method,evaluation_policy=policy,weighting=scheme)))
                for j,w in enumerate(workers):
                    person_agg.append(dict(method=method,evaluation_policy=policy,weighting=scheme,worker=w,
                        additive_utility=float(meanbeta[j]),fusion_utility_rank=float(tolerant_rank(-meanbeta)[j]),
                        positive_images=int(np.sum(betas[:,j]>EPS)),negative_images=int(np.sum(betas[:,j]<-EPS)),
                        positive_buildings=int(np.sum(building_beta[:,j]>EPS)),negative_buildings=int(np.sum(building_beta[:,j]<-EPS))))
    # Paired sign sensitivity to references and vote rules; leave zero effects separate.
    for gi,g in enumerate(groups):
        for method in METHODS:
            x=utility[(gi,method,'original')];y=utility[(gi,method,'revised_where_available')]
            a=x[d['pairs'][:,0]]-x[d['pairs'][:,1]];b=y[d['pairs'][:,0]]-y[d['pairs'][:,1]]
            sensitivity.append(dict(kind='evaluation_reference',image=g['image'],building=g['building'],condition=method,
                changed_reference=g['image'] in revisions,utility_rank_rho=correlation(x,y),
                pair_mean_opposite_nonzero_signs=int(np.sum((a*b<0)&(abs(a)>EPS)&(abs(b)>EPS)))))
        for policy in POLICIES:
            x=utility[(gi,'mv50',policy)];y=utility[(gi,'mv_strict',policy)]
            a=x[d['pairs'][:,0]]-x[d['pairs'][:,1]];b=y[d['pairs'][:,0]]-y[d['pairs'][:,1]]
            sensitivity.append(dict(kind='vote_rule',image=g['image'],building=g['building'],condition=policy,
                changed_reference=None,utility_rank_rho=correlation(x,y),
                pair_mean_opposite_nonzero_signs=int(np.sum((a*b<0)&(abs(a)>EPS)&(abs(b)>EPS)))))
    tables={'pair_effects_by_image':pairdf,'additive_projection_by_image':projdf,
        'person_utility_by_image':persondf,'group_contrasts_by_image':groupdf,
        'candidate_influence_by_image':influencedf,'background_composition_by_image':bgdf,
        'group_contrasts_aggregate':pd.concat(grouped),'candidate_influence_aggregate':pd.concat(influence_agg),
        'additive_projection_aggregate':pd.concat(proj_agg),'background_composition_aggregate':pd.concat(bg_agg),
        'pair_effects_panel_average':pd.DataFrame(agg_pairs),'person_utility_panel_average':pd.DataFrame(person_agg),
        'pair_signs_across_buildings':pd.DataFrame(pair_crossbuilding),
        'reference_and_rule_sensitivity':pd.DataFrame(sensitivity)}
    for name,table in tables.items():
        table.to_csv(args.out/f'{name}.csv',index=False,float_format='%.17g')
    summary=dict(fixed_commit='405f3041fdd76977f625d50c558c63dbf342699d',workers=n,images=len(groups),buildings=len(set(buildings)),
        k=4,subsets=len(d['members']),person_pairs=len(d['pairs']),backgrounds_per_pair=d['ia'].shape[1],
        score_arrays_stored=len(archive.files)-2,score_cells_evaluated=len(proj_rows),revision_images=revisions,
        pair_image_policy_rows=len(pair_rows),pair_background_differences=40*276*1540,
        lobo_assignment_max_absolute_error=assignment_check,
        pair_identity_max_absolute_error=float(projdf.pair_identity_max_error.max()),
        additive_projection_orthogonality_max_absolute_error=float(projdf.projection_orthogonality_max_error.max()),
        definition='Delta(a,b;T)=f(T+a)-f(T+b), uniform T of size 3 excluding a,b; all 24 recorded votes retained.',
        exact_identity='E_T Delta(a,b;T)=(23/20)(E[f(S)|a in S]-E[f(S)|b in S])=beta_a-beta_b',
        additive_projection='fhat(S)=mean(f)+sum_{i in S} beta_i; beta_i=(23/20)(inclusion_mean_i-mean(f)), sum(beta)=0',
        numeric_tie_tolerance=EPS,illustrative_sign_reversal_thresholds=[.001,.005],
        target_projection_status='Descriptive/oracle use of target GT; never enters LOBO labels or deployed vote weights.',
        reference_policy='revised_where_available uses the 4 available revised references and original for the other 6 images',
        inference_boundary='Fixed selected finite pool. Scores are source artifacts, not new geometry reconstruction. No independent human sampling CI, no population or causal ability claim.',
        inputs={p:sha256(src/p) for p in paths},
        output_rows={k:len(v) for k,v in tables.items()},
        environment=dict(python=sys.version,numpy=np.__version__,pandas=pd.__version__,platform=platform.platform()))
    (args.out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
