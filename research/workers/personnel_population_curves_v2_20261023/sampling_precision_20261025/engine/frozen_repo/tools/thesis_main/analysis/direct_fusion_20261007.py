"""当前全部>=2人Manual池：对应后全员直接定位，节点与排序解耦。"""
import copy
import json
from collections import Counter
from collections import defaultdict
import numpy as np
from scipy.cluster.hierarchy import linkage
from scipy.spatial.distance import squareform

from .research_artifact_io import ROOT, write_json, write_csv
from .ring_correspondence_20261007 import build, assemble_fusion, GAP
from .fixed_identity_location_20261007 import median_pair
from .paired_split_research.study import angular

OUT=ROOT/'analysis_results/direct_fusion_20261007'
PREVIOUS=ROOT/'analysis_results/ring_correspondence_20261007/expanded'


def separation_diagnostic(members):
    """单链接最后一次连接的两侧，仅用来挑复核样本，不决定是否同墙角。"""
    p=np.array([m['points'] for m in members])
    d=np.maximum(angular(p[:,0]-.5,p[:,0]-.5),angular(p[:,1]-.5,p[:,1]-.5))
    np.fill_diagonal(d,0)
    z=linkage(squareform(d,checks=False),method='single');n=len(p)
    def leaves(k):
        k=int(k)
        return [k] if k<n else leaves(z[k-n,0])+leaves(z[k-n,1])
    groups=[leaves(k) for k in z[-1,:2]]
    within=float(z[-2,2]) if len(z)>1 else 0.
    return dict(subgroups=[[[members[i]['id'],members[i]['pair_index']] for i in g] for g in groups],
        bridge_deg=float(z[-1,2]),within_connectivity_deg=within,gap_margin_deg=float(z[-1,2])-within,
        min_side=min(map(len,groups)),decision='diagnostic_only_no_automatic_split')


def adjacent_cohort_signals(groups,assignments):
    """相邻节点在共同人员中呈同一两团划分：只提出复核，不自动改身份。"""
    diagnostics={}
    for g in groups:
        if len(g['members'])<4:continue
        d=separation_diagnostic(g['members'])
        if d['min_side']>=2:diagnostics[g['feature_id']]=d
    edges=defaultdict(set)
    for row in assignments:
        ids=row['feature_ids']
        for a,b in zip(ids,ids[1:]+ids[:1]):
            if a!=b and a in diagnostics and b in diagnostics:
                edges[tuple(sorted((a,b)))].add(row['id'])
    results=[]
    for (a,b),adjacent in edges.items():
        da,db=diagnostics[a],diagnostics[b]
        pa=[set(k[0] for k in group) for group in da['subgroups']]
        pb=[set(k[0] for k in group) for group in db['subgroups']]
        common=set.union(*pa)&set.union(*pb)
        ca=[p&common for p in pa];cb=[p&common for p in pb]
        if min(map(len,ca))<2 or {frozenset(p) for p in ca}!={frozenset(p) for p in cb}:continue
        if min(len(p&adjacent) for p in ca)<2:continue
        results.append(dict(nodes=[a,b],common_cohorts=[sorted(p) for p in ca],
            common_people=len(common),direct_neighbor_people=len(adjacent),
            shared_fraction=[len(common)/len(set.union(*p)) for p in [pa,pb]],
            gap_margin_deg=[da['gap_margin_deg'],db['gap_margin_deg']],
            priority=min(da['gap_margin_deg'],db['gap_margin_deg']),
            source_subgroups=[da['subgroups'],db['subgroups']],
            decision='review_signal_only_not_identity_split'))
    return sorted(results,key=lambda r:-r['priority'])


