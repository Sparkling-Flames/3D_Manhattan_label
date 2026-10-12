"""四个固定候选的真实影响、旧审核补齐和一对局部代价材料。"""
from pathlib import Path
from itertools import combinations
from collections import defaultdict
import argparse
import json

if __package__:
    from .quality_joint_response_20261012 import terms,read_json,save_json,validate_development_gates,coordinate_key
    from .quality_decision_check_20261012 import render_reviews
else:
    from quality_joint_response_20261012 import terms,read_json,save_json,validate_development_gates,coordinate_key
    from quality_decision_check_20261012 import render_reviews

NAMES=('relative2','relative4','relative2_mean1','probe_local0125_noTop')


def build(study):
    inputs=read_json(study/'inputs.json');previous=read_json(study/'results.json')
    validate_development_gates([dict(record_id=r['id']) for r in inputs['rows']],inputs['gates'])
    configs={r['name']:r['config'] for r in read_json(study/'candidate_matrix.json')['candidates'] if r['name'] in NAMES}
    saved={r['id']:r for r in previous['development']};records=[];errors=[];groups={}
    for r in sorted(inputs['rows'],key=lambda r:r['id']):
        scores={n:terms(r['metrics'],configs[n])['score'] for n in NAMES}
        errors.extend(abs(scores[n]-saved[r['id']]['scores'][n]) for n in NAMES[:3])
        row=dict(r,scores=scores);records.append(row)
        key=coordinate_key(r,inputs['geometries'][r['object_id']])
        if key not in groups:groups[key]=dict(row,members=[])
        assert groups[key]['applicability_confirmed']==r['applicability_confirmed']
        groups[key]['members'].append(r['id'])
    unique=list(groups.values());strata={};pair_sets={}
    for label,flag in [('confirmed',True),('unknown',False)]:
        rr=[r for r in records if r['applicability_confirmed']==flag]
        uu=[r for r in unique if r['applicability_confirmed']==flag]
        by_ref=defaultdict(list)
        for r in uu:by_ref[(r['image_id'],r['reference_object_id'])].append(r)
        pairs=[(a,b) for group in by_ref.values() for a,b in combinations(group,2)];pair_sets[label]=pairs
        contrasts={}
        for n,m in combinations(NAMES,2):
            reversals=[]
            for a,b in pairs:
                d1=a['scores'][n]-b['scores'][n];d2=a['scores'][m]-b['scores'][m]
                if d1*d2<0 and min(abs(d1),abs(d2))>1e-8:
                    reversals.append(dict(A=a['id'],B=b['id'],image_code=a['image_code'],building_id=a['building_id'],
                        first_difference=d1,second_difference=d2,smaller_margin=min(abs(d1),abs(d2))))
            contrasts[n+'__'+m]=dict(reversal_pairs=len(reversals),images=len({r['image_code'] for r in reversals}),
                buildings=len({r['building_id'] for r in reversals}),largest_smaller_margin=max([0]+[r['smaller_margin'] for r in reversals]),
                maximum_record_difference=max(abs(r['scores'][n]-r['scores'][m]) for r in uu),
                leading_reversals=sorted(reversals,key=lambda r:(-r['smaller_margin'],r['A'],r['B']))[:3])
        lifted=[r for r in uu if r['scores']['relative4']-r['scores']['relative2']>=2]
        strata[label]=dict(records=len(rr),coordinate_groups=len(uu),same_reference_pairs=len(pairs),contrasts=contrasts,
            quartic_gain_ge2=dict(groups=len(lifted),images=sorted({r['image_code'] for r in lifted}),buildings=sorted({r['building_id'] for r in lifted})),
            changes_from_baseline={n:dict(minimum=min(r['scores'][n]-r['scores']['relative2'] for r in uu),
                                         maximum=max(r['scores'][n]-r['scores']['relative2'] for r in uu)) for n in NAMES[1:]})
    evidence=read_json(study.parent/'quality_review_constraints_20261012/evidence.json');anchors={}
    for panel,rid in [('P02','R00272'),('P03','R00991')]:
        r=next(r for r in evidence['tables']['real39'] if r['id']==rid)
        anchors[panel]=dict(id=rid,receipt=evidence['raw_receipt']['answers'][panel],metrics=r['metrics'],
            scores={n:terms(r['metrics'],configs[n])['score'] for n in NAMES},human_score_cutoff=None,
            scope='仅复用旧审核池，不加入907开发分母；混合缺陷，不作为纯整体高度校准')
    # Post-exploration sampling for review, not quality thresholds or a preregistered test.
    eligible=[];reviewed=set(previous['reviewed_terms'])
    for a,b in pair_sets['confirmed']:
        if reviewed.intersection(a['members']+b['members']):continue
        if any(abs(a['metrics'][k]-b['metrics'][k])>v for k,v in [('iou_2d',.02),('dir',.5),('S_bottom_deg',.5)]):continue
        base=a['scores']['relative2']-b['scores']['relative2']
        local=a['scores']['probe_local0125_noTop']-b['scores']['probe_local0125_noTop']
        eligible.append((abs(local)-abs(base),a['id'],b['id'],a,b))
    chosen=sorted(eligible,key=lambda x:(-x[0],x[1],x[2]))[0];a,b=chosen[-2:]
    previous_images={r['image_id'] for p in read_json(study/'review_pairs.json')['pairs'] for r in p['records']}
    review=dict(id='L01',records=[a,b],answer=None,confidence=None,prior_same_pair_review=False,
        prior_image_exposure=a['image_id'] in previous_images,eligible_pairs=len(eligible),gap_expansion=chosen[0],
        selection='探索后固定：明确适用/同图同参考/精确坐标去重；排除旧45条审核及坐标重复组；IoU差<=.02、D差<=.5度、Sb差<=.5度，取局部加强导致绝对分差扩张最大对，并列按id。筛选刻度非质量阈值。',
        question='局部顶部起伏的差异是否明显？结合照片和底面，两份整体质量接近，还是其中一份明显更好？可回答无法判断，并指出参考可能的问题。',
        scope='照片/二维与三维结合判断；不展示候选得分，不要求给分，不推断原始点对语义；已曝光开发图片')
    return dict(schema='quality_real_impact_v1',records=records,coordinate_groups=[dict(id=r['id'],members=r['members']) for r in unique],
        strata=strata,known_anchors=anchors,review=review,
        verification=dict(saved_score_cells=len(errors),maximum_saved_score_delta=max(errors)),
        scope='仅4个固定候选；未搜参或重建几何。排序反转不是误排率，2分仅描述切片，未知适用层不认证。')


