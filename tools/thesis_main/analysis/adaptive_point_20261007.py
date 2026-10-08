"""Local incidence-adaptive experiment, not a validated correspondence solver.

Use independent endpoint estimates only in overlap components containing one
majority top group, one majority bottom group and at most one majority bound
group. Otherwise retain the bound baseline for that component. No GT access.
"""
import copy
import math
from collections import defaultdict

from .point_route_panel_20261005 import paired_identity, member_key
from .global_pair_consensus_20261004 import _ring_diagnostics
from .research_round_20260929 import reconstruct


def choose_components(paired, tops, bottoms):
    nodes=[(kind,g) for kind,groups in [('paired',paired),('top',tops),('bottom',bottoms)] for g in groups]
    owners=defaultdict(set)
    for i,(_,g) in enumerate(nodes):
        for m in g['members']:owners[member_key(m)].add(i)
    unseen=set(range(len(nodes))); selected=[]; trace=[]
    while unseen:
        seed=min(unseen); component={seed}; todo=[seed];unseen.remove(seed)
        while todo:
            i=todo.pop()
            neighbors=set().union(*(owners[member_key(m)] for m in nodes[i][1]['members']))
            for j in sorted(neighbors & unseen):
                unseen.remove(j);component.add(j);todo.append(j)
        parts={side:[nodes[i][1] for i in sorted(component) if nodes[i][0]==side] for side in ('paired','top','bottom')}
        joint=[]; decision='paired_fallback'; reason='missing_or_competing_endpoint_groups'
        if len(parts['top'])==len(parts['bottom'])==1 and len(parts['paired'])<=1:
            t,b=parts['top'][0],parts['bottom'][0]
            bkeys={member_key(m) for m in b['members']}
            joint=[m for m in t['members'] if member_key(m) in bkeys]
            if joint:
                g,reason=paired_identity(t,b,joint,len(selected))
                if g is not None:
                    g.update(local_mode='split',members=joint)
                    selected.append(g);decision='independent_unique'
        if decision=='paired_fallback':
            for p in parts['paired']:
                g=copy.deepcopy(p)
                g.update(local_mode='paired',top_support=p['support'],bottom_support=p['support'],joint_support=p['support'],top_members=p['members'],bottom_members=p['members'],joint_members=p['members'])
                selected.append(g)
        trace.append(dict(component=len(trace),choice=decision,reason=reason,
                          paired_n=len(parts['paired']),top_n=len(parts['top']),bottom_n=len(parts['bottom']),
                          source_groups={k:[g['feature_id'] for g in v] for k,v in parts.items()}))
    for i,g in enumerate(selected):g['feature_id']=f'hybrid_{i:03d}'
    return selected,trace


def adaptive_candidate(records, threshold, routes):
    minimum=math.ceil(len(records)/2)
    p=[g for g in routes['paired']['identity_groups'] if g['support']>=minimum]
    t=[g for g in routes['split_unique']['endpoint_groups']['top'] if g['support']>=minimum]
    b=[g for g in routes['split_unique']['endpoint_groups']['bottom'] if g['support']>=minimum]
    groups,trace=choose_components(p,t,b)
    assignments=copy.deepcopy(routes['paired']['assignments'])
    mapping={member_key(m):g['feature_id'] for g in groups for m in g['joint_members']}
    for a in assignments:
        a['feature_ids']=[mapping.get((str(a['id']),i),f"unresolved:{a['id']}:{i}") for i in range(len(a['feature_ids']))]
    candidate=dict(status='unavailable',reason=None,points=None,footprint=None,ring_confirmed=False,order_status='default_x_exploratory_unconfirmed',source_pair_indices=None,source_point_indices=None,source_point_labels=None)
    ring=None
    if len(groups)<3:candidate['reason']='fewer_than_three_selected_pairs'
    elif any(g['center'] is None for g in groups):candidate['reason']='ambiguous_periodic_center'
    else:
        groups,ring=_ring_diagnostics(groups,assignments,len(records),minimum)
        if ring['ambiguous_x_pairs']:candidate['reason']='ambiguous_shared_x_order'
        else:
            candidate['points']=[v for g in groups for v in g['center']]
            geometry=reconstruct(candidate,coordinate_convention='continuous')
            candidate.update(geometry_status=geometry['status'],geometry_issues=geometry.get('issues',[]))
            if geometry['status']=='ok':
                candidate.update(status='geometry_review',footprint=geometry['floor'].tolist(),reason='adaptive_identity_and_new_ring_unconfirmed')
            else:candidate['reason']='invalid_candidate_ring:'+str(geometry['reason'])
    return dict(route='adaptive_incidence_v1',threshold_deg=threshold,status=candidate['status'],candidate=candidate,
                vote_denominator=len(records),minimum_support=minimum,paired_identities=groups,assignments=assignments,
                components=trace,ring_diagnostics=ring,
                policy='one selected top/one bottom and <=one bound group in source-overlap component -> split; otherwise bound baseline; unresolved endpoints remain logged, not filled',
                limitation='Incidence uniqueness is not semantic correctness; this is one operationalization of adaptive fusion, not the entire hybrid idea.')