def workflow():
    """复用178图与人审修正，输出可交付节点/连接和独立的异常提示。"""
    from .research_artifact_io import read_csv
    target=OUT/'workflow';target.mkdir(exist_ok=True)
    summaries=[];outputs=[];signals=[]
    for row in read_csv(OUT/'summary.csv'):
        code=row['image'];artifact=json.loads((OUT/(code+'.json')).read_text(encoding='utf-8'))
        summary=dict(image=code,n=int(row['n']),input_status='ok',origin='automatic',nodes=0,
                     connection_ready=False,geometry_status='',review_signals=0)
        if artifact.get('pool_error'):
            summary.update(input_status=artifact['pool_error']);summaries.append(summary)
            outputs.append(dict(image=code,input_error=artifact['pool_error']));continue
        automatic=artifact['correspondence']
        auto_signals=adjacent_cohort_signals(automatic['identity_groups'],automatic['assignments'])
        assisted=OUT/(code+'_assisted.json')
        current=json.loads(assisted.read_text(encoding='utf-8')) if assisted.exists() else automatic
        current_signals=adjacent_cohort_signals(current['identity_groups'],current['assignments']) if assisted.exists() else auto_signals
        origin='human_assisted' if assisted.exists() else 'automatic'
        signals.extend(dict(image=code,origin='automatic',**s) for s in auto_signals)
        if assisted.exists():signals.extend(dict(image=code,origin=origin,**s) for s in current_signals)
        candidate=current['candidate']
        summary.update(origin=origin,nodes=len(current['node_consensus']['nodes']),
            connection_ready=candidate['points'] is not None,
            geometry_status=candidate.get('geometry_status','not_evaluable'),review_signals=len(current_signals))
        summaries.append(summary)
        outputs.append(dict(image=code,n=current['n'],minimum_support=(current['n']+1)//2,origin=origin,
            source=str((assisted if assisted.exists() else OUT/(code+'.json')).relative_to(ROOT)),
            node_consensus=current['node_consensus'],candidate=candidate,
            excluded_identities=[dict(feature_id=g['feature_id'],support=g['support']) for g in current['identity_groups'] if not g['selected']],
            identity_review='partial_user_review' if assisted.exists() else 'not_fully_reviewed',
            local_review_signals=current_signals))
    write_json(target/'outputs.json',outputs);write_csv(target/'summary.csv',summaries)
    write_json(target/'adjacent_signals.json',sorted(signals,key=lambda r:-r['priority']))
    valid=[r for r in summaries if r['input_status']=='ok']
    write_json(target/'summary.json',dict(attempted_images=len(summaries),valid_images=len(valid),
        nodes=sum(r['nodes'] for r in valid),connection_ready=sum(r['connection_ready'] for r in valid),
        output_origin=dict(Counter(r['origin'] for r in valid)),geometry=dict(Counter(r['geometry_status'] for r in valid)),
        automatic_signals=sum(s['origin']=='automatic' for s in signals),
        automatic_signal_images=len({s['image'] for s in signals if s['origin']=='automatic'}),
        note='same 178 pools; outputs include reviewed corrections; geometry and signals are not semantic success rates'))
    write_json(target/'field_contract.json',dict(schema='fusion_workflow_v1',
        scope='same 178 pools; no new people, GT use, parameter fit or automatic semantic split',
        outputs='automatic or existing human-assisted nodes, original full-N votes, equal-person centers, connection and geometry separately',
        signal='same two-cohort partition of common people at two source-adjacent identities; at least two directly adjacent people per cohort; no identity decision',
        priority='minimum single-link gap margin of the two identities; uncalibrated review ranking, not error probability',
        input_error='whole pool remains failed; no voter silently omitted'))
    return summaries,signals


def draw_layout(ax,points,color,alpha=1.,closed=True):
    """按实际环序画球面短弧，跨接缝分段；仅显示声明的连线，不改变节点。"""
    from .layout_reliability_20261005.arc_consensus import rays,project
    p=np.asarray(points).reshape(-1,2,2)
    for pair in p:ax.plot(pair[:,0],pair[:,1],'-o',color=color,alpha=alpha,lw=1,ms=2)
    for side in [0,1]:
        v=rays(p[:,side]);edges=list(zip(v,np.roll(v,-1,axis=0)))
        for a,b in (edges if closed else edges[:-1]):
            t=np.linspace(0,1,65)[:,None];xy=project(a*(1-t)+b*t)
            for part in np.split(xy,np.flatnonzero(abs(np.diff(xy[:,0]))>512)+1):
                ax.plot(part[:,0],part[:,1],color=color,alpha=alpha,lw=1)


