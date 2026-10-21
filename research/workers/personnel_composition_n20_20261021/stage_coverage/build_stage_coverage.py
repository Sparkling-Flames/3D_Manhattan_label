"""Join phase identities and finite n20 coverage; no fitting, scoring or fusion.

Only two condition/domain-subset rows receive new MV deep-study counts. Other
method families, inherited coarse projections and legacy QT comparison support
remain explicit in separate tables. Old field values are preserved verbatim.
"""
from __future__ import annotations
import csv, gzip, hashlib, io, json, math, zipfile
from pathlib import Path
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
CONT=HERE.parent
STUDY=CONT.parent
REPO=STUDY.parents[2]
NEXT=CONT/'next_stage'
ABC=CONT/'n20_abc'
ANALYSIS=CONT/'n20_analysis'
SOURCES={}
DOMAIN_METHODS={('manual','Q+T+D'):'MV_QTD_manual_new',
                ('semi','Q+T+scope+Semi'):'MV_QTScopeSemi_semi_new'}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path,**kwargs):
    path=Path(path);out=pd.read_csv(path,**kwargs)
    SOURCES[str(path.relative_to(REPO))]=sha(path)
    return out


def read_json(path):
    path=Path(path);SOURCES[str(path.relative_to(REPO))]=sha(path)
    return json.loads(path.read_text())


def publish(frame,name,keys=()):
    if keys:assert not frame.duplicated(list(keys)).any(),name
    raw=frame.to_csv(index=False,lineterminator='\n').encode('utf-8-sig')
    p=HERE/name;tmp=p.with_suffix(p.suffix+'.tmp')
    assert tmp.write_bytes(raw)==len(raw)
    assert tmp.read_bytes()==raw
    rows=list(csv.reader(io.StringIO(raw.decode('utf-8-sig'))))
    assert len(rows)==len(frame)+1 and all(len(r)==len(frame.columns) for r in rows)
    tmp.replace(p)


def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(tuple,list)):return [clean(v) for v in x]
    if isinstance(x,np.generic):return clean(x.item())
    if isinstance(x,float) and not math.isfinite(x):return None
    return x


