"""原环保序、允许缺点的对应开发对照；不读取GT，不认定物理身份。

默认工作参数：平均上下角距离；每个跳过节点13.5度代价，可显式传gap比较。
成组要求组内每一对都被两份作答的匹配支持，不用连通分量传递合并。
"""
from collections import defaultdict
import itertools
import math
import numpy as np
from scipy.optimize import linear_sum_assignment
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform

from .paired_split_research.study import angular
from .point_pattern_demo_20261003 import _pairs
from .union_branch_consensus_20260926 import _ring_key
from .research_round_20260929 import reconstruct
from .research_artifact_io import ROOT, write_json, write_csv

OUT=ROOT/'analysis_results/ring_correspondence_20261007'
GAP=13.5
CODES=['yqstnuAEVhm-25','uNb9QFRL6hY-26','uNb9QFRL6hY-41',
       'rPc6DW4iMge-06','uNb9QFRL6hY-67']


def linear_match(cost, gap):
    n,m=cost.shape
    dp=np.zeros((n+1,m+1));move=np.zeros((n+1,m+1),dtype=int)
    dp[:,0]=np.arange(n+1)*gap;dp[0,:]=np.arange(m+1)*gap
    move[1:,0]=1;move[0,1:]=2
    for i in range(1,n+1):
        for j in range(1,m+1):
            choices=(dp[i-1,j-1]+cost[i-1,j-1],dp[i-1,j]+gap,dp[i,j-1]+gap)
            k=int(np.argmin(choices));dp[i,j]=choices[k];move[i,j]=k
    i,j=n,m;matches=[]
    while i or j:
        k=move[i,j]
        if k==0:matches.append((i-1,j-1));i-=1;j-=1
        elif k==1:i-=1
        else:j-=1
    return float(dp[n,m]),list(reversed(matches))


def cyclic_match(cost, gap=GAP):
    """遍历起点与方向，不改点坐标；DP允许双方缺点。"""
    options=[]
    for direction in (1,-1):
        for shift in range(cost.shape[1]):
            order=(shift+direction*np.arange(cost.shape[1]))%cost.shape[1]
            loss,matched=linear_match(cost[:,order],gap)
            pairs=tuple(sorted((a,int(order[b])) for a,b in matched))
            options.append((loss,pairs))
    best=min(options)
    return dict(cost=best[0],matches=[list(p) for p in best[1]],
                tied_cyclic_solutions=len({p for loss,p in options if abs(loss-best[0])<1e-9}),
                tie_scope='cyclic cuts/directions only; within-DP equal-cost alternatives not enumerated')


def free_match(cost, gap=GAP):
    n,m=cost.shape
    padded=np.full((n+m,n+m),gap);padded[:n,:m]=cost;padded[n:,m:]=0
    a,b=linear_sum_assignment(padded)
    return dict(cost=float(padded[a,b].sum()),matches=[[int(i),int(j)] for i,j in zip(a,b) if i<n and j<m])


def source_ring(groups, assignments):
    """只从覆盖全部保留节点的来源投影环中选众数；不凑节点闭环。"""
    retained={g['feature_id'] for g in groups};options=defaultdict(list)
    direct=defaultdict(set);projected=defaultdict(set)
    for row in assignments:
        ring=row['feature_ids'];worker=str(row['worker'])
        for a,b in zip(ring,ring[1:]+ring[:1]):direct[tuple(sorted((a,b)))].add(worker)
        kept=[v for v in ring if v in retained]
        if len(kept)>=3:
            for a,b in zip(kept,kept[1:]+kept[:1]):projected[tuple(sorted((a,b)))].add(worker)
        if len(retained)>=3 and len(kept)==len(retained) and set(kept)==retained:
            options[_ring_key(kept)].append(worker)
    ranked=sorted(options,key=lambda k:(-len(options[k]),k))
    ids=list(ranked[0]) if ranked else []
    return dict(feature_ids=ids,ring_confirmed=False,
        policy='most supported complete projected source ring; no x sorting; ties lexicographic and flagged',
        reason=None if ids else 'no_source_ring_covering_all_selected_nodes',
        tied_best=len(ranked)>1 and len(options[ranked[0]])==len(options[ranked[1]]),
        alternatives=[dict(feature_ids=list(k),support=len(options[k]),workers=options[k]) for k in ranked],
        edges=[dict(feature_ids=[a,b],direct_support=len(direct[tuple(sorted((a,b)))]),
                    direct_workers=sorted(direct[tuple(sorted((a,b)))]),
                    projected_support=len(projected[tuple(sorted((a,b)))]),
                    projected_workers=sorted(projected[tuple(sorted((a,b)))]))
               for a,b in zip(ids,ids[1:]+ids[:1])])