def workflow_plot(code,signal=None):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from PIL import Image
    plt.rcParams['font.sans-serif']=['Microsoft YaHei','DejaVu Sans']
    artifact=json.loads((OUT/(code+'.json')).read_text(encoding='utf-8'))
    result=artifact['correspondence'];assisted=OUT/(code+'_assisted.json')
    current=json.loads(assisted.read_text(encoding='utf-8')) if assisted.exists() else result
    photo=Image.open(next(ROOT.glob('data/mp3d_layout/*/img/'+artifact['image_id']+'.png')))
    if signal is not None:
        groups={g['feature_id']:g for g in result['identity_groups']}
        members=[{m['id']:m for m in groups[f]['members']} for f in signal['nodes']]
        fig,axes=plt.subplots(1,4,figsize=(16,6))
        for ax in axes:ax.imshow(photo,extent=(0,1024,512,0));ax.axis('off')
        points=[]
        for k,cohort in enumerate(signal['common_cohorts']):
            for rid in cohort:
                p=np.array([ms[rid]['points'] for ms in members]).reshape(-1,2);points.extend(p)
                draw_layout(axes[k+1],p,['#00a6e5','#e58116'][k],.55,closed=False)
            axes[k+1].set_title(f"{'蓝A' if k==0 else '橙B'}：{len(cohort)}人，两处均来自同一批人")
        centers=[groups[f]['center'] for f in signal['nodes']]
        draw_layout(axes[0],centers,'red',closed=False);draw_layout(axes[3],centers,'red',closed=False)
        for k,cohort in enumerate(signal['common_cohorts']):
            center=[median_pair([ms[rid] for rid in cohort]) for ms in members]
            draw_layout(axes[3],center,['#00a6e5','#e58116'][k],closed=False)
        points=np.array(points);lo=points.min(axis=0);hi=points.max(axis=0)
        for ax in axes[1:]:ax.set_xlim(max(0,lo[0]-30),min(1024,hi[0]+30));ax.set_ylim(min(512,hi[1]+30),max(0,lo[1]-30))
        axes[0].set_xlim(0,1024);axes[0].set_ylim(512,0);axes[0].set_title('原图；红为自动合组中心')
        axes[3].set_title('红：自动融合；蓝橙：分组中心作诊断')
        name=code+'_adjacent_review.png'
    else:
        fig,axes=plt.subplots(2,2,figsize=(16,9))
        for ax in axes.flat:ax.imshow(photo,extent=(0,1024,512,0));ax.axis('off')
        axes[0,0].set_title('原图')
        for record in artifact['records']:draw_layout(axes[0,1],record['points'],'#2477bd',.22)
        axes[0,1].set_title(f"全体{len(artifact['records'])}人原作答；环序不变")
        for ax,res,title in [(axes[1,0],result,'自动融合'),(axes[1,1],current,'当前输出（人工辅助）' if assisted.exists() else '当前输出（沿用自动）')]:
            c=res['candidate']
            if c['points'] is not None:draw_layout(ax,c['points'],'#d22d39')
            else:
                for node in res['node_consensus']['nodes']:
                    p=np.array(node['points']);ax.plot(p[:,0],p[:,1],'-o',color='#d22d39')
            for i,node in enumerate(res['node_consensus']['nodes'],1):
                ax.text(node['points'][0][0],node['points'][0][1]-6,f"{i}:{node['support']}/{res['n']}",color='#b00020',fontsize=8,
                        bbox=dict(facecolor='white',alpha=.8,edgecolor='none'))
            ax.set_title(title+'；'+c['order_status'])
        for ax in axes.flat:ax.set_xlim(0,1024);ax.set_ylim(512,0)
        name=code+'_complete.png'
    fig.suptitle(code+'；节点按全池MV50，定位等权中位数；不含GT，画面可用不代表语义已确认')
    fig.tight_layout();fig.savefig(OUT/'workflow'/name,dpi=130);plt.close(fig)
    return name