def publish_json(obj,name):
    p=HERE/name;tmp=p.with_suffix(p.suffix+'.tmp')
    tmp.write_text(json.dumps(clean(obj),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    json.loads(tmp.read_text());tmp.replace(p)


def caps(s):return {a:int(b) for a,b in (x.rsplit(':',1) for x in s.split('|'))}
def capstr(d):return '|'.join(f'{k}:{v}' for k,v in sorted(d.items()))
def truth(s):return s.astype(str).str.lower().isin(['true','1'])
def integer_sum(s):return sum(int(v) for v in s)


def mdtable(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+
                     ['| '+' | '.join(map(str,r))+' |' for r in rows])


def main():
    HERE.mkdir(exist_ok=True)
    oldpath=STUDY/'integration/DOMAIN_SUBSET_COVERAGE_26x2.csv'
    old=read(oldpath,dtype=str,keep_default_na=False)
    assert old.shape==(52,43) and not old.duplicated(['condition','domain_subset']).any()
    rename={c:'phase1_'+c for c in old if c.startswith('current_')}
    domains=old.rename(columns=rename).copy()
    domains['phase1_source_file']=str(oldpath.relative_to(REPO))
    domains['phase1_source_sha256']=SOURCES[str(oldpath.relative_to(REPO))]
    domains['phase1_source_row']=range(1,53)
    fields=[]
    for c in old:
        fields.append(dict(original_field=c,integrated_field=rename.get(c,c),
            phase='phase1_current' if c.startswith('current_') else ('historical_legacy_reference' if c.startswith('legacy_') else 'identity_or_inherited_interpretation'),
            values_preserved_verbatim=True,
            note='current in the old file denotes phase1 only; never overwritten with continuation counts' if c.startswith('current_') else 'original field identity retained'))
    publish(pd.DataFrame(fields),'DOMAIN_SUBSET_FIELD_STAGE_MAP.csv',('original_field',))

    membership=read(NEXT/'candidate_n20/CONFIG_MEMBERSHIP.csv.gz')
    config=read(NEXT/'candidate_n20/POOL_METHOD_COVERAGE.csv')
    cells=read(NEXT/'candidate_n20/CONFIG_CELLS.csv.gz')
    assert len(membership)==144666 and membership.team_key.nunique()==144642 and len(cells)==48321
    labels=read(STUDY/'composition/FROZEN_LABELS.csv',keep_default_na=False)
    ksummary=read(NEXT/'coverage/FROZEN_METHOD_K_SUMMARY.csv')
    complete=read_json(NEXT/'coverage/N20_COMPLETION.json')
    assert complete['missing']==0 and complete['computed_unique']==144642
    universe=read(NEXT/'coverage/UNIVERSE_FINAL_COVERAGE_AFTER_N20.csv.gz',dtype=str,keep_default_na=False)
    universe=universe[(universe.n=='20') & universe.layer.isin(['ordinary_manual','ordinary_semi'])].copy()
    poolscale=[];event_frames=[];primary=[];design_receipts={};result_receipts={}
    eventcols=['condition','method_id','tier','pool_id','building','image_id','event_id','physical_triple_id',
               'oriented_triple_id','team_A','team_B','team_C','m_AB','m_AC','m_BC','within_parent_fine_change',
               'previously_registered_same_oriented_triple']
    for condition in ['manual','semi']:
        d=read_json(ABC/f'design_{condition}/DESIGN_RECEIPT.json');design_receipts[condition]=d
        p=read(ABC/f'design_{condition}/MATCHED_ABC_POOL_SCALE.csv');poolscale.append(p)
        ev=read(ABC/f'design_{condition}/MATCHED_ABC_EVENTS.csv.gz',usecols=eventcols)
        assert len(ev)==d['events'] and ev.event_id.is_unique
        assert (ev.m_AB==ev.m_AC).all() and ev.m_AB.ge(4).all()
        assert not truth(ev.previously_registered_same_oriented_triple).any()
        event_frames.append(ev)
        if condition=='manual':
            r=read_json(ABC/'checkpointed_manual/summary/SUMMARY_RECEIPT.json')
            assert r['events_computed']==d['events'] and r['complete_event_id_equality']
            q=read(ABC/'checkpointed_manual/summary/N20_MATCHED_PRIMARY_SUMMARY.csv')
        else:
            r=read_json(ABC/'results_semi/RESULT_RECEIPT.json')
            assert r['events_computed']==d['events'] and r['missing_endpoint_keys']==0
            q=read(ABC/'results_semi/N20_ABC_PRIMARY_SUMMARY.csv')
        result_receipts[condition]=r
        q=q[q.scope.eq('all_composition_changes')]
        for _,g in q.groupby(['condition','method_id','tier']):
            for c in ['events','all_scored_events','all_complete_events']:
                assert g[c].nunique()==1
        primary.append(q.drop_duplicates(['condition','method_id','tier']))
    poolscale=pd.concat(poolscale,ignore_index=True)
    events=pd.concat(event_frames,ignore_index=True)
    primary=pd.concat(primary,ignore_index=True)
    assert len(events)==269814+1517
    selected=set(map(tuple,config[['method_id','condition']].drop_duplicates().to_numpy()))
    config_lookup=config.set_index(['method_id','condition','pool_id'])
    pools=[]
    for r in poolscale.itertuples():
        c=config_lookup.loc[(r.method_id,r.condition,r.pool_id)]
        capacities=caps(c.class_capacities)
        lab=labels[labels.method_id.eq(r.method_id) & labels.condition.eq(r.condition) & labels.heldout_building.eq(r.building)]
        if r.tier=='coarse':
            fine=lab[lab.tier.eq('fine')]
            assert fine.groupby('class_id').parent_class.nunique().max()==1
            parent=dict(zip(fine.class_id,fine.parent_class));projected={}
            for cl,n in capacities.items():projected[parent[cl]]=projected.get(parent[cl],0)+n
            capacities=projected
        assert sum(capacities.values())==r.labelled_pool_n
        pools.append(dict(condition=r.condition,method_id=r.method_id,tier=r.tier,input_panel_tier=r.input_panel_tier,
            pool_id=r.pool_id,image_id=r.image_id,image=r.image,building=r.building,n=20,
            formal_pool_n=r.formal_pool_n,labelled_pool_n=r.labelled_pool_n,
            fitted_K=lab.loc[lab.tier.eq(r.tier),'class_id'].nunique(),available_K=len(capacities),
            class_capacities=capstr(capacities),materialized_tier_vectors=r.registered_vectors,
            direct_registered_vectors=r.registered_vectors if r.tier==r.input_panel_tier else 0,
            input_panel_member_references=r.registered_member_sets,
            distinct_input_panel_teams=r.registered_member_sets,
            direct_registration_member_references=r.registered_member_sets if r.tier==r.input_panel_tier else 0,
            matched_event_references=r.unique_matched_triples,
            within_parent_fine_matched_event_references=r.within_parent_fine_triples,
            necessary_m_ge4_member_capacity=r.labelled_pool_n-20>=4,
            matched_events_computed=True,registration_count_basis='same fine/A2 input panel; coarse projection reuses members'))
    pooltable=pd.DataFrame(pools)
    publish(pooltable,'N20_METHOD_POOL_TIER_COVERAGE.csv',('condition','method_id','tier','pool_id'))

    support={};target_support={};prediction={}
    for condition in ['manual','semi']:
        support[condition]=read(ANALYSIS/condition/'N20_COMMON_SUPPORT.csv')
        target_support[condition]=read(ANALYSIS/condition/'N20_TARGET_COMPOSITION_SUPPORT.csv')
        prediction[condition]=read(ANALYSIS/condition/'N20_PREDICTION_SUMMARY.csv')
    legacy=support['manual'][support['manual'].support_scope.eq('legacy_anchor')].copy()
    legacy_rows=[]
    for method,g in legacy.groupby('family'):
        for status,h in g.groupby('status'):
            legacy_rows.append(dict(method_id=method,condition='manual',tier='coarse',n=20,
                design_anchor='M_structure',support_scope='legacy_anchor',status=status,
                pools=h.pool_id.nunique(),buildings=h.heldout_building.nunique(),
                anchor_registered_member_references=int(h.registered_draws.sum()),
                common_QT_member_references=int(h.supported_draws.sum()),
                joint_supported_pool_n_min=h.joint_supported_pool_n.min(),
                joint_supported_pool_n_max=h.joint_supported_pool_n.max(),
                interpretation='no endpoint or label refit; continuous QT comparison only; zero support is not a failed effect'))
    publish(pd.DataFrame(legacy_rows),'N20_LEGACY_QT_COMPARISON_DOMAIN.csv',('method_id','status'))

    methods=[]
    for kr in ksummary.itertuples():
        method,tier,condition=kr.method_id,kr.tier,kr.condition
        key=(method,condition)
        p=pooltable[pooltable.method_id.eq(method)&pooltable.tier.eq(tier)&pooltable.condition.eq(condition)]
        u=universe[universe.method_id.eq(method)&universe.tier.eq(tier)&universe.condition.eq(condition)]
        mem=membership[membership.method_id.eq(method)&membership.condition.eq(condition)]
        e=events[events.method_id.eq(method)&events.tier.eq(tier)&events.condition.eq(condition)]
        ps=primary[primary.method_id.eq(method)&primary.tier.eq(tier)&primary.condition.eq(condition)]
        role=('dedicated_registered_fine_or_single_grid' if len(p) and tier==p.input_panel_tier.iloc[0]
              else 'parent_projection_of_same_registered_grid' if len(p)
              else 'legacy_continuous_QT_comparison_only' if method in ['Rnew2','F01']
              else 'incidental_cache_projection_no_new_deep_study')
        caps_all=[caps(s) for s in u.class_capacities] if len(u) else []
        available_K=[len(z) for z in caps_all]
        class_sizes=[n for z in caps_all for n in z.values()]
        row=dict(method_id=method,condition=condition,tier=tier,n=20,phase='phase2_n20_continuation',
            phase2_role=role,domain_subset_for_new_deep_study=next((d for (c,d),m in DOMAIN_METHODS.items() if c==condition and m==method),''),
            fitted_K_min=kr.fitted_K_min,fitted_K_max=kr.fitted_K_max,
            available_K_min=min(available_K) if available_K else None,available_K_max=max(available_K) if available_K else None,
            formal_pool_n_min=int(u.formal_pool_n.astype(int).min()) if len(u) else None,
            formal_pool_n_max=int(u.formal_pool_n.astype(int).max()) if len(u) else None,
            labelled_pool_n_min=int(u.labelled_pool_n.astype(int).min()) if len(u) else None,
            labelled_pool_n_max=int(u.labelled_pool_n.astype(int).max()) if len(u) else None,
            positive_class_capacity_min=min(class_sizes) if class_sizes else None,
            positive_class_capacity_max=max(class_sizes) if class_sizes else None,
            phase2_input_panel_tier=p.input_panel_tier.iloc[0] if len(p) else '',
            phase2_direct_registration_configuration_cells=int(p.direct_registered_vectors.sum()) if len(p) else 0,
            phase2_materialized_tier_configuration_cells=int(p.materialized_tier_vectors.sum()) if len(p) else 0,
            phase2_direct_registration_member_references=int(p.direct_registration_member_references.sum()) if len(p) else 0,
            phase2_input_panel_member_references=len(mem) if key in selected else 0,
            phase2_input_panel_distinct_teams=mem.team_key.nunique() if key in selected else 0,
            phase2_input_panel_new_native_teams=int((~truth(mem.cached_previous_request)).sum()) if key in selected else 0,
            phase2_input_panel_reused_phase1_teams=int(truth(mem.cached_previous_request).sum()) if key in selected else 0,
            phase2_configuration_pools=p.pool_id.nunique(),phase2_configuration_images=p.image_id.nunique(),phase2_configuration_buildings=p.building.nunique(),
            phase2_all_materialized_vectors_computed=bool(len(p)),
            phase2_matched_event_references=len(e),phase2_matched_events_computed=len(e),
            phase2_matched_unique_physical_triples=e.physical_triple_id.nunique(),
            phase2_matched_unique_oriented_triples=e.oriented_triple_id.nunique(),
            phase2_matched_unique_endpoint_teams=len(set(e.team_A)|set(e.team_B)|set(e.team_C)),
            phase2_matched_all_complete_evaluable_events=int(ps.all_complete_events.iloc[0]) if len(ps) else 0,
            phase2_matched_any_incomplete_events=len(e)-int(ps.all_complete_events.iloc[0]) if len(ps) else 0,
            phase2_matched_pools=e.pool_id.nunique(),phase2_matched_buildings=e.building.nunique(),
            phase2_m_AB_min=int(e.m_AB.min()) if len(e) else None,phase2_m_AB_max=int(e.m_AB.max()) if len(e) else None,
            phase2_m_BC_min=int(e.m_BC.min()) if len(e) else None,phase2_m_BC_max=int(e.m_BC.max()) if len(e) else None,
            phase2_within_parent_fine_matched_event_references=int(truth(e.within_parent_fine_change).sum()),
            phase2_within_parent_fine_matched_pools=e.loc[truth(e.within_parent_fine_change),'pool_id'].nunique(),
            phase2_pools_with_necessary_m_ge4_capacity=int(p.necessary_m_ge4_member_capacity.sum()) if len(p) else 0,
            combined_phase1_phase2_n20_cached_configuration_cells=integer_sum(u.computed_class_vectors),
            combined_n20_feasible_configuration_cells=integer_sum(u.all_feasible_class_vectors),
            combined_n20_remaining_configuration_cells=integer_sum(u.remaining_uncomputed_class_vectors),
            combined_n20_cached_distinct_teams_within_method_tier=integer_sum(u.computed_actual_member_sets),
            combined_cache_scope='all existing actual sets eligible under method/tier in ordinary n20 pools; not direct phase2 design counts',
            counts_additive_across_tiers=False,
            class_count_limit='none; K follows actual frozen building-excluded labels; ABC denotes comparison team arms')
        if len(e):
            assert len(ps)==1 and len(e)==int(ps.events.iloc[0])
        if len(p):
            assert len(e)==int(p.matched_event_references.sum())
            if not p.necessary_m_ge4_member_capacity.any():status='m_ge4_has_no_member_capacity'
            elif not len(e):status='no_matched_triples_in_registered_panel'
            else:status='matched_triples_exhausted_within_registered_panel'
        else:status='not_designed_for_new_matched_events'
        row['phase2_matched_status']=status
        ts=target_support[condition]
        ts=ts[ts.method_id.eq(method)&ts.support_scope.eq('own_class_supported')&ts.outcome_support.eq('all_endpoints')]
        row['phase2_within_parent_fine_grid_opportunity_pools']=int(truth(ts.has_within_coarse_fine_composition_opportunity).sum()) if len(ts) else 0
        row['phase2_grid_opportunity_interpretation']='observed multiple fine compositions at fixed coarse composition; no background or m matching' if len(ts) else 'not assessed in an own-class n20 grid in this phase'
        sp=support[condition]
        if method in ['Rnew2','F01']:
            sg=sp[sp.support_scope.eq('legacy_anchor')&sp.family.eq(method)]
            row.update(continuous_comparison_scope='legacy_anchor_on_M_structure_registered_grid',
                continuous_comparison_supported_pools=int((sg.status=='supported').sum()),
                continuous_comparison_supported_team_references=int(sg.loc[sg.status.eq('supported'),'supported_draws'].sum()),
                continuous_comparison_missing_outer_map_pools=int((sg.status=='missing_outer_map').sum()),
                continuous_comparison_capacity_lt20_pools=int((sg.status=='joint_capacity_lt20').sum()),
                continuous_comparison_sampled_support_insufficient_pools=int((sg.status=='sampled_support_insufficient').sum()),
                continuous_comparison_joint_pool_n_min=sg.joint_supported_pool_n.min(),
                continuous_comparison_joint_pool_n_max=sg.joint_supported_pool_n.max(),
                continuous_comparison_status='evaluated_on_available_legal_target_domain' if (sg.status=='supported').any() else 'no_supported_n20_comparison; not an effect failure')
        else:
            sg=sp[sp.support_scope.eq('own_design')&sp.family.eq(method)]
            row.update(continuous_comparison_scope='own_design; common_anchor domains remain separate in n20_analysis' if key in selected else 'not newly compared',
                continuous_comparison_supported_pools=int((sg.status=='supported').sum()),
                continuous_comparison_supported_team_references=int(sg.loc[sg.status.eq('supported'),'supported_draws'].sum()),
                continuous_comparison_missing_outer_map_pools=int((sg.status=='missing_outer_map').sum()),
                continuous_comparison_capacity_lt20_pools=int((sg.status=='joint_capacity_lt20').sum()),
                continuous_comparison_sampled_support_insufficient_pools=int((sg.status=='sampled_support_insufficient').sum()),
                continuous_comparison_joint_pool_n_min=sg.joint_supported_pool_n.min(),
                continuous_comparison_joint_pool_n_max=sg.joint_supported_pool_n.max(),
                continuous_comparison_status='see n20_analysis method-specific common-support ledgers' if key in selected else 'not conducted in phase2')
        summ=prediction[condition]
        ss=summ[summ.method_id.eq(method)&summ.support_scope.eq('legacy_anchor')&summ.target_panel.eq('all')&summ.weighting.eq('configuration_uniform')&summ.model.eq('QT_source')]
        for metric,label in [('B8L2','B8'),('log_source_time_total','time')]:
            q=ss[ss.outcome.eq(metric)]
            row['legacy_QT_'+label+'_evaluated_buildings']=int(q.buildings.iloc[0]) if len(q) else 0
            row['legacy_QT_'+label+'_evaluated_images']=int(q.images.iloc[0]) if len(q) else 0
            row['legacy_QT_'+label+'_evaluated_team_references']=int(q.draws.iloc[0]) if len(q) else 0
        methods.append(row)
    methodtable=pd.DataFrame(methods)
    publish(methodtable,'N20_METHOD_CONDITION_TIER_COVERAGE.csv',('condition','method_id','tier'))

    zero_fields=['phase2_n20_deep_method_count','phase2_n20_fine_configuration_cells','phase2_n20_parent_projected_configuration_cells',
        'phase2_n20_registered_member_references','phase2_n20_distinct_registered_teams','phase2_n20_new_native_teams_in_panel','phase2_n20_reused_phase1_teams_in_panel',
        'phase2_n20_configuration_pools','phase2_n20_configuration_images','phase2_n20_configuration_buildings',
        'phase2_n20_matched_method_tier_event_references','phase2_n20_coarse_matched_event_references','phase2_n20_fine_matched_event_references',
        'phase2_n20_within_parent_fine_matched_event_references','phase2_n20_unique_physical_triples_across_tiers',
        'phase2_n20_unique_matched_endpoint_teams','phase2_n20_matched_all_complete_evaluable_event_references',
        'phase2_n20_m_ge4_member_capacity_pools','phase2_new_personnel_label_sets_fitted']
    for c in zero_fields:domains[c]=0
    domains['phase2_n20_method_ids']=''
    domains['phase2_n20_deep_research_status']='未开展新深研'
    domains['phase2_n20_matched_status']='本轮未为此域组合设计匹配对照；0不表示效果失败'
    domains['phase2_label_identity']='本轮未新增人员标签；既有标签身份见phase1字段'
    domains['phase2_n20_count_unit_note']='配置、具体成员、方法×层级事件与物理三元组分别计数；不跨层相加为独立实验'
    for i,r in domains.iterrows():
        method=DOMAIN_METHODS.get((r.condition,r.domain_subset))
        if method is None:continue
        mm=methodtable[methodtable.method_id.eq(method)&methodtable.condition.eq(r.condition)]
        fine=mm[mm.tier.eq('fine')].iloc[0];coarse=mm[mm.tier.eq('coarse')].iloc[0]
        ev=events[events.method_id.eq(method)&events.condition.eq(r.condition)]
        updates=dict(phase2_n20_deep_method_count=1,phase2_n20_method_ids=method,
            phase2_n20_fine_configuration_cells=int(fine.phase2_direct_registration_configuration_cells),
            phase2_n20_parent_projected_configuration_cells=int(coarse.phase2_materialized_tier_configuration_cells),
            phase2_n20_registered_member_references=int(fine.phase2_direct_registration_member_references),
            phase2_n20_distinct_registered_teams=int(fine.phase2_input_panel_distinct_teams),
            phase2_n20_new_native_teams_in_panel=int(fine.phase2_input_panel_new_native_teams),
            phase2_n20_reused_phase1_teams_in_panel=int(fine.phase2_input_panel_reused_phase1_teams),
            phase2_n20_configuration_pools=int(fine.phase2_configuration_pools),
            phase2_n20_configuration_images=int(fine.phase2_configuration_images),
            phase2_n20_configuration_buildings=int(fine.phase2_configuration_buildings),
            phase2_n20_matched_method_tier_event_references=len(ev),
            phase2_n20_coarse_matched_event_references=int(coarse.phase2_matched_event_references),
            phase2_n20_fine_matched_event_references=int(fine.phase2_matched_event_references),
            phase2_n20_within_parent_fine_matched_event_references=int(fine.phase2_within_parent_fine_matched_event_references),
            phase2_n20_unique_physical_triples_across_tiers=ev.physical_triple_id.nunique(),
            phase2_n20_unique_matched_endpoint_teams=len(set(ev.team_A)|set(ev.team_B)|set(ev.team_C)),
            phase2_n20_matched_all_complete_evaluable_event_references=int(mm.phase2_matched_all_complete_evaluable_events.sum()),
            phase2_n20_m_ge4_member_capacity_pools=int(fine.phase2_pools_with_necessary_m_ge4_capacity),
            phase2_n20_deep_research_status='配置与匹配对照已完成' if len(ev) else '配置与连续对照已完成；n20的m>=4无容量机会',
            phase2_n20_matched_status='登记面板内全部合法m>=4匹配三元组已完成' if len(ev) else '合法人员池21–22人；n20最多换1–2人，m>=4无机会，非效果失败',
            phase2_label_identity='复用phase1目标建筑外冻结标签；没有把本轮连续模型另算新分类')
        for k,v in updates.items():domains.at[i,k]=v
    assert domains.loc[domains.phase2_n20_deep_method_count.eq(0),'phase2_n20_deep_research_status'].eq('未开展新深研').all()
    assert int(domains.phase2_n20_deep_method_count.sum())==2
    # Reversing the explicit field-stage map must recover every old cell exactly.
    restored=domains[[rename.get(c,c) for c in old]].rename(columns={v:k for k,v in rename.items()})
    assert restored.equals(old)
    manual=domains[(domains.condition=='manual')&(domains.domain_subset=='Q+T+D')].iloc[0]
    semi=domains[(domains.condition=='semi')&(domains.domain_subset=='Q+T+scope+Semi')].iloc[0]
    assert (manual.phase2_n20_fine_configuration_cells,manual.phase2_n20_matched_method_tier_event_references)==(15530,135504)
    assert (semi.phase2_n20_fine_configuration_cells,semi.phase2_n20_registered_member_references,semi.phase2_n20_matched_method_tier_event_references)==(135,395,0)
    publish(domains,'PHASE1_PHASE2_DOMAIN_SUBSET_COVERAGE_26x2.csv',('condition','domain_subset'))

    highlights=[]
    for r in methodtable[methodtable.phase2_input_panel_member_references.gt(0)].itertuples():
        kk=str(r.fitted_K_min) if r.fitted_K_min==r.fitted_K_max else f'{r.fitted_K_min}–{r.fitted_K_max}'
        highlights.append([r.condition,r.method_id,r.tier,kk,
            f'{r.labelled_pool_n_min}–{r.labelled_pool_n_max}',r.phase2_materialized_tier_configuration_cells,
            r.phase2_input_panel_distinct_teams,r.phase2_matched_event_references,r.phase2_within_parent_fine_matched_event_references])
    report='''# 人员分类研究：阶段身份与本轮 n=20 覆盖账

本文件只整合已完成结果，不重做分类、融合、评分或匹配事件计算。旧文件 `integration/DOMAIN_SUBSET_COVERAGE_26x2.csv` 的 **52 行、43 个字段值逐项保留**；其中旧 `current_*` 在新账中显式命名为 `phase1_current_*`，映射关系见 `DOMAIN_SUBSET_FIELD_STAGE_MAP.csv`。原文件本身没有修改，不能把其中的 current 理解为本次续研累计结果。

## 五域子集：只追加两条真实深入研究

26 个二至五域子集分别登记 Manual/Semi，仍是 52 行。只有下面两行增加本轮深入研究计数，另外 **50 行本轮新增值为 0，状态为“未开展新深研”**；它们的旧标签、筛查、真实组合和复核记录仍原样保留。0 表示本阶段未新增该项工作，不表示分类失败。

| 条件与域组合 | 本轮方法 | 直接登记细配置 | 同一网格的父类投影 | 登记团队引用/不同团队 | 匹配事件引用 | 父类不变的细换类 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Manual Q+T+D | MV_QTD_manual_new | 15,530 | 1,418 | 46,447 / 46,447 | 135,504＝131,357粗＋4,147细 | 1,319 |
| Semi Q+T+scope+Semi | MV_QTScopeSemi_semi_new | 135 | 59 | 395 / 395 | 0 | 0 |

Manual 本行只追加新来源 MV 方法，不把 phase1 同域的 `MV_QTD_manual` 一起算成本轮新增。Semi MV 的合法图片人员池只有 21–22 人，n=20 时最多换 1–2 人，所以本轮 m≥4 匹配没有容量机会；其配置与连续对照已经完成，不能把零事件记成负效果。

M/SP 是结构或尺度方法，A2 是跨图原答关系方法，均在独立方法表登记，**不冒充五域子集的新增覆盖**。Q/T 作为既有方法的连续对照也不是一次新的 Q+T 人员分型。旧 QTDS 的 S 是结构，旧 scope 字段与本轮 scope 回答倾向的机会、筛选口径继续保留原文件说明。

## 方法、条件和层级分别登记

'''+mdtable(['条件','方法','层级','拟合 K','合法人员池范围','本层配置','同一登记网格不同团队','本层匹配事件','父类内细换类事件'],highlights)+'''

细层或 A2 的单层是直接登记网格；对应粗层使用同一成员集合投影。粗层的“本层配置”是投影后的完整类别人数向量数，不是额外抽取一批团队。表中团队数、物理三元组和层级引用不能跨层直接相加。`direct_registration_*` 与 `input_panel_*` 字段分别保存这两种含义。方法表还保留其他冻结方法在现有缓存上的 n=20 附带覆盖，明确标成 `incidental_cache_projection_no_new_deep_study`，不据此增加新深研方法数。

实际类别数由冻结楼外标签决定，没有三类上限；本批有 3–4 细类方法，M 是 4 细类。K、团队人数 n=20、每格最多 3 个成员抽样是三个不同参数；ABC 是三个对照团队臂，不是限定三类人员。`N20_METHOD_POOL_TIER_COVERAGE.csv` 逐池给出正式人数、合法标签人数、各类实际容量和可用 K。

`phase2_within_parent_fine_grid_opportunity_pools` 只表示在同一粗构成下观察到多个细构成，不控制共同背景或换人数；`phase2_within_parent_fine_matched_event_references` 才是此次同背景、同实际 m 的父类内细换类事件。Semi SP 没有登记面板内的此类匹配事件，不等于证明全部实际成员空间没有机会。

## Rnew2 与 F01 的连续特征比较域

它们保留旧方法和原合法目标楼身份，本轮不建立新 n=20 专属网格，也不追加五域深研计数。使用 M 的已登记网格作对照锚，要求旧类别和楼外 QT 共同有效：

- **Rnew2**：63 池支持，1,647 条共同团队用于完整端点/时间对照；B8 有 63 图、12 楼、1,640 个可评价团队。另有 76 池没有合法外层映射，20 池共同容量不足 20，9 池已抽样共同支持不足，均保留分母。
- **F01**：76 池没有合法外层映射，92 池共同容量不足 20，未形成可评估 n=20 连续对照。这是容量和适用域限制，不是效果失败。

逐状态计数在 `N20_LEGACY_QT_COMPARISON_DOMAIN.csv`；方法表中的 `legacy_QT_B8_*` 和 `legacy_QT_time_*` 列清楚区分质量与时间支持。连续对照已完成不意味着已穷尽 Rnew2/F01 的所有成员构成。

## 阶段与计数约定

- phase1：原已保存分类、筛查、配置与匹配统计，保持原字段值和适用域。
- phase2 n20 配置：六个方法×条件的 48,321 个直接登记配置、144,666 条方法/团队引用、144,642 个不同实际集合；其中新增原生终点 126,268，复用 18,374。该批完成全部合法类别人数配置，成员只按冻结预算抽取。
- phase2 n20 匹配：在各自已登记团队面板内穷尽满足合同的 m≥4 三元组，Manual 269,814 条方法×层级事件、Semi 1,517 条。原生融合与评分直接复用，不把这些事件数当作新融合次数。
- 累计实际终点为 418,172，来自旧 291,904 与新增 126,268 去重合并。分类网格、方法×层级事件、物理三元组、不同实际团队及加入顺序是不同单位。
- 新标签拟合数为 0：本轮复用已冻结目标建筑外标签，新增的是配置覆盖、共同端点模型和匹配事件证据。既有探索与 v2 检查历史继续有效，不重新宣称全新盲测。

本整合包只包含覆盖小表、代码和说明；原图、全量原生几何、已交付的匹配宽表和重复输入不重复装入。`STAGE_COVERAGE_RECEIPT.json` 保存每个实际读取来源的 SHA256、事件完成回执和保留旧字段的断言；`build_stage_coverage.py` 从已存在结果重建，不调用融合或模型拟合。
'''
    (HERE/'STAGE_COVERAGE_LEDGER_ZH.md').write_text(report,encoding='utf-8')
    receipt=dict(status='frozen_complete',new_fusion_calls=0,new_score_calls=0,new_model_fits=0,
        phase1_rows_preserved=52,phase1_original_columns_preserved=43,
        old_current_fields_renamed=rename,old_values_verified_identical=True,
        phase2_domain_subset_condition_rows_with_new_deep_study=2,phase2_domain_rows_without_new_deep_study=50,
        phase2_selected_domain_method_mapping={c+'|'+d:m for (c,d),m in DOMAIN_METHODS.items()},
        phase2_method_condition_tier_rows=len(methodtable),phase2_primary_pool_tier_rows=len(pooltable),
        phase2_manual_matched_events=269814,phase2_semi_matched_events=1517,
        phase2_unique_physical_triples_manual=int(events[events.condition.eq('manual')].physical_triple_id.nunique()),
        phase2_unique_physical_triples_semi=int(events[events.condition.eq('semi')].physical_triple_id.nunique()),
        phase2_MV_manual_event_references=int(manual.phase2_n20_matched_method_tier_event_references),
        phase2_MV_manual_unique_physical_triples=int(manual.phase2_n20_unique_physical_triples_across_tiers),
        phase2_MV_semi_event_status=semi.phase2_n20_matched_status,
        class_count_limit=None,ABC_definition='comparison team arms, not personnel classes',
        design_receipts=design_receipts,result_receipts=result_receipts,source_files=SOURCES)
    publish_json(receipt,'STAGE_COVERAGE_RECEIPT.json')
    names=['PHASE1_PHASE2_DOMAIN_SUBSET_COVERAGE_26x2.csv','DOMAIN_SUBSET_FIELD_STAGE_MAP.csv',
           'N20_METHOD_CONDITION_TIER_COVERAGE.csv','N20_METHOD_POOL_TIER_COVERAGE.csv',
           'N20_LEGACY_QT_COMPARISON_DOMAIN.csv','STAGE_COVERAGE_LEDGER_ZH.md',
           'STAGE_COVERAGE_RECEIPT.json','build_stage_coverage.py']
    manifest=pd.DataFrame([dict(path=n,bytes=(HERE/n).stat().st_size,sha256=sha(HERE/n)) for n in names])
    publish(manifest,'STAGE_COVERAGE_PACKAGE_MANIFEST.csv',('path',));names.append('STAGE_COVERAGE_PACKAGE_MANIFEST.csv')
    z=HERE/'HOHONET_阶段身份_52行域组合与n20方法覆盖_20261021.zip';tmp=z.with_suffix('.zip.tmp')
    with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=5) as archive:
        for name in names:archive.write(HERE/name,name)
    with zipfile.ZipFile(tmp) as archive:
        assert archive.testzip() is None
        restored=archive.read('PHASE1_PHASE2_DOMAIN_SUBSET_COVERAGE_26x2.csv')
        assert len(list(csv.DictReader(io.StringIO(restored.decode('utf-8-sig')))))==52
    tmp.replace(z)
    info=dict(path=str(z.resolve()),bytes=z.stat().st_size,sha256=sha(z),files=len(names))
    publish_json(info,'STAGE_COVERAGE_PACKAGE.json')
    print(json.dumps(info,ensure_ascii=False),flush=True)
    print(methodtable[['method_id','condition','tier','phase2_role','phase2_materialized_tier_configuration_cells',
          'phase2_input_panel_distinct_teams','phase2_matched_event_references','phase2_within_parent_fine_matched_event_references']].to_string(index=False),flush=True)


if __name__=='__main__':main()