def assemble_fusion(groups, assignments, manual_order=None):
    """节点融合独立交付；来源环只是顺序建议，人工排序不改变存在票或坐标。"""
    selected=[g for g in groups if g['selected']]
    byid={g['feature_id']:g for g in selected}
    ring=source_ring(selected,assignments)
    order=ring['feature_ids'] if manual_order is None else list(manual_order)
    if manual_order is not None and (len(order)!=len(byid) or set(order)!=set(byid)):
        raise ValueError('manual_order_must_contain_selected_nodes_exactly_once')
    nodes=[dict(feature_id=g['feature_id'],support=g['support'],points=g['center'],
                members=[dict(id=m['id'],worker=m['worker'],pair_index=m['pair_index']) for m in g['members']]) for g in selected]
    ready=bool(nodes) and all(g['center'] is not None for g in selected)
    node_output=dict(status='ready' if ready else 'empty_or_unresolved_location',nodes=nodes,
                     order_independent=True,location_policy='all identity members, equal-person coordinate medians')
    candidate=dict(status='unavailable',reason=ring['reason'],points=None,footprint=None,
                   ring_confirmed=manual_order is not None,feature_ids=order,
                   order_status='human_provided' if manual_order is not None else ('source_suggestion' if order else 'needs_manual_order'))
    if order and ready:
        candidate['points']=[p for fid in order for p in byid[fid]['center']]
        geometry=reconstruct(candidate,coordinate_convention='continuous')
        candidate.update(status='geometry_review' if geometry['status']=='ok' else 'unavailable',
            reason=('identity_unconfirmed' if manual_order is not None else 'source_order_and_identity_unconfirmed') if geometry['status']=='ok' else str(geometry['reason']),
            geometry_status=geometry['status'],footprint=geometry['floor'].tolist() if geometry['floor'] is not None else None)
    elif any(g['center'] is None for g in selected):candidate['reason']='ambiguous_periodic_center'
    return dict(node_consensus=node_output,candidate=candidate,ring_diagnostics=ring)