def human_split(artifact,review):
    r=copy.deepcopy(artifact['correspondence']);fid=review['feature_id']
    old=next(g for g in r['identity_groups'] if g['feature_id']==fid)
    lookup={(m['id'],m['pair_index']):m for m in old['members']};new=[];mapping={}
    for h in review['groups']:
        members=[lookup[m['id'],m['pair_index']] for m in h['members']]
        assert len({m['worker'] for m in members})==len(members)
        g=dict(feature_id=h['identity'],members=members,support=len(members),
               selected=2*len(members)>=r['n'],center=median_pair(members))
        new.append(g)
        for m in members:
            key=m['id'],m['pair_index']
            assert key not in mapping
            mapping[key]=g['feature_id']
    assert set(mapping)==set(lookup)
    groups=[g for g in r['identity_groups'] if g['feature_id']!=fid]+new
    for row in r['assignments']:
        row['feature_ids']=[mapping.get((row['id'],i),g) for i,g in enumerate(row['feature_ids'])]
    return dict(image=artifact['image'],n=r['n'],intervention='user_identity_split_only',
        review_source=review['review_source'],
        identity_groups=groups,assignments=r['assignments'],**assemble_fusion(groups,r['assignments']))


def apply_reviews():
    """只应用明确的人审身份；保留原自动输出，人工顺序绑定具体节点版本。"""
    reviews=json.loads((OUT/'user_review.json').read_text(encoding='utf-8'))
    results={}
    for review in reviews['decisions']:
        if review['decision']!='split':continue
        artifact=json.loads((OUT/(review['image']+'.json')).read_text(encoding='utf-8'))
        if review['image'] in results:artifact['correspondence']=results[review['image']]
        result=human_split(artifact,review)
        result['review_scope']=review['scope']
        if review.get('display_order'):
            byid={g['feature_id']:g for g in result['identity_groups']}
            result['identity_groups']=[byid[f] for f in review['display_order']]
            result.update(assemble_fusion(result['identity_groups'],result['assignments']))
        if review.get('manual_order'):
            result.update(assemble_fusion(result['identity_groups'],result['assignments'],review['manual_order']))
        if review.get('order_rule')=='x_ascending':
            order=[g['feature_id'] for g in sorted((g for g in result['identity_groups'] if g['selected']),key=lambda g:g['center'][0][0])]
            result.update(assemble_fusion(result['identity_groups'],result['assignments'],order))
            result['candidate'].update(order_status='user_requested_x_sort',order_rule='x_ascending',ring_confirmed=False)
        results[review['image']]=result
    for code,result in results.items():
        write_json(OUT/(code+'_assisted.json'),result)
    diagnostics=json.loads((OUT/'separation_diagnostics.json').read_text(encoding='utf-8'))
    lookup={(d['image'],d['node']):d for d in diagnostics};linked=[]
    for code in ['uNb9QFRL6hY-36','B6ByNegPMKs-11']:
        ds=[lookup[code,fid] for fid in ['node_002','node_003']]
        partitions=[{frozenset(k[0] for k in group) for group in d['subgroups']} for d in ds]
        linked.append(dict(image=code,nodes=['node_002','node_003'],
            identical_person_partition=partitions[0]==partitions[1],
            source_partitions=[d['subgroups'] for d in ds],
            meaning='same people separate at adjacent corners; coordinates alone do not establish different identities'))
    write_json(OUT/'linked_local_groups.json',linked)


