"""Independent portrait exploration: traceable outcomes and interpretable inputs.

No images, no model inference, no alteration of source annotations.  All numerical
geometry operations reuse the work-package's required geometry implementation.
"""
from __future__ import annotations
import argparse, collections, gzip, hashlib, itertools, json, math, platform
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform
from tools.thesis_main.analysis.audit_annotation_research_data_20260905 import normalize_geometry, _dense_boundaries, _d_mask
from tools.thesis_main.analysis.image_portrait.build_bundle import verify_bundle

ROOT=Path(__file__).resolve().parents[4]
BUNDLE=ROOT/'analysis_results/image_portrait_20260914_v1'
OUT=BUNDLE/'cloud/pro_exploration/v1_e086b2b9'
COMMIT='e086b2b94d60b8a858a71f0326f12930538fe4fe'
SEED=20260914
TRAITS=['floor_boundary','ceiling_boundary','corner_occlusion','connected_space','reflection_glass','low_contrast']
SCOPE=['normal','oos_open_boundary','oos_geometry','oos_split_level','oos_insufficient','unknown']
TARGETS=['reference_geometry_error','owner_valid_active_seconds','point_count_disagreement','within_topology_geometry_dispersion','scope_non_normal_rate','scope_entropy']

def load(path:Path):
    if path.suffix=='.gz':
        with gzip.open(path,'rt',encoding='utf-8-sig') as f:return [json.loads(s) for s in f if s.strip()]
    if path.suffix=='.jsonl':return [json.loads(s) for s in path.read_text(encoding='utf-8-sig').splitlines() if s.strip()]
    return json.loads(path.read_text(encoding='utf-8-sig'))

def json_safe(a):
    if isinstance(a,dict):return {str(k):json_safe(v) for k,v in a.items()}
    if isinstance(a,(list,tuple)):return [json_safe(v) for v in a]
    if isinstance(a,np.ndarray):return json_safe(a.tolist())
    if isinstance(a,np.integer):return int(a)
    if isinstance(a,(float,np.floating)):return float(a) if np.isfinite(a) else None
    if isinstance(a,np.bool_):return bool(a)
    return a