def build(records, mode='cyclic', gap=GAP):
    rows=sorted(records,key=lambda r:(str(r['worker']),str(r['id'])))
    if len({r['worker'] for r in rows})!=len(rows):raise ValueError('duplicate_worker')
    arrays=[];nodes=[];assignments=[]
    for r in rows:
        p,reason=_pairs(r)
        if reason:raise ValueError(str(r['id'])+':'+reason)  # fail the pool; never drop a voter
        arrays.append(p)
        assignments.append(dict(id=r['id'],worker=r['worker'],feature_ids=[None]*len(p),
                                source_ring_confirmed=r.get('ring_confirmed'),source_order_status=r.get('order_status')))
        for k,pair in enumerate(p):
            nodes.append(dict(id=r['id'],worker=r['worker'],pair_index=k,points=pair.tolist(),
                              source_pair_index=r['source_pair_indices'][k] if r.get('source_pair_indices') is not None else None))
    points=np.array([n['points'] for n in nodes]);offsets=np.cumsum([0]+[len(p) for p in arrays])
    top=angular(points[:,0]-.5,points[:,0]-.5);bottom=angular(points[:,1]-.5,points[:,1]-.5)
    distance=(top+bottom)/2
    compatible=np.full(distance.shape,2.);np.fill_diagonal(compatible,0)
    pairwise=[]
    for i,j in itertools.combinations(range(len(rows)),2):
        cost=distance[offsets[i]:offsets[i+1],offsets[j]:offsets[j+1]]
        result=(cyclic_match if mode=='cyclic' else free_match)(cost,gap)
        pairwise.append(dict(a=rows[i]['id'],b=rows[j]['id'],**result))
        for a,b in result['matches']:
            u,v=int(offsets[i]+a),int(offsets[j]+b)
            compatible[u,v]=compatible[v,u]=distance[u,v]/180
    # ponytail: pairwise-compatible complete linkage is a conservative prototype;
    # inconsistent pairwise matches can split a true identity, not solved by transitive merging.
    labels=fcluster(linkage(squareform(compatible,checks=False),method='complete'),1,criterion='distance')
    groups=[];lookup={r['id']:a for r,a in zip(rows,assignments)}
    for number,label in enumerate(sorted(set(labels),key=lambda x:np.flatnonzero(labels==x)[0])):
        ix=np.flatnonzero(labels==label);members=[nodes[int(k)] for k in ix]
        assert len({v['worker'] for v in members})==len(members)
        joint=np.maximum(top,bottom)[np.ix_(ix,ix)]
        anchor=int(ix[int(np.argmin(joint.sum(axis=1)))])
        delta=(points[ix,0,0]-points[anchor,0,0]+512)%1024-512
        ambiguous=bool(np.ptp(delta)>=512-1e-9 or np.any(abs(abs(delta)-512)<1e-9))
        x=float((points[anchor,0,0]+np.median(delta))%1024)
        center=None if ambiguous else [[x,float(np.median(points[ix,0,1]))],[x,float(np.median(points[ix,1,1]))]]
        fid=f'node_{number:03d}'
        g=dict(feature_id=fid,members=members,support=len(members),selected=2*len(members)>=len(rows),
               center=center,top_support=len(members),bottom_support=len(members),joint_support=len(members),
               maximum_top_angle=float(top[np.ix_(ix,ix)].max()),maximum_bottom_angle=float(bottom[np.ix_(ix,ix)].max()))
        # Diagnostic only: position groups do not decide identity, inclusion, or center.
        for side,dist in [('top',top),('bottom',bottom)]:
            local=dist[np.ix_(ix,ix)]
            sub=fcluster(linkage(squareform(local,checks=False),method='complete'),9,criterion='distance') if len(ix)>1 else np.ones(1,dtype=int)
            g[side+'_position_groups_9deg']=[dict(support=int(sum(sub==label)),
                members=[dict(id=members[k]['id'],pair_index=members[k]['pair_index']) for k in np.flatnonzero(sub==label)]) for label in sorted(set(sub))]
        groups.append(g)
        for member in members:lookup[member['id']]['feature_ids'][member['pair_index']]=fid
    output=assemble_fusion(groups,assignments)
    return dict(route=mode+'_identity',n=len(rows),minimum_support=math.ceil(len(rows)/2),
        identity_groups=groups,assignments=assignments,pairwise=pairwise,**output,
        location_policy='all identity members, same medoid-anchored coordinate medians as bound baseline; not semantic mode selection')