def run():
    from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
    from tools.thesis_main.data_prep.project_public_research_20260929 import project_bundle
    OUT.mkdir(parents=True,exist_ok=True)
    bundle=load_current_bundle();data,aliases=project_bundle(bundle)
    objects={aliases['records'][o['object_id']]:o for o in bundle['data']['objects']}
    pools=[]
    for im in data['images']:
        records=sorted([dict(r) for r in im['annotations'] if r['independent'] and r['consensus_eligible']
            and r['condition']=='manual' and r['main_consensus_gate']['status']=='main_candidate'],key=lambda r:r['id'])
        if len(records)>=2:pools.append((im['code'],records))
    write_json(OUT/'PLAN.json',dict(images=[c for c,_ in pools],input='current load_current_bundle; all independent Manual main_candidate pools N>=2',
        correspondence='reuse exact-input previous cyclic partitions, compute new pools with unchanged cyclic matching',
        gap_deg=GAP,existence='full-N MV50, >=ceil(N/2)',location='all same-identity observations, equal-person coordinate median',
        review='user_review.json records uNb36/uNb04 splits and provisional jtc26 retention; assisted outputs separate; no automatic diagnostic splitting',
        order='source suggestion when present; otherwise all nodes still delivered, manual ordering permitted',
        diagnostic='largest single-link bridge in max(top,bottom) angular distance; exploratory ranking only, no calibrated threshold',
        gt='not loaded or used'))
    summary=[];diagnostics=[]
    for number,(code,records) in enumerate(pools,1):
        for r in records:
            o=objects[r['id']];r.update(object_id=o['object_id'],source_pair_indices=o['ordered_source_pair_indices'])
        artifact=dict(image=code,image_id=objects[records[0]['id']]['image_id'],records=records)
        old_path=PREVIOUS/(code+'.json');reuse=old_path.exists()
        row=dict(image=code,n=len(records),correspondence_origin='previous_exact_input' if reuse else 'new_computation',
                 pool_error='',nodes=0,node_status='',order_status='',geometry_status='',reason='')
        if reuse:
            old=json.loads(old_path.read_text(encoding='utf-8'))
            assert {r['id']:(r['worker'],r['points'],r['source_pair_indices']) for r in records}=={
                r['id']:(r['worker'],r['points'],r['source_pair_indices']) for r in old['records']},code
            r=old.get('correspondence',{}).get('cyclic');error=old.get('pool_error','')
        else:
            try:r=build(records);error=''
            except ValueError as e:r=None;error=str(e)
        if r is None:
            row['pool_error']=error;artifact['pool_error']=error
        else:
            # Re-estimate from current source coordinates; saved partitions are derived evidence, not new raw input.
            current={r['id']:r for r in records}
            for g in r['identity_groups']:
                for m in g['members']:
                    assert m['points']==current[m['id']]['points'][2*m['pair_index']:2*m['pair_index']+2]
                g['center']=median_pair(g['members'])
                assert g['support']==len({m['worker'] for m in g['members']})
                assert g['selected']==(2*g['support']>=len(records))
            output=assemble_fusion(r['identity_groups'],r['assignments']);r.update(output)
            artifact['correspondence']=r
            nodes=output['node_consensus'];candidate=output['candidate']
            row.update(nodes=len(nodes['nodes']),node_status=nodes['status'],order_status=candidate['order_status'],
                       geometry_status=candidate.get('geometry_status','not_evaluable'),reason=candidate.get('reason'))
            for g in r['identity_groups']:
                if g['selected'] and len(g['members'])>=4:
                    diagnostics.append(dict(image=code,node=g['feature_id'],n=len(records),support=g['support'],
                                            **separation_diagnostic(g['members'])))
        write_json(OUT/(code+'.json'),artifact);summary.append(row)
        print(number,code,row['correspondence_origin'],row['nodes'],row['pool_error'],flush=True)
    write_csv(OUT/'summary.csv',summary);write_json(OUT/'separation_diagnostics.json',diagnostics)
    write_json(OUT/'summary.json',dict(images=len(summary),people_records=sum(r['n'] for r in summary),
        new_images=sum(r['correspondence_origin']=='new_computation' for r in summary),
        new_records=sum(r['n'] for r in summary if r['correspondence_origin']=='new_computation'),
        pool_errors=[r for r in summary if r['pool_error']],nodes=sum(r['nodes'] for r in summary),
        node_status=dict(Counter(r['node_status'] for r in summary if not r['pool_error'])),
        order_status=dict(Counter(r['order_status'] for r in summary if not r['pool_error'])),
        geometry_status=dict(Counter(r['geometry_status'] for r in summary if not r['pool_error']))))
    apply_reviews()
    write_json(OUT/'field_contract.json',dict(schema='direct_fusion_v1',
        node_consensus='all selected identities, centers and support regardless of order or geometry; no silent node dropping',
        candidate='ordered coordinates only; absence of order leaves points null but node_consensus remains ready',
        manual_order='explicit permutation of all selected IDs exactly once; changes no identity, support or center',
        user_requested_x_sort='explicit user-selected ordering policy for a reviewed image; not geometry certification; changes no vote or center',
        diagnostic='two spatial subgroups are not semantic identities; exploratory queue only, no automatic mutation',
        provenance='current bundle records; old partitions reused after exact input check; new correspondence computed on additional pools',
        human_assisted='separate outputs from user_review.json; human order applies only to its exact node version; no general automation success claim'))


