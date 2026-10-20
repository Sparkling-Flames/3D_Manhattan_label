"""v2固定人数换类及固定成员块增人：逐观察追踪投票、对应与连接。"""
from collections import Counter, defaultdict
from pathlib import Path
import argparse
import os
import sys

import numpy as np
import pandas as pd

from .personnel_composition_followup_20261019 import ROOT, FUSION, read, save, csv
from .personnel_vote_trace_20261020 import observations, trace_groups

OUT = ROOT / 'research/fusion/fusion_change_mechanisms_20261020'
PRO = ROOT / 'research/workers/personnel_interchangeability_20261020/interchangeability_20261020'


def partition_changed(before, after, retained):
    def partition(groups):
        return {frozenset(o for o in observations(g) if o[0] in retained)
                for g in groups} - {frozenset()}
    return partition(before) != partition(after)


def step_mechanisms(before, after, retained):
    rows = trace_groups(before['identity_groups'], after['identity_groups'], retained)
    one = [r for r in rows if r['kind'] == 'one_to_one']
    rising = after['minimum_support'] > before['minimum_support']
    return dict(retained_partition_changed=partition_changed(before['identity_groups'], after['identity_groups'], retained),
                threshold_only_losses=sum(rising and r['selected_before'] == 1 and r['selected_after'] == 0
                                          and r['support_before'] == r['support_after'] for r in one),
                new_vote_gains=sum(r['selected_before'] == 0 and r['selected_after'] == 1
                                   and r['support_after'] > r['support_before'] for r in one),
                group_components=rows)


def restore_reviewed_identity(state, keys):
    """局部人审最小对照：只移动指定观察，其余观察和全N投票均保留。"""
    import copy
    from .fixed_identity_location_20261007 import median_pair
    from .ring_correspondence_20261007 import assemble_fusion
    result=copy.deepcopy(state);groups=[];reviewed=[];mapping={}
    for g in state['identity_groups']:
        picked=[m for m in g['members'] if (m['worker'],m['source_pair_index']) in keys]
        reviewed.extend(picked)
        remaining=[m for m in g['members'] if (m['worker'],m['source_pair_index']) not in keys]
        if remaining:
            groups.append(dict(feature_id=g['feature_id'],members=remaining,support=len(remaining),
                               selected=2*len(remaining)>=state['n'],center=median_pair(remaining)))
    assert observations(dict(members=reviewed))==keys
    assert len({m['worker'] for m in reviewed})==len(reviewed)
    for m in reviewed:mapping[m['id'],m['pair_index']]='reviewed_target'
    groups.append(dict(feature_id='reviewed_target',members=reviewed,support=len(reviewed),
                       selected=2*len(reviewed)>=state['n'],center=median_pair(reviewed)))
    for row in result['assignments']:
        row['feature_ids']=[mapping.get((row['id'],i),fid) for i,fid in enumerate(row['feature_ids'])]
    result['identity_groups']=groups
    assert set().union(*(observations(g) for g in groups))==set().union(*(observations(g) for g in state['identity_groups']))
    result.update(assemble_fusion(groups,result['assignments']))
    return result


def engine():
    os.environ['PERSONNEL_V2_REPOSITORY'] = str(ROOT)
    sys.path.insert(0, str(FUSION))
    import fusion_engine
    return fusion_engine


def records_from_evidence(records):
    return [dict(id=x['object_id'], object_id=x['object_id'], worker=x['worker_id'], worker_id=x['worker_id'],
                 points=x['points_1024x512'], source_pair_indices=x['coordinate_evidence'].get('ordered_source_pair_indices'),
                 ring_confirmed=x['ring_confirmed'], order_status=x['order_status']) for x in records]


def inventory(records):
    result = []
    grouped = defaultdict(list)
    for r in records:
        if not r['is_oos']:
            grouped[r['image_id']].append(r)
    for iid, rs in grouped.items():
        r = rs[0]
        result.append(dict(image_id=iid, image=r['image_code'], building=r['building_id'], doorway=r['is_doorway'],
                           records=len(rs), workers=len({x['worker_id'] for x in rs}),
                           quality_usable=sum(x['quality_usable'] for x in rs),
                           independent_vote_eligible=sum(x['independent_vote_eligible'] for x in rs),
                           processed_geometry_available=sum(bool(x['points_1024x512']) for x in rs),
                           reference_versions='|'.join(sorted({str(x['reference_version']) for x in rs}))))
    return pd.DataFrame(result)


