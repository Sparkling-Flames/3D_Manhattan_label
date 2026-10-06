"""复用四路全员融合，比较较宽阈值；不改变对应或投票算法。"""
import json
import shutil
import argparse
from pathlib import Path

from .point_route_panel_20261005 import ROOT, OUT as BASE
from .point_route_review_20261006 import run, audit_correspondences
from .point_route_review_view_20261006 import build, write_page, photo
from .point_route_panel_view_20261005 import project

OUT = ROOT/'analysis_results/point_threshold_sweep_20261006'


def comparison_page(out=OUT):
    panel = json.loads((out/'candidates.json').read_text(encoding='utf-8'))
    evaluation = json.loads((out/'evaluations.json').read_text(encoding='utf-8'))
    for image in panel['images']:
        image['photo'] = photo(image['image_id'], out)
        for state in image['states']:
            state['view'] = project(state['result']['candidate'])
            state['evaluation'] = next(r for r in evaluation['rows'] if
                (r['image'], r['route'], r['threshold_deg']) == (image['image'], state['route'], state['threshold_deg']))
    panel['lee_scores'] = evaluation['lee']
    write_page(out/'compare.html', '''<h1>阈值对照：大图叠加</h1>
<p>黄色为现有算法生成的上下点与x排序连接，供研究比较；复杂环的连接仍可能有误。点簇来源、原序备选及Lee叠加可在<a href="index.html">详细交互页</a>查看。</p>
<label>图片<select id="image"></select></label><label>路线<select id="route"></select></label>
<label>A（青色）<select id="a"></select></label><label>B（黄色）<select id="b"></select></label>
<div><button id="both">叠加</button><button id="only-a">只看A</button><button id="only-b">只看B</button><button id="full">全图</button><button id="left">放大左半</button><button id="right">放大右半</button><button id="clean">只看原图</button></div>
<p id="status"></p><svg id="large" viewBox="0 0 1024 512" role="img" aria-label="阈值大图叠加，可滚轮放大并拖动" style="height:70vh;touch-action:none;cursor:grab"></svg>
<p>滚轮放大、拖动平移。青色虚线=A，黄色实线=B；重合处可切换“只看A／B”。坐标一致的设置无需重复审核。</p>
<details><summary>参考分数与点来源</summary><p id="lee-score"></p><pre id="source">点击点查看来源</pre></details>
<p>点数增加表示更多点簇达到现有票数门限，不直接表示恢复了真实细节。参考IoU评价的是这里显示的x排序底面。</p>
<a href="REPORT.md">本轮结论与下一步</a>''', r'''
const labels={paired:'上下绑定',bottom_anchor:'下端锚定',top_anchor:'上端锚定',split_unique:'上下分开'};
options('image',DATA.images.map((im,i)=>[i,im.image]));$('image').value=String(DATA.plan.display_image_index??2);options('route',Object.entries(labels));
for(const id of ['a','b'])options(id,DATA.plan.thresholds_deg.map(t=>[t,t+'°']));$('a').value='5';$('b').value='9';
let mode='both',box=[0,0,1024,512],drag=null;const svg=$('large');
function viewport(){svg.setAttribute('viewBox',box.join(' '));}
function draw(){const im=DATA.images[Number($('image').value)],states=['a','b'].map(id=>im.states.find(s=>s.route===$('route').value&&s.threshold_deg===Number($(id).value)));svg.replaceChildren();background(svg,im.photo);
states.forEach((s,k)=>{if(mode==='clean'||(mode==='a'&&k===1)||(mode==='b'&&k===0))return;const g=el('g'),color=k?'#ffd658':'#23e3da';paths(g,s.view,color,2);if(!k)g.querySelectorAll('path').forEach(p=>p.setAttribute('stroke-dasharray','7 4'));const c=s.result.candidate;(c.points||[]).forEach((p,i)=>dot(g,p,color,(k?'B':'A')+'点'+(i+1),()=>{const fid=c.feature_ids[Math.floor(i/2)];$('source').textContent=pretty({threshold:s.threshold_deg,...((c.source_pair_maps||[]).find(g=>g.feature_id===fid)||{feature_id:fid})});$('source').parentElement.open=true;}));svg.append(g);});
const counts=states.map(s=>(s.result.candidate.points||[]).length/2),same=JSON.stringify(states[0].result.candidate.points)===JSON.stringify(states[1].result.candidate.points);
$('status').textContent=`${im.image} · ${im.n}份记录 · A ${$('a').value}°：${counts[0]}对；B ${$('b').value}°：${counts[1]}对。`+(same?(counts[0]?' 两份输出点坐标完全一致，无需审核阈值差异。':' 两者均无完整候选。'):' 青黄分离处是输出变化位置。');
const shortfalls=counts.flatMap((n,i)=>n<4?[(i?'B':'A')+'不足4对：保留原始投票结果，需诊断完整性']:[]);$('status').textContent+=' '+shortfalls.join('；');$('status').style.color=shortfalls.length?'#9b6200':'';
const lee=DATA.lee_scores.find(x=>x.image===im.image);$('lee-score').textContent=`参考底面IoU：A ${states[0].evaluation.bev?.iou.toFixed(4)??'不可用'}；B ${states[1].evaluation.bev?.iou.toFixed(4)??'不可用'}；Lee ${lee.bev?.iou.toFixed(4)??'不可用'}。`;$('source').textContent='点击点查看来源';viewport();}
for(const id of ['a','b','route'])$(id).onchange=draw;$('image').onchange=()=>{box=[0,0,1024,512];draw();};
for(const [id,value] of [['both','both'],['only-a','a'],['only-b','b'],['clean','clean']])$(id).onclick=()=>{mode=value;draw();};
for(const [id,value] of [['full',[0,0,1024,512]],['left',[0,100,512,300]],['right',[512,100,512,300]]])$(id).onclick=()=>{box=[...value];viewport();};
function point(e){const p=new DOMPoint(e.clientX,e.clientY);return p.matrixTransform(svg.getScreenCTM().inverse());}
svg.addEventListener('wheel',e=>{e.preventDefault();const p=point(e),factor=e.deltaY<0?.8:1.25,w=Math.max(100,Math.min(1024,box[2]*factor)),f=w/box[2];box=[p.x+(box[0]-p.x)*f,p.y+(box[1]-p.y)*f,w,box[3]*f];viewport();},{passive:false});
svg.onpointerdown=e=>{if(e.target.closest('circle'))return;drag=point(e);svg.setPointerCapture(e.pointerId);};svg.onpointermove=e=>{if(!drag)return;const p=point(e);box[0]+=drag.x-p.x;box[1]+=drag.y-p.y;viewport();};svg.onpointerup=svg.onpointercancel=()=>{drag=null;};draw();
    ''', panel)