def run():
    import json
    import numpy as np
    from .point_route_panel_20261005 import build_routes
    from .research_artifact_io import ROOT, read_csv, write_csv, write_json
    from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
    from tools.thesis_main.data_prep.project_public_research_20260929 import project_bundle
    out=ROOT/'analysis_results/adaptive_point_20261007';out.mkdir(exist_ok=True)
    source=ROOT/'research/fast_research_handoff_20261006/dot_return/nine_image_study/inputs/inputs.json'
    panel=json.loads(source.read_text(encoding='utf-8'))['images']
    plan=dict(schema='adaptive_point_experiment_v1',images=[i['image'] for i in panel],thresholds=[5,9,12],
              views=['shared_x','late_x'],routes=['paired','split_unique','bottom_anchor','top_anchor','adaptive_incidence_v1'],
              denominator='Same nine development pools / 150 independent records; ceil(N/2); no new collection or per-image GT tuning.',
              adaptive_rule='Connected components of majority bound/top/bottom groups linked by original observation identity. One top and one bottom, <=one bound, nonempty original-pair incidence -> independent; else bound baseline. No density threshold fitted.',
              variables='Adaptive changes selected identities/members and pairing; coordinate median and x-order fixed. late_x separately changes coordinates used for matching and timing of x projection, not source ring or y.',
              raw_scope='Restore before_preprocessing_points via ordered_source_point_indices; does NOT undo historical repairs, cleaning, borrowing, canonical snapshot or source-pair decisions.',
              comparison='Coverage over all attempts; reference error comparisons on common available states, separately per view/threshold/reference; no success-only pooled ranking.',
              order='Freeze plan -> build without GT -> serialize -> evaluate; all images previously seen, not blind validation.')
    write_json(out/'PLAN.json',plan)
    bundle=load_current_bundle();current,ids=project_bundle(bundle)
    objects={ids['records'][o['object_id']]:o for o in bundle['data']['objects']}
    current_images={i['code']:i for i in current['images']}
    inputs=[];input_rows=[];states=[]
    for im in panel:
        code=im['image'];records=im['records'];new={r['id']:r for r in current_images[code]['annotations']};raw={}
        for r in records:
            o=objects[r['id']]
            assert r['points']==new[r['id']]['points']
            assert r['independent'] and r['consensus_eligible'] and r['condition']=='manual'
            before=np.asarray(o['before_preprocessing_points'],float)[o['ordered_source_point_indices']]
            main=np.asarray(r['points'],float)
            assert np.array_equal(before[:,1],main[:,1])
            pairs=before.reshape(-1,2,2);dx=(pairs[:,1,0]-pairs[:,0,0]+512)%1024-512
            np.testing.assert_allclose((pairs[:,0,0]+dx/2)%1024,main[::2,0],atol=1e-8)
            raw[r['id']]=before.tolist()
            input_rows.append(dict(image=code,record=r['id'],worker=r['worker'],pairs=len(pairs),
                                   nonshared_pairs=int(sum(abs(dx)>1e-8)),max_pair_x_gap_px=float(abs(dx).max()),mean_pair_x_gap_px=float(abs(dx).mean()),
                                   before_equals_export=o['before_preprocessing_points']==o['original_export_points']))
        inputs.append(dict(image=code,image_id=im['image_id'],records=records,before_shared_x=raw))
        for view in plan['views']:
            for theta in plan['thresholds']:
                routes=build_routes(records,theta,endpoint_points=raw if view=='late_x' else None)
                routes['adaptive_incidence_v1']=adaptive_candidate(records,theta,routes)
                for route,result in routes.items():
                    states.append(dict(image=code,n=len(records),view=view,threshold=theta,route=route,result=result))
        print(code,'built',flush=True)
    write_csv(out/'input_comparison.csv',input_rows)
    write_json(out/'inputs.json',dict(images=inputs))
    write_json(out/'candidates.json',dict(states=states))
    # Reference access is confined to the evaluation after candidates are saved.
    refs=[dict(image=im['image'],references=current_images[im['image']]['references']) for im in panel]
    write_json(out/'references.json',dict(images=refs))
    evaluate(out)
    write_json(out/'field_contract.json',dict(
        schema='adaptive_point_experiment_v1',plan='PLAN.json',inputs='inputs.json and input_comparison.csv; before_shared_x is a coordinate sensitivity view, not a replacement canonical input',
        states='All 270 image/view/threshold/route states retained. geometry_review and ok both mean geometry available, not semantic approval.',
        identity='adaptive component graph over majority groups; top/bottom/joint support separate; binding fallback may omit unmatched endpoint observations with explicit component trace',
        centers='Existing medoid-anchored coordinate median; late_x estimates each endpoint x then periodic midpoint. Same-member differences across views can be projection/median noncommutativity, not identity gains.',
        metrics='Post-construction reference versions separate. D=normalized symmetric difference, IoU/centroid, top/bottom same-longitude angular MAE where Ring domain permits. Not corner RMSE.',
        human='Known development relations only, not complete semantic gold. Correct triples together is not certification of remaining cluster members.',
        mutations='Only opt-in endpoint coordinate view added to existing helpers; default shared-x calculations preserved by tests. No source/GT/eligibility edits.'))
    deliver(out)
    plot_cases(out)