def node_plot(code,assisted=False):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from PIL import Image
    plt.rcParams['font.sans-serif']=['Microsoft YaHei','DejaVu Sans']
    artifact=json.loads((OUT/(code+'.json')).read_text(encoding='utf-8'))
    output=json.loads((OUT/(code+'_assisted.json')).read_text(encoding='utf-8')) if assisted else artifact['correspondence']
    photo=Image.open(next(ROOT.glob('data/mp3d_layout/*/img/'+artifact['image_id']+'.png')))
    nodes=output['node_consensus']['nodes']
    fig,axes=plt.subplots(2,1,figsize=(15,10));colors=plt.get_cmap('tab10')
    for ax in axes:ax.imshow(photo,extent=(0,1024,512,0));ax.axis('off')
    candidate=output['candidate']
    if assisted and candidate['order_status']=='user_requested_x_sort':
        points=np.array(candidate['points']).reshape(-1,2,2)
        for side in [0,1]:
            boundary=points[:,side]
            for a,b in zip(boundary,np.roll(boundary,-1,axis=0)):
                b=b.copy()
                if b[0]<a[0]:b[0]+=1024
                for shift in [-1024,0]:
                    for ax in axes:ax.plot([a[0]+shift,b[0]+shift],[a[1],b[1]],'--',c='#444444',lw=1,alpha=.7)
    groups={g['feature_id']:g for g in output['identity_groups']}
    for i,node in enumerate(nodes,1):
        p=np.array(node['points']);color=colors((i-1)%10)
        for ax in axes:
            ax.plot(p[:,0],p[:,1],'-o',color=color,lw=2.5,ms=4)
            ax.text(p[0,0]+3,p[0,1]-8,f"{i} ({node['support']}/{len(artifact['records'])})",color=color,
                    fontsize=12,bbox=dict(facecolor='white',alpha=.85,edgecolor='none'))
        for m in groups[node['feature_id']]['members']:
            q=np.array(m['points']);axes[1].plot(q[:,0],q[:,1],'-',color=color,lw=.6,alpha=.35)
    axes[0].set_title('融合节点及票数；按用户指定x递增连接（虚线为画布直线示意）' if assisted and candidate['order_status']=='user_requested_x_sort'
                      else '融合节点及票数；尚未画连接，不按横坐标猜顺序')
    for ax in axes:ax.set_xlim(0,1024);ax.set_ylim(512,0)
    if assisted and code=='uNb9QFRL6hY-36':
        axes[1].set_xlim(180,340);axes[1].set_ylim(380,190)
        axes[1].set_title('后方：3与4；前方：6与5。原3号拆为新3、6；浅线为原始来源')
    else:axes[1].set_title('同一节点来源同色；只是自动对应，尚未逐点确认')
    fig.suptitle(code+(' 人工辅助拆分；每个身份内部直接融合' if assisted else ' 全部同角观察直接融合'))
    fig.tight_layout();target=OUT/(code+('_assisted_nodes.png' if assisted else '_nodes.png'))
    fig.savefig(target,dpi=140);plt.close(fig)
    return [dict(display=i,feature_id=n['feature_id'],support=n['support']) for i,n in enumerate(nodes,1)]