def main():
    plan = json.loads((BASE/'PLAN.json').read_text(encoding='utf-8'))
    plan.update(date='2026-10-06', thresholds_deg=[3, 5, 6, 9, 12, 15],
                threshold_role='9 degrees is the focal exploratory setting; compare full layouts before choosing a working threshold',
                display_threshold_deg=9)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'EXPERIMENT_PLAN.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
    run(OUT, plan=plan)
    # run preserves the old entry's provenance; this experiment supplies its own plan.
    (OUT/'PLAN.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
    shutil.copyfile(ROOT/'research/point_route_review_20261006/human_review.json', OUT/'human_review.json')
    audit_correspondences(OUT)
    build(OUT)
    comparison_page()


def expanded_main():
    from .point_route_panel_20261005 import construct_panel, evaluate_panel, audit_outputs
    from .point_route_review_20261006 import connection_review, partial_correspondences
    out = ROOT/'analysis_results/point_threshold_expanded_20261006'
    source = json.loads((ROOT/'analysis_results/lee_expanded_20261003/source_input.json').read_text(encoding='utf-8'))
    excluded = {'2t7WUuJeko7','7y3sRwLe3Va','rPc6DW4iMge','uNb9QFRL6hY'}
    selected, used = [], set(excluded)
    for varying in (False, True):
        count = 0
        for im in sorted(source['images'], key=lambda x:x['code']):
            records = [r for r in im['annotations'] if r['independent'] and r['consensus_eligible'] and r['condition']=='manual' and r['main_consensus_gate']['status']=='main_candidate']
            sizes = {len(r['points'])//2 for r in records}
            if im['building'] in used or len(records)<8 or (len(sizes)>1)!=varying:
                continue
            selected.append(dict(image=im['code'], building=im['building'], n=len(records), pair_counts=sorted(sizes), stratum='variable_count' if varying else 'uniform_count'))
            used.add(im['building']);count+=1
            if count==4: break
    assert len(selected)==8
    plan = json.loads((BASE/'PLAN.json').read_text(encoding='utf-8'))
    plan.update(date='2026-10-06',images=[r['image'] for r in selected], expected_records=sum(r['n'] for r in selected),
        thresholds_deg=[5,9,12],roster_source='current_source_input',display_threshold_deg=9,display_image_index=4,
        selection_reason='Before new fusion scores: exclude four development buildings; >=8 eligible records; code order; four uniform-count then four variable-count images, one per building.',
        selected_inventory=selected, threshold_role='9 degree working setting, 5/12 sensitivity; no per-image score-based tuning',
        status='fixed_before_expanded_outputs',not_done=['new manual review','global optimum calibration','general topology recovery'])
    out.mkdir(parents=True,exist_ok=True)
    (out/'PLAN.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(selected,ensure_ascii=False),flush=True)
    construct_panel(out,plan)
    refs={'images':[dict(image=im['code'],references=im['references']) for im in source['images'] if im['code'] in plan['images']]}
    evaluate_panel(out,refs)
    audit_outputs(out)
    panel=json.loads((out/'candidates.json').read_text(encoding='utf-8'))
    for im in panel['images']:
        for state in im['states']:
            result=state['result'];result['connection_review']=connection_review(result)
            if state['route']=='split_unique':result['partial_correspondences']=partial_correspondences(result)
    (out/'candidates.json').write_bytes(json.dumps(panel,ensure_ascii=False,allow_nan=False).encode('utf-8'))
    (out/'review_cases.json').write_text('[]',encoding='utf-8')
    build(out);comparison_page(out)


def diagnose_e9z():
    """保存用户指定删点对照及最低点数复核；不将人工删点当自动算法。"""
    import numpy as np
    from shapely.geometry import Polygon
    from .paired_split_research.study import angular
    from .point_route_panel_20261005 import build_routes, reconstruct, area_scores
    from .lee_tile_stage1_20261002 import write_json
    out=ROOT/'analysis_results/point_threshold_expanded_20261006'
    data=json.loads((out/'candidates.json').read_text(encoding='utf-8'))
    evaluation=json.loads((out/'evaluations.json').read_text(encoding='utf-8'))
    im=next(i for i in data['images'] if i['image']=='e9zR4mvMWw7-15')
    ref=next(r['record'] for r in evaluation['references'] if r['image']==im['image'])
    right=[]
    for r in im['records']:
        for k,pair in enumerate(np.asarray(r['points']).reshape(-1,2,2)):
            if pair[0,0]>990:
                right.append(dict(id=r['id'],worker=r['worker'],pair_index=k,points=pair.tolist()))
    p=np.asarray([r['points'] for r in right])
    distances={side:float(angular(p[:,i]-.5,p[:,i]-.5).max()) for i,side in enumerate(['top','bottom'])}
    old=next(s['result']['candidate'] for s in im['states'] if s['route']=='paired' and s['threshold_deg']==12)
    k=min(range(len(old['points'])//2),key=lambda i:old['points'][2*i][0])
    manual=dict(old,points=[p for i in range(len(old['points'])//2) if i!=k for p in old['points'][2*i:2*i+2]],
                source_pair_maps=[v for i,v in enumerate(old['source_pair_maps']) if i!=k],
                feature_ids=[v for i,v in enumerate(old['feature_ids']) if i!=k],
                point_support_counts=[v for i,v in enumerate(old['point_support_counts']) if i!=k])
    geo=reconstruct(manual,coordinate_convention='continuous');manual['footprint']=geo['floor'].tolist()
    manual.update(status='human_specified_deletion_diagnostic',reason='user-requested removal; not automatic consensus')
    gt=Polygon(ref['footprint'])
    results=[]
    for t in [5,9,12]:
        for route,r in build_routes(im['records'],t).items():
            results.append(dict(threshold_deg=t,route=route,status=r['status'],reason=r['candidate']['reason'],
                                pair_count=len(r['candidate']['points'] or [])//2))
    coverage=[]
    for t in [5,9,12]:
        for route in data['plan']['routes']:
            rows=[r for r in evaluation['rows'] if r['threshold_deg']==t and r['route']==route]
            coverage.append(dict(threshold_deg=t,route=route,attempts=len(rows),
                historical_computable=sum(r['bev'] is not None for r in rows),
                geometry_and_min8=sum(r['bev'] is not None and r['pair_count']>=4 for r in rows)))
    write_json(out/'e9z_min8_diagnosis.json',dict(schema='e9z_min8_diagnosis_v1',image=im['image'],
        source_counts=[dict(id=r['id'],worker=r['worker'],endpoints=len(r['points'])) for r in im['records']],
        right_observations=right,right_max_angle_deg=distances,
        right_group_support_at_5=[g['support'] for g in next(s['result'] for s in im['states'] if s['threshold_deg']==5 and s['route']=='paired')['identity_groups'] if g['center'][0][0]>990],
        manual_delete_left_from_12=manual,reference=ref,
        manual_delete_bev=area_scores(Polygon(manual['footprint']),gt),
        original_12_bev=area_scores(Polygon(old['footprint']),gt),
        revised_current_code_results=results,reclassified_coverage=coverage,
        policy='fewer than 8 endpoints is diagnostic only; raw majority retained, structure constraints researched separately; manual deletion never used to select an automatic candidate'))
    comparison_page(out)


def count_shortfalls():
    """全库点数诊断与e9z完整子集重放；不使用GT、不强制补点。"""
    from collections import Counter
    from itertools import combinations
    from .point_route_panel_20261005 import build_routes
    from .global_pair_consensus_20261004 import build_global_pair_consensus
    from .lee_tile_stage1_20261002 import write_json
    source=json.loads((ROOT/'analysis_results/lee_expanded_20261003/source_input.json').read_text(encoding='utf-8'))
    rows=[]; inventory=[]; pools={}
    for im in source['images']:
        records=[r for r in im['annotations'] if r['independent'] and r['consensus_eligible']
                 and r['condition']=='manual' and r['main_consensus_gate']['status']=='main_candidate']
        pools[im['code']]=records
        inventory.append(dict(image=im['code'],building=im['building'],n=len(records),
            source_endpoint_counts=sorted(Counter(len(r['points']) for r in records).items())))
        for t in [5,9,12]:
            for route,r in build_routes(records,t).items():
                selected=(sum(g['selected'] for g in r['identity_groups']) if route!='split_unique' else None)
                c=r['candidate']; points=c['points']; count=len(points)//2 if points is not None else None
                rows.append(dict(image=im['code'],building=im['building'],n=len(records),threshold_deg=t,route=route,
                    selected_pair_count=selected,below_four_selected_pairs=selected<4 if selected is not None else None,
                    generated_pair_count=count,below_four_generated_pairs=count<4 if count is not None else None,
                    status=r['status'],reason=c['reason'],geometry_computable=c.get('geometry_status')=='ok',
                    minimum_support=r['minimum_support'],input_issues=r['input_issues'],
                    group_supports=sorted([g['support'] for g in r.get('identity_groups',[])],reverse=True)))
        if len(inventory)%20==0:print(f'counted {len(inventory)}/{len(source["images"])} images',flush=True)
    replay=[]; records=pools['e9zR4mvMWw7-15']
    for n in range(2,len(records)+1):
        counts={t:Counter() for t in [5,9,12]}
        for subset in combinations(records,n):
            for t in counts:
                r=build_global_pair_consensus(subset,t)
                counts[t][sum(g['selected'] for g in r['identity_groups'])]+=1
        for t,distribution in counts.items():
            attempts=sum(distribution.values())
            replay.append(dict(n=n,threshold_deg=t,subsets=attempts,
                below_four=sum(v for k,v in distribution.items() if k<4),
                selected_pair_count_distribution=sorted(distribution.items())))
    out=ROOT/'analysis_results/point_threshold_expanded_20261006'
    write_json(out/'all_image_pair_count_audit.json',dict(schema='all_image_pair_count_audit_v1',
        policy='Raw >=50% point vote retained; fewer than four is diagnostic only. No GT, padding, forced four-pair gate or changed source eligibility.',
        fields=dict(selected_pair_count='Majority identity count before center/ring validation; null for split_unique because endpoint incidence can remain unresolved.',
                    generated_pair_count='Number of serialized candidate pairs, including geometrically invalid candidates; null if no serialized candidate.',
                    below_four_selected_pairs='Primary shortfall measure for paired/anchor routes; distinct from missing output or incorrect layout.',
                    e9z_subsets='All subsets of the existing eight records for n=2..8, not new workers or independent trials; >=50% has odd/even effects.'),
        inventory=inventory,rows=rows,e9z_exhaustive_subset_replay=replay))
    print('saved all_image_pair_count_audit.json',flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expanded',action='store_true')
    parser.add_argument('--diagnose-e9z',action='store_true')
    parser.add_argument('--count-shortfalls',action='store_true')
    args=parser.parse_args()
    count_shortfalls() if args.count_shortfalls else diagnose_e9z() if args.diagnose_e9z else expanded_main() if args.expanded else main()
