"""Re-express completed v2-data exchanges without any new native fusion.

All class roles use archived target-building-excluded historical centroids.
Numerical labels from different new-taxonomy folds are never treated as the
same class unless their family, K and ranked domain-centroid roles agree.
"""
from __future__ import annotations
from common_screening import *
import argparse, time

DOMAIN = {
    'E':['turn_history','short_history'],
    'R':['redundancy_history'],
    'G':['area_history','height_history'],
    'C':['simple_turn_history','complex_turn_history','complex_short_history'],
    'Q':['q_history','q_downside'], 'T':['t_history'],
}
FAMILY = {'TURN':['E'],'STRUCTURE':['E','R'],'SCALE':['G'],
          'JOINT':['E','R','G'],'CONTEXT':['C','R','G'],
          'EQT':['E','Q','T'],'GEQT':['E','G','Q','T'],'CQT':['C','Q','T']}
HISTORY = list(dict.fromkeys(x for v in DOMAIN.values() for x in v))
QUALITY = ['B8L2','D10','IoU3D100','iou_2d','S_bottom_deg','dir',
           'Hmean','Hcenter','omission','extension','height_mean_ratio','nodes',
           'ref_node_recall_5','ref_node_recall_9','ref_edge_recall_5','ref_edge_recall_9',
           'diag_wall_coverage_03','diag_wall_coverage_05','diag_corner_recall_05']
LOCATION = ['geometry_area_h2','centroid_x_h','centroid_z_h','bounds_min_x_h',
            'bounds_min_z_h','bounds_max_x_h','bounds_max_z_h','height_mean_h',
            'height_min_h','height_max_h','top_y_mean_px','bottom_y_mean_px']
EXPRESSION = ['fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n']
PAIR = ['floor_jaccard_difference','floor_symdiff_h2','mean_height_prism_pair_difference',
        'height_ratio_pair_abs_logdiff','centroid_distance_h','floor_area_abs_log_ratio',
        'structure_bound_cyclic_deg','ref_node_set_jaccard_difference_5',
        'ref_edge_set_jaccard_difference_5','joint_stable_main','joint_stable_D10_main',
        'corner_angle_deg','corner_bev_mean_h','corner_bev_max_h','corner_top_mean_h',
        'corner_top_max_h','corner_bev_mean_pairscale','corner_top_mean_pairscale']

def freeze_protocol():
    protocol = dict(
      status='frozen_before_uniform_full_event_screen', data_version='v2',
      round='personnel_effective_exchange_conditions_20261022',
      prior_round_directory='personnel_useful_taxonomy_v3_20261021',
      prior_round_v3_is_data_version=False, native_fusion_calls=0,
      inherited_candidates=['A2 manual n17 m9', 'M fine parent-fixed M01->M00 n10 m5 or m6 separately',
                            'V3_BEHAVIOR manual n10 m7'],
      inherited_candidates_already_selected_from_prior_explored_results=True,
      outcomes_used_for_role_alignment=False,
      crossfold_role_alignment='new methods: selected family + actual tier K + per-domain training-centroid rank; fine role also includes parent role. Ties/collisions retained explicitly. Legacy fixed IDs preserved with archived training identity.',
      exact_conditions=['event_mode ABC vs AC-only','condition','method_id','tier','source_domain',
                        'role-aligned exact outgoing and incoming class-count vectors',
                        'n','actual m','actual parent-fixed indicator'],
      supplementary_views=['net class-seat direction, with unchanged class exchanges removed',
                           'actual incoming-minus-outgoing historical axis sign, explicitly not an exact class direction',
                           'difficulty conditional summaries'],
      failure_policy='every registered event retained; success-Q denominators, all-result failure denominators and failure-or->10-loss denominators separate',
      weighting='within actual common background, then image, then building; event-weighted means and medians also provided',
      deduplication='same oriented actual endpoints + method/tier + actual source/domain + n/m + actual parent status once; stage/design provenance kept',
      thresholds=dict(min_buildings=4, min_images=4, min_building_same_direction_fraction=.60,
        stability_mean_abs_Q_advantage=.5, stability_median_positive=True,
        quality_mean_B8L2_change=1.0, quality_median_positive=True,
        geometry_mean_floor_or_prism_difference_advantage=.003,
        structure_mean_reference_recall_change=.02, structure_min_positive_buildings=3,
        efficiency_mean_recorded_time_pct=-10.0, efficiency_same_time_support_mean_Q_min=-2.0),
      limited_support='2-3 buildings or otherwise insufficient support retained as provisional, not discarded',
      selection='purpose-specific positive effect plus support plus majority; null/adverse and every not-selected reason exported; no p-value gate',
      internal_LOBO='For a held-out building, candidate effects and selection criteria use fusion outcomes only from other buildings; evaluate the selected candidate on held-out-building events. Existing frozen personnel LOBO labels are reused, not double-excluded refits.',
      validation_limit='Data have been repeatedly explored. Internal outcome-exclusion checks are not external blind validation; old frozen label inputs can contain other-fold history from the evaluation building.',
      all_metrics_sign='cross_* is C-A; same_* is B-A. Greater omission/extension is worse. Geometry difference advantage=cross distance-within distance. Expression count change is not correctness.',
      time_qualification='sum recorded seconds only when all team-member times are known and source-compatible; missing/heterogeneous source totals remain unavailable for time conclusions.'
    )
    save_json('SCREENING_PROTOCOL.json', protocol)

