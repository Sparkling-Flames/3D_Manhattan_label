"""冻结墙角对应、存在票和顺序，只比较定位来源；不读取GT。"""
import copy
import json
import numpy as np

from .paired_split_research.study import angular
from .point_route_panel_20261005 import paired_identity
from .research_artifact_io import ROOT,write_json,write_csv
from .research_round_20260929 import reconstruct

SOURCE=ROOT/'analysis_results/ring_correspondence_20261007'
OUT=SOURCE/'location'


def median_pair(members):
    p=np.array([m['points'] for m in members])
    d=np.maximum(angular(p[:,0]-.5,p[:,0]-.5),angular(p[:,1]-.5,p[:,1]-.5))
    anchor=int(np.argmin(d.sum(axis=1)))
    dx=(p[:,0,0]-p[anchor,0,0]+512)%1024-512
    if np.ptp(dx)>=512-1e-9 or np.any(abs(abs(dx)-512)<1e-9):return None
    x=float((p[anchor,0,0]+np.median(dx))%1024)
    return [[x,float(np.median(p[:,0,1]))],[x,float(np.median(p[:,1,1]))]]


def largest_compatible_sets(distance,threshold):
    """Exact maximum cliques; no transitive merging or greedy partition."""
    neighbors=[set(np.flatnonzero(row<=threshold+1e-9))-{i} for i,row in enumerate(distance)]
    best=0;solutions=[]
    # ponytail: exponential worst case, limited to existing <=24-person local identities;
    # a larger future pool needs a bounded maximum-clique solver, not silent truncation.
    def visit(chosen,possible,excluded):
        nonlocal best,solutions
        if len(chosen)+len(possible)<best:return
        if not possible and not excluded:
            if len(chosen)>best:best=len(chosen);solutions=[]
            if len(chosen)==best:solutions.append(tuple(sorted(chosen)))
            return
        pivot=max(sorted(possible|excluded),key=lambda i:len(possible&neighbors[i]))
        for v in sorted(possible-neighbors[pivot]):
            visit(chosen|{v},possible&neighbors[v],excluded&neighbors[v])
            possible.remove(v);excluded.add(v)
    visit(set(),set(range(len(distance))),set())
    return sorted(solutions)


def position_groups(members,distance,threshold):
    groups=[]
    for label,indices in enumerate(largest_compatible_sets(distance,threshold)):
        subset=[members[k] for k in indices]
        groups.append(dict(feature_id=str(label),support=len(subset),members=subset,center=median_pair(subset)))
    return groups,groups[0] if len(groups)==1 else None


def compare_locations(group,n,threshold):
    members=group['members'];s=len(members)
    if len({m['worker'] for m in members})!=s:raise ValueError('duplicate_person_in_identity')
    p=np.array([m['points'] for m in members])
    top=angular(p[:,0]-.5,p[:,0]-.5);bottom=angular(p[:,1]-.5,p[:,1]-.5)
    groups={};winners={}
    for side,d in [('joint',np.maximum(top,bottom)),('top',top),('bottom',bottom)]:
        groups[side],winners[side]=position_groups(members,d,threshold)
    def estimate(t,b,center,reason=None):
        tk={(m['id'],m['pair_index']) for m in t};bk={(m['id'],m['pair_index']) for m in b}
        return dict(center=center,reason=reason,top_support=len(t),bottom_support=len(b),joint_support=len(tk&bk),
            top_full_pool_majority=2*len(t)>=n,bottom_full_pool_majority=2*len(b)>=n,
            top_members=sorted(tk),bottom_members=sorted(bk),joint_members=sorted(tk&bk))
    estimates={'all_median':estimate(members,members,median_pair(members))}
    j=winners['joint'];t=winners['top'];b=winners['bottom']
    estimates['joint_mode']=estimate(j['members'],j['members'],j['center']) if j else estimate([],[],None,'tied_largest_joint_position_groups')
    if t and b:
        bk={(m['id'],m['pair_index']) for m in b['members']}
        joint=[m for m in t['members'] if (m['id'],m['pair_index']) in bk]
        paired,reason=paired_identity(t,b,joint,0)
        estimates['split_mode']=estimate(t['members'],b['members'],paired['center'] if paired else None,reason)
    else:estimates['split_mode']=estimate(t['members'] if t else [],b['members'] if b else [],None,'tied_largest_endpoint_position_groups')
    if j and 2*j['support']>s:
        choice='joint_mode';why='joint_position_group_strict_majority_within_identity'
    elif t and b and 2*t['support']>s and 2*b['support']>s:
        choice='split_mode';why='both_marginal_position_groups_strict_majorities_within_identity'
    else:choice='all_median';why='no_unique_conditional_majority_mode_use_declared_all_observation_compromise'
    estimates['adaptive']=dict(copy.deepcopy(estimates[choice]),choice=choice,choice_reason=why)
    return dict(feature_id=group['feature_id'],existence_support=s,vote_denominator=n,threshold_deg=threshold,
        existence_selected=2*s>=n,position_candidates=groups,estimates=estimates)