def write_json(path,a):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(json_safe(a),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def write_csv(name,a):
    p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
    frame=a if isinstance(a,pd.DataFrame) else pd.DataFrame(a)
    if len(frame.columns)==0:frame=pd.DataFrame(columns=['status'])
    frame.to_csv(p,index=False,float_format='%.12g')

def number(x):
    try:return float(x)
    except (TypeError,ValueError):return np.nan

def median(x):
    a=np.asarray(x,dtype=float);a=a[np.isfinite(a)]
    return float(np.median(a)) if a.size else np.nan

def scope_choice(r):
    vals=[v for c in r.get('choices',[]) if str(c.get('from_name','')).lower()=='scope' for v in c.get('choices',[])]
    return vals[0] if len(vals)==1 else 'unknown'

def geometries_and_responses():
    refs={r['image_id']:r for r in load(BUNDLE/'human/references.jsonl.gz')}
    checks={r['canonical_annotation_id']:r for r in load(BUNDLE/'human/time_source_checks.jsonl')}
    source=load(BUNDLE/'human/responses.jsonl.gz')
    ids=[]; bounds=[];rows=[];rdense={};refaudit=[]
    for image,r in refs.items():
        status=r['current_quality_status'];err='';valid=False
        if status not in {'missing','reference_not_geometry_ready','not_evaluable_bad_gt'}:
            try:
                assert len(r['pairs'])>=2
                a=_dense_boundaries(r['pairs']);assert np.isfinite(a).all();rdense[image]=a;valid=True
            except Exception as e:err=repr(e)
        refaudit.append(dict(image_id=image,status=status,reference_scope=r.get('scope_status','unknown'),source=r.get('source',''),split=r.get('split','unknown'),valid_for_reference_comparison=valid,error=err))
    dense={}
    for r in source:
        cid=r['canonical_annotation_id'];image=r['image_id'];eligible=r['main_worker_included'];e=r['evidence'];check=checks[cid]
        geom=normalize_geometry(r['effective_points_1024x512']);valid=bool(r['calculation_included'] and geom['valid'])
        boundary=_dense_boundaries(geom['pairs']) if valid else None
        if valid:dense[cid]=boundary;ids.append(cid);bounds.append(boundary)
        q=np.nan;top=np.nan;floor=np.nan;band=np.nan
        if valid and image in rdense:
            q=_d_mask(boundary,rdense[image]);top=float(np.mean(boundary[0]-rdense[image][0]));floor=float(np.mean(boundary[1]-rdense[image][1]));band=floor-top
        time=number(e.get('active_time_seconds')) if eligible and check['speed_usable'] else np.nan
        if np.isfinite(time) and time<0:raise ValueError('Negative verified time')
        rt=refs[image]
        row={k:r.get(k) for k in ['canonical_annotation_id','image_id','worker_id','context_key','stage','block_index','raw_condition','raw_point_count','effective_point_count','processing_status','imputed_point','calculation_included','main_worker_included']}
        row.update(building=image.split('_')[0],geometry_valid=valid,geometry_failure='' if valid else (r.get('exclusion_reason') or geom['reason'] or 'calculation_excluded'),pairing_method=geom['pairing_method'],
                   scope=scope_choice(r),quality=q,top_signed_pixels=top,floor_signed_pixels=floor,band_width_bias_pixels=band,
                   reference_status=rt['current_quality_status'],reference_scope=rt.get('scope_status','unknown'),reference_source=rt.get('source',''),
                   active_seconds=time,speed_usable=bool(check['speed_usable']),time_trace_status=check['raw_trace_status'],historical_scope_status=e.get('scope_status',''),historical_reference_scope=e.get('reference_scope_status',''))
        rows.append(row)
    df=pd.DataFrame(rows)
    assert not df.duplicated(['image_id','raw_condition','worker_id']).any(), 'Do not count repeat workers as independent.'
    write_csv('inputs/reference_audit.csv',refaudit);write_csv('human/response_metrics.csv.gz',df)
    np.savez_compressed(OUT/'human/dense_boundaries.npz',canonical_annotation_ids=np.array(ids),boundaries=np.array(bounds,dtype=np.int16))
    return df,dense,rdense

def summarize_group(g,dense,image,arm,view,context='pooled_unique_workers'):
    valid=g[g.geometry_valid];assert not valid.worker_id.duplicated().any()
    n=len(g);nv=len(valid);pairs=[];same=[];topology=[]
    for (_,a),(_,b) in itertools.combinations(valid.iterrows(),2):
        eq=a.effective_point_count==b.effective_point_count
        d=_d_mask(dense[a.canonical_annotation_id],dense[b.canonical_annotation_id]) if eq else np.nan
        pairs.append(dict(image_id=image,condition=arm,view=view,context=context,worker_a=a.worker_id,worker_b=b.worker_id,cid_a=a.canonical_annotation_id,cid_b=b.canonical_annotation_id,points_a=a.effective_point_count,points_b=b.effective_point_count,same_point_count=eq,d_mask_same_topology=d))
        topology.append(not eq)
        if eq:same.append(d)
    sc=collections.Counter(g.scope);known=sum(sc[s] for s in SCOPE if s!='unknown');total=sum(sc.values())
    p=np.array([sc[s]/known for s in SCOPE if s!='unknown']) if known else np.zeros(5)
    entropy=-np.sum(p[p>0]*np.log2(p[p>0])) if known else np.nan
    q=g.quality.dropna();tm=g.active_seconds.dropna()
    row=dict(image_id=image,building=image.split('_')[0],condition=arm,view=view,context=context,
      n_responses=n,n_workers=g.worker_id.nunique(),n_geometry=nv,n_geometry_failed=n-nv,n_quality=len(q),n_time=len(tm),n_scope_known=known,n_scope_unknown=sc['unknown'],
      n_distinct_point_counts=valid.effective_point_count.nunique(),n_structural_pairs=len(topology),n_same_topology_pairs=len(same),
      reference_geometry_error=median(q),owner_valid_active_seconds=median(tm),point_count_disagreement=float(np.mean(topology)) if topology else np.nan,
      within_topology_geometry_dispersion=median(same),scope_non_normal_rate=1-p[0] if known else np.nan,scope_entropy=entropy,
      geometry_failure_rate=(n-nv)/n if n else np.nan,stage_count=g.stage.nunique(),stages=';'.join(sorted(g.stage.unique())),
      reference_status=';'.join(sorted(g.reference_status.unique())),imputed_responses=int(g.imputed_point.sum()))
    row.update({'scope_p_'+s:sc[s]/known if known and s!='unknown' else sc[s]/total for s in SCOPE})
    layers=[]
    for pc,z in valid.groupby('effective_point_count'):
        within=[r['d_mask_same_topology'] for r in pairs if r['points_a']==pc and r['points_b']==pc]
        layers.append(dict(image_id=image,condition=arm,view=view,context=context,point_count=pc,n_workers=len(z),n_pairs=len(within),median_d_mask=median(within)))
    return row,pairs,layers

def image_outcomes(df,dense):
    base=df[df.main_worker_included];targets=[];pairs=[];layers=[]
    for view,f in [('reviewed',base),('no_imputed',base[~base.imputed_point])]:
        for (image,arm),g in f.groupby(['image_id','raw_condition']):
            t,p,l=summarize_group(g,dense,image,arm,view);targets.append(t);pairs+=p;layers+=l
    for (image,arm,context),g in base.groupby(['image_id','raw_condition','context_key']):
        t,p,l=summarize_group(g,dense,image,arm,'context_specific',context);targets.append(t)
    write_csv('human/image_outcomes.csv',targets);write_csv('human/distinct_worker_pairs.csv.gz',pairs);write_csv('human/point_count_strata.csv',layers)
    return pd.DataFrame(targets),pd.DataFrame(pairs)

def interpretable_inputs():
    spatial={r['image_id']:r for r in load(BUNDLE/'metadata/spatial_history.jsonl.gz')}
    traits={r['image_id']:r for r in load(BUNDLE/'visual/visual_traits.json')}
    recheck={r['image_id']:r for r in load(BUNDLE/'visual/resolution_recheck.json')['images']}
    rows=[]
    for m in load(BUNDLE/'metadata/images.jsonl'):
        i=m['image_id'];s=spatial[i];v=traits[i];door=s.get('doorway_reconciliation') or {};c=s.get('current_coarse_review') or {}
        row=dict(image_id=i,building=m['building'],source_split=m['source_split'],scene=c.get('value') or 'unknown',scene_initial=(s.get('spatial_classification') or {}).get('coarse_type') or 'unknown',
             scene_source=c.get('source') or 'unknown',scene_human_accepted=c.get('human_accepted'),doorway=door.get('current_working_label') or 'unknown',doorway_source=door.get('source') or 'unknown',
             doorway_coordinate_verified=door.get('coordinate_verified',False),open_layout_evidence=s.get('spatial_open_layout_status') or 'unknown',trait_reviewer=v['reviewer'],trait_basis=v['review_basis'],resolution_rechecked=i in recheck)
        row.update({k:v[k] for k in TRAITS});row.update({k+'_rechecked':recheck[i]['reviewed_traits'][k] if i in recheck else v[k] for k in TRAITS})
        rows.append(row)
    f=pd.DataFrame(rows);write_csv('A/interpretable_inputs.csv',f)
    coverage=[]
    for k in ['scene','scene_initial','doorway','open_layout_evidence',*TRAITS]:
        for value,n in f[k].value_counts(dropna=False).items():coverage.append(dict(feature=k,value=value,n=n,proportion=n/len(f)))
    co=[]
    for a,b in itertools.combinations(TRAITS,2):
        for (av,bv),n in f.groupby([a,b]).size().items():co.append(dict(feature_a=a,feature_b=b,value_a=av,value_b=bv,n=n))
    write_csv('A/feature_coverage.csv',coverage);write_csv('A/trait_cooccurrence.csv',co)
    write_json(OUT/'A/redundancy_audit.json',dict(floor_partial_exactly_occlusion_present=bool(np.array_equal(f.floor_boundary.eq('partial'),f.corner_occlusion.eq('present'))),
        changes_21_same_AI_reviewer=load(BUNDLE/'visual/resolution_recheck.json')['summary'],
        scene_changed_from_initial=int((f.scene!=f.scene_initial).sum()),notes=['Do not include index, historical human difficulty, response count, or historical outcome-bearing descriptions as image features.','Open-layout unknown is not closed. Scope choices are rule/rejection categories, not direct enclosed/extended labels.']))
    return f

def paired_views(df,targets,feat):
    results=[];common=[];base=df[df.main_worker_included]
    tb=targets[(targets.view=='reviewed')].set_index(['image_id','condition']);fb=feat.set_index('image_id')
    for room in load(BUNDLE/'evaluation/room_components.jsonl'):
        if room['status']!='supported_component':continue
        for a,b in itertools.combinations(room['image_ids'],2):
            for arm in ('manual','semi'):
                if (a,arm) not in tb.index or (b,arm) not in tb.index:continue
                x=tb.loc[(a,arm)];y=tb.loc[(b,arm)]
                row=dict(room_id=room['room_id'],image_a=a,image_b=b,building=a.split('_')[0],condition=arm,n_a=int(x.n_workers),n_b=int(y.n_workers),same_scene=fb.loc[a,'scene']==fb.loc[b,'scene'])
                row.update({k+'_a':fb.loc[a,k] for k in ['scene','doorway',*TRAITS]});row.update({k+'_b':fb.loc[b,k] for k in ['scene','doorway',*TRAITS]})
                for t in TARGETS:row[t+'_a']=x[t];row[t+'_b']=y[t];row[t+'_delta']=y[t]-x[t]
                ag=base[(base.image_id==a)&(base.raw_condition==arm)].set_index('worker_id');bg=base[(base.image_id==b)&(base.raw_condition==arm)].set_index('worker_id')
                ws=ag.index.intersection(bg.index);row['n_common_workers']=len(ws)
                for w in ws:
                    r=dict(room_id=room['room_id'],building=a.split('_')[0],image_a=a,image_b=b,condition=arm,worker_id=w,same_stage=ag.loc[w,'stage']==bg.loc[w,'stage'])
                    for target,col in [('quality','quality'),('time','active_seconds'),('scope_non_normal','scope')]:
                        if col=='scope':v1=float(ag.loc[w,col]!='normal') if ag.loc[w,col]!='unknown' else np.nan;v2=float(bg.loc[w,col]!='normal') if bg.loc[w,col]!='unknown' else np.nan
                        else:v1=ag.loc[w,col];v2=bg.loc[w,col]
                        r[target+'_a']=v1;r[target+'_b']=v2;r[target+'_delta']=v2-v1
                    for k in ['doorway',*TRAITS]:r[k+'_a']=fb.loc[a,k];r[k+'_b']=fb.loc[b,k]
                    common.append(r)
                results.append(row)
    write_csv('A/same_room_view_pairs.csv',results);write_csv('A/same_room_common_workers.csv',common)
    return pd.DataFrame(results),pd.DataFrame(common)

def topology_clusters(dmat,point_counts,cut):
    """Complete linkage: no cross-point-count merging, no duplicated persons."""
    labels=np.zeros(len(point_counts),dtype=int);next_id=0
    for pc in sorted(set(point_counts)):
        ix=np.flatnonzero(np.array(point_counts)==pc)
        if len(ix)==1:lab=np.array([1])
        else:
            dm=np.asarray(dmat)[np.ix_(ix,ix)].copy();np.fill_diagonal(dm,0)
            lab=fcluster(linkage(squareform(dm,checks=True),method='complete'),cut,criterion='distance')
        labels[ix]=lab+next_id;next_id=int(labels.max())
    return labels

def stability(df,dense,repeats=100):
    """Finite-population, without-replacement saturation; not a formal stopping rule.
    At prefix k, at most 10% uncovered full-observed records; at least two future
    persons remain. Supported prefix clusters require >=2 persons. A candidate k
    must continue meeting that coverage at all later prefixes through n-2.
    Report threshold sensitivity and full-observed modes, never infinite claims.
    """
    rng=np.random.default_rng(SEED);summaries=[];curves=[];members=[]
    for (image,arm),g in df[df.main_worker_included & df.geometry_valid & df.raw_condition.isin(['manual','semi'])].groupby(['image_id','raw_condition']):
        g=g.sort_values('worker_id');n=len(g);pcs=g.effective_point_count.to_numpy();cids=g.canonical_annotation_id.to_list();workers=g.worker_id.tolist()
        dm=np.zeros((n,n))
        for i,j in itertools.combinations(range(n),2):dm[i,j]=dm[j,i]=_d_mask(dense[cids[i]],dense[cids[j]]) if pcs[i]==pcs[j] else 2.
        for cut in (.05,.10,.20):
            full=topology_clusters(dm,pcs,cut);sizes=collections.Counter(full);support=[k for k,v in sizes.items() if v>=2];largest=max(sizes.values())/n
            for w,p,l in zip(workers,pcs,full):members.append(dict(image_id=image,condition=arm,cut=cut,worker_id=w,point_count=p,cluster=int(l),cluster_n=sizes[l],supported=sizes[l]>=2))
            status='low_n' if n<4 else 'one_supported_dominant_mode' if len(support)==1 and largest>=.9 else 'multiple_supported_modes' if len(support)>=2 else 'no_dominant_supported_mode'
            hit=[];coverage_by_k=collections.defaultdict(list);supported_by_k=collections.defaultdict(list)
            if n>=4:
                for _ in range(repeats):
                    order=rng.permutation(n);ok=[]
                    for k in range(2,n-1):
                        ix=order[:k];lab=topology_clusters(dm[np.ix_(ix,ix)],pcs[ix],cut);cnt=collections.Counter(lab);med=[]
                        for l in cnt:
                            cluster=ix[lab==l]
                            if len(cluster)<2:continue
                            med.append(cluster[np.argmin(dm[np.ix_(cluster,cluster)].sum(1))])
                        # Coverage includes all observed records, including preserved singleton conventions.
                        cov=float(np.mean(np.min(dm[:,med],axis=1)<=cut+1e-12)) if med else 0.
                        coverage_by_k[k].append(cov);supported_by_k[k].append(len(med));ok.append(cov>=.9)
                    sustained=np.flip(np.cumprod(np.flip(ok))).astype(bool)
                    hit.append(2+int(np.flatnonzero(sustained)[0]) if sustained.any() else np.nan)
            for k,cov in coverage_by_k.items():
                curves.append(dict(image_id=image,condition=arm,cut=cut,n_workers=n,k=k,order_repetitions=repeats,mean_observed_coverage=float(np.mean(cov)),coverage_p10=float(np.quantile(cov,.1)),coverage_p90=float(np.quantile(cov,.9)),mean_supported_clusters=float(np.mean(supported_by_k[k])),probability_observed_coverage90=float(np.mean(np.array(cov)>=.9))))
            summaries.append(dict(image_id=image,building=image.split('_')[0],condition=arm,cut=cut,n_workers=n,clusters=len(sizes),supported_clusters=len(support),singleton_workers=sum(v for v in sizes.values() if v==1),largest_cluster_fraction=largest,finite_observed_pattern=status,
                order_repetitions=repeats if n>=4 else 0,future_people_minimum=2,observed_coverage_target=.9,sustained_saturation_fraction=float(np.mean(np.isfinite(hit))) if hit else np.nan,conditional_median_k=median(hit),not_a_frozen_convergence_criterion=True))
    write_csv('stability/observed_cluster_memberships.csv.gz',members);write_csv('stability/finite_population_summaries.csv',summaries);write_csv('stability/without_replacement_curves.csv.gz',curves)
    return pd.DataFrame(summaries)

def historical_semi(df,dense,refdense):
    table=[];bycid=df.set_index('canonical_annotation_id')
    for init in load(BUNDLE/'human/semi_initializations.jsonl.gz'):
        cid=init['canonical_annotation_id'];r=bycid.loc[cid];g=normalize_geometry(init['initial_points_1024x512']);q0=edit=np.nan
        a=_dense_boundaries(g['pairs']) if g['valid'] else None
        if a is not None and r.image_id in refdense:q0=_d_mask(a,refdense[r.image_id])
        if a is not None and cid in dense:edit=_d_mask(a,dense[cid])
        table.append(dict(canonical_annotation_id=cid,image_id=r.image_id,building=r.building,worker_id=r.worker_id,main_worker_included=r.main_worker_included,stage=r.stage,initialization_source=init['initialization_source_kind'],initialization_reference_type=init['reference_type'],current_reference_status=r.reference_status,
            planned_payload_verified=init['trace']['initial_import_match_status']=='all_matching',participant_view_event_verified=False,checkpoint_known=False,initial_geometry_valid=g['valid'],initial_failure=g['reason'],initial_points=len(init['initial_points_1024x512']),final_points=r.effective_point_count,
            initial_error_current_reference=q0,final_error_current_reference=r.quality,net_reference_improvement=q0-r.quality,initial_final_d_mask=edit,point_count_changed=len(init['initial_points_1024x512'])!=r.effective_point_count,active_seconds=r.active_seconds,scope=r.scope))
    frame=pd.DataFrame(table);write_csv('B/historical_semi_responses.csv',frame)
    summaries=[]
    for key,g in frame[frame.main_worker_included].groupby(['initialization_source','stage','current_reference_status']):
        usable=g.dropna(subset=['net_reference_improvement']);summaries.append(dict(initialization_source=key[0],stage=key[1],reference_status=key[2],n=len(g),n_quality_comparable=len(usable),images=g.image_id.nunique(),mean_net_improvement=usable.net_reference_improvement.mean(),median_net_improvement=usable.net_reference_improvement.median(),improved=int((usable.net_reference_improvement>1e-9).sum()),worsened=int((usable.net_reference_improvement < -1e-9).sum()),unchanged=int((usable.net_reference_improvement.abs()<=1e-9).sum()),point_change_rate=g.point_count_changed.mean(),median_edit=g.initial_final_d_mask.median()))
    write_csv('B/historical_semi_summary.csv',summaries)

def run(skip_stability=False):
    OUT.mkdir(parents=True,exist_ok=True)
    check=verify_bundle(BUNDLE);write_json(OUT/'inputs/bundle_check.json',check)
    inputs=[p for folder in ['evaluation','human','metadata','visual','history','projection'] for p in (BUNDLE/folder).rglob('*') if p.is_file()]
    write_json(OUT/'inputs/input_manifest.json',dict(commit=COMMIT,method_version='pro_v1_20260914',seed=SEED,python=platform.python_version(),files=[dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in inputs]))
    df,dense,rdense=geometries_and_responses();t,p=image_outcomes(df,dense);f=interpretable_inputs();v,c=paired_views(df,t,f);historical_semi(df,dense,rdense)
    coverage=[]
    for (arm,inc),g in df.groupby(['raw_condition','main_worker_included']):
        z=t[(t.condition==arm)&(t.view=='reviewed')]
        coverage.append(dict(condition=arm,main_included=inc,responses=len(g),workers=g.worker_id.nunique(),images=g.image_id.nunique(),valid_geometry=int(g.geometry_valid.sum()),quality_evaluable=int(g.quality.notna().sum()),time_usable=int(g.active_seconds.notna().sum()),n_pooled_image_targets=len(z) if inc else None,quality_images=int(z.reference_geometry_error.notna().sum()) if inc else None,time_images=int(z.owner_valid_active_seconds.notna().sum()) if inc else None,geometry_dispersion_images=int(z.within_topology_geometry_dispersion.notna().sum()) if inc else None))
    write_csv('coverage.csv',coverage);write_csv('human/geometry_failures.csv',df[~df.geometry_valid]);write_csv('human/worker_overall_descriptive.csv',df[df.main_worker_included].groupby(['worker_id','raw_condition']).agg(n=('image_id','size'),images=('image_id','nunique'),buildings=('building','nunique'),median_quality=('quality','median'),median_time=('active_seconds','median'),geometry_failure_rate=('geometry_valid',lambda x:1-x.mean())).reset_index())
    if not skip_stability:stability(df,dense)
    print(pd.DataFrame(coverage).to_string(index=False),flush=True)
    print('same-room pairs',len(v),'common-person comparisons',len(c),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--skip-stability',action='store_true');a=ap.parse_args();run(a.skip_stability)