def make_roles():
    labels = pd.read_csv(TAXONOMY/'ALL_METHOD_LABELS_LOBO.csv.gz')
    labels = labels[labels.known.astype(str).str.lower().isin(['true','1']) & labels.heldout_building.ne('ALL')].copy()
    out=[]; maps={}
    for (method,condition,building), g in labels.groupby(['method','condition','heldout_building']):
        family = g.selected_family.iloc[0]
        domains=FAMILY[family]
        z=g.copy()
        for domain in domains:
            fields=DOMAIN[domain]
            a=g[fields].to_numpy(float)
            med=np.median(a,axis=0);scale=np.quantile(a,.75,axis=0)-np.quantile(a,.25,axis=0)
            scale=np.where(scale>1e-8,scale,np.std(a,axis=0));scale=np.where(scale>1e-8,scale,1.)
            transformed=np.clip((a-med)/scale,-3,3)
            # Q role points toward better quality / smaller downside, while T
            # retains its natural slower-to-faster interpretation in the map.
            if domain=='Q': transformed[:,1]*=-1
            z['domain_'+domain]=transformed.mean(axis=1)
        parent_roles={}
        for tier in ['coarse','fine']:
            label_col=tier+'_label'; k=int(g[tier+'_k'].iloc[0])
            centers=z.groupby(label_col)[HISTORY+['domain_'+a for a in domains]].mean()
            ranks=centers[['domain_'+a for a in domains]].rank(method='min').astype(int)
            for cl, cg in z.groupby(label_col):
                code=family+f'/K{k}/'+','.join(f'{a}{int(ranks.loc[cl,"domain_"+a])}' for a in domains)
                parent=cg.coarse_label.iloc[0]
                if tier=='fine':code=parent_roles[parent]+'>'+code
                else:parent_roles[cl]=code
                row=dict(method_id=method,tier=tier,condition=condition,heldout_building=building,
                  raw_class_id=cl,parent_class_id=parent,selected_family=family,coarse_k=int(g.coarse_k.iloc[0]),
                  fine_k=int(g.fine_k.iloc[0]),tier_k=k,role_id=code,role_basis='training_centroid_domain_ranks',
                  n_members=len(cg),members='|'.join(sorted(cg.worker_id)),
                  parent_role=parent_roles[parent])
                for field in HISTORY:row['centroid_'+field]=float(centers.loc[cl,field]) if pd.notna(centers.loc[cl,field]) else None
                for a in domains:
                    row['standardized_domain_'+a]=float(centers.loc[cl,'domain_'+a])
                    row['rank_'+a]=int(ranks.loc[cl,'domain_'+a])
                out.append(row)
            # Do not merge two different classes if all ranked domain centers
            # happen to coincide. The fold identity then remains part of role.
            sub=[r for r in out if (r['method_id'],r['tier'],r['condition'],r['heldout_building'])==(method,tier,condition,building)]
            count=collections.Counter(r['role_id'] for r in sub)
            for row in sub:
                row['ambiguous_rank_role']=count[row['role_id']]>1
                if row['ambiguous_rank_role']:row['role_id']+='@'+building+':'+row['raw_class_id']
                maps[(method,tier,condition,building,row['raw_class_id'])]=row['role_id']
    table=pd.DataFrame(out)
    receipt=save_csv('CLASS_TRAINING_ROLE_MAP.csv.gz',table)
    save_json('CLASS_ROLE_RECEIPT.json',dict(status='complete',file=receipt,
      label_input_sha256=sha(TAXONOMY/'ALL_METHOD_LABELS_LOBO.csv.gz'),
      target_fusion_outcomes_used=False,role_definition='family, actual K and per-domain rank; fine includes parent',
      Q_role='high quality with small downside',T_role='higher is slower',
      geometry_roles='higher E/C=more turns/details, R=more redundancy, G=larger scale/height',
      folds=labels.groupby(['method','condition','heldout_building']).ngroups))
    return maps