def normalized_state(state):
    out = dict(state)
    out['identity_groups'] = [dict(g, members=[dict(m, worker=str(m['worker']),
                         source_pair_index=m['source_pair_index'] if m['source_pair_index'] is not None else m['pair_index'])
                         for m in g['members']]) for g in state['identity_groups']]
    return out


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    records = read(ROOT / 'research/statistics/v2_evidence_audit_20261019/records.json.gz')['records']
    byid = {r['object_id']: r for r in records}
    inv = inventory(records)
    csv(OUT / 'NON_OOS_INVENTORY.csv', inv)
    requests = read(PRO / 'assessment/nested_new2_requests.json.gz')
    primary = [e for e in requests['events'] if e['n'] == 13 and e['m'] == 5]
    # 事先指定已有代表图；沿冻结成员名单重放完整增人过程，不按本轮分数挑拐点。
    path_images = {'UwV83HsGsw3-22', 'q9vSo1VnCiC-30', 'B6ByNegPMKs-22', 'X7HyMhZNoso-19'}
    paths = [p for p in requests['paths'] if p['m'] == 5 and p['replicate'] == 0
             and p['outgoing_class'] == 'C02' and p['image'] in path_images]
    path_ids = {p['path_id'] for p in paths}
    path_events = [e for e in requests['events'] if e['path_id'] in path_ids]
    events = {e['event_id']: e for e in primary + path_events}
    pools = {p['pool_id']: p for p in read(FUSION / 'INPUT_SNAPSHOT.json.gz')['images']}
    classes = {w: c['class_id'] for c in read(PRO / 'reverse/assessment_interpretation/nested_new2/NEW2_CLASS_MEMBERS.json')['classes'] for w in c['worker_ids']}
    oldteams = read(OUT / 'TEAMS.json.gz') if (OUT / 'TEAMS.json.gz').exists() else {}
    oldstates = read(OUT / 'STATES.json.gz') if (OUT / 'STATES.json.gz').exists() else {}
    teams, states = {}, {}
    fe = engine()
    with fe.cached_matching(), fe.scoring_engine(fe.ENGINE / 'measurement_engine.zip', fe.ENGINE / 'working_models.py') as (scorer, models):
        for ei, e in enumerate(events.values()):
            pool = pools[e['pool_id']]
            source = {r['worker_id']: byid[r['object_id']] for r in pool['records']}
            for arm in 'ABC':
                key = e[arm + '_team_key']
                if key in teams:
                    continue
                selected = [source[w] for w in sorted(e[arm + '_workers'])]
                assert all(not x['is_oos'] for x in selected)
                if key in oldstates:
                    assert oldteams[key]['object_ids'] == [x['object_id'] for x in selected]
                    assert oldteams[key]['processed_points'] == [x['points_1024x512'] for x in selected]
                    assert oldteams[key]['reference'] == pool['reference']
                    states[key], teams[key] = oldstates[key], oldteams[key]
                    continue
                state = normalized_state(fe.compact(fe.fuse(records_from_evidence(selected), gap=fe.WORKING_GAP)['automatic']))
                score = fe.compute_score(state, pool, scorer, models)
                summary = fe.summarize_state(state)
                teams[key] = dict(team_key=key, workers=sorted(e[arm + '_workers']), object_ids=[x['object_id'] for x in selected],
                                  processed_points=[x['points_1024x512'] for x in selected], reference=pool['reference'],
                                  pool_id=e['pool_id'], image=e['image'], building=e['building'],
                                  counts=dict(Counter(classes[x['worker_id']] for x in selected)), **summary, **score)
                states[key] = state
            if ei % 20 == 0:
                print('events', ei + 1, '/', len(events), 'teams', len(teams), flush=True)
                save(OUT / 'TEAMS.json.gz', teams)
                save(OUT / 'STATES.json.gz', states)
    save(OUT / 'TEAMS.json.gz', teams)
    save(OUT / 'STATES.json.gz', states)
    save(OUT / 'DESIGN.json', dict(primary_events=primary, paths=paths, path_events=path_events,
         source='v2_evidence_audit_20261019/records.json.gz', gap=fe.WORKING_GAP,
         class_method=requests['paths'][0]['method_id'], class_semantics='Rnew2 classes, not semantic detail-retainer labels',
         path_selection='four previously displayed representative images; C02>C01 m5 replicate0, all feasible n; not population prevalence'))
    rows = []
    local = []
    for e in primary:
        for arm in 'BC':
            a, b = states[e['A_team_key']], states[e[arm + '_team_key']]
            ta, tb = teams[e['A_team_key']], teams[e[arm + '_team_key']]
            retained = set(ta['workers']) & set(tb['workers'])
            result = trace_groups(a['identity_groups'], b['identity_groups'], retained)
            one = [r for r in result if r['kind'] == 'one_to_one']
            rows.append(dict(event_id=e['event_id'], image=e['image'], building=e['building'], arm=arm,
                             direction=e['direction'], nodes_before=ta['nodes'], nodes_after=tb['nodes'],
                             B8L2_before=ta['B8L2'], B8L2_after=tb['B8L2'],
                             retained_partition_changed=partition_changed(a['identity_groups'], b['identity_groups'], retained),
                             one_to_one_losses=sum(r['selected_before'] == 1 and r['selected_after'] == 0 for r in one),
                             one_to_one_gains=sum(r['selected_before'] == 0 and r['selected_after'] == 1 for r in one),
                             complex_selected_change=any(r['selected_before'] != r['selected_after'] for r in result if r['kind'] in ('split','merge','many_to_many'))))
            local.extend(dict(r, event_id=e['event_id'], image=e['image'], arm=arm, direction=e['direction']) for r in result)
    csv(OUT / 'PRIMARY_EVENTS.csv', pd.DataFrame(rows))
    csv(OUT / 'PRIMARY_GROUP_TRANSITIONS.csv.gz', pd.DataFrame(local))
    steps = []
    for pid in sorted(path_ids):
        sequence = sorted((e for e in path_events if e['path_id'] == pid), key=lambda e:e['n'])
        for e0, e1 in zip(sequence, sequence[1:]):
            assert e1['n'] == e0['n'] + 1
            for arm in 'ABC':
                k0, k1 = e0[arm + '_team_key'], e1[arm + '_team_key']
                t0,t1 = teams[k0],teams[k1]
                assert set(t0['workers']) < set(t1['workers'])
                result = step_mechanisms(states[k0], states[k1], set(t0['workers']))
                result.pop('group_components')
                steps.append(dict(path_id=pid,image=e1['image'],building=e1['building'],arm=arm,n_from=e0['n'],n_to=e1['n'],
                             added_worker=e1['added_core_worker'],added_class=classes[e1['added_core_worker']],
                             team_before=k0,team_after=k1,nodes_before=t0['nodes'],nodes_after=t1['nodes'],
                             B8L2_before=t0['B8L2'],B8L2_after=t1['B8L2'],threshold_before=states[k0]['minimum_support'],
                             threshold_after=states[k1]['minimum_support'], **result))
    csv(OUT / 'NESTED_STEPS.csv', pd.DataFrame(steps))
    save(OUT / 'COVERAGE.json', dict(non_oos_images=len(inv),non_oos_doorway_images=int(inv.doorway.sum()),
          non_oos_records=int(inv.records.sum()),primary_events=len(primary),primary_images=len({e['image'] for e in primary}),
          primary_buildings=len({e['building'] for e in primary}),nested_paths=len(paths),nested_images=sorted({p['image'] for p in paths}),
          teams=len(teams),nested_steps=len(steps),quality_not_used_to_form_identity=True,
          input_points='current processed points, no additional preprocessing',N1_applied=False))
    print(read(OUT / 'COVERAGE.json'))