def endpoint_sets(result,route,side,selected=True):
    if route=='adaptive_incidence_v1':
        return [{member_key(m) for m in g[side+'_members']} for g in result['paired_identities']]
    groups=result['endpoint_groups'][side] if route=='split_unique' else result['identity_groups']
    return [{member_key(m) for m in g['members']} for g in groups if not selected or g['support']>=result['minimum_support']]


def evaluate(out):
    import json
    from shapely.geometry import Polygon
    from .research_artifact_io import ROOT,write_csv,write_json
    from .layout_reliability_20261005.arc_consensus import Ring,Unsupported,area_scores
    from .layout_reliability_20261005.continuous_metrics import fixed_longitude
    data=json.loads((out/'candidates.json').read_text(encoding='utf-8'))['states']
    refs={im['image']:im['references'] for im in json.loads((out/'references.json').read_text(encoding='utf-8'))['images']}
    prepared={}
    for code,rr in refs.items():
        for ref in rr:
            geo=reconstruct(ref,coordinate_convention='continuous')
            prepared[code,ref['version']]=(ref,Polygon(geo['floor']) if geo['status']=='ok' else None)
    reviews=json.loads((ROOT/'research/point_route_review_20261006/human_review.json').read_text(encoding='utf-8'))['reviews']
    human=[];rows=[];coverage=[]
    for state in data:
        result=state['result'];c=result['candidate'];ring=result.get('ring_diagnostics') or {}
        base={k:state[k] for k in ('image','n','view','threshold','route')}
        base.update(status=c['status'],reason=c.get('reason'),pair_count=len(c.get('points') or [])//2,
                    unsupported_edges=ring.get('unsupported_edge_count'),below_majority_edges=ring.get('below_majority_edge_count'),
                    independent_components=sum(x['choice']=='independent_unique' for x in result.get('components',[])),
                    fallback_components=sum(x['choice']=='paired_fallback' for x in result.get('components',[])))
        coverage.append(base)
        for review in reviews:
            if review['image']!=state['image']:continue
            keys=set(zip(review['record_ids'],review['processed_pair_indices']))
            for side in ('top','bottom'):
                groups=endpoint_sets(result,state['route'],side)
                together=any(keys<=g for g in groups)
                bad=(review['record_ids'][-1],review.get('rejected_previous_purple_processed_pair_index',-999))
                human.append(dict(**{k:base[k] for k in ('image','view','threshold','route')},side=side,known_relation=review['relation'],
                                  selected_known_triple_together=together,
                                  before_vote_known_triple_together=any(keys<=g for g in endpoint_sets(result,state['route'],side,selected=False)) if state['route']!='adaptive_incidence_v1' else None,
                                  selected_triple_with_rejected=any(keys<=g and bad in g for g in groups),
                                  selected_unb_lower_upper_target_mixed=any((review['record_ids'][0],review['processed_pair_indices'][0]) in g and any(k in g for k in list(keys) if k[0]!=review['record_ids'][0]) for g in groups) if review['case_id']=='unb_upper' and side=='top' else None))
        for ref in refs[state['image']]:
            ref,g=prepared[state['image'],ref['version']]
            r=dict(base,version=ref['version'],D=None,iou=None,O=None,E=None,centroid_h=None,top_mae_deg=None,bottom_mae_deg=None,boundary_status='candidate_or_reference_unavailable')
            if c['status']!='unavailable' and g is not None:
                poly=Polygon(c['footprint']);m=area_scores(poly,g)
                r.update(D=(m['omission_h2']+m['extension_h2'])/g.area,iou=m['iou'],O=m['omission_h2']/g.area,E=m['extension_h2']/g.area,centroid_h=m['centroid_distance_h'])
                try:
                    Ring(c);Ring(ref);bm=fixed_longitude(c,ref)
                    r.update(top_mae_deg=bm['top_mean_abs_px']*180/512,bottom_mae_deg=bm['bottom_mean_abs_px']*180/512,boundary_status='ok')
                except Unsupported as e:r['boundary_status']=str(e)
            rows.append(r)
    write_csv(out/'coverage.csv',coverage);write_csv(out/'metrics.csv',rows);write_csv(out/'human_relations.csv',human)