def bseries(v):
    return v.astype(str).str.lower().map({'true':True,'false':False,'1':True,'0':False})

def minimal_vectors(a,b):
    diff={k:b.get(k,0)-a.get(k,0) for k in set(a)|set(b)}
    return canonical_counts({k:-v for k,v in diff.items() if v<0}),canonical_counts({k:v for k,v in diff.items() if v>0})

def transform(stage,condition,d,maps,roles):
    d=d.copy(); d['prior_stage']=stage;d['comparison']='AC_only' if stage=='PURE_CROSS' else 'ABC_matched'
    if 'design_scope' not in d:d['design_scope']='cross_only'
    for field in META:
        if field not in d:d[field]=np.nan
    for f in ['A_failure','B_failure','C_failure','all_complete','all_scored','same_source_counts','source_and_historyQ5_matched']:
        d[f]=bseries(d[f]).astype(float)
    for f in ['A_failure','C_failure']:
        assert d[f].notna().all(),f
    if stage!='PURE_CROSS':assert d.B_failure.notna().all()
    d['n']=d.n.astype(int);d['m']=d.m_AC.astype(int)
    for f in ['common_background','outgoing_block_X','same_count_block_Y','changed_count_block_Z','B_member_workers','team_B']:
        d[f]=d[f].fillna('')
    metadata=[]
    for r in d.to_dict('records'):
        key=(r['method_id'],r['tier'],condition,r['building']); labels=maps[key]
        blocks={a:workers(r[field]) for a,field in [('X','outgoing_block_X'),('Y','same_count_block_Y'),('Z','changed_count_block_Z')]}
        counts={a:collections.Counter(labels[w] for w in ws) for a,ws in blocks.items()}
        if stage!='PURE_CROSS':assert counts['X']==counts['Y'],r['event_id']
        assert sum(counts['X'].values())==r['m']==sum(counts['Z'].values())
        mapped={a:collections.Counter() for a in blocks}
        for a,cc in counts.items():
            for cl,v in cc.items():
                role=roles.get((*key,cl),cl)
                mapped[a][role]+=v
        raw_from,raw_to=minimal_vectors(counts['X'],counts['Z'])
        role_from,role_to=minimal_vectors(mapped['X'],mapped['Z'])
        parent_fixed=r['tier']=='fine' and parse_counts(r['A_parent_counts'])==parse_counts(r['C_parent_counts'])
        raw_direction=canonical_counts(counts['X'])+' -> '+canonical_counts(counts['Z'])
        role_direction=canonical_counts(mapped['X'])+' -> '+canonical_counts(mapped['Z'])
        B=r['team_B'] if stage!='PURE_CROSS' else ''
        actual_unit=digest([r['pool_id'],r['team_A'],B,r['team_C']])[:24]
        m=dict(raw_block_direction=raw_direction,role_block_direction=role_direction,
          raw_net_direction=raw_from+' -> '+raw_to,role_net_direction=role_from+' -> '+role_to,
          exact_fold_direction=r['building']+' / '+str(r['fold_selected_family'])+' / '+raw_direction,
          role_alignment='training_centroids' if r['method_id'].startswith('V3_') else 'archived_fixed_id',
          X_class_counts=canonical_counts(counts['X']),Y_class_counts=canonical_counts(counts['Y']),Z_class_counts=canonical_counts(counts['Z']),
          whole_class_transfer=int(r['composition_turnover_AC'])==r['m'],parent_fixed=parent_fixed,
          common_background_id=digest([r['pool_id'],r['common_background']])[:24],
          actual_exchange_id=actual_unit,directed_pair_id=digest([r['pool_id'],r['team_A'],r['team_C']])[:24],
          union_member_n=len(set(workers(r['A_member_workers'])+workers(r['B_member_workers'])+workers(r['C_member_workers']))),
          analysis_event_id=digest([r['comparison'],*key,r['source_domain'],r['n'],r['m'],parent_fixed,actual_unit])[:24])
        metadata.append(m)
    for f in metadata[0]:d[f]=[r[f] for r in metadata]
    for stem in QUALITY+LOCATION+EXPRESSION:
        for arm in ['same','cross']:
            f=arm+'_'+stem
            if f not in d:d[f]=np.nan
    for stem in PAIR:
        for arm in ['within','cross']:
            f=arm+'_'+stem
            if f not in d:d[f]=np.nan
            if stage=='PURE_CROSS' and arm=='cross':
                alt='cross_geometry_'+stem
                if alt in d:d[f]=d[alt]
        if stem=='mean_height_prism_pair_difference' and stage=='PURE_CROSS':
            alt='cross_geometry_mean_height_prism_pair_iou'
            if alt in d:d['cross_'+stem]=1-d[alt]
        d['advantage_'+stem]=pd.to_numeric(d['cross_'+stem],errors='coerce').astype(float)-pd.to_numeric(d['within_'+stem],errors='coerce').astype(float)
    for metric in ['abs_Q_change_advantage','stable_advantage','stable_D10_advantage','common_quality_within_abs','common_quality_cross_abs']:
        if metric not in d:d[metric]=np.nan
    for arm,target in [('same','B'),('cross','C')]:
        q=d[arm+'_B8L2'];fail=d[target+'_failure']
        for threshold in [5,10]:
            d[arm+f'_loss_gt{threshold}']=q.lt(-threshold).astype(float).where(q.notna())
            d[arm+f'_gain_gt{threshold}']=q.gt(threshold).astype(float).where(q.notna())
        d[arm+'_failure_difference']=fail-d.A_failure
        d[arm+'_complete_to_failure']=((d.A_failure.eq(0))&fail.eq(1)).astype(float).where(fail.notna())
        d[arm+'_failure_to_complete']=(d.A_failure.eq(1)&fail.eq(0)).astype(float).where(fail.notna())
        d[arm+'_failure_or_loss_gt10']=np.where(fail.eq(1),1,np.where(q.notna(),q.lt(-10),np.nan))
    d['risk_advantage']=d.cross_failure_or_loss_gt10-d.same_failure_or_loss_gt10
    if 'cross_recorded_time_pct' not in d:d['cross_recorded_time_pct']=d.get('recorded_time_pct',np.nan)
    for f in ['same_recorded_time_pct','same_abs_log_time','cross_abs_log_time','time_variation_advantage']:
        if f not in d:d[f]=np.nan
    d['cross_B8L2_time_qualified']=d.cross_B8L2.where(d.cross_recorded_time_pct.notna())
    for axis in HISTORY:
        f='cross_'+axis+'_change'
        if f not in d:d[f]=np.nan
        d['direction_'+axis]=np.select([d[f].gt(1e-10),d[f].lt(-1e-10),d[f].abs().le(1e-10)],['increase','decrease','unchanged'],default='unknown')
    # No need to duplicate the full 800-column endpoint/correspondence archive.
    keep=META+['prior_stage','comparison','m']+list(metadata[0])+CORE
    keep += [a+'_'+s for a in ['same','cross'] for s in QUALITY+LOCATION+EXPRESSION]
    keep += [a+'_'+s for a in ['within','cross','advantage'] for s in PAIR]
    keep += [a+'_'+s for a in ['same','cross'] for s in ['loss_gt5','loss_gt10','gain_gt5','gain_gt10','failure_difference','complete_to_failure','failure_to_complete','failure_or_loss_gt10']]
    keep += ['risk_advantage','cross_B8L2_time_qualified']
    keep += ['direction_'+a for a in HISTORY]+['cross_'+a+'_change' for a in HISTORY]
    keep = list(dict.fromkeys(c for c in keep if c in d))
    return d[keep]

