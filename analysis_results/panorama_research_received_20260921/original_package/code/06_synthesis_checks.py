"""Onset-transfer coverage, an actual local-stage case, and auditable evidence selection."""
import common as c
import json,collections,itertools,importlib.util,math
import numpy as np,pandas as pd

def main():
    args=c.main_parser().parse_args();c.configure(args.source_root)
    _,records,views,registry,_=c.load()
    curves=json.loads((c.ROOT/'results/replay_curves.json').read_text())
    cc={(x['image_id'],x['method'],x['tail']):x for x in curves if x['epsilon']==.1 and x['profile']=='uncapped'}
    supported=[x for x in registry['candidates'] if x['physical_same_supported']]
    from tools.thesis_main.analysis.audit_collection_plan_20260921 import blocks
    family=blocks(supported);adj=collections.defaultdict(set);strict=collections.defaultdict(set)
    for g in supported:
        ids=[i for i in g['image_ids'] if i in views]
        for a,b in itertools.combinations(ids,2):
            adj[a].add(b);adj[b].add(a)
            if g['comparable_for_prediction']:strict[a].add(b);strict[b].add(a)
    def aggregate_curve(ids,method,tail):
        arr=[cc[i,method,tail] for i in ids];h=min(len(x['ks']) for x in arr)
        if not h:return dict(possible=None,certain=None,grid=0)
        lo=np.mean([x['L'][:h] for x in arr],axis=0);hi=np.mean([x['U'][:h] for x in arr],axis=0)
        first=lambda p:next((j+2 for j,v in enumerate(p) if v>=.8-1e-12),None)
        return dict(possible=first(hi),certain=first(lo),grid=h+1)
    out=[]
    for kind in ['complete','representative']:
        for tail in [2,3,5]:
            for iid,v in views.items():
                if v['N']<8:continue
                truth=cc[iid,kind,tail]
                for group,adjacency in [('same_room_broad',adj),('same_room_comparable',strict)]:
                    ids=sorted(i for i in adjacency[iid] if views[i]['N']>=8)
                    if not ids:continue
                    est=aggregate_curve(ids,kind,tail);identified=est['certain'] is not None and est['possible']==est['certain']
                    test_identified=truth['status']=='identified'
                    # Do not silently drop censored or unsupported targets.
                    state='both_identified' if identified and test_identified else 'source_only_identified' if identified else 'target_only_identified' if test_identified else 'neither_identified'
                    out.append(dict(image_id=iid,code=v['code'],building=v['building'],family=family.get(iid,iid),N=v['N'],method=kind,tail=tail,scope=group,
                        source_ids=';'.join(ids),source_codes=';'.join(views[i]['code'] for i in ids),source_N=';'.join(str(views[i]['N']) for i in ids),
                        source_grid_end=est['grid'],prediction_possible=est['possible'],prediction_certain=est['certain'],target_status=truth['status'],
                        target_possible=truth['possible_onset'],target_certain=truth['conservative_onset'],evaluation_status=state,
                        absolute_error=abs(est['certain']-truth['conservative_onset']) if state=='both_identified' else None))
    df=pd.DataFrame(out);c.save('same_room_onset_transfer.csv',df)
    summary=[]
    for key,g in df.groupby(['method','tail','scope']):
        valid=g[g.evaluation_status=='both_identified']
        summary.append(dict(method=key[0],tail=key[1],scope=key[2],all_eligible_targets=len(g),all_buildings=g.building.nunique(),
            statuses=g.evaluation_status.value_counts().to_dict(),scorable_targets=len(valid),scorable_buildings=valid.building.nunique(),
            conditional_MAE=valid.groupby(['building','family']).absolute_error.mean().groupby('building').mean().mean() if len(valid) else None,
            warning='Conditional on source and target identified; NOT an overall predictive success rate. Native observation horizons differ.'))
    c.save('same_room_onset_transfer_summary.json',summary)
    # Case study identified from the local-vs-joint diagnostic; not a prevalence estimate.
    spec=importlib.util.spec_from_file_location('replay',(c.ROOT/'code/02_replay.py'));mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    v=next(x for x in views.values() if x['code']=='uNb9QFRL6hY-47');ix=[j for j,r in enumerate(v['rows']) if r['effective_point_count']==14]
    prs=np.array([records[v['ids'][j]]['p'][records[v['ids'][j]]['links']] for j in ix])
    dx=abs((prs[:,None,:,:,0]-prs[None,:,:,:,0]+512)%1024-512);dy=abs(prs[:,None,:,:,1]-prs[None,:,:,:,1]);locald=np.hypot(dx,dy).max(3)
    orders=json.loads((c.ROOT/'results/replay_orders.json').read_text())['orders']
    local_results=[];local_counts=[]
    for m in range(-1,7):
        job=dict(image_id=v['image_id'],code=v['code'],building=v['building'],N=len(ix),ids=[v['ids'][j] for j in ix],workers=[v['workers'][j] for j in ix],d=locald.max(2) if m==-1 else locald[:,:,m])
        res=mod.run((job,orders))[0]
        for z in res:
            if z['epsilon']==.1 and z['profile']=='uncapped':local_results.append(dict(z,local_pair='joint' if m==-1 else str(m+1)))
        for k in range(1,len(ix)):
            local_counts.append(dict(local_pair='joint' if m==-1 else str(m+1),k=k,U=c.next_uncovered(job['d'],k),N=len(ix)))
    c.save('uNb47_local_stage_case.json',local_results);c.save('uNb47_local_coverage_curve.csv',pd.DataFrame(local_counts))
    # Response-weighted and image-equal descriptive variance decomposition (not causal variance components).
    wr=pd.read_csv(c.ROOT/'results/response_metrics.csv');wr=wr[wr.N>=4]
    vals=[]
    for y in ['pair_disagreement','count_disagreement']:
        ag=wr.groupby('image_id')[y].agg(['mean',lambda x:x.var(ddof=0)]);ag.columns=['mean','var']
        between=ag['mean'].var(ddof=0);within=ag['var'].mean()
        vals.append(dict(outcome=y,images=len(ag),responses=len(wr),between_image_variance=between,within_image_variance=within,
            image_fraction=between/(between+within),warning='Equal image weighting; describes observed assignment, does not identify true item/person causal variance.'))
    c.save('image_person_variance_description.json',vals)
    # Evidence queues preserve closed decisions and exact raw point identities.
    pp=pd.read_csv(c.ROOT/'results/pair_diagnostics.csv.gz');queue=[]
    def add(r,issue,question,priority='conditional_manual_review'):
        z=r.to_dict();z.update(issue=issue,question=question,priority=priority,automatic_repair=False);queue.append(z)
    # Original human-approved uNb21 only used as a mechanism example, not asked again.
    z=pp[(pp.a_id=='8178591994d42ce3')&(pp.b_id=='a4e0cac5adec2e1e')]
    if len(z):add(z.iloc[0],'已确认跨作答对应','已落实用户[1,2,4,3,5,6]，不再询问；作为默认度量未接入的已知对照。','closed_reference')
    # Newly highlighted diagnostics exclude known uNb21 and uNb40 decisions.
    candidates=pp[(pp.diagnostic_case=='free_only_rescue')&(~pp.code.isin(['uNb9QFRL6hY-21','uNb9QFRL6hY-40']))]
    for _,r in candidates.sort_values('fixed_max',ascending=False).drop_duplicates('code').head(2).iterrows():
        add(r,'自由对应可消除超阈值','给出的候选映射是否保持同一物理墙角、上下角色及墙邻接？只需确认或否定此对，不能推广到整图。')
    z=pp[(pp.code=='uNb9QFRL6hY-47')&pp.same_count&(pp.a_pairs==7)&(pp.n_corner_fail==1)]
    if len(z):add(z.sort_values('fixed_max',ascending=False).iloc[0],'局部单角对波动','在列出的原点号附近，二者是否选择同一物理角？差异属于位置偏移、局部结构遗漏，还是不同范围？其余角不请求重审。')
    z=pp[(~pp.same_count)&(pp.partial_matching_fraction>=.8)&(~pp.code.isin(['uNb9QFRL6hY-40','uNb9QFRL6hY-59','e9zR4mvMWw7-26']))]
    for _,r in z.sort_values('partial_matching_fraction',ascending=False).drop_duplicates('code').head(2).iterrows():
        add(r,'不同点数但局部高度重合','未匹配角对表示漏标、真实额外墙段、范围选择，还是冗余细分？保留少数表达，不直接删除。')
    c.save('manual_semantic_case_queue.csv',pd.DataFrame(queue))
    snippets=[];sp=c.read('analysis_results/spatial_dimensions_review_20260913_v2/空间描述与历轮人工记录.json')
    ids={r['image_id'] for r in queue}
    ids.update(x['image_id'] for x in views.values() if x['code'] in ['q9vSo1VnCiC-02','q9vSo1VnCiC-13','uNb9QFRL6hY-47'])
    for im in sp['images']:
        if im['image_id'] in ids:snippets.append({k:im.get(k) for k in ['image_id','building','number','main_visual_space','expected_annotation_extent','ambiguity_and_information','note','current_coarse_review','spatial_prior_user','specific_user_issues']})
    c.save('case_spatial_source_excerpts.json',snippets)
    c.save('q9_preexisting_range_review.json',[g for g in registry['groups'] if g['review_code']=='G145'])
    print(json.dumps(c.clean(summary),ensure_ascii=False,indent=2));print('LOCAL',[(r['method'],r['local_pair'],r['status'],r['conservative_onset']) for r in local_results if r['tail']==3]);print('VAR',vals)

if __name__=='__main__':main()