def run():
    from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
    from tools.thesis_main.data_prep.project_public_research_20260929 import project_bundle
    from .point_route_panel_20261005 import build_routes
    from .adaptive_point_20261007 import adaptive_candidate
    OUT.mkdir(exist_ok=True)
    plan=dict(images=CODES,gap_per_omitted_node_deg=GAP,matching_cost='mean(top_angle,bottom_angle)',
        controls=['existing paired/split/anchors at 9deg','unordered matching with same cost/gap','cyclic matching with same cost/gap'],
        grouping='complete linkage with unmatched observation pairs prohibited; one per person',
        location='fixed current medoid anchored median; no semantic mode selector in this first correspondence experiment',
        connection='most supported complete projected source ring; nodes/positions fixed; no x fallback',
        evidence='existing development cases; no GT selection, no new people or blind test',
        limitation='13.5deg skip is an uncalibrated working choice (1.5 times old 9deg); changed metric/tolerance separated by free control')
    write_json(OUT/'PLAN.json',plan)
    bundle=load_current_bundle();data,aliases=project_bundle(bundle)
    objects={aliases['records'][o['object_id']]:o for o in bundle['data']['objects']}
    images={r['code']:r for r in data['images']}
    states=[];inputs=[];summary=[]
    for code in CODES:
        im=images[code]
        records=sorted([r for r in im['annotations'] if r['independent'] and r['consensus_eligible']
            and r['condition']=='manual' and r['main_consensus_gate']['status']=='main_candidate'],key=lambda r:r['id'])
        for r in records:
            obj=objects[r['id']]
            r.update(source_pair_indices=obj['ordered_source_pair_indices'],object_id=obj['object_id'])
        image_id=objects[records[0]['id']]['image_id']
        image_path=next(ROOT.glob('data/mp3d_layout/*/img/'+image_id+'.png'))
        inputs.append(dict(image=code,image_id=image_id,image_path=str(image_path),records=records))
        values=build_routes(records,9)
        values['adaptive_incidence_v1']=adaptive_candidate(records,9,values)
        values.update({mode+'_identity':build(records,mode) for mode in ('free','cyclic')})
        for route,result in values.items():
            states.append(dict(image=code,route=route,result=result))
            candidate=result['candidate']
            summary.append(dict(image=code,route=route,n=len(records),
                selected_nodes=sum(g.get('selected',True) for g in result.get('identity_groups',result.get('paired_identities',[]))),
                output_pairs=len(candidate.get('points') or [])//2,status=candidate['status'],reason=candidate.get('reason')))
        print(code,[(r['route'],r['output_pairs'],r['status']) for r in summary if r['image']==code],flush=True)
    write_json(OUT/'inputs.json',dict(images=inputs));write_json(OUT/'candidates.json',dict(states=states))
    write_csv(OUT/'summary.csv',summary)
    write_json(OUT/'field_contract.json',dict(schema='ring_correspondence_development_v2',
        indices='pair_index is zero-based in current processed source ring; source_pair_index maps original paired identity',
        identity='algorithmic partition, not semantic certification; all members retained in ledger',
        endpoint_position_groups='within each new identity, separate top/bottom complete-link at old 9deg; descriptive only, not semantic classes or output selection',
        votes='full input N, one worker one vote; >=50%; top/bottom/joint all same membership in new routes',
        edges='direct is actual source adjacency; projected skips unselected nodes; neither means whole ring majority',
        order='source complete projected ring as suggestion; no such ring -> nodes retained, manual order permitted without changing nodes',
        node_consensus='order-independent retained node coordinates and source people; ready does not certify identity or geometry',
        candidate='geometry_review means geometry usable but identity/ordering unconfirmed; unavailable still retains evidence',
        raw_input='current load_current_bundle -> project_bundle; immutable original arrays',
        references='no GT loaded into this output; quality evaluation remains external'))
    diagnostics(inputs,states)


def diagnostics(inputs,states):
    import json
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from PIL import Image
    from .research_artifact_io import read_csv
    plt.rcParams['font.sans-serif']=['Microsoft YaHei','DejaVu Sans']
    lookup={(s['image'],s['route']):s['result'] for s in states}
    prior=read_csv(ROOT/'analysis_results/adaptive_point_20261007/expanded/g184/source_ledger.csv')
    reviews=json.loads((ROOT/'research/structure_constraints_20261006/human_review.json').read_text(encoding='utf-8'))['reviews']
    target_rows=[];comparisons=[]
    for im in inputs:
        code=im['image'];records=im['records']
        if code.endswith('-25'):
            keys={(r['id'],3) for r in records if len(r['points'])==12};evidence='13 six-pair source-ring slot-4 hypotheses; not new human identity certification'
        elif code.endswith(('-26','-41')):
            keys={(r['record'],int(r['processed_pair_index'])) for r in prior if r['image']==code and (code.endswith('-41') or r['category']=='joint')}
            evidence='41 user same-wall-corner 14; 26 displayed joint five, not all same-target certified'
        else:
            review=next(r for r in reviews if r['image']==code)
            keys=set(zip(review['record_ids'],review['processed_pair_indices']));evidence=review['relation']
        for route in ('paired','free_identity','cyclic_identity'):
            result=lookup[code,route]
            for g in result['identity_groups']:
                members={(m['id'],m['pair_index']) for m in g['members']};hit=keys&members
                if hit:target_rows.append(dict(image=code,route=route,group=g['feature_id'],tracked_total=len(keys),
                    tracked_hit=len(hit),support=g['support'],selected=g['selected'],evidence=evidence,
                    tracked_members=sorted(hit),additional_members=sorted(members-keys),center=g['center']))
        free=lookup[code,'free_identity'];cyclic=lookup[code,'cyclic_identity']
        def partition(r):return {frozenset((m['id'],m['pair_index']) for m in g['members']) for g in r['identity_groups']}
        pairs={(r['a'],r['b']):r for r in free['pairwise']}
        comparisons.append(dict(image=code,same_partition=partition(free)==partition(cyclic),
            changed_pairwise_matches=sum(r['matches']!=pairs[r['a'],r['b']]['matches'] for r in cyclic['pairwise']),
            pairwise_total=len(pairs),same_output=free['candidate']['points']==cyclic['candidate']['points']))
        if code=='yqstnuAEVhm-25':
            from shapely.geometry import Polygon
            selected=[g for g in cyclic['identity_groups'] if g['selected']]
            xordered=sorted(selected,key=lambda g:g['center'][0][0])
            xpoints=[p for g in xordered for p in g['center']]
            geo=reconstruct(dict(points=xpoints),coordinate_convention='continuous')
            a=Polygon(cyclic['candidate']['footprint']);b=Polygon(geo['floor'])
            write_json(OUT/'connection_control.json',dict(same_nodes_same_centers=True,
                source_order=cyclic['ring_diagnostics']['feature_ids'],x_order=[g['feature_id'] for g in xordered],
                x_geometry_status=geo['status'],source_area=float(a.area),x_area=float(b.area),
                difference_area=float(a.symmetric_difference(b).area),
                difference_over_source_area=float(a.symmetric_difference(b).area/a.area),
                reference='source-order candidate, not GT',x_points=xpoints))
        photo=Image.open(im['image_path'])
        routes=['paired','split_unique','adaptive_incidence_v1','cyclic_identity']
        fig,axes=plt.subplots(2,4,figsize=(20,9))
        for col,(route,title) in enumerate(zip(routes,['绑定9°','独立9°','自适应v1 9°','共同身份＋来源环（新）'])):
            result=lookup[code,route];candidate=result['candidate'];pp=candidate.get('points')
            ax=axes[0,col];ax.imshow(photo,extent=(0,1024,512,0))
            if pp:
                p=np.array(pp).reshape(-1,2,2)
                for k,pair in enumerate(p):
                    ax.plot(pair[:,0],pair[:,1],'-o',color=plt.cm.tab20(k%20),lw=2,ms=3)
                    ax.text(pair[0,0],pair[0,1]-10,str(k+1),color='yellow',fontsize=9)
            ax.set_title(title+'：'+str(len(pp or [])//2)+'对');ax.axis('off')
            ax=axes[1,col]
            for r in records:
                geo=reconstruct(r,coordinate_convention='continuous')
                if geo['floor'] is not None:
                    p=np.asarray(geo['floor']);ax.plot(*np.vstack([p,p[0]]).T,color='gray',alpha=.12,lw=.7)
            if candidate.get('footprint') is not None:
                p=np.array(candidate['footprint']);ax.plot(*np.vstack([p,p[0]]).T,color='#c02536',lw=2)
                for k,xy in enumerate(p):ax.text(*xy,str(k+1),fontsize=10,color='#c02536')
            ax.set_aspect('equal');ax.set_title(candidate['status']+'；所有连线未认证',fontsize=9)
        fig.suptitle(code+'，N='+str(len(records))+'；上：实际端点对，下：按候选顺序的BEV（灰色为原作答）；不含GT')
        fig.tight_layout();fig.savefig(OUT/(code+'_complete.png'),dpi=135);plt.close(fig)
        # Review only new membership; already discussed members remain a visual reference.
        if code.endswith(('-25','-41')):
            target=max((g for g in cyclic['identity_groups'] if keys&{(m['id'],m['pair_index']) for m in g['members']}),
                       key=lambda g:len(keys&{(m['id'],m['pair_index']) for m in g['members']}))
            extra=[m for m in target['members'] if (m['id'],m['pair_index']) not in keys]
            fig,axes=plt.subplots(1,len(extra)+1,figsize=(3.2*(len(extra)+1),6),squeeze=False)
            x=target['center'][0][0];lo,hi=(680,840) if code.endswith('-25') else (610,790)
            for k,ax in enumerate(axes[0]):
                ax.imshow(photo,extent=(0,1024,512,0));ax.set_xlim(lo,hi);ax.set_ylim(460,65)
                if k==0:
                    members=[m for m in target['members'] if (m['id'],m['pair_index']) in keys]
                    title='已有来源参照（不重审）'
                else:members=[extra[k-1]];title=f"新增{k}: {members[0]['worker']} / {members[0]['id']}\n原环第{members[0]['pair_index']+1}对"
                for member in members:
                    p=np.array(member['points']);ax.plot(p[:,0],p[:,1],'-o',color='#ff4040' if k else '#00ffff',lw=1.7)
                ax.set_title(title,fontsize=9);ax.axis('off')
            fig.suptitle(code+'：只核对新增来源是否表达同一墙角；不要求判定精确坐标或上下语义类型')
            fig.tight_layout();fig.savefig(OUT/(code+'_new_members.png'),dpi=145);plt.close(fig)
    write_json(OUT/'known_relations.json',target_rows);write_json(OUT/'order_ablation.json',comparisons)


if __name__=='__main__':run()