def main():
    started=time.time();freeze_protocol();roles=make_roles();maps,_=label_maps()
    receipts=[];frames=[];sources=[]
    wanted=set(META+CORE)
    wanted.update(a+'_'+s for a in ['same','cross'] for s in QUALITY+LOCATION+EXPRESSION)
    wanted.update(a+'_'+s for a in ['within','cross','cross_geometry'] for s in PAIR)
    wanted.add('cross_geometry_mean_height_prism_pair_iou')
    wanted.update('cross_'+a+'_change' for a in HISTORY)
    for stage,condition,path in event_sources():
        parts=[]
        for d in pd.read_csv(path,usecols=lambda x:x in wanted,chunksize=2000,low_memory=False):
            parts.append(transform(stage,condition,d,maps,roles))
        part=pd.concat(parts,ignore_index=True)
        sources.append(dict(stage=stage,condition=condition,path=str(path.relative_to(WORKERS)),sha256=sha(path),rows=len(part)))
        receipt=save_csv('event_parts/'+stage+'_'+condition+'_UNIFIED.csv.gz',part);receipts.append(receipt)
        frames.append(part)
        save_json('UNIFIED_PROGRESS.json',dict(status='building',seconds=time.time()-started,parts=receipts,native_calls=0))
        print(json.dumps(dict(stage=stage,condition=condition,rows=len(part),seconds=round(time.time()-started,1))),flush=True)
    allrows=pd.concat(frames,ignore_index=True)
    assert len(allrows)==sum(EXPECTED.values()),len(allrows)
    assert allrows.event_id.nunique()==len(allrows),'prior event keys duplicate'
    duplicate=allrows[allrows.duplicated('analysis_event_id',False)].copy()
    receipts.append(save_csv('DUPLICATE_ANALYSIS_EVENT_PROVENANCE.csv.gz',duplicate))
    provenance=allrows.groupby('analysis_event_id').agg(prior_event_ids=('event_id',lambda s:'|'.join(sorted(s))),
      registered_rows=('event_id','size'),prior_stages=('prior_stage',lambda s:'|'.join(sorted(set(s)))),
      design_scopes=('design_scope',lambda s:'|'.join(sorted(set(s.astype(str)))))).reset_index()
    unique=allrows.drop_duplicates('analysis_event_id').merge(provenance,on='analysis_event_id',validate='one_to_one')
    receipts.append(save_csv('EVENTS_UNIFIED.csv.gz',unique))
    inventory=allrows.groupby(['prior_stage','condition','comparison','method_id','tier','source_domain']).agg(
      registered_rows=('event_id','size'),unique_analysis_events=('analysis_event_id','nunique'),
      actual_exchange_sets=('actual_exchange_id','nunique'),directed_pairs=('directed_pair_id','nunique'),
      backgrounds=('common_background_id','nunique'),images=('image','nunique'),buildings=('building','nunique'),
      n_min=('n','min'),n_max=('n','max'),m_min=('m','min'),m_max=('m','max'),A_failed=('A_failure','sum'),C_failed=('C_failure','sum')).reset_index()
    receipts.append(save_csv('EVENT_COVERAGE.csv',inventory))
    metric_rows=[]
    for f in unique.columns:
        if pd.api.types.is_numeric_dtype(unique[f]) and f not in ['n','m','m_AB','m_AC','m_BC']:
            metric_rows.append(dict(field=f,available_events=int(unique[f].notna().sum()),
              meaning='C minus A' if f.startswith('cross_') else 'B minus A' if f.startswith('same_') else 'pair distance or metadata',
              denominator='all registered successful-or-failed outcomes' if f in ['A_failure','B_failure','C_failure'] or 'failure_difference' in f or 'to_failure' in f else 'valid metric values only; metric unavailable is never zero'))
    receipts.append(save_csv('METRIC_AVAILABILITY_AND_SIGNS.csv',pd.DataFrame(metric_rows)))
    result=dict(status='complete',registered_old_event_rows=len(allrows),unique_analysis_events=len(unique),
      duplicate_design_registrations=len(allrows)-len(unique),data_version='v2',native_calls=0,
      prior_expected_by_stage=EXPECTED,seconds=time.time()-started,sources=sources,files=receipts,
      role_input_sha256=sha(HERE/'CLASS_TRAINING_ROLE_MAP.csv.gz'),protocol_sha256=sha(HERE/'SCREENING_PROTOCOL.json'))
    save_json('UNIFIED_COMPLETION.json',result)
    print(json.dumps(dict(status='complete',rows=len(allrows),unique=len(unique),seconds=round(time.time()-started,1))),flush=True)

if __name__=='__main__':main()
