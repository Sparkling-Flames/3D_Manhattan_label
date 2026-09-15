"""Historical response-derived tiers, separate from the 106 expert tags.

This follow-up reuses audited finite-person replays, never experimental difficulty.
All outputs are versioned; no original annotation or formal protocol is changed.
"""
from __future__ import annotations
import argparse, collections, gzip, hashlib, itertools, json, os, re, subprocess
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
B = ROOT / 'analysis_results/image_portrait_20260914_v1'
OLD = B / 'cloud/pro_exploration/v2_convergence_e086b2b9'
MAINSPACE = B / 'cloud/difficulty_tags_20260915_v1/mainspace_v1_9d19e4e7'
OUT = B / 'cloud/history_difficulty_20260915_v1/run_13859d59'
BASE = '13859d591acb1bac7790fb0762f2c53282f65748'
SEED = 20260915
TRAITS = ['floor_boundary','ceiling_boundary','corner_occlusion','connected_space','reflection_glass','low_contrast']
RULES = ['P_pattern','D10_distribution','D20_distribution','G10_geometry']
GRADES = ['simple','medium','difficult_candidate']
ANCHOR = dict(cut=.1, rule='G10_geometry', early_k=7, late_h=19, max_few_modes=3, max_singleton_mass=.1, order_fraction_required=.8, confirmation='suffix', medium_definition='cumulative')


def safe(x):
    if isinstance(x,dict): return {str(k):safe(v) for k,v in x.items()}
    if isinstance(x,(list,tuple,np.ndarray)): return [safe(v) for v in x]
    if isinstance(x,(np.integer,)): return int(x)
    if isinstance(x,(np.bool_,)): return bool(x)
    if isinstance(x,(float,np.floating)): return float(x) if np.isfinite(x) else None
    return x


def read(p):
    p=Path(p)
    if p.suffix=='.gz':
        with gzip.open(p,'rt',encoding='utf-8-sig') as f: return [json.loads(x) for x in f if x.strip()]
    if p.suffix=='.jsonl': return [json.loads(x) for x in p.read_text(encoding='utf-8-sig').splitlines() if x.strip()]
    return json.loads(p.read_text(encoding='utf-8-sig'))


