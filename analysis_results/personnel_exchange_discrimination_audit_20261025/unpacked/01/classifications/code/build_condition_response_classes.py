#!/usr/bin/env python3
"""Finite new personnel candidates, frozen v2 data, both-condition LOBO.

No target-building response or fusion endpoint is used to fit labels.  The
candidate grid is intentionally finite; K2/3/4 are all retained for the parent's
matched-block experiment, without selecting on its target outcomes.
"""
from __future__ import annotations
import os
for _v in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[_v] = '1'
import argparse, gzip, hashlib, json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, cut_tree
from scipy.optimize import linear_sum_assignment
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_rand_score, silhouette_score

BASE_METRICS = ['turn_n', 'short_turn_edges', 'near_straight_nodes_5deg',
                'unmatched_ref_9', 'log_area_ratio', 'log_height',
                'bottom_bias_9', 'omission', 'extension', 'B8L2', 'D10',
                'matched_top_bias_deg', 'matched_bottom_bias_deg',
                'matched_horizontal_bias_deg', 'matched_boundary_abs_deg',
                'matched_pair_fraction', 'log_time']
ST = ['turn_n', 'short_turn_edges', 'near_straight_nodes_5deg', 'unmatched_ref_9']
BD = ['matched_top_bias_deg', 'matched_bottom_bias_deg',
      'log_area_ratio', 'log_height']

def cols(cond, stratum, metrics):
    return [f'{cond}_{stratum}_{c}' for c in metrics]

DOMAINS = {
    'M_STRUCTURE_LEVEL': cols('m', 'all', ST),
    'M_STRUCTURE_HARD': cols('m', 'hard', ST) + cols('m', 'hard_minus_easy', ST),
    'M_BOUNDARY_LEVEL': cols('m', 'all', BD),
    'M_BOUNDARY_HARD': cols('m', 'hard', BD) + cols('m', 'hard_minus_easy', BD),
    'M_QUALITY_DIFFICULTY': ['m_easy_B8L2', 'm_hard_B8L2', 'm_all_B8L2_p20',
                             'm_hard_minus_easy_B8L2'],
    'M_TIME_DIFFICULTY': ['m_easy_log_time', 'm_hard_log_time',
                         'm_hard_minus_easy_log_time'],
    'S_STRUCTURE': cols('s', 'all', ST),
    'S_BOUNDARY': cols('s', 'all', BD),
}
FAMILIES = {
    'DSTRUCT': dict(domains=['M_STRUCTURE_LEVEL', 'M_STRUCTURE_HARD'],
        required=['manual_geometry'], input_conditions='manual',
        distinction='Current easy/hard difficulty responses, including corner correspondence; no Q/T input.',
        sort=['m_hard_turn_n', 'm_hard_short_turn_edges', 'm_all_turn_n']),
    'DBOUNDARY': dict(domains=['M_BOUNDARY_LEVEL', 'M_BOUNDARY_HARD'],
        required=['manual_geometry'], input_conditions='manual',
        distinction='Signed top/bottom boundary, scale and height behavior plus hard-minus-easy response; no Q/T input.',
        sort=['m_all_matched_bottom_bias_deg', 'm_hard_matched_top_bias_deg', 'm_all_log_area_ratio']),
    'DJOINT': dict(domains=['M_STRUCTURE_HARD', 'M_BOUNDARY_HARD',
                          'M_QUALITY_DIFFICULTY', 'M_TIME_DIFFICULTY'],
        required=['manual_geometry', 'manual_time'], input_conditions='manual',
        distinction='Equal-domain joint hard-structure, signed boundary, difficulty-specific Q and source-compatible time.',
        sort=['m_hard_B8L2', 'm_hard_turn_n', 'm_hard_log_time']),
    'MSDGEOM': dict(domains=['M_STRUCTURE_HARD', 'M_BOUNDARY_HARD',
                           'S_STRUCTURE', 'S_BOUNDARY'],
        required=['manual_geometry', 'semi_geometry'], input_conditions='manual|semi',
        distinction='Manual difficulty response jointly with Semi structure and signed boundary/scale; distinct from old unconditional XCOND.',
        sort=['m_hard_turn_n', 's_all_turn_n', 'm_all_matched_bottom_bias_deg']),
}