def figures():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from PIL import Image
    sys.path.insert(0, str(PRO.parent / 'analysis/composition'))
    import case_visuals as visual
    plt.rcParams.update({'font.sans-serif': ['Microsoft YaHei', 'DejaVu Sans'], 'axes.unicode_minus': False})
    teams, states = read(OUT / 'TEAMS.json.gz'), read(OUT / 'STATES.json.gz')
    design = read(OUT / 'DESIGN.json')
    events = design['primary_events']
    steps = pd.read_csv(OUT / 'NESTED_STEPS.csv')
    records = read(ROOT / 'research/statistics/v2_evidence_audit_20261019/records.json.gz')['records']
    byid = {r['object_id']:r for r in records}
    cls = {w:c['class_id'] for c in read(PRO / 'reverse/assessment_interpretation/nested_new2/NEW2_CLASS_MEMBERS.json')['classes'] for w in c['worker_ids']}
    colors = {'C01':'#29c4ff', 'C02':'#ff8b26'}
    summary = []

    def plot(name, keys, labels, bounds, focus_ids, title):
        imid = byid[teams[keys[0]]['object_ids'][0]]['image_id']
        photo = np.asarray(Image.open(next(ROOT.glob('data/mp3d_layout/*/img/' + imid + '.png'))).convert('RGB'))
        fig, axes = plt.subplots(3, len(keys), figsize=(5.2*len(keys), 10.6), squeeze=False,
                                 gridspec_kw={'height_ratios':[1.05, 1.45, .85]})
        for j, (key, label, ids) in enumerate(zip(keys, labels, focus_ids)):
            team, state = teams[key], states[key]
            selected = [g for g in state['identity_groups'] if g['selected']]
            localgroups = [g for g in state['identity_groups'] if g['feature_id'] in ids]
            votes = '；'.join(g['feature_id'].replace('node_', 'G') + ':' + str(g['support']) + ('留' if g['selected'] else '缺') for g in localgroups)
            row = dict(figure=name,panel=label,image=team['image'],team_key=key,k=team['k'],threshold=state['minimum_support'],
                       nodes=team['nodes'],B8L2=team['B8L2'],class_counts=team['counts'],focus_votes=votes,
                       complete_projected_source_ring_support=max((a['support'] for a in state['ring_diagnostics']['alternatives']),default=0),
                       minimum_direct_edge_support=min((e['direct_support'] for e in state['ring_diagnostics']['edges']),default=None),
                       minimum_projected_edge_support=min((e['projected_support'] for e in state['ring_diagnostics']['edges']),default=None))
            summary.append(row)
            for r in range(2):
                ax = axes[r,j]
                visual._erp_background(ax,photo)
                if r == 0:
                    for oid in team['object_ids']:
                        source=byid[oid]
                        visual._erp_edges(ax,source['points_1024x512'],colors[cls[source['worker_id']]],linewidth=.65,alpha=.34)
                else:
                    # 下排只高亮本次解释的来源组，避免整池原答遮住局部。
                    for g in localgroups:
                        for m in g['members']:
                            p=np.asarray(m['points'])
                            ax.plot(p[:,0],p[:,1],color=colors[cls[m['worker']]],alpha=.60,lw=.8)
                visual._erp_edges(ax,team['reference']['points_1024x512'],'#d6ffb1',linewidth=1.2,reference=True)
                if state['candidate']['points']:
                    visual._erp_edges(ax,state['candidate']['points'],'#ff3b80',linewidth=2.1,markers=True)
                if r == 1:
                    ax.set_xlim(bounds[:2]);ax.set_ylim(bounds[3],bounds[2])
                    for gi,g in enumerate(localgroups):
                        p=np.asarray(g['center']);mid=p.mean(axis=0)
                        ax.annotate(g['feature_id'].replace('node_','G')+': '+str(g['support'])+('留' if g['selected'] else '缺'),
                                    xy=mid,xytext=(.05,.85-gi*.16),textcoords='axes fraction',fontsize=8,
                                    color='white',bbox=dict(facecolor='#202838',alpha=.88,pad=2,edgecolor='none'),
                                    arrowprops=dict(arrowstyle='-',color='white',lw=.7))
                else:
                    ax.set_title(label + f"\nn={team['k']}，{team['nodes']}节点，B8L2={team['B8L2']:.2f}",fontsize=11)
                ax.set_xticks([]);ax.set_yticks([])
            ax=axes[2,j];ax.axis('off')
            lines=[f"类别人数：{team['counts']}",f"门槛：{state['minimum_support']}票；局部组：{votes}",
                   f"完整来源投影环支持：{row['complete_projected_source_ring_support']}人",
                   f"边支持最小值：原邻接{row['minimum_direct_edge_support']}／投影邻接{row['minimum_projected_edge_support']}"]
            for g in localgroups:
                count=Counter(cls[m['worker']] for m in g['members'])
                lines.append(g['feature_id'].replace('node_', 'G')+f"：C01 {count['C01']}票 + C02 {count['C02']}票")
            ax.text(.01,.97,'\n'.join(lines),va='top',fontsize=9,linespacing=1.6,wrap=True)
        fig.suptitle(title+'\n上：完整原答与融合；中：局部来源与融合；下：票数及连接账本',fontsize=15,y=.985)
        fig.text(.035,.025,'原答：C01蓝／C02橙；融合：玫红；固定参考：浅绿。组号只在各团队内部有效。\n曲线按原邻接画球面短弧；参考仅用于比较，不参与成组与投票。',fontsize=9)
        fig.subplots_adjust(left=.025,right=.985,top=.89,bottom=.09,wspace=.09,hspace=.13)
        fig.savefig(OUT/(name+'.png'),dpi=155);plt.close(fig)

    # 已有正、反例的精确团队；新增的是来源与局部投票解释。
    for filename, focus, bounds, title in [
        ('S07_reverse_new2', [['node_001','node_005'],['node_001','node_006'],['node_001','node_005']], [425,605,100,385], 'Uw-22：固定13人，换类使两处局部节点过票'),
        ('S10_reverse_counterexample', [['node_004','node_006','node_009'],['node_004','node_006','node_007'],['node_005']], [348,410,190,365], 'q9-30：相同类别配比，具体成员仍改变节点是否入选')]:
        case=read(PRO/'cases'/(filename+'.json'));e=case['event']
        keys=[e[a+'_team_key'] for a in 'ABC']
        plot(filename,keys,['A 原团队','B 同类换5人','C 跨类换5人'],bounds,focus,title)

    e=next(e for e in design['path_events'] if e['image']=='B6ByNegPMKs-22' and e['n']==13)
    keys=[e[a+'_team_key'] for a in 'ABC']
    plot('B622_position',keys,['A 原团队','B 同类换5人','C 跨类换5人'],[230,275,220,300],
         [['node_000','node_001']]*3,'B6-22：四处墙角全部13票，差异仍来自融合位置')
    csv(OUT/'POSITION_ONLY_SCORES.csv',pd.DataFrame([dict(arm=a,team_key=k,**{f:teams[k][f] for f in
        ['k','nodes','B8L2','D10','iou_2d','omission','extension','Hmean','Hcenter','S_bottom_deg']}) for a,k in zip('ABC',keys)]))

    triplets=[('UwV83HsGsw3-22','C',[16,17,18],[430,600,100,390],
               [['node_001','node_005']]*3,'Uw22_addition','Uw-22：同一成员块增人，8票节点先失选再恢复'),
              ('X7HyMhZNoso-19','A',[8,9,10],[445,525,90,400],
               [['node_006','node_007']]*3,'X719_addition','X7-19：增人使凹槽消失又重现，参考表现反向变化'),
              ('q9vSo1VnCiC-30','B',[16,17,18],[348,410,190,365],
               [['node_005'],['node_005','node_006','node_007'],['node_005','node_006']],
               'q930_regrouping','q9-30：新增一人后原13份观察被重新拆组')]
    for image,arm,ns,bounds,focus,name,title in triplets:
        es=[e for e in design['path_events'] if e['image']==image]
        keys=[next(e[arm+'_team_key'] for e in es if e['n']==n) for n in ns]
        plot(name,keys,[f'{arm}臂：{n}人' for n in ns],bounds,focus,title)
    csv(OUT/'FIGURE_PANELS.csv',pd.DataFrame(summary))

    # 只改变旧身份的投票分母；不引入新成员，诊断旧13票是否仍足以过新门槛。
    from .ring_correspondence_20261007 import assemble_fusion
    import copy
    r=steps[(steps.image=='q9vSo1VnCiC-30') & (steps.arm=='B') & (steps.n_to==17)].iloc[0]
    old,new=states[r.team_before],states[r.team_after]
    groups=copy.deepcopy(old['identity_groups'])
    for g in groups:g['selected']=g['support']>=new['minimum_support']
    control=assemble_fusion(groups,old['assignments'])
    oldgroup=next(g for g in old['identity_groups'] if g['feature_id']=='node_005')
    allocation=[dict(group=g['feature_id'],total_support=g['support'],old13_observations=len(observations(g)&observations(oldgroup)))
                for g in new['identity_groups'] if observations(g)&observations(oldgroup)]
    assert control['candidate']['points']==old['candidate']['points']
    save(OUT/'FROZEN_IDENTITY_CONTROL.json',dict(image=r.image,old_n=16,new_n=17,old_support=13,new_threshold=9,
         old13_allocation=allocation,control_points=control['candidate']['points'],automatic_points=new['candidate']['points'],
         control_equals_old_geometry=True,control_B8L2=teams[r.team_before]['B8L2'],automatic_B8L2=teams[r.team_after]['B8L2'],
         interpretation='Diagnostic only: rethreshold old groups, coordinates and source rings; entrant observations not assigned. Not a replacement fusion policy or proof that all nearby observations share a physical target.'))
    # 只请求一处语义判断；每列保留一份完整原答，并叠加该组来自旧13份的全部观察。
    photo=np.asarray(Image.open(next(ROOT.glob('data/mp3d_layout/*/img/'+byid[teams[r.team_after]['object_ids'][0]]['image_id']+'.png'))).convert('RGB'))
    fig,axes=plt.subplots(2,3,figsize=(14,8.6),gridspec_kw={'height_ratios':[1,1.5]})
    review_sources=[]
    for j,(item,color) in enumerate(zip(allocation,['#28e1ff','#ff9326','#c27bff'])):
        g=next(g for g in new['identity_groups'] if g['feature_id']==item['group'])
        members=[m for m in g['members'] if (m['worker'],m['source_pair_index']) in observations(oldgroup)]
        representative=min(members,key=lambda m:np.linalg.norm(np.asarray(m['points'])-np.asarray(g['center'])))
        source=byid[representative['id']]
        for i in range(2):
            ax=axes[i,j];visual._erp_background(ax,photo)
            visual._erp_edges(ax,source['points_1024x512'],'#ffe766',linewidth=1.1)
            if i==0:
                p=np.asarray(representative['points']);ax.plot(p[:,0],p[:,1],color=color,lw=3)
                ax.set_title(f"第{j+1}列：{representative['worker']}完整原答\n彩色为待判断点对，黄色为其余原答",fontsize=10)
            else:
                for m in members:
                    p=np.asarray(m['points']);ax.plot(p[:,0],p[:,1],color=color,lw=1.2,alpha=.85)
                ax.set_xlim(348,410);ax.set_ylim(365,190)
                ax.set_title(f"{item['group']}：旧13份中有{len(members)}份在此组",fontsize=10)
            ax.set_xticks([]);ax.set_yticks([])
        review_sources.append(dict(group=g['feature_id'],representative_object_id=source['object_id'],worker=source['worker_id'],
                                   members=[dict(object_id=m['id'],worker=m['worker'],source_pair_index=m['source_pair_index']) for m in members]))
    fig.suptitle('q9-30：三列是否都想标餐桌后方同一个墙角？\n只判断目标身份；上端／下端位置偏差可以保留，不要求选择算法参数',fontsize=14)
    fig.tight_layout(rect=(0,0,1,.91))
    if not (OUT/'q930_local_review.png').exists():fig.savefig(OUT/'q930_local_review.png',dpi=155)
    plt.close(fig)
    if not (OUT/'HUMAN_REVIEW.json').exists():
        save(OUT/'HUMAN_REVIEW.json',dict(status='pending',question='三列是否都想标同一实体墙角，还是有不同停止／转折目标？',
                                       sources=review_sources,no_new_judgment_assumed=True))
    review=read(OUT/'HUMAN_REVIEW.json')
    if review['status']=='same_intended_corner_probable':
        assisted=restore_reviewed_identity(new,observations(oldgroup))
        fe=engine()
        with fe.scoring_engine(fe.ENGINE/'measurement_engine.zip',fe.ENGINE/'working_models.py') as (scorer,models):
            score=fe.compute_score(assisted,dict(reference=teams[r.team_after]['reference']),scorer,models)
        key=r.team_after+'__local_review'
        states[key]=assisted
        teams[key]=dict(teams[r.team_after],team_key=key,**fe.summarize_state(assisted),**score)
        save(OUT/'LOCAL_REVIEW_CONTROL.json',dict(status='human_assisted_mechanism_control',user_feedback=review['verbatim'],
             actual_n=17,minimum_support=9,restored_old_observations=13,all_original_observations_retained=True,
             automatic_team=r.team_after,automatic_nodes=teams[r.team_after]['nodes'],automatic_B8L2=teams[r.team_after]['B8L2'],
             assisted_nodes=teams[key]['nodes'],assisted_B8L2=score['B8L2'],state=assisted,score=score,
             boundary='Only reviewed old13 are regrouped; other17-person observations retained; no automatic generalization.'))
        plot('q930_local_control',[r.team_after,key],['原17人自动融合','同17人：仅恢复已审13份归属'],[348,410,190,365],
             [['node_005','node_006','node_007'],['reviewed_target']],'q9-30最小人审对照：保持全部17人和9票门槛')
        csv(OUT/'FIGURE_PANELS.csv',pd.DataFrame(summary))
    f=pd.read_csv(OUT/'PRIMARY_EVENTS.csv')
    f['node_count_changed']=f.nodes_before.ne(f.nodes_after)
    cols=['node_count_changed','retained_partition_changed','one_to_one_losses','one_to_one_gains','complex_selected_change']
    summary=f.groupby(['direction','arm'])[cols].sum().reset_index()
    summary=summary.merge(f.groupby(['direction','arm']).size().rename('events').reset_index(),on=['direction','arm'])
    csv(OUT/'PRIMARY_MECHANISM_COUNTS.csv',summary)
    # 每个图和建筑各一票；这些是已选定面板的描述，不作总体发生率。
    per_image=f.groupby(['direction','arm','building','image'])[cols].mean().reset_index()
    equal_building=per_image.groupby(['direction','arm','building'])[cols].mean().groupby(['direction','arm']).mean().reset_index()
    csv(OUT/'PRIMARY_MECHANISM_BUILDING_EQUAL.csv',equal_building)
    local_rows=[]
    event=read(PRO/'cases/S07_reverse_new2.json')['event']
    for arm,ids in zip('ABC',[['node_001','node_005'],['node_001','node_006'],['node_001','node_005']]):
        key=event[arm+'_team_key'];st=states[key];team=teams[key]
        groups=[next(g for g in st['identity_groups'] if g['feature_id']==gid) for gid in ids]
        w1,w2=[{m['worker'] for m in g['members']} for g in groups]
        for label,workers in [('both',w1&w2),('one',(w1|w2)-(w1&w2)),('neither',set(team['workers'])-(w1|w2))]:
            local_rows.append(dict(image=team['image'],arm=arm,team_key=key,local_pattern=label,workers='|'.join(sorted(workers)),
                                   n=len(workers),C01=sum(cls[w]=='C01' for w in workers),C02=sum(cls[w]=='C02' for w in workers)))
    csv(OUT/'LOCAL_PATTERN_SUPPORT.csv',pd.DataFrame(local_rows))
    fig,axes=plt.subplots(2,2,figsize=(12,7.4),layout='constrained')
    from matplotlib.ticker import MaxNLocator
    for ax,(image,g) in zip(axes.flat,steps.groupby('image')):
        for arm,color in zip('ABC',['#098da8','#d87918','#944ab3']):
            h=g[g.arm==arm].sort_values('n_to');first=h.iloc[0]
            ns=[first.n_from,*h.n_to];qs=[first.B8L2_before,*h.B8L2_after]
            ax.plot(ns,qs,'-o',color=color,ms=3,label=arm)
            for _,x in h.iterrows():
                if x.threshold_only_losses:
                    ax.scatter([x.n_to],[x.B8L2_after],marker='x',s=100,color='#c52842',zorder=6)
        ax.set_title(image);ax.set_xlabel('团队人数（同一路径保留原成员，三臂加入同一人）');ax.set_ylabel('B8L2：相对固定参考');ax.grid(alpha=.15);ax.legend()
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    fig.suptitle('固定成员块的真实增人过程：红叉表示至少一组票数不变、因门槛提高而失选\n四张代表图用于机制解释；不是同一配比、不是随机总体均值',fontsize=12)
    fig.savefig(OUT/'addition_paths.png',dpi=165);plt.close(fig)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--figures-only',action='store_true')
    args=parser.parse_args()
    if not args.figures_only:
        run()
    figures()