def js(name,x):
    p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(safe(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def csv(name,x):
    p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
    d=x if isinstance(x,pd.DataFrame) else pd.DataFrame(x)
    if not len(d.columns): d=pd.DataFrame(columns=['status'])
    kw={'compression':{'method':'gzip','mtime':0}} if p.suffix=='.gz' else {}
    d.to_csv(p,index=False,float_format='%.12g',**kw)
    return d


def seed(*x): return int(hashlib.sha256('|'.join(map(str,x)).encode()).hexdigest()[:8],16)

def scope_collapse(x):
    x=str(x or '').lower().strip()
    if x.startswith('oos') or x.startswith('out_of_scope'): return 'oos'
    if x in ('normal','in_scope','in-scope'): return 'in_scope'
    return 'unknown'


def finite_median(a):
    a=np.asarray(a,float);return float(np.median(a[np.isfinite(a)])) if np.isfinite(a).any() else np.nan


def paired_ci(d,column,group='building',repeats=2000):
    z=d[[group,column]].dropna();a=z.groupby(group)[column].agg(['sum','count'])
    r=dict(n=len(z),groups=len(a),delta=z[column].mean() if len(z) else np.nan,lo=np.nan,hi=np.nan,group_macro=z.groupby(group)[column].mean().mean() if len(z) else np.nan)
    if len(a)>1:
        v=a.to_numpy();rng=np.random.default_rng(SEED);ii=rng.integers(len(v),size=(repeats,len(v)));w=v[ii].sum(1);q=w[:,0]/w[:,1];r.update(lo=np.quantile(q,.025),hi=np.quantile(q,.975))
    return r


def classify(n,invalid,modes,singletons,early,cumulative,interval,any_stable,late_change,k=7,h=19,x=3,smax=.1,q=.8,medium='cumulative'):
    """No n replication, no permanent non-convergence claim, no forced balance."""
    if invalid: return '', 'invalid_response_evidence'
    if n<4: return '', 'insufficient_people'
    if modes>=1 and modes<=2 and singletons<=smax+1e-10 and early>=q-1e-10:
        return 'simple','assigned_observed_early'
    later = cumulative if medium=='cumulative' else interval
    if n>=10 and 1<=modes<=x and singletons<=smax+1e-10 and early<q-1e-10 and later>=q-1e-10:
        return 'medium','assigned_observed_later'
    if modes>=1 and singletons<=smax+1e-10 and any_stable>=q-1e-10:
        return '', 'stable_outside_three_tier_limits'
    ns=int(round(singletons*n))
    if n>=10 and modes+ns>=5 and ns>=2 and singletons>=.2-1e-10 and late_change:
        return 'difficult_candidate','assigned_observed_fragmentation_and_change'
    if n<10: return '', 'limited_horizon_or_order_sensitive'
    if singletons>smax+1e-10: return '', 'singleton_support_unresolved'
    return '', 'order_sensitive_or_other_trajectory'


def prepare():
    from tools.thesis_main.analysis.image_portrait.build_bundle import verify_bundle
    OUT.mkdir(parents=True,exist_ok=True)
    check=verify_bundle(B)
    raw=read(B/'human/responses.jsonl.gz')
    rawmap={r['canonical_annotation_id']:r for r in raw}
    source=OLD/'foundation/human/response_metrics.csv.gz'
    df=pd.read_csv(source)
    assert len(df)==len(rawmap)==2501
    for r in df.to_dict('records'):
        z=rawmap[r['canonical_annotation_id']]
        assert (r['image_id'],r['worker_id'],r['raw_condition'])==(z['image_id'],z['worker_id'],z['raw_condition'])
        assert int(r['effective_point_count'])==len(z['effective_points_1024x512'])
        assert bool(r['main_worker_included'])==(z['worker_id'] not in ('W019','W026'))
    # Project only named numerical/person fields. Legacy difficulty/context labels are not carried.
    fields=['canonical_annotation_id','image_id','worker_id','raw_condition','effective_point_count','geometry_valid','geometry_failure','imputed_point','main_worker_included','quality','active_seconds','top_signed_pixels','floor_signed_pixels','band_width_bias_pixels']
    rows=df[[c for c in fields if c in df]].copy()
    rows['building']=rows.image_id.str.split('_').str[0]
    choices={}
    for cid,r in rawmap.items():
        sc=[v for c in r.get('choices',[]) if str(c.get('from_name','')).lower()=='scope' for v in c.get('choices',[])]
        choices[cid]=scope_collapse(sc[0]) if len(sc)==1 else 'unknown'
    rows['scope']=rows.canonical_annotation_id.map(choices)
    assert not rows.duplicated(['image_id','raw_condition','worker_id']).any()
    csv('inputs/response_metrics_sanitized.csv.gz',rows)
    sp={r['image_id']:r for r in read(B/'metadata/spatial_history.jsonl.gz')}
    ims=pd.DataFrame(read(B/'metadata/images.jsonl'))
    whitelist=['image_id','building','source_split','scene_category','scene_source','main_space_raw','main_space_safe','main_space_source','main_space_basis','main_space_human','main_space_human_source','fine_human','fine_ai','doorway','room_id','room_status','main_function_primary','main_function_primary_source','main_semantic_key',*TRAITS,*[t+'_recheck' for t in TRAITS],'resolution_rechecked']
    oldmeta=MAINSPACE/'images/metadata_all648.csv'
    header=pd.read_csv(oldmeta,nrows=0).columns
    whitelist += [c for c in header if c.startswith('position_') or c in ['main_sleep','main_bathroom','main_kitchen','main_dining','main_living','main_work','main_circulation','main_storage','main_special','main_empty']]
    meta=pd.read_csv(oldmeta,usecols=[c for c in whitelist if c in header],keep_default_na=False)
    assert len(meta)==648 and set(meta.image_id)==set(ims.image_id)
    # Match original categories and main-space text against the declared source only.
    for r in meta.to_dict('records'):
        s=sp[r['image_id']];c=s.get('spatial_classification') or {};p=s.get('spatial_prior_user') or {}
        expected=c.get('coarse_type') or p.get('user_type') or 'unknown'
        if r['scene_category'] and expected!='unknown': assert r['scene_category']==expected
        text=(s.get('new_spatial_review') or {}).get('main_space') or s.get('main_visual_space') or ''
        assert str(r['main_space_raw'])==str(text)
    csv('inputs/image_metadata_whitelist.csv',meta)
    original_path=ROOT/'analysis_results/candidate_selection_review_20260913_v2/用户审查原始记录.json'
    original=read(original_path) if original_path.exists() else {}
    groupnotes={r.get('group'):r.get('note','') for r in original.get('groups',[])}
    tags=[]
    for i,s in sp.items():
        v=s.get('latest_selection_record') or {}
        tag=v.get('difficulty')
        if tag not in ('简单','中等','困难'):continue
        note={k:v[k] for k in ('note','notes','comment','comments','reason') if k in v}
        group=v.get('group',v.get('display_group',v.get('review_code','')))
        tags.append(dict(image_id=i,expert_tag=tag,comment_json=json.dumps(note,ensure_ascii=False),selection_record_json=json.dumps(v,ensure_ascii=False),display_group=group,group_comment=groupnotes.get(group,''),source='metadata/spatial_history.jsonl.gz#/latest_selection_record',use='independent contrast only; excluded from tier formation and image predictors'))
    td=csv('expert/independent_tags106.csv',tags)
    assert td.expert_tag.value_counts().to_dict()=={'简单':49,'中等':41,'困难':16}
    geo=rows[rows.main_worker_included & rows.raw_condition.isin(['manual','semi'])]
    targetids=sorted(geo.image_id.unique());js('inputs/historical_ids.json',targetids)
    counts=[]
    for arm,g in rows[rows.main_worker_included].groupby('raw_condition'):
        counts.append(dict(condition=arm,responses=len(g),images=g.image_id.nunique(),workers=g.worker_id.nunique(),valid_responses=int(g.geometry_valid.sum()),valid_images=g[g.geometry_valid].image_id.nunique()))
    csv('inputs/response_coverage.csv',counts)
    oos=rows[rows.main_worker_included & ~rows.raw_condition.isin(['manual','semi'])].copy()
    if len(oos):
        oos['condition']='oos';csv('oos/unified_rule_responses.csv',oos)
        csv('oos/unified_image_results.csv',oos.groupby('image_id').agg(n_people=('worker_id','nunique'),oos_choices=('scope',lambda a:(a=='oos').sum()),in_scope_choices=('scope',lambda a:(a=='in_scope').sum()),unknown_choices=('scope',lambda a:(a=='unknown').sum())).reset_index())
    artifacts=['human/responses.jsonl.gz','metadata/spatial_history.jsonl.gz','evaluation/folds.jsonl.gz','evaluation/config.json','visual/visual_traits.json']
    artifacts += [str(p.relative_to(B)) for p in (OLD/'process').glob('*') if p.is_file()]
    hashes=[dict(path=str(B/p),sha256=hashlib.sha256((B/p).read_bytes()).hexdigest()) for p in artifacts]
    js('inputs/source_manifest.json',dict(input_commit=BASE,execution_commit=subprocess.check_output(['git','rev-parse','HEAD']).decode().strip(),bundle_check=check,actual_historical_images=len(targetids),expert_tag_images=len(td),overlap_images=len(set(targetids)&set(td.image_id)),old_experimental_difficulty_used=False,scope_subtypes_collapsed=True,early_k_supersedes_old_prompt=[2,3,4,5,6,7,8],artifacts=hashes,notes=['No original images, model weights or new visual inference.','Human tags and comments are never predictors of historical tiers.','Source hashes include raw evidence; analytical columns are explicitly whitelisted.','Historical processes are finite-person replay evidence, not original submission chronology.']))
    print('PREPARE',counts,'historical images',len(targetids),'overlap',len(set(targetids)&set(td.image_id)),flush=True)


def targets():
    keys=['image_id','condition','cut']
    s=pd.read_csv(OLD/'process/image_uncertainty_structure.csv')
    r=pd.read_csv(OLD/'process/replay_states.csv.gz')
    c=pd.read_csv(OLD/'process/image_growth_curves.csv.gz')
    membership=pd.read_csv(OLD/'process/mode_memberships.csv.gz')
    raw=pd.read_csv(OUT/'inputs/response_metrics_sanitized.csv.gz')
    allow=set(raw.loc[raw.main_worker_included & raw.geometry_valid,'canonical_annotation_id'])
    assert set(membership.canonical_annotation_id)<=allow
    assert not membership.worker_id.isin(['W019','W026']).any()
    actual=raw[raw.main_worker_included & raw.raw_condition.isin(['manual','semi'])].groupby(['image_id','raw_condition']).size()
    for v in s.to_dict('records'): assert int(v['n_observed'])==int(actual.loc[(v['image_id'],v['condition'])])
    curvegroups={k:g.sort_values('k') for k,g in c.groupby(keys)}
    reps={k:g for k,g in r.groupby(keys+['rule'])}
    evidence=[];allgrid=[]
    for st in s.to_dict('records'):
        ident=(st['image_id'],st['condition'],st['cut']);n=int(st['n_valid']);inv=int(st['n_invalid'])
        modes=int(st.get('n_supported_modes',0)) if pd.notna(st.get('n_supported_modes')) else 0
        singleton=float(st.get('singleton_mass',1)) if pd.notna(st.get('singleton_mass')) else 1.
        cg=curvegroups.get(ident,pd.DataFrame());late=cg[cg.k>n/2] if len(cg) else cg
        def mean_col(col): return float(late[col].mean()) if col in late and len(late) else np.nan
        novelty=mean_col('new_incompatible_mode');repartition=mean_col('repartition_pair_change');drift=mean_col('within_mode_step_delta')
        mid=cg.iloc[(cg.k-n/2).abs().argmin()] if len(cg) else {}
        half_tv=float(mid.get('TV_full_observed',np.nan));late_promotions=mean_col('support_promotions')
        changing=bool((np.isfinite(novelty) and novelty>.05) or (np.isfinite(repartition) and repartition>.05) or (np.isfinite(drift) and drift>.02))
        for rule in RULES:
            rr=reps.get(ident+(rule,))
            ons=rr.onset.to_numpy(float) if rr is not None else np.array([np.nan])
            tail=(rr.state.isin(['observed_unified','stable_multicluster']).to_numpy()) if rr is not None else np.array([False])
            base=dict(image_id=ident[0],condition=ident[1],cut=ident[2],building=ident[0].split('_')[0],rule=rule,n_observed=int(st['n_observed']),n_valid=n,n_invalid=inv,n_supported_modes=modes,n_singletons=int(round(singleton*n)),singleton_mass=singleton,n_modes=st.get('n_modes',0),same_point_count_multimodality=st.get('same_topology_multimodality',False),point_count_disagreement=st.get('topology_disagreement',np.nan),within_mode_median=st.get('within_mode_median_d',np.nan),late_new_geometry=novelty,late_repartition=repartition,late_geometry_step=drift,late_support_promotions=late_promotions,half_tv=half_tv,p_tail_stable=float(np.mean(tail)),onset_median_conditional=finite_median(ons),mode_semantics='numerical candidate; legitimacy needs local visual review')
            for confirm in ['suffix','suffix_and_tail']:
                onset=np.where(tail,ons,np.nan) if confirm=='suffix_and_tail' else ons
                pany=float(np.mean(np.isfinite(onset)))
                for k in range(2,9):
                    early=float(np.mean(onset<=k))
                    ev=dict(base,confirmation=confirm,early_k=k,p_early=early,p_any_stable=pany,observed_early_limit=min(k,max(0,n-1)),observations_after_k=max(0,n-k),early_limit_censored=n<=k)
                    evidence.append(ev)
                    for h,x,smax,q,medium in itertools.product([10,12,15,18,19],[2,3,4],[0.,.1],[.8,.9],['interval','cumulative']):
                        cum=float(np.mean(onset<=h));inter=float(np.mean((onset>k)&(onset<=h)))
                        grade,status=classify(n,inv,modes,singleton,early,cum,inter,pany,changing,k,h,x,smax,q,medium)
                        allgrid.append(dict(image_id=ident[0],condition=ident[1],cut=ident[2],rule=rule,confirmation=confirm,early_k=k,late_h=h,max_few_modes=x,max_singleton_mass=smax,order_fraction_required=q,medium_definition=medium,grade=grade,status=status,p_early=early,p_cumulative=cum,p_late_interval=inter,actual_late_limit=min(h,max(0,n-1)),horizon_censored=n<h))
    ed=csv('targets/onset_evidence.csv.gz',evidence)
    grid=csv('targets/definition_grid.csv.gz',allgrid)
    params=['cut','rule','confirmation','early_k','late_h','max_few_modes','max_singleton_mass','order_fraction_required','medium_definition']
    csv('targets/definition_counts.csv',grid.groupby(params+['condition','grade','status'],dropna=False).size().reset_index(name='n_images'))
    mask=np.ones(len(grid),bool)
    for key,val in ANCHOR.items(): mask &= np.isclose(grid[key],val) if isinstance(val,(int,float)) else grid[key].eq(val)
    anchor=grid[mask].copy()
    em=ed[(ed.cut==.1)&(ed.rule=='G10_geometry')&(ed.confirmation=='suffix')&(ed.early_k==7)]
    anchor=anchor.merge(em,on=['image_id','condition','cut','rule','confirmation','early_k','p_early'],validate='one_to_one')
    csv('targets/primary_per_image.csv',anchor)
    # A small declared robustness family, not data-chosen thresholds or confidence probabilities.
    z=grid[grid.rule.isin(['D10_distribution','G10_geometry']) & grid.early_k.isin([7,8]) & grid.late_h.isin([15,19]) & grid.max_few_modes.eq(3) & grid.max_singleton_mass.eq(.1) & grid.order_fraction_required.eq(.8) & grid.medium_definition.eq('cumulative')]
    robust=[]
    for key,g in z.groupby(['image_id','condition']):
        counts=g.grade.fillna('').value_counts();winner=str(counts.index[0]);prop=float(counts.iloc[0]/len(g))
        robust.append(dict(image_id=key[0],condition=key[1],modal_grade=winner,agreement_across_definitions=prop,robust_assigned_grade=winner if winner in GRADES and prop>=.8 else '',distinct_assigned_grades=g[g.grade.isin(GRADES)].grade.nunique(),status='definition_disagreement' if len(counts)>1 else 'same_output_across_family',n_definitions=len(g)))
    rb=csv('targets/robustness_per_image.csv',robust)
    csv('targets/primary_with_robustness.csv',anchor.merge(rb,on=['image_id','condition']))
    # The same data under interval vs cumulative medium definitions.
    common=[p for p in params if p!='medium_definition']+['image_id','condition']
    zz=grid.pivot(index=common,columns='medium_definition',values='grade').reset_index()
    csv('targets/interval_to_cumulative_changes.csv.gz',zz[zz['interval'].fillna('')!=zz['cumulative'].fillna('')])
    csv('targets/growth_curves_reused.csv.gz',c[[x for x in c if x not in ['scene']]])
    csv('targets/mode_memberships_reused.csv.gz',membership[[x for x in membership if x!='scene']])
    # Continuous endpoints remain available independently of a three-tier assignment.
    cont=anchor.copy();eligible=(cont.n_valid>=4)&cont.n_invalid.eq(0)&(cont.singleton_mass<=.1+1e-10)
    cont['cdf_early7']=cont.p_early.where(eligible);cont['cdf_observed_by19']=cont.p_cumulative.where(eligible)
    for name in ['late_new_geometry','half_tv','within_mode_median']:
        cont.loc[cont.n_valid<4,name]=np.nan
    cont.loc[cont.n_valid<2,'singleton_mass']=np.nan
    csv('targets/continuous_targets.csv',cont)
    tags=pd.read_csv(OUT/'expert/independent_tags106.csv');overlap=anchor.merge(tags,on='image_id',how='inner')
    csv('expert/overlap_per_image.csv',overlap)
    csv('expert/overlap_cross_tab.csv',overlap.groupby(['condition','expert_tag','grade','status'],dropna=False).size().reset_index(name='images'))
    expert_ids=set(tags.image_id);hist_ids=set(anchor.image_id);assigned=anchor[anchor.grade.isin(GRADES)];robust_ids=set(rb.loc[rb.robust_assigned_grade.isin(GRADES),'image_id'])
    coverage=dict(historical_unique_images=len(hist_ids),historical_image_conditions=len(anchor),expert_images=len(expert_ids),overlap_images=len(hist_ids&expert_ids),historical_outside_expert=len(hist_ids-expert_ids),primary_assigned_images=assigned.image_id.nunique(),primary_assigned_image_conditions=len(assigned),new_primary_assigned_images=len(set(assigned.image_id)-expert_ids),robust_assigned_images=len(robust_ids),new_robust_assigned_images=len(robust_ids-expert_ids),union_descriptive_images=len(hist_ids|expert_ids),union_expert_or_primary_assigned=len(expert_ids|set(assigned.image_id)),grid_rows=len(grid),grade_counts=assigned.groupby(['condition','grade']).size().to_dict(),status_counts=anchor.groupby(['condition','status']).size().to_dict())
    js('targets/coverage.json',coverage)
    js('METHOD.json',dict(version='history_difficulty_v1_followup',anchor=ANCHOR,early_k=list(range(2,9)),late_h=[10,12,15,18,19],mode_caps=[2,3,4],singleton_caps=[0,.1],order_proportions=[.8,.9],cuts=[.05,.1,.2],rules=RULES,medium_definitions=['interval','cumulative'],confirmation=['suffix','suffix_and_tail'],difficulty_candidate='n>=10, total modes>=5, >=2 singleton people and singleton share>=.2, plus observed latter-half novelty>.05 or repartition>.05 or within-mode step>.02; never permanent nonconvergence',actual_n_is_primary=True,grade_and_status_separate=True,old_experimental_difficulty_used=False,expert_tags_used_for_tiers=False,retrospective_full_partition_used_only_for_targets=True,replays_are_not_independent_samples=True,short_suffix_is_not_long_term_stability=True,unresolved_singletons_may_be_rare_unseen_supported_modes=True,robustness='declared cut/rule/k/h/confirmation family; 80% agreement is sensitivity summary, not posterior confidence',classification_k8='latest user request supersedes older k<8 text'))
    print('TARGET COVERAGE',json.dumps(safe(coverage),ensure_ascii=False),flush=True)

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('stage',choices=['prepare','targets']);args=a.parse_args()
    prepare() if args.stage=='prepare' else targets()
