"""Bind adopted reference frames and publish explicit, unadopted doorway candidates."""
import copy
import json
import math
from pathlib import Path
import build_doorframe_alignment_20261031 as view

OUT=view.PREP/'new_geometry_review_20261031'
ADOPT=view.ROOT/'research/data/scope_quality_rescore_20261016/vertical_cut_audit_20261028/extension_v1/adopted_references_20261028'

def rotate(p,angle):
    x,z=p;return [x*math.cos(angle)+z*math.sin(angle),-x*math.sin(angle)+z*math.cos(angle)]

def main():
    cases=json.loads((view.BASE/'data.js').read_text(encoding='utf8').split('=',1)[1][:-1])['cases']
    decisions=view.read(view.PREP/'manhattan_correction_20261031/ALIGNMENT_DECISIONS.json')
    by={r['image']:r for r in decisions};caseby={c['image']:c for c in cases}
    for group in 'abc':
        for row in view.read(OUT/f'group_{group}.json'):
            r=by[row['image']]
            r['cuts']=row.get('recommended_cuts',row.get('cuts'))
            r['space_polygons']=row.get('recommended_space_polygons',row.get('derived_space_polygons',row.get('space_polygons')))
            if isinstance(r['space_polygons'],dict):r['space_polygons']=[r['space_polygons'][k] for k in ['空间1','空间2']]
            r['portal_segments']=[dict(p,space=i+1) for i,p in enumerate(row.get('portal_segments',[]))]
            r['notes']='原图与俯视联合复核的条件性候选；不覆盖已采用GT。'
            r['source']='new_geometry_review_20261031/group_'+group+'.json'
            r['review_evidence']=row
            r['reference_adopted']=False
            r['needs_human']=row.get('needs_human',False)
    adopted=view.read(ADOPT/'ADOPTED_REFERENCES.json')
    ceilings=view.read(ADOPT/'ceiling_adopted_20261028/ADOPTED_REFERENCES.json')
    bindings=[]
    for c in cases:
        hits=[r for r in adopted if r['image_id']==c['image_id']]
        bindings.append(dict(image=c['image'],adopted_matches=[r['target_id'] for r in hits],floor_matches=[r['target_id'] for r in hits if r['floor_xz_h']==c['floor']]))
    image='q9vSo1VnCiC-13';r=by[image];c=caseby[image]
    adopted_ref=next(a for a in adopted if a['image']==image)
    current=next(a for a in ceilings if a['target_id']==adopted_ref['target_id'])
    assert c['floor']==current['floor_xz_h']==adopted_ref['floor_xz_h']
    theta=adopted_ref['axis_radians']
    c['reference_id']=current['target_id'];c['reference_version']=current['reference_version']
    c['floor']=copy.deepcopy(current['floor_xz_h'])
    local=[rotate(p,theta) for p in c['floor']]
    offsets=[min(local[i][0] for i in [0,1,4,5]),max(local[i][0] for i in [6,7,10,11])]
    r['cuts']=[dict(line=[rotate([x,-100],-theta),rotate([x,100],-theta)],side=1 if i==0 else -1) for i,x in enumerate(offsets)]
    r['display_yaw']=theta
    r['space_polygons']=[view.clip(c['floor'],cut) for cut in r['cuts']]
    r['notes']='直接采用v2.1保存的主轴，不重拟合GT。两停止面在该主轴坐标下闭合两房；俯视图统一旋正显示，ERP投影仍用原坐标。小连接凸台留在过渡带。'
    r['reference_id']=current['target_id'];r['reference_version']=current['reference_version']
    r['adopted_axis_radians']=theta
    r['source']=str(ADOPT.relative_to(view.ROOT))+'/ADOPTED_REFERENCES.json'
    r['reference_receipt']=current['adoption_receipt']
    r['scope_reference_is_new_candidate']=True
    for image,offset in [('q9vSo1VnCiC-04',.09004306876495304),('q9vSo1VnCiC-24',.21615142557900444)]:
        r=by[image];c=caseby[image];cuts=copy.deepcopy(r['cuts'] or r['provisional_cuts'])
        for p in cuts[1]['line']:p[0]=offset
        if r['cuts']:r['cuts']=cuts
        else:r['provisional_cuts']=cuts
        r['space_polygons']=[view.clip(c['floor'],cut) for cut in cuts]
        r['notes']='空间2旧转角是门洞连接段残留：两端回墙不共面，旧停止边只齐一端。本候选平移空间2闭合面到另一端，使连接段留在过渡带；不是宣称所有房间都应矩形。'
    view.main(decisions,OUT,cases)
    view.save('REFERENCE_BINDING_AUDIT.json',bindings)
    view.save('Q9_13_ADOPTION_BINDING.json',dict(target_id=current['target_id'],reference_version=current['reference_version'],axis_radians=theta,axis_degrees=math.degrees(theta),floor_unchanged=True,geometry= current['geometry'],source=str(ADOPT.relative_to(view.ROOT)),cut_offsets_in_adopted_frame=offsets,original_reference_modified=False))
    p=OUT/'index.html';text=p.read_text(encoding='utf8').replace('门框逐图视觉对齐','门洞空间几何联合复核')
    text=text.replace('<h1>门洞空间几何联合复核</h1>','<h1>门洞空间几何联合复核</h1><p><strong>彩色虚线：空间闭合边投影，并非整条都是门框；彩色实线：有单独依据的门洞开口段。q9-13使用v2.1已采用主轴统一俯视方向。灰底保留原参考，彩色区域是本轮派生候选。</strong></p>')
    p.write_text(text,encoding='utf8')

if __name__=='__main__':main()