def run():
    OUT.mkdir(exist_ok=True)
    write_json(OUT/'PLAN.json',dict(source=str(SOURCE.relative_to(ROOT)),input='frozen cyclic_identity partitions from current-bundle five-image study',
        variables='only source selection and resulting coordinates change; existence groups/votes and order frozen',
        routes=['all_median','joint_mode','split_mode','adaptive'],thresholds=[5,9,12],primary_threshold=9,
        mode='unique maximum-cardinality pairwise-compatible subset, found exactly; tied subsets unresolved',
        adaptive='joint conditional strict majority -> joint; else both marginal conditional strict majorities -> split; otherwise all-member median compromise',
        denominator='existence uses full N and original MV50; adaptive >s/2 only chooses estimator, never deletes an identity',
        caveat='working rules, no semantic type detector; thresholds not tuned by GT; order delegated to human check'))
    source=json.loads((SOURCE/'candidates.json').read_text(encoding='utf-8'))['states']
    states=[];rows=[];layouts=[]
    for state in source:
        if state['route']!='cyclic_identity':continue
        r=state['result'];selected=[g for g in r['identity_groups'] if g['selected']]
        for threshold in [5,9,12]:
            results=[compare_locations(g,r['n'],threshold) for g in selected]
            byid={g['feature_id']:g for g in results}
            states.extend(dict(image=state['image'],**g) for g in results)
            for g in results:
                original=next(v for v in selected if v['feature_id']==g['feature_id'])
                np.testing.assert_allclose(g['estimates']['all_median']['center'],original['center'])
                for route,e in g['estimates'].items():
                    rows.append(dict(image=state['image'],node=g['feature_id'],threshold=threshold,route=route,
                        N=r['n'],existence=g['existence_support'],top=e['top_support'],bottom=e['bottom_support'],joint=e['joint_support'],
                        available=e['center'] is not None,choice=e.get('choice',route),reason=e.get('choice_reason') or e.get('reason'),
                        x=e['center'][0][0] if e['center'] else '',top_y=e['center'][0][1] if e['center'] else '',bottom_y=e['center'][1][1] if e['center'] else ''))
            order=r['ring_diagnostics']['feature_ids']
            for route in ['all_median','joint_mode','split_mode','adaptive']:
                centers=[byid[f]['estimates'][route]['center'] for f in order]
                points=[p for c in centers for p in c] if centers and all(c is not None for c in centers) else None
                candidate=dict(points=points,geometry_status='not_evaluable',footprint=None)
                if points:
                    geo=reconstruct(candidate,coordinate_convention='continuous')
                    candidate.update(geometry_status=geo['status'],geometry_reason=geo['reason'],footprint=geo['floor'].tolist() if geo['floor'] is not None else None)
                layouts.append(dict(image=state['image'],threshold=threshold,route=route,order=order,
                    unresolved_nodes=[f for f in order if byid[f]['estimates'][route]['center'] is None],candidate=candidate))
    write_json(OUT/'location_states.json',states);write_csv(OUT/'location_summary.csv',rows);write_json(OUT/'layouts.json',layouts)
    write_json(OUT/'field_contract.json',dict(schema='fixed_identity_location_v2',input='previous frozen candidates/inputs, not new raw observations',
        support='number of source people used, not votes at an exact output coordinate; joint is intersection of source pair IDs',
        mode='exact maximum-cardinality pairwise-compatible subsets; may overlap, not a partition or semantic types; threshold uncalibrated',
        ties='pure mode routes retain unresolved nodes; adaptive falls back to declared all-source median, not point omission',
        adaptive='conditional strict-majority rule among same-identity s, not a change to full-N MV50 existence',
        connection='previous order copied without optimization; source nodes unchanged; endpoints can shift',
        unit='1024x512 continuous ERP; angular degrees; periodic midpoint x after independent endpoint estimation'))
    plots(states)
    grouping_diagnostic(source)
    print('identity states',len(states),'estimate rows',len(rows),'layouts',len(layouts))