def diagnostic_plot(code,fid):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from PIL import Image
    plt.rcParams['font.sans-serif']=['Microsoft YaHei','DejaVu Sans']
    a=json.loads((OUT/(code+'.json')).read_text(encoding='utf-8'))
    g=next(g for g in a['correspondence']['identity_groups'] if g['feature_id']==fid)
    diag=separation_diagnostic(g['members']);lookup={(m['id'],m['pair_index']):m for m in g['members']}
    photo=np.asarray(Image.open(next(ROOT.glob('data/mp3d_layout/*/img/'+a['image_id']+'.png'))))
    groups=[[lookup[tuple(k)] for k in keys] for keys in diag['subgroups']]
    anchor=g['center'][0][0]
    def shifted(points):
        q=np.array(points,float);q[:,0]=anchor+(q[:,0]-anchor+512)%1024-512
        return q
    allp=np.concatenate([shifted(m['points']) for m in g['members']])
    lo,hi=allp.min(axis=0),allp.max(axis=0)
    fig,axes=plt.subplots(1,4,figsize=(16,7))
    for ax in axes:
        ax.imshow(np.tile(photo,(1,3,1)),extent=(-1024,2048,512,0));ax.axis('off')
        ax.set_xlim(lo[0]-35,hi[0]+35);ax.set_ylim(min(512,hi[1]+35),max(0,lo[1]-35))
    axes[0].set_xlim(0,1024);axes[0].set_ylim(512,0)
    axes[0].set_title('原图与自动融合位置')
    center=shifted(g['center'])
    axes[0].plot(center[:,0],center[:,1],'-o',c='red',lw=2)
    for label,(ax,ms,col) in enumerate(zip(axes[1:3],groups,['#00a6e5','#e58116'])):
        for m in ms:
            q=shifted(m['points']);ax.plot(q[:,0],q[:,1],'-o',c=col,lw=1,ms=3,alpha=.65)
        ax.set_title(f"{'A' if label==0 else 'B'}组：{len(ms)}人，全部来源叠加")
    for ms,col in zip(groups,['#00a6e5','#e58116']):
        q=shifted(median_pair(ms));axes[3].plot(q[:,0],q[:,1],'-o',c=col,lw=2)
    axes[3].plot(center[:,0],center[:,1],'-o',c='red',lw=2,label='当前全部来源融合')
    axes[3].legend(fontsize=8);axes[3].set_title('红：现有结果；蓝橙：仅供比较的分组中心')
    fig.suptitle(f'{code} / {fid}，当前合为{g["support"]}/{len(a["records"])}\n分组只按坐标供检查，不代表已认定不同墙角；没有GT')
    fig.tight_layout();fig.savefig(OUT/(code+'_'+fid+'_diagnostic.png'),dpi=140);plt.close(fig)
    return dict(image=code,node=fid,subgroups=diag['subgroups'],diagnostic=diag,
                source_image=code+'_'+fid+'_diagnostic.png',status='not_semantically_reviewed')


if __name__=='__main__':
    run()
    mapping=node_plot('uNb9QFRL6hY-36',assisted=True)
    write_json(OUT/'order_review_request.json',dict(image='uNb9QFRL6hY-36',
        status='user_requested_x_sort',nodes=mapping,historical_five_node_order=[1,2,3,4,5],
        scope='用户明确该图六节点按x递增排序；节点、票数和坐标不变。',
        order_source='user_rule_not_automatic_topology_validation'))
    node_plot('uNb9QFRL6hY-04',assisted=True)
    cases=[('uNb9QFRL6hY-04','node_000'),('B6ByNegPMKs-11','node_002'),('jtcxE69GiFV-26','node_006'),('uNb9QFRL6hY-36','node_002')]
    cases=[diagnostic_plot(*case) for case in cases]
    reviews=json.loads((OUT/'user_review.json').read_text(encoding='utf-8'))
    for case in cases:
        decisions=[r for r in reviews['decisions'] if (r['image'],r['feature_id'])==(case['image'],case['node'])]
        if decisions:case.update(status=decisions[-1]['decision'],review_source='user_review.json')
    write_json(OUT/'diagnostic_review_cases.json',cases)
    for code in ['7y3sRwLe3Va-04','B6ByNegPMKs-18','q9vSo1VnCiC-23','uNb9QFRL6hY-06','yqstnuAEVhm-25']:
        node_plot(code)
    workflow()
    panel_path=OUT/'workflow/panel.json'
    if panel_path.exists():
        panel=json.loads(panel_path.read_text(encoding='utf-8'))
        for code in panel['new_images']+panel['controls']:workflow_plot(code)