def deliver(out):
    import json
    from statistics import mean
    from .research_artifact_io import ROOT,read_csv,write_csv
    m=read_csv(out/'metrics.csv'); coverage=read_csv(out/'coverage.csv')
    comparisons=[]
    idx={(r['image'],r['view'],r['threshold'],r['route'],r['version']):r for r in m}
    for view in ('shared_x','late_x'):
        for threshold in (5,9,12):
            for version in sorted({r['version'] for r in m}):
                for route in ('split_unique','bottom_anchor','top_anchor','adaptive_incidence_v1'):
                    rr=[r for r in m if (r['view'],r['threshold'],r['route'],r['version'])==(view,str(threshold),route,version)]
                    for metric in ('D','top_mae_deg','bottom_mae_deg'):
                        pairs=[(r,idx[r['image'],view,str(threshold),'paired',version]) for r in rr]
                        common=[(a,b) for a,b in pairs if a[metric]!='' and b[metric]!='']
                        comparisons.append(dict(view=view,threshold=threshold,version=version,route=route,metric=metric,
                                                attempted=len(rr),common=len(common),
                                                mean_delta=mean(float(a[metric])-float(b[metric]) for a,b in common) if common else None,
                                                better=sum(float(a[metric])<float(b[metric])-1e-10 for a,b in common),
                                                worse=sum(float(a[metric])>float(b[metric])+1e-10 for a,b in common),
                                                images='|'.join(a['image'] for a,b in common)))
    write_csv(out/'paired_comparisons.csv',comparisons)
    view_comparisons=[]
    for early in m:
        if early['view']!='shared_x':continue
        late=idx[early['image'],'late_x',early['threshold'],early['route'],early['version']]
        view_comparisons.append(dict(image=early['image'],threshold=early['threshold'],route=early['route'],version=early['version'],
                                     early_available=early['status']!='unavailable',late_available=late['status']!='unavailable',
                                     D_late_minus_early=float(late['D'])-float(early['D']) if early['D'] and late['D'] else None,
                                     top_late_minus_early=float(late['top_mae_deg'])-float(early['top_mae_deg']) if early['top_mae_deg'] and late['top_mae_deg'] else None,
                                     bottom_late_minus_early=float(late['bottom_mae_deg'])-float(early['bottom_mae_deg']) if early['bottom_mae_deg'] and late['bottom_mae_deg'] else None))
    write_csv(out/'input_view_comparisons.csv',view_comparisons)
    names=dict(paired='绑定',split_unique='独立unique',bottom_anchor='下锚混合',top_anchor='上锚混合',adaptive_incidence_v1='局部自适应v1')
    lines=['# 上下融合三路线与共享x时机实验','',
        '2026-10-07。本轮实际完成九图、150份独立Manual作答、800个点对；两种输入视图×5/9/12°×五个实现，共270个设置。五个实现属于绑定、独立、混合三路线，非五个互斥研究方向。图片和参数均为既有开发材料，不宣布泛化赢家。', '',
        '## 1. 输入定义及冻结的自适应规则', '',
        '主输入继续用用户认可的共享x预处理作答。late_x只按canonical身份与既定环序恢复before_preprocessing_points的上下x，保留相同y、人员、点对、资格及参考；匹配／分组与端点定位之后才共享x。它不是把所有历史修复和顺序处理也撤回的“完全原始重跑”。150份中149份before_preprocessing_points与original_export_points一致，1份不同，明细在input_comparison.csv。',
        '800对中582对处理前上下x不同，最大差29.19756px；这些是坐标差，不是已确认标错。每个输入视图单独比较方法，再在同方法下比较输入视图。',
        '本轮混合自适应发生在局部对应组，不按人员质量分配路线，也不让每个组按GT挑方法：把达票绑定组／上组／下组按共同原点对连接成局部组件；组件恰有一个上组、一个下组、至多一个绑定组且有原配对关联，采用独立端点估计，否则保留组件中的绑定基线。无绑定组时保留缺失记录，不补点。该规则是旧混合思路的一个自动选择版本，并非已验证密度分类器；没有以“密集一定该拆”作既成事实。',
        '身份、成员和配对选择可能改变；中心仍用原medoid周期展开与坐标中位数，环仍按新共享x排序且未确认。上下支持和联合支持分别记录。未匹配端点可留在组件账本，几何候选不等于这些端点问题全部解决。', '',
        '## 2. 输出覆盖：不是正确率', '', '|实现|先共享x，有几何候选/27|晚共享x，有几何候选/27|', '|---|---:|---:|']
    for route,name in names.items():
        ns=[sum(r['route']==route and r['view']==v and r['status']!='unavailable' for r in coverage) for v in ('shared_x','late_x')]
        lines.append(f'|{name}|{ns[0]}|{ns[1]}|')
    lines+=['', 'ok与geometry_review均按几何候选计数，不按状态字符串排名。未输出仍保留分母；各方法成功案例不一样，不将其各自均值直接比较。', '',
            '## 3. 与绑定的共同可比较范围误差', '',
            '以下固定主输入与原GT；D为参考面积归一化的对称差，差值为该方法减绑定，负数表示更接近本版参考。完整两输入／两参考及上下边界对照见paired_comparisons.csv。', '',
            '|门限|实现|共同可计算设置|平均D差|更近／更远|', '|---|---|---:|---:|---:|']
    for r in comparisons:
        if r['view']=='shared_x' and r['version']=='original' and r['metric']=='D':
            delta=f"{r['mean_delta']:+.6f}" if r['mean_delta'] is not None else 'NA'
            lines.append(f"|{r['threshold']}°|{names[r['route']]}|{r['common']}|{delta}|{r['better']}／{r['worse']}|")
    lines+=['', '不同门限不作为独立重复。D改善可能来自范围补偿，不认证对应、细节或完整语义。门限不能按各图最高GT分数选择。', '',
            '## 4. 能回答适用性的案例', '',
            '- **2t7：对应一致时没有混合增量。** 主输入9°五种实现点坐标相同，D=0.174742，上／下边界MAE=1.319730°／2.254840°。同一组人和同一中心规则并不会因方法改名而改进。',
            '- **rPc：自适应能绕开独立法的整环拒绝，但尚未恢复已知身份。** 主输入9°独立法无完整候选，自适应产生9对；D=0.492210，绑定为0.490499，自适应略差。既有人审的三份同角观察在绑定、锚定和独立法的达票前分组中就没有完整同组，最终也未一起保留；这次仅切换已有组的规则不能称对应修复。原参考超出当前单值上下边界指标适用域，该分项保留NA。',
            '- **uNb：锚定可以保留稳定下端，却会混合上端目标。** 主输入9°下锚把已知低玻璃顶与天花板目标一起用于上端中心。独立法在下组中保留这三份观察、在上组中分开，却因覆盖缺失不出整环；自适应没有混合已知上端目标，但也未在最终下端保留三份同角关系，只有3对并有无直接原邻接供者的新边。这不是完整修复。',
            '- **e9z：范围分数改善也不能宣称身份正确。** 主输入9°自适应与独立法均为4对、D约0.072112；还需尊重既有接缝混组判断，不能从点数和低D推翻人审。', '',
            '这些例子分别定位：无增量、局部／全图失败策略差异、目标混合、参考补偿。完整候选、支持、组件选择和原点来源在candidates.json；已知关系在human_relations.csv，并列达票前与达票后情况。', '',
            '## 5. 要不要改用真正原始点', '',
            '当前没有依据全面替换主输入。绑定候选覆盖由23/27降到20/27，自适应由24降到21；上锚则由24升到26，独立和下锚数量不变。方向依赖方法。',
            '即使成员完全相同，先对每人的上下x平均再取跨人中位数，与先分别取上下中位数再平均，也不交换。本轮3人控制证明可产生6px差异；这不属于对应改善。2t7真实例晚共享x使上边界MAE略降到1.289119°、下边界略升到2.302587°，D升到0.177200。更接近导出坐标不自动更正确。',
            '因此保留预处理输入为研究主视图、处理前坐标为敏感性视图；用上下配对的原始横向差分析预处理影响。将来若要撤回其它修复，应另立问题，不把输入替换的所有变化算到融合算法。', '',
            '## 6. 本轮判断与下一步', '',
            '三路线均有适用条件，尚无通用赢家。绑定在两端目标一致且距离门支持同角身份时是可靠的控制基线；独立能表达上下不同支持，却受达票不对称与配对政策限制；锚定和局部自适应有实际输出增量，但可能混目标、保留错误身份或产生有待确认的新边。以上是这些开发例的解释，不是已校准的自动适用条件分类器。',
            '下一步应优先解决能改变已知失败的局部选择证据，而不是仅扩大门限或把更多输出当成功；Pro质量线继续评价真实上下定位与细节。此自适应v1未恢复rPc已知对应，不能因局部切换可执行就继续堆复杂选择器。人员／人数旧结论保留为Lee范围结果。', '',
            '验证：18项相关测试通过，含默认输入不变、晚对齐同输入无变化、均值／中位数不交换、冲突回退与上下／联合票区分。构造先于GT评价并保存文件；所有新环未人工认证。未修改原数据、原GT、资格、票权或正式方法选择。']
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