def atomic_bytes(path, data):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.partial')
    with tmp.open('wb') as f:
        f.write(data); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)

def save_csv(frame, path):
    data = frame.to_csv(index=False).encode('utf-8-sig')
    if str(path).endswith('.gz'): data = gzip.compress(data, compresslevel=5, mtime=0)
    atomic_bytes(path, data)

def save_json(obj, path):
    atomic_bytes(path, (json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+'\n').encode())

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def matched_boundary_features(record_points, reference_points):
    """Feature-only 9-degree one-to-one azimuth matching, never fusion matching.

    Geometry stays in supplied ring order.  Positive y error is downwards in ERP.
    No additional ring sort, target reference edit, or vote threshold adjustment.
    """
    p = np.asarray(record_points, float).reshape(-1, 2)
    r = np.asarray(reference_points, float).reshape(-1, 2)
    if len(p) % 2 or len(r) % 2: return {}
    az = ((p[::2, 0, None]-r[None, ::2, 0]+512) % 1024-512)*360/1024
    ii, jj = linear_sum_assignment(np.abs(az))
    ok = np.abs(az[ii, jj]) <= 9
    ii, jj = ii[ok], jj[ok]
    if not len(ii): return {'matched_pair_fraction': 0.}
    top = (p[2*ii, 1]-r[2*jj, 1])*180/512
    bot = (p[2*ii+1, 1]-r[2*jj+1, 1])*180/512
    return dict(matched_top_bias_deg=float(np.mean(top)),
                matched_bottom_bias_deg=float(np.mean(bot)),
                matched_horizontal_bias_deg=float(np.mean(az[ii, jj])),
                matched_boundary_abs_deg=float(np.mean((np.abs(top)+np.abs(bot))/2)),
                matched_pair_fraction=float(len(ii)/(len(r)//2)))

def build_records(inp):
    raw = pd.read_csv(inp/'RAW_POOL_MEMBER_FEATURES.csv.gz')
    image = pd.read_csv(inp/'IMAGE_DIFFICULTY_OPPORTUNITIES.csv')
    use = ['image_id', 'building', 'difficulty_coarse', 'image_layer',
           'ref_turn5', 'ref_H', 'ref_short_edges', 'structure_opportunity',
           'fixed_six_turn_opportunity', 'gt_detail_omission_mark']
    raw = raw.merge(image[use], on='image_id', how='left', validate='many_to_one')
    snapshot = json.load(gzip.open(inp/'INPUT_SNAPSHOT.json.gz', 'rt'))
    extra = []
    for pool in snapshot['images']:
        for record in pool['records']:
            m = matched_boundary_features(record['points'], pool['reference']['points_1024x512'])
            extra.append(dict(object_id=record['object_id'], origin=record['origin'],
                              time_source=record.get('time_source_kind'), **m))
    raw = raw.merge(pd.DataFrame(extra), on='object_id', validate='one_to_one')
    raw['log_time'] = np.log(raw.source_active_time_seconds.where(raw.source_active_time_seconds > 0))
    # This group adjustment uses only the particular image in each history row.
    # Removing a held-out building therefore removes every use of its records.
    for metric in BASE_METRICS:
        group = ['image_id', 'condition']
        if metric == 'log_time': group += ['origin', 'time_source']
        raw[metric+'_peer'] = raw[metric] - raw.groupby(group, dropna=False)[metric].transform('median')
    raw['history_eligible'] = raw.image_layer.eq('non_doorway') & raw.difficulty_coarse.isin(['简单', '中等', '困难'])
    return raw

def history(raw, roster, heldout):
    d = raw[raw.history_eligible].copy()
    if heldout != 'ALL': d = d[d.building.ne(heldout)]
    pieces = []
    for cond, prefix in [('manual','m'), ('semi','s')]:
        dc = d[d.condition.eq(cond)]
        for stratum, levels in [('all',['简单','中等','困难']), ('easy',['简单']),
                                ('medium',['中等']), ('hard',['困难'])]:
            s = dc[dc.difficulty_coarse.isin(levels)]
            if s.empty: continue
            # Equal weight to buildings so a large single building does not
            # determine a worker's role.  Within a building: equal image rows.
            metrics = [c+'_peer' for c in BASE_METRICS]
            v = s.groupby(['worker_id','building'])[metrics].mean().groupby('worker_id').mean()
            v = v.rename(columns={c+'_peer':f'{prefix}_{stratum}_{c}' for c in BASE_METRICS})
            sp = s.groupby('worker_id').agg(images=('image_id','nunique'),
                      buildings=('building','nunique'), records=('object_id','size'),
                      time_images=('log_time','count'))
            sp.columns = [f'{prefix}_{stratum}_{c}' for c in sp]
            q20 = s.groupby('worker_id').B8L2_peer.quantile(.2).rename(f'{prefix}_{stratum}_B8L2_p20')
            pieces.extend([v, sp, q20.to_frame()])
    out = roster.set_index('worker_id').join(pieces, how='left')
    for prefix in ['m','s']:
        for metric in BASE_METRICS:
            a,b = f'{prefix}_hard_{metric}', f'{prefix}_easy_{metric}'
            if a in out and b in out: out[f'{prefix}_hard_minus_easy_{metric}'] = out[a]-out[b]
    # Only counts (not behavior values) become zero where there is no history.
    countcols = [c for c in out if c.endswith(('_images','_buildings','_records'))]
    out[countcols] = out[countcols].fillna(0).astype(int)
    out['manual_geometry'] = out.m_all_images.ge(12) & out.m_all_buildings.ge(3) & out.m_easy_images.ge(5) & out.m_easy_buildings.ge(2) & out.m_hard_images.ge(4) & out.m_hard_buildings.ge(2)
    out['manual_time'] = out.m_easy_time_images.ge(5) & out.m_hard_time_images.ge(4)
    out['semi_geometry'] = out.s_all_images.ge(6) & out.s_all_buildings.ge(3)
    out['heldout_building'] = heldout
    return out.reset_index()

def domain_matrix(frame, domains):
    arrays=[]; registry={}
    for domain in domains:
        cc = DOMAINS[domain]
        a = frame[cc].to_numpy(float)
        median = np.median(a,axis=0)
        scale = np.quantile(a,.85,axis=0)-np.quantile(a,.15,axis=0)
        scale = np.where(scale>1e-9,scale,np.std(a,axis=0))
        scale = np.where(scale>1e-9,scale,1.)
        z = np.clip((a-median)/scale, -3, 3)
        # Up to two PCs capture the dominant response pattern of each domain;
        # domain normalization prevents duplicated fields from extra weighting.
        pca=PCA(n_components=min(2,len(cc),len(frame)-1),svd_solver='full')
        y=pca.fit_transform(z)
        norm=float(np.sqrt(np.mean(np.sum(y*y,axis=1))))
        y=y/max(norm,1e-9)/np.sqrt(len(domains))
        arrays.append(y)
        registry[domain]=dict(features=cc,median=median.tolist(),scale=scale.tolist(),
            components=pca.components_.tolist(),explained_variance_ratio=pca.explained_variance_ratio_.tolist(),
            domain_norm=norm,clip=3,domain_weight=1/len(domains))
    return np.column_stack(arrays),registry

def fit_one(features,family):
    spec=FAMILIES[family]
    need=[c for d in spec['domains'] for c in DOMAINS[d]]
    supported=features[spec['required']].all(axis=1) & features[need].notna().all(axis=1)
    f=features[supported].copy().reset_index(drop=True)
    x,scales=domain_matrix(f,spec['domains'])
    tree=linkage(x,method='ward',optimal_ordering=True)
    out=[]; centers=[]; registrations=[]
    for k in [2,3,4]:
        raw=cut_tree(tree,n_clusters=k).ravel()
        order=sorted(np.unique(raw),key=lambda j:tuple(f.loc[raw==j,spec['sort']].mean()))
        lab=np.array([order.index(j) for j in raw])
        mapping=dict(zip(f.worker_id,[f'C{j+1}' for j in lab]))
        method=f'{family}_K{k}'
        z=features[['worker_id','origin','heldout_building','manual_geometry','manual_time','semi_geometry']].copy()
        z['method']=method;z['family']=family;z['class_id']=z.worker_id.map(mapping).fillna('unknown')
        z['known']=z.class_id.ne('unknown');z['missing_reason']=''
        for i in z.index[~z.known]:
            rec=features.iloc[i]
            reasons=[s for s in spec['required'] if not bool(rec[s])]
            if not reasons: reasons=['missing_behavior_feature']
            z.loc[i,'missing_reason']='insufficient_'+ '|'.join(reasons)
        z['input_conditions']=spec['input_conditions'];z['evaluation_condition']='manual_and_semi_separately'
        z['condition']='manual';z['coarse_label']=z.class_id;z['fine_label']=z.class_id
        z['k']=k;z['underlying_data_version']='v2'
        z['label_stage']='all_data_descriptive' if features.heldout_building.iloc[0]=='ALL' else 'both_conditions_target_building_excluded'
        out.append(z)
        semantic_cols = list(dict.fromkeys(need + cols('m','all',ST+BD+['B8L2','log_time']) + cols('m','hard',ST+BD+['B8L2','log_time']) + cols('s','all',ST+BD+['B8L2','log_time'])))
        for j in range(k):
            g=f[lab==j]
            row=dict(method=method,family=family,k=k,heldout_building=features.heldout_building.iloc[0],
                     class_id=f'C{j+1}',members='|'.join(g.worker_id),people=len(g),
                     input_conditions=spec['input_conditions'],
                     manual_history_min=int(g.m_all_images.min()),hard_history_min=int(g.m_hard_images.min()),
                     manual_buildings_min=int(g.m_all_buildings.min()),semi_history_min=int(g.s_all_images.min()),
                     new_people=int(g.origin.eq('new').sum()),old_people=int(g.origin.eq('v1').sum()))
            row.update({c:float(g[c].mean()) for c in semantic_cols if c in g})
            centers.append(row)
        registrations.append(dict(method=method,family=family,heldout_building=features.heldout_building.iloc[0],
            k=k,known_workers=int(supported.sum()),unknown_workers=int((~supported).sum()),
            class_size_vector='|'.join(map(str,np.bincount(lab,minlength=k))),
            min_class=int(np.bincount(lab,minlength=k).min()),
            silhouette=float(silhouette_score(x,lab)),
            input_conditions=spec['input_conditions'],domains='|'.join(spec['domains']),
            selected_on_target_fusion=False,fit='Ward; same tree K2/K3/K4; equal-domain 2-PC encoding',
            distinction=spec['distinction']))
    return pd.concat(out,ignore_index=True),pd.DataFrame(centers),pd.DataFrame(registrations),scales

def main(args):
    inp=Path(args.inputs);out=Path(args.output);fea=Path(args.features)
    out.mkdir(parents=True,exist_ok=True);fea.mkdir(parents=True,exist_ok=True)
    raw=build_records(inp)
    save_csv(raw,fea/'RAW_CONDITION_RESPONSE_RECORDS.csv.gz')
    roster=raw[['worker_id','origin']].drop_duplicates().sort_values('worker_id').reset_index(drop=True)
    for wid in ['W019','W026']:
        if wid not in set(roster.worker_id): roster.loc[len(roster)]=[wid,'v1']
    roster=roster.sort_values('worker_id').reset_index(drop=True)
    buildings=sorted(raw.building.unique())
    all_history=[];all_labels=[];all_centers=[];all_reg=[];all_scales={}
    for heldout in ['ALL']+buildings:
        h=history(raw,roster,heldout);all_history.append(h)
        ll=[];cc=[];rr=[]
        for fam in FAMILIES:
            labels,centers,reg,scales=fit_one(h,fam)
            ll.append(labels);cc.append(centers);rr.append(reg)
            all_scales[f'{heldout}:{fam}']=scales
        labels=pd.concat(ll,ignore_index=True);centers=pd.concat(cc,ignore_index=True);reg=pd.concat(rr,ignore_index=True)
        all_labels.append(labels);all_centers.append(centers);all_reg.append(reg)
        # Every fold is a valid checkpoint, not just an end-of-run artifact.
        save_csv(labels,out/'folds'/f'LABELS_{heldout}.csv.gz')
        save_csv(centers,out/'folds'/f'CENTERS_{heldout}.csv')
        print('saved',heldout,len(labels),'labels',flush=True)
    hs=pd.concat(all_history,ignore_index=True);ls=pd.concat(all_labels,ignore_index=True)
    cs=pd.concat(all_centers,ignore_index=True);rs=pd.concat(all_reg,ignore_index=True)
    save_csv(hs,fea/'HISTORY_FEATURES_ALL_LOBO.csv.gz')
    save_csv(ls,out/'NEW_METHOD_LABELS_ALL_LOBO.csv.gz')
    save_csv(ls[ls.heldout_building.eq('ALL')],out/'NEW_METHOD_LABELS_ALL.csv')
    save_csv(ls[ls.heldout_building.ne('ALL')],out/'NEW_METHOD_LABELS_LOBO.csv.gz')
    save_csv(cs,out/'NEW_CLASS_DEFINITIONS_ALL_LOBO.csv.gz')
    save_csv(cs[cs.heldout_building.eq('ALL')],out/'NEW_CLASS_DEFINITIONS_ALL.csv')
    save_csv(rs,out/'CANDIDATE_REGISTRY.csv')
    save_json(all_scales,out/'TRANSFORMS_ALL_LOBO.json')
    stability=[]
    for method,d in ls.groupby('method'):
        a=d[d.heldout_building.eq('ALL') & d.known].set_index('worker_id').class_id
        for b,g in d[d.heldout_building.ne('ALL') & d.known].groupby('heldout_building'):
            bb=g.set_index('worker_id').class_id;common=a.index.intersection(bb.index)
            stability.append(dict(method=method,heldout_building=b,workers=len(common),
                                  ari=adjusted_rand_score(a.loc[common],bb.loc[common])))
    save_csv(pd.DataFrame(stability),out/'ALL_LOBO_MEMBERSHIP_STABILITY.csv')
    receipt=dict(input_commit='972857b2b3f548316be215400e42d6ef6e639250',
        underlying_data_version='v2',research_date='2026-10-25',records=len(raw),
        current_workers=raw.worker_id.nunique(),roster_workers=len(roster),
        heldout_buildings=buildings,methods=list(rs.method.unique()),
        no_target_fusion_selection=True,no_new_fusion=True,
        scope_included=False,scope_missing_note='Separate supported old-worker common-domain increment only.',
        source_files={str(p):sha(p) for p in [inp/'INPUT_SNAPSHOT.json.gz',inp/'RAW_POOL_MEMBER_FEATURES.csv.gz',inp/'IMAGE_DIFFICULTY_OPPORTUNITIES.csv']},
        class_history='Non-doorway current-v2 formal-pool records with fixed simple/medium/hard difficulty only.',
        missing_rule='Unknown retained; only support counts filled with 0; no behavior imputation.',
        support_rules=dict(manual_geometry='>=12 ordinary images/3 buildings, >=5 easy images/2 buildings, >=4 hard images/2 buildings',manual_time='>=5 easy and >=4 hard source-compatible times',semi_geometry='>=6 images/3 buildings'),
        quality_and_time='Historical B8L2; log source record seconds centered by image/condition/origin/time_source, not measured production time.',
        feature_matching='9-degree nearest one-to-one azimuth Hungarian match is feature-only; distinct from fusion correspondence.',
        geometry='Positive signed ERP top/bottom error means downwards; supplied ring order unchanged.',
        aggregation='Image-condition peer median residuals; equal building means within worker and difficulty stratum.',
        code_sha256=sha(__file__))
    save_json(receipt,out/'BUILD_RECEIPT.json')
    print(rs[rs.heldout_building.eq('ALL')][['method','known_workers','class_size_vector','silhouette']].to_string(index=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--inputs',required=True);p.add_argument('--output',required=True);p.add_argument('--features',required=True)
    main(p.parse_args())
