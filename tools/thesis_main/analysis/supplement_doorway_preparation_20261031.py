"""Refresh scope proposals and build auditable target drafts; no curve execution."""
import csv
import importlib.util
import json
import math
import sys
from dataclasses import replace
from collections import Counter
from pathlib import Path

import numpy as np
from shapely.geometry import Point, Polygon

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'research/data/doorway_review_20261030'
PREP=BASE/'curve_preparation_v21'
OUT=PREP/'supplement_20261031'

def read(path):return json.loads(path.read_text(encoding='utf8'))
def write(name,obj):(OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
def load_js(path):return json.loads(path.read_text(encoding='utf8').split('=',1)[1][:-1])

def clip(poly,cut):
    a,b=cut['line'];side=cut['side']
    def dist(p):return side*((b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0]))
    out=[]
    for p,q in zip(poly,poly[1:]+poly[:1]):
        x,y=dist(p),dist(q)
        if x>=0:out.append(p)
        if (x>=0)!=(y>=0):
            t=x/(x-y);out.append([p[k]+t*(q[k]-p[k]) for k in range(len(p))])
    return out

def floor(points):
    result=[]
    for x,y in (points or [])[1::2]:
        r=1/math.tan((y/512-.5)*math.pi);a=(x/1024-.5)*math.tau
        result.append([r*math.sin(a),-r*math.cos(a)])
    return result

def classify(poly,cuts):
    if len(poly)<3 or not Polygon(poly).is_valid or Polygon(poly).area<=0:return 'invalid',None
    area=Polygon(poly).area
    fractions=[]
    for cut in cuts:
        p=clip(poly,cut);fractions.append(Polygon(p).area/area if len(p)>=3 else 0.)
    x,y=fractions
    label='space1' if x>=.85 and y<=.1 else 'space2' if y>=.85 and x<=.1 else 'both' if min(x,y)>=.15 else 'neither' if max(x,y)<.15 else 'borderline'
    return label,dict(space1=x,space2=y,band=max(0.,1-x-y))