def grouping_diagnostic(states):
    """固定已算两人匹配；检查贪心合并是否丢失相容群体。"""
    import itertools
    r=next(s['result'] for s in states if s['image']=='rPc6DW4iMge-06' and s['route']=='cyclic_identity')
    members={(m['id'],m['pair_index']):m for g in r['identity_groups'] for m in g['members']}
    adj={k:set() for k in members}
    for row in r['pairwise']:
        for a,b in row['matches']:
            u,v=(row['a'],a),(row['b'],b);adj[u].add(v);adj[v].add(u)
    def compatible(keys):
        return np.array([[0 if a==b or b in adj[a] else 2 for b in keys] for a in keys],float)
    # Unsupervised control: largest compatible group first, then remove its observations.
    # ponytail: greedy cover, not a globally optimal partition; all tied choices logged.
    remaining=set(members);groups=[];trace=[]
    while remaining:
        keys=sorted(remaining);options=largest_compatible_sets(compatible(keys),1)
        chosen=[keys[i] for i in options[0]]
        assert len({members[k]['worker'] for k in chosen})==len(chosen)
        groups.append(dict(feature_id=f'cover_{len(groups):03d}',support=len(chosen),
            selected=2*len(chosen)>=r['n'],members=[members[k] for k in chosen],
            center=median_pair([members[k] for k in chosen])))
        trace.append(dict(step=len(groups)-1,maximum_size=len(chosen),tied_maxima=len(options),
            alternatives=[[keys[i] for i in option] for option in options]))
        remaining.difference_update(chosen)
    assert sum(g['support'] for g in groups)==len(members)
    # Human relations are used only below this line to evaluate frozen groups.
    seeds={('R02452',2),('R01986',2),('R01557',4)}
    pairwise_present=all(b in adj[a] for a,b in itertools.combinations(seeds,2))
    keys=sorted(set.intersection(*(adj[s]|{s} for s in seeds)))
    solutions=largest_compatible_sets(compatible(keys),1)
    assert all(seeds<=set(keys[i] for i in sol) for sol in solutions)
    def hits(gs):
        return [dict(id=g['feature_id'],support=g['support'],
            tracked_members=sorted(seeds&{(m['id'],m['pair_index']) for m in g['members']}),
            old_wrong_member_in_group=('R01557',2) in {(m['id'],m['pair_index']) for m in g['members']})
            for g in gs if seeds&{(m['id'],m['pair_index']) for m in g['members']}]
    write_json(OUT/'rpc_grouping_diagnostic.json',dict(image='rPc6DW4iMge-06',processed_zero_based_seeds=sorted(seeds),
        all_three_pairwise_links_present=pairwise_present,current_groups=hits(r['identity_groups']),
        largest_seed_compatible_support=len(solutions[0]),maximum_subset_count=len(solutions),
        seeded_members=[[keys[i] for i in sol] for sol in solutions],
        automatic_cover=dict(groups=groups,trace=trace,known_relation_hits=hits(groups),
            policy='greedy maximum-clique cover, canonical first among ties; no GT or human seeds in construction'),
        denominator=r['n'],minimum=r['minimum_support'],
        scope='seeded feasibility and separate automatic grouping control; no source order optimization or claim of all-member semantic correctness'))


def plots(states):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from PIL import Image
    plt.rcParams['font.sans-serif']=['Microsoft YaHei','DejaVu Sans']
    inputs={im['image']:im for im in json.loads((SOURCE/'inputs.json').read_text(encoding='utf-8'))['images']}
    cases=[('uNb9QFRL6hY-41','node_002',610,790),('uNb9QFRL6hY-67','node_000',80,210),('yqstnuAEVhm-25','node_003',680,840)]
    for code,fid,lo,hi in cases:
        s=next(s for s in states if s['image']==code and s['feature_id']==fid and s['threshold_deg']==9)
        records={r['id']:r for r in inputs[code]['records']};photo=Image.open(inputs[code]['image_path'])
        fig,axes=plt.subplots(1,4,figsize=(14,7))
        for ax,(route,title) in zip(axes,zip(['all_median','joint_mode','split_mode','adaptive'],['全部观察中位数','联合最大相容源集','上下分别最大相容源集','自适应选择'])):
            e=s['estimates'][route];ax.imshow(photo,extent=(0,1024,512,0));ax.set_xlim(lo,hi);ax.set_ylim(480,60)
            for side,color in [('top','#00bbff'),('bottom','#f4a200')]:
                for rid,k in e[side+'_members']:
                    pair=np.array(records[rid]['points']).reshape(-1,2,2)[k]
                    xy=pair[0 if side=='top' else 1];ax.scatter(*xy,c=color,s=22,alpha=.75)
            if e['center']:
                p=np.array(e['center']);ax.plot(p[:,0],p[:,1],'-o',color='#f02050',lw=2.3,ms=5)
            if e['center'] is None:
                kinds=['joint'] if route=='joint_mode' else ['top','bottom']
                detail='\n'.join(f"{ {'joint':'联合','top':'上','bottom':'下'}[k]}最多{s['position_candidates'][k][0]['support']}人，{len(s['position_candidates'][k])}个并列源集" for k in kinds)
                subtitle='\n'+detail+'\n未任意选取唯一输出'
            else:subtitle=f"\n上{e['top_support']}／下{e['bottom_support']}／共同{e['joint_support']}"
            ax.set_title(title+subtitle,fontsize=10);ax.axis('off')
        fig.suptitle(code+f" 固定身份{s['existence_support']}/{s['vote_denominator']}；9°仅用于组内位置分组\n蓝点：上端来源；橙点：下端来源；红线：输出；不含GT，不判断连线顺序")
        fig.tight_layout();fig.savefig(OUT/(code+'_location.png'),dpi=145);plt.close(fig)


if __name__=='__main__':run()