def add_rotation(inputs,review,folder):
    geometries=[inputs['geometries'][review['records'][0]['reference_object_id']]]
    geometries.extend(inputs['geometries'][r['object_id']] for r in review['records'])
    panel='''<section><h2>同步旋转三维</h2><p>绿线参考，橙线作答；底面虚线，相机黑点。相机高=1，非米制。两侧保持同尺度、同视角；线框不表示遮挡或真实可见性。</p>
<label>水平旋转 <input id="yaw" type="range" min="-180" max="180" value="30"></label>
<label>俯仰 <input id="pitch" type="range" min="-80" max="80" value="20"></label>
<div style="display:flex;flex-wrap:wrap"><figure style="flex:1;min-width:300px;margin:0"><figcaption>A</figcaption><canvas id="left" width="850" height="560" style="width:100%" aria-label="A与参考三维线框"></canvas></figure>
<figure style="flex:1;min-width:300px;margin:0"><figcaption>B</figcaption><canvas id="right" width="850" height="560" style="width:100%" aria-label="B与参考三维线框"></canvas></figure></div></section>'''
    script='''
const geos=GEOMETRIES;
const xyz=p=>[p[0],p[2],p[1]+1];
const points=geos.flatMap(g=>[...g.bottom3d,...g.top3d].map(xyz)).concat([[0,0,1]]);
const low=[0,1,2].map(i=>Math.min(...points.map(p=>p[i])));
const high=[0,1,2].map(i=>Math.max(...points.map(p=>p[i])));
const center=low.map((v,i)=>(v+high[i])/2);
const radius=Math.hypot(...high.map((v,i)=>(v-low[i])/2));
function project(p,yaw,pitch,w,h){
 const [x,y,z]=p.map((v,i)=>v-center[i]),a=yaw*Math.PI/180,b=pitch*Math.PI/180;
 const u=Math.cos(a)*x-Math.sin(a)*y,v=Math.sin(a)*x+Math.cos(a)*y;
 const vertical=Math.cos(b)*z-Math.sin(b)*v,scale=Math.min(w,h)*.44/radius;
 return [w/2+u*scale,h/2-vertical*scale];
}
function draw(canvas,annotation){
 const ctx=canvas.getContext('2d'),w=canvas.width,h=canvas.height;
 const yaw=Number(document.getElementById('yaw').value),pitch=Number(document.getElementById('pitch').value);
 const p=point=>project(xyz(point),yaw,pitch,w,h);
 ctx.clearRect(0,0,w,h);
 for(const [g,color] of [[geos[0],'#218944'],[annotation,'#d66c00']]){
  ctx.strokeStyle=color;
  for(const k of ['bottom3d','top3d']){
   ctx.globalAlpha=1;ctx.lineWidth=2.5;ctx.setLineDash(k==='bottom3d'?[7,5]:[]);ctx.beginPath();
   g[k].forEach((point,i)=>{const q=p(point);if(i===0)ctx.moveTo(...q);else ctx.lineTo(...q);});ctx.closePath();ctx.stroke();
  }
  ctx.setLineDash([]);ctx.globalAlpha=.35;ctx.lineWidth=1;
  g.bottom3d.forEach((point,i)=>{ctx.beginPath();ctx.moveTo(...p(point));ctx.lineTo(...p(g.top3d[i]));ctx.stroke();});
 }
 ctx.globalAlpha=1;ctx.fillStyle='#111';ctx.beginPath();ctx.arc(...project([0,0,1],yaw,pitch,w,h),4,0,2*Math.PI);ctx.fill();
}
function redraw(){draw(document.getElementById('left'),geos[1]);draw(document.getElementById('right'),geos[2]);}
for(const id of ['yaw','pitch'])document.getElementById(id).addEventListener('input',redraw);
redraw();
'''.replace('GEOMETRIES',json.dumps(geometries,separators=(',',':')))
    p=folder/'REVIEW_PAIRS.html';html=p.read_text(encoding='utf-8')
    html=html.replace('<h3>同尺度三维对照</h3>',panel+'<h3>固定视角备查</h3>')
    p.write_text(html.replace('</html>','<script>'+script+'</script></html>'),encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--reviews',action='store_true')
    p.add_argument('--study',type=Path,default=Path('research/quality_top_height_response_20261012'));args=p.parse_args()
    out=build(args.study)
    if args.reviews:
        folder=args.study/'impact_review';folder.mkdir(exist_ok=True)
        inputs=read_json(args.study/'inputs.json')
        render_reviews(inputs,dict(review_pairs=[out['review']]),folder)
        add_rotation(inputs,out['review'],folder)
    save_json(args.study/'real_impact.json',out)
    print(out['verification']);print({k:(v['coordinate_groups'],v['same_reference_pairs']) for k,v in out['strata'].items()})
    print('Selected',[(r['id'],r['image_code']) for r in out['review']['records']])