def plot_cases(out):
    import json
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from PIL import Image
    from .research_artifact_io import ROOT
    plt.rcParams['font.sans-serif']=['Microsoft YaHei','DejaVu Sans'];plt.rcParams['axes.unicode_minus']=False
    data=json.loads((out/'candidates.json').read_text(encoding='utf-8'))['states']
    inputs={r['image']:r for r in json.loads((out/'inputs.json').read_text(encoding='utf-8'))['images']}
    for code in ('2t7WUuJeko7-06','rPc6DW4iMge-06','uNb9QFRL6hY-67','e9zR4mvMWw7-15'):
        image_id=inputs[code]['image_id'];path=next(ROOT.glob(f'data/mp3d_layout/*/img/{image_id}.png'))
        photo=Image.open(path).convert('RGB')
        fig,axs=plt.subplots(1,3,figsize=(18,4))
        for ax,route,title in zip(axs,('paired','split_unique','adaptive_incidence_v1'),('绑定','独立unique','局部自适应v1')):
            s=next(r for r in data if r['image']==code and r['view']=='shared_x' and r['threshold']==9 and r['route']==route)
            ax.imshow(photo,extent=(0,1024,512,0));c=s['result']['candidate']
            if c['status']!='unavailable':
                p=np.asarray(c['points']).reshape(-1,2,2)
                for j,pair in enumerate(p):
                    ax.plot(pair[:,0],pair[:,1],color='#00ffff',lw=1);ax.text(pair[0,0],pair[0,1],str(j),color='white',fontsize=8,bbox=dict(facecolor='black',alpha=.5,pad=1))
                for side,color in ((0,'#ffff00'),(1,'#00ffff')):
                    ring=p[:,side]
                    ring=np.vstack([ring,ring[0]])
                    for a,b in zip(ring,ring[1:]):
                        dx=(b[0]-a[0]+512)%1024-512
                        for shift in (-1024,0,1024):ax.plot([a[0]+shift,a[0]+dx+shift],[a[1],b[1]],color=color,lw=1.5)
                ax.set_title(f'{title}：{len(p)}对，未认证新环')
            else:ax.set_title(f'{title}：无完整候选')
            ax.set_xlim(0,1024);ax.set_ylim(512,0);ax.axis('off')
        fig.suptitle(f'{code}  主输入／固定9°；端点与连接示意线（非精确球面边界），不按GT选结果',fontsize=12)
        fig.tight_layout();fig.savefig(out/f'{code}_comparison.png',dpi=140);plt.close(fig)


if __name__=='__main__':run()
