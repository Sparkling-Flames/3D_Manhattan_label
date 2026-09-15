"""Evidence-specific diagnostics, not outcome-selected redefinition.

Future people are always disjoint from the observed prefix. Geometric support
means threshold compatibility, not semantic correctness or a validated mode.
"""
from __future__ import annotations
import collections,itertools,math
import numpy as np,pandas as pd
from tools.thesis_main.analysis.image_portrait.history_difficulty_v1_core import *
from tools.thesis_main.analysis.image_portrait.history_difficulty_v1_people import boundaries_and_audit,clusters,dmask,replay


def run():
    primary=pd.read_csv(OUT/'targets/primary_per_image.csv');primary['grade']=primary.grade.fillna('')
    tags=pd.read_csv(OUT/'expert/independent_tags106.csv',keep_default_na=False)
    def note_text(s):
        j=json.loads(s);return '\n'.join(str(v).strip() for v in j.values() if v is not None and str(v).strip())
    tags['actual_image_comment']=tags.comment_json.map(note_text)
    csv('expert/verified_nonempty_comments.csv',tags[['image_id','expert_tag','actual_image_comment','display_group','group_comment']])
    cm=dict(total_tag_images=len(tags),actual_nonempty_image_comments=int(tags.actual_image_comment.str.len().gt(0).sum()),images_with_nonempty_group_comment=int(tags.group_comment.str.len().gt(0).sum()),unique_groups_with_nonempty_comment=tags.loc[tags.group_comment.str.len().gt(0),'display_group'].nunique(),supersedes='A_B/executed_summary.json comments_nonempty counted JSON containers, not actual text',old_value_not_used_for_any_model=True)
    js('expert/COMMENT_COUNT_CORRECTION.json',cm)
    # Explicit min/exact-x alternative: original grid x is a CAP and permits 1 mode.
    alternatives=[]
    evidence=pd.read_csv(OUT/'targets/onset_evidence.csv.gz')
    for arm,g in primary.groupby('condition'):
        for cap in (2,3,4):
            for semantics in ('cap_allow_unified','between2_and_cap','exact_x'):
                out=g.copy();allowed=out.n_supported_modes.between(1,cap) if semantics=='cap_allow_unified' else out.n_supported_modes.between(2,cap) if semantics=='between2_and_cap' else out.n_supported_modes.eq(cap)
                medium=(out.n_valid>=10)&out.n_invalid.eq(0)&allowed&(out.singleton_mass<=.1+1e-10)&(out.p_early<.8)&(out.p_cumulative>=.8)
                for i in np.flatnonzero(medium):alternatives.append(dict(condition=arm,image_id=out.iloc[i].image_id,max_few_modes=cap,mode_semantics=semantics,n_valid=int(out.iloc[i].n_valid),n_supported_modes=int(out.iloc[i].n_supported_modes),p_early=float(out.iloc[i].p_early),p_cumulative=float(out.iloc[i].p_cumulative)))
                if not medium.any():alternatives.append(dict(condition=arm,image_id='',max_few_modes=cap,mode_semantics=semantics,status='zero_images'))
    csv('targets/medium_mode_semantics.csv',alternatives)
    states=pd.read_csv(OLD/'process/replay_states.csv.gz')
    p=states.pivot(index=['image_id','condition','cut','replay'],columns='rule',values='onset').reset_index()
    p['G10_later_than_D10']=p.G10_geometry.fillna(np.inf)>p.D10_distribution.fillna(np.inf)
    p['D10_later_than_pattern']=p.D10_distribution.fillna(np.inf)>p.P_pattern.fillna(np.inf)
    csv('targets/stability_rule_increment_per_image.csv',p.groupby(['image_id','condition','cut']).agg(orders=('replay','size'),fraction_geometry_adds_delay=('G10_later_than_D10','mean'),fraction_distribution_adds_delay=('D10_later_than_pattern','mean')).reset_index())
    assigned=primary[primary.grade.isin(GRADES)]
    csv('targets/grade_actual_n_distribution.csv',assigned.groupby(['condition','grade','n_valid']).size().reset_index(name='images'))
    # Count-only prediction is a DIAGNOSTIC counterfactual; never a pure-image feature.
    count_predictions=[]
    for arm,g in assigned.groupby('condition'):
        g=g.reset_index(drop=True);y=g.grade.map(dict(zip(GRADES,range(3)))).to_numpy();Y=np.column_stack((y>=1,y>=2)).astype(float)
        for j,a in g.iterrows():
            tr=np.flatnonzero(g.building.to_numpy()!=a.building)
            for model in ('overall_frequency','actual_n_1NN_diagnostic'):
                use=tr
                if model!='overall_frequency' and len(tr):
                    distance=np.abs(g.n_valid.to_numpy()[tr]-a.n_valid);use=tr[distance==distance.min()]
                pred=Y[use].mean(0) if len(use) else np.array([np.nan,np.nan]);prob=np.r_[1-pred[0],pred[0]-pred[1],pred[1]]
                count_predictions.append(dict(image_id=a.image_id,condition=arm,building=a.building,grade=a.grade,model=model,n_valid=a.n_valid,loss=np.mean((pred-Y[j])**2),correct=int(prob.argmax()==y[j]),input_warning='actual target response count is allowed ONLY in this confounding diagnostic; not pure-image prediction'))
    counts=csv('diagnostics/count_only_not_image_predictions.csv',count_predictions)
    csv('diagnostics/count_only_summary.csv',counts.groupby(['condition','model']).agg(images=('image_id','nunique'),RPS=('loss','mean'),accuracy=('correct','mean')).reset_index())
    # Missing same-room tier source is a concrete relationship/label support fact.
    folds={f['test'][0]:f for f in read(B/'evaluation/folds.jsonl.gz') if f['design']=='same_room_leave_view'}
    status=primary.set_index(['image_id','condition']);missing=[]
    for r in assigned.to_dict('records'):
        f=folds.get(r['image_id']);sources=[]
        if f:
            for i in f['train']:
                if (i,r['condition']) in status.index:
                    z=status.loc[(i,r['condition'])];sources.append(dict(image_id=i,grade=z.grade,status=z.status,n_valid=int(z.n_valid)))
                else:sources.append(dict(image_id=i,status='no_history_in_this_condition'))
        missing.append(dict(image_id=r['image_id'],condition=r['condition'],grade=r['grade'],room_fold=f['fold_id'] if f else '',other_source_statuses=json.dumps(sources,ensure_ascii=False),status='no_supported_room_fold' if not f else 'no_assigned_same_condition_neighbor' if not any(x.get('grade') in GRADES for x in sources) else 'available'))
    csv('D/assigned_tier_room_source_coverage.csv',missing)
    # Recompute original geometry, then match prefix-singletons to distinct FUTURE people.
    raw=pd.read_csv(OUT/'inputs/response_metrics_sanitized.csv.gz');raw=raw[raw.main_worker_included&raw.raw_condition.isin(['manual','semi'])]
    bd=boundaries_and_audit(raw);events=[];short=[]
    for (image,arm),g in raw.groupby(['image_id','raw_condition']):
        if not g.geometry_valid.all() or len(g)<8:continue
        g=g.sort_values('worker_id').reset_index(drop=True);n=len(g);pcs=g.effective_point_count.to_numpy(int);dm=np.zeros((n,n))
        for a,b in itertools.combinations(range(n),2):dm[a,b]=dm[b,a]=dmask(bd[g.canonical_annotation_id.iloc[a]],bd[g.canonical_annotation_id.iloc[b]]) if pcs[a]==pcs[b] else 2.
        rng=np.random.default_rng(seed('singletons',image,arm));orders=[rng.permutation(n) for _ in range(40)]
        for cut in (.05,.1,.2):
            for rep,order in enumerate(orders):
                for k in range(2,min(8,n-1)+1):
                    obs=np.sort(order[:k]);future=np.sort(order[k:]);lab=clusters(dm[np.ix_(obs,obs)],pcs[obs],cut);co=collections.Counter(lab)
                    singles=[obs[j] for j,l in enumerate(lab) if co[l]==1]
                    for u in singles:
                        other=obs[obs!=u];isolated=bool((dm[u,other]>cut+1e-12).all());compat=future[dm[u,future]<=cut+1e-12]
                        events.append(dict(image_id=image,building=image.split('_')[0],condition=arm,cut=cut,order=rep,k=k,n_total=n,n_future=len(future),singleton_worker=g.worker_id.iloc[u],canonical_annotation_id=g.canonical_annotation_id.iloc[u],isolated_from_all_observed=isolated,has_future_compatible_person=bool(len(compat)),future_compatible_count=len(compat),future_compatible_worker_ids=';'.join(g.worker_id.iloc[compat]),future_compatible_canonical_ids=';'.join(g.canonical_annotation_id.iloc[compat]),prefix_worker_ids=';'.join(g.worker_id.iloc[obs])))
        if n>=12:
            for rep,order in enumerate(orders[:12]):
                sub=g.iloc[np.sort(order[:6])];res=replay(sub,bd,orders=30)
                future=np.sort(order[6:]);full=status.loc[(image,arm)]
                short.append(dict(image_id=image,building=image.split('_')[0],condition=arm,subset=rep,observed_n=6,actual_full_n=n,workers=';'.join(sub.worker_id),prefix_grade=res['grade'],prefix_status=res['status'],full_grade=full.grade,full_status=full.status,prefix_early=res.get('p_early7'),future_pair_coverage=float(np.mean(np.min(dm[np.ix_(future,np.sort(order[:6]))],axis=1)<=.1)),definition='reclassify actual 6-person pool using only its responses; full target is retrospective comparison'))
    e=csv('extra/singleton_real_future_support.csv.gz',events);q=csv('extra/six_person_vs_full_history.csv',short)
    if len(e):
        image_summary=e.groupby(['image_id','building','condition','cut','k','isolated_from_all_observed']).agg(singleton_events=('singleton_worker','size'),future_support_rate=('has_future_compatible_person','mean'),future_support_count_mean=('future_compatible_count','mean'),n_total=('n_total','first'),n_future=('n_future','first')).reset_index()
        csv('extra/singleton_future_support_per_image.csv',image_summary)
        csv('extra/singleton_future_support_summary.csv',image_summary.groupby(['condition','cut','k','isolated_from_all_observed']).agg(images=('image_id','nunique'),image_macro_future_support=('future_support_rate','mean'),median_future_people=('n_future','median')).reset_index())
    if len(q):csv('extra/six_person_vs_full_summary.csv',q.groupby(['condition','prefix_grade','full_grade'],dropna=False).agg(subsets=('subset','size'),images=('image_id','nunique'),mean_future_coverage=('future_pair_coverage','mean')).reset_index())
    # Check historical Semi source heterogeneity, not current model output substitution.
    init=read(B/'human/semi_initializations.jsonl.gz');valid=set(raw.loc[raw.raw_condition=='semi','canonical_annotation_id']);sem=[]
    for r in init:
        if r['canonical_annotation_id'] not in valid:continue
        geometry=r['initial_points_1024x512'];sha=hashlib.sha256(json.dumps(geometry,separators=(',',':')).encode()).hexdigest()
        sem.append(dict(image_id=r['image_id'],worker_id=r['worker_id'],canonical_annotation_id=r['canonical_annotation_id'],initialization_geometry_hash=sha,initialization_source_kind=r.get('initialization_source_kind'),reference_type=r.get('reference_type'),historical_checkpoint_status=r.get('historical_checkpoint_status'),trace_status=r.get('trace',{}).get('initial_import_match_status')))
    sd=csv('B/historical_semi_initialization_audit.csv',sem)
    if len(sd):csv('B/semi_initialization_image_heterogeneity.csv',sd.groupby('image_id').agg(responses=('worker_id','size'),distinct_initial_geometries=('initialization_geometry_hash','nunique'),source_kinds=('initialization_source_kind',lambda a:';'.join(sorted(set(a.astype(str)))))).reset_index())
    js('diagnostics/executed_summary.json',dict(singleton_events=len(e),singleton_images=e.image_id.nunique() if len(e) else 0,prefix6_actual_subsets=len(q),prefix6_images=q.image_id.nunique() if len(q) else 0,semi_verified_initialization_rows=len(sd),comments=cm,orders_not_new_people=True,semantic_legitimacy_not_judged=True,rare_future_modes_not_assumed_noise=True,median_mode_semantics='cap1..x primary;2..x and exactx separately reported'))
    print('DIAGNOSTICS',read(OUT/'diagnostics/executed_summary.json'),flush=True)

if __name__=='__main__':run()