def main():
    OUT.mkdir(exist_ok=True)
    initial=load_js(BASE/'data.js');cases=initial['cases']
    review=read(PREP/'USER_REVIEW_FINAL_RECEIVED.json')
    old={r['record_id']:r for r in csv.DictReader((BASE/'first_review_audit/classification.csv').open(encoding='utf-8-sig'))}
    ledger=read(PREP/'RECORD_LEDGER.json');byid={r['object_id']:r for r in ledger}
    scopes=[];changed=[];old_matches=0
    for c in cases:
        cuts=review['cases'][c['image_id']]['cuts']
        for answer in c['records']:
            oid=answer['id'];poly=floor(answer['points']);previous,frac=classify(poly,c['cuts'])
            assert previous==old[oid]['space_verdict'],(oid,previous,old[oid]['space_verdict'])
            old_matches+=1
            proposed,newfrac=classify(poly,cuts)
            record=dict(object_id=oid,image=c['image'],worker=answer['worker'],old_machine_scope=previous,
                current_machine_scope=proposed,fractions=newfrac,cuts=cuts,rule_version='doorway_area_proposal_20261031')
            scopes.append(record)
            row=byid[oid];before=row['adopted_scope'];source=row['scope_adoption']
            # Human and independently visual-reviewed records retain their adopted identity.
            if source in ['automatic_provisional','automatic_cut_stale','unresolved']:
                row['adopted_scope']={'space1':'空间1','space2':'空间2','both':'全部'}.get(proposed)
                row['scope_adoption']='automatic_current_cuts' if row['adopted_scope'] else 'automatic_unresolved'
                row['machine_cut_binding_current']=True
                row['automatic_scope_evidence']=record
                if before!=row['adopted_scope']:changed.append(dict(object_id=oid,image=c['image'],worker=answer['worker'],before=before,after=row['adopted_scope']))
            row['screened_version_candidate']=row['base_candidate'] and row['adopted_scope']!='都不符合（看不懂）'
    assert old_matches==708
    assert all(byid[r['object_id']]['adopted_scope']==r['adopted_scope'] for r in read(PREP/'RECORD_LEDGER.json') if r['scope_adoption'].startswith('user') or r.get('visual_review'))
    write('UPDATED_RECORD_LEDGER.json',ledger);write('CURRENT_CUT_SCOPE_PROPOSALS.json',scopes);write('SCOPE_CHANGES.json',changed)
    write('AUTOMATIC_RULE.json',dict(version='doorway_area_proposal_20261031',
        source='本轮明确实现的面积规则，复现原始切分下全部708份存档分类；原分类程序源码未取得，不宣称恢复原源码。',
        rules=['空间1: f1>=0.85且f2<=0.10','空间2: f2>=0.85且f1<=0.10','全部: f1>=0.15且f2>=0.15','neither:两侧均<0.15','其它:borderline'],
        qualification='仅范围初判，不是质量或剔除规则；不覆盖人工或独立视觉裁决。',old_label_parity=old_matches))

    engine_path=ROOT/'research/statistics/b8l2_shared_v6_20261016/inputs/measurement_engine/src/quality.py'
    spec=importlib.util.spec_from_file_location('doorway_probe_engine',engine_path);engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)
    model_path=ROOT/'research/quality/quality_ab_feedback_handoff_20261015/prior_AB/src/working_models.py'
    spec=importlib.util.spec_from_file_location('doorway_probe_models',model_path);models=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=models;spec.loader.exec_module(models)
    targets=[];checks=[]
    for c in cases:
        cuts=review['cases'][c['image_id']]['cuts'];parent=engine.geometry(c['points'])
        # Third coordinate carries existing wall-top height through edge interpolation.
        vertices=[[p[0],p[2],parent['top3d'][i][1]] for i,p in enumerate(parent['bottom3d'])]
        for index,poly in enumerate([vertices,clip(vertices,cuts[0]),clip(vertices,cuts[1])]):
            target='全部' if index==0 else '空间'+str(index)
            raw_poly=poly
            removed=[]
            if index:
                # Clipping through an existing vertex can emit that vertex twice.
                tolerance=64*np.finfo(float).eps*max(1.,max(abs(v) for p in poly for v in p),max(abs(v) for p in cuts[index-1]['line'] for v in p))
                clean=[]
                for k,p in enumerate(poly):
                    if clean and math.dist(clean[-1],p)<=tolerance:removed.append(k)
                    else:clean.append(p)
                if len(clean)>1 and math.dist(clean[0],clean[-1])<=tolerance:
                    removed.append('closing_duplicate');clean.pop()
                assert abs(Polygon([p[:2] for p in raw_poly]).area-Polygon([p[:2] for p in clean]).area)<1e-10
                poly=clean
            fp=[[p[0],p[1]] for p in poly];geom=dict(bottom3d=[[p[0],-1.,p[1]] for p in poly],top3d=[[p[0],p[2],p[1]] for p in poly])
            validation=engine.valid.validate_record(geom,role='reference')
            assert Polygon(fp).is_valid and Polygon(fp).area>0
            closure=[]
            if index:
                cut=cuts[index-1];a,b=cut['line']
                for k,(p,q) in enumerate(zip(fp,fp[1:]+fp[:1])):
                    cross=lambda v:(b[0]-a[0])*(v[1]-a[1])-(b[1]-a[1])*(v[0]-a[0])
                    if abs(cross(p))<1e-8 and abs(cross(q))<1e-8:closure.append(k)
            targets.append(dict(target_id=c['image']+':doorway:'+str(index)+':draft_20261031',image=c['image'],scope=target,
                parent_reference_id=c['reference_id'],parent_reference_version=c['reference_version'],floor_xz_h=fp,
                conditional_geometry=geom,closure_edge_indices=closure,camera_inside=Polygon(fp).covers(Point(0,0)),
                clipping_raw_vertices=raw_poly,clipping_duplicate_removals=removed,
                clipping_numerical_tolerance=tolerance if index else None,
                geometry_validation=validation['available'],geometry_errors=validation.get('errors'),
                top_provenance='继承原GT顶点；新增边界交点沿原墙段线性插值；停止面的顶边连接仅是条件性闭合假设。' if index else '原参考全环，不删除门框通行带',
                adoption='draft_not_ground_truth_adopted',full_quality_allowed=False))
            if c['image'] not in ['pRbA3pwrgk9-01','pRbA3pwrgk9-11','q9vSo1VnCiC-24'] and index:
                measured=engine.measure(geom,geom,floor_only=True)
                checks.append(dict(image=c['image'],scope=target,camera_inside=Polygon(fp).covers(Point(0,0)),
                    status=measured['status'],metrics=measured.get('metrics'),reasons=measured.get('reasons',[])))
    # Full-metric contract probe uses synthetic constant ceilings, never adopted as GT.
    fixtures=[]
    for name,fp in [('inside',[[-1,-1],[1,-1],[1,1],[-1,1]]),('outside',[[1,-1],[3,-1],[3,1],[1,1]]),('boundary',[[0,-1],[2,-1],[2,1],[0,1]])]:
        geom=dict(bottom3d=[[x,-1,z] for x,z in fp],top3d=[[x,1.5,z] for x,z in fp])
        result=engine.measure(geom,geom)
        assert result['status']=='complete' and abs(result['scores']['WQ']-100)<1e-8
        vals=[result['metrics'][k] for k in ['iou_2d','S_bottom_deg','dir','Hmean','Hcenter']]
        params=models.MODELS['B8L2']
        result['primary_checks']={name:float(models.score(*vals,p)) for name,p in [('B8L2',params),('D10',replace(params,direction_scale_deg=10.))]}
        assert all(abs(v-100)<1e-8 for v in result['primary_checks'].values())
        fixtures.append(dict(name=name,synthetic_not_reference=True,result=result))
    write('TARGET_CANDIDATES.json',targets)
    write('METRIC_APPLICABILITY_CHECKS.json',dict(engine=str(engine_path.relative_to(ROOT)),floor_self_checks=checks,synthetic_full_checks=fixtures,
        conclusion='现有评分支持相机外部与边界位置；此项不构成禁用。通过自检不证明门框/顶界候选为真实GT；不改现行指标，不默默屏蔽闭合边。'))
    base=[r for r in ledger if r['base_candidate']]
    write('CHECKS.json',dict(inventory=len(ledger),base_candidates=len(base),screened_candidates=sum(r['screened_version_candidate'] for r in base),
        scope_counts=dict(Counter(r['adopted_scope'] or '未定' for r in base)),updated_scope_records=len(changed),
        inherited_classification_parity=old_matches,target_drafts=len(targets),floor_checks=dict(Counter(r['status'] for r in checks)),
        actual_curve_execution=False,formal_reference_adoption=False))
    print(json.dumps(read(OUT/'CHECKS.json'),ensure_ascii=False))

if __name__=='__main__':main()
