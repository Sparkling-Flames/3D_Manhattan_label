"""Publish visually checked doorway cuts without overwriting submitted labels or GT."""
import html
import json
import math
import os
from collections import Counter
from pathlib import Path
from shapely.geometry import Polygon, LineString
from supplement_doorway_preparation_20261031 import clip, classify, floor

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'research/data/doorway_review_20261030'
PREP=BASE/'curve_preparation_v21'
OUT=PREP/'doorframe_alignment_20261031'

def read(p):return json.loads(p.read_text(encoding='utf8'))
def save(name,d): (OUT/name).write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
def erp(p):
    x,z=p;return [((math.atan2(x,-z)/math.tau+.5)%1)*1024,(.5+math.atan2(1,math.hypot(x,z))/math.pi)*512]
def segment_path(a,b):
    points=[erp([a[k]+(b[k]-a[k])*t/100 for k in range(2)]) for t in range(101)]
    return ' '.join(f'M{p[0]:.2f},{p[1]:.2f}L{q[0]:.2f},{q[1]:.2f}' for p,q in zip(points,points[1:]) if abs(p[0]-q[0])<512)
def main(decisions=None, output=None, cases=None):
    global OUT
    if output is not None:
        OUT=output
        OUT.mkdir(exist_ok=True)
    if cases is None:
        cases=json.loads((BASE/'data.js').read_text(encoding='utf8').split('=',1)[1][:-1])['cases']
    old=read(PREP/'USER_REVIEW_FINAL_RECEIVED.json')['cases']
    supplied=decisions is not None
    if not supplied:
        decisions=sum((read(OUT/f'group_{g}.json') for g in 'abc'),[])
    assert len(decisions)==20 and len({r['image'] for r in decisions})==20
    for peer_path in [OUT/'peer_review_c.json',OUT/'peer_review_a.json']:
        if supplied:break
        if not peer_path.exists():continue
        for review in read(peer_path):
            for d in decisions:
                downgrade=review.get('downgrade',False) or review.get('recommendation') in ['downgrade_uncertain','same_standard_review_own_b_candidate']
                if review['image']==d['image'] and downgrade:
                    if d['cuts']:d['provisional_cuts']=d['cuts']
                    d['cuts']=None;d['status']='uncertain';d['needs_human']=True;d['peer_review']=review;d['superseded_claims']='原分组中的落地误差数值及精确对齐表述撤回；方位证据保留，条件性深度不得作为已确认GT。'
    byimage={r['image']:r for r in decisions}; audit=[]; impacts=[]; sections=[]
    colors=['#05c4d5','#ff9b38']
    for c in cases:
        d=byimage[c['image']]; cuts=d.get('cuts'); oldcuts=old[c['image_id']]['cuts']; polygon=Polygon(c['floor'])
        assert d['status'] in ['aligned','uncertain','excluded','manhattan']
        if cuts:
            assert len(cuts)==2
            regions=[Polygon(p) for p in d.get('space_polygons', [clip(c['floor'],cut) for cut in cuts])]
            assert all(r.is_valid and r.area>0 for r in regions),c['image']
            assert regions[0].intersection(regions[1]).area<1e-8,c['image']
            # Preserve side identity using the old region centroids, not image left/right.
            for cut,oldcut in zip(cuts,oldcuts):
                center=Polygon(clip(c['floor'],oldcut)).centroid
                a,b=cut['line']; assert cut['side']*((b[0]-a[0])*(center.y-a[1])-(b[1]-a[1])*(center.x-a[0]))>=0,c['image']
            for r in c['records']:
                before,_=classify(floor(r['points']),oldcuts);after,_=classify(floor(r['points']),cuts)
                if before!=after:impacts.append(dict(image=c['image'],object_id=r['id'],worker=r['worker'],previous_proposal=before,new_proposal=after,adoption='candidate_only_not_overwriting_human'))
        audit.append(dict(image=c['image'],status=d['status'],has_cut_candidate=bool(cuts),geometry_checked=bool(cuts),needs_human=d['needs_human']))
        photo=os.path.relpath((BASE/c['photo']).resolve(),OUT).replace('\\','/')
        assert (OUT/photo).is_file()
        overlay=[]; bev=[]
        yaw=d.get('display_yaw',0.)
        def rotated(p):return [p[0]*math.cos(yaw)+p[1]*math.sin(yaw),-p[0]*math.sin(yaw)+p[1]*math.cos(yaw)]
        minx,minz,maxx,maxz=Polygon([rotated(p) for p in c['floor']]).bounds; scale=min(620/(maxx-minx),300/(maxz-minz))
        def xy(p):
            q=rotated(p);return [20+(q[0]-minx)*scale,20+(q[1]-minz)*scale]
        def poly_svg(p,color,fill):
            pts=' '.join(','.join(str(v) for v in xy(q)) for q in p)
            return f'<polygon points="{pts}" fill="{color if fill else "none"}" fill-opacity=".18" stroke="{color}" stroke-width="2"/>'
        bev.append(poly_svg(c['floor'],'#aaa',False))
        for diagnostic in d.get('diagnostic_regions',[]):
            bev.append(poly_svg(diagnostic['polygon'],diagnostic['color'],True))
            center=Polygon(diagnostic['polygon']).representative_point();pos=xy([center.x,center.y])
            bev.append(f'<text x="{pos[0]}" y="{pos[1]}" fill="{diagnostic["color"]}" font-size="12">{html.escape(diagnostic["label"])}</text>')
        for candidate,dashed in [(oldcuts,True),(cuts or d.get('provisional_cuts'),False)]:
            if not candidate:continue
            for index,cut in enumerate(candidate):
                a,b=cut['line'];length=math.dist(a,b);assert length>0
                middle=[(a[k]+b[k])/2 for k in range(2)]
                radius=max(100,max(abs(v) for v in polygon.bounds)*10,math.hypot(*middle)*3)
                aa=[middle[k]-(b[k]-a[k])/length*radius for k in range(2)];bb=[middle[k]+(b[k]-a[k])/length*radius for k in range(2)]
                intersection=polygon.intersection(LineString([aa,bb]))
                lines=list(intersection.geoms) if hasattr(intersection,'geoms') else [intersection]
                color='#bbb' if dashed else colors[index]; dash='stroke-dasharray="6 5"' if dashed else ''
                if not dashed:
                    region=d['space_polygons'][index] if d.get('space_polygons') else clip(c['floor'],cut)
                    if len(region)>=3 and Polygon(region).is_valid:
                        bev.append(poly_svg(region,color,True))
                        label=Polygon(region).representative_point();labelxy=xy([label.x,label.y])
                        bev.append(f'<text x="{labelxy[0]}" y="{labelxy[1]}" fill="{color}" font-size="18">空间{index+1}</text>')
                for line in lines:
                    if line.geom_type!='LineString':continue
                    coords=list(line.coords);u,v=coords[0],coords[-1];p,q=xy(u),xy(v)
                    overlay.append(f'<path d="{segment_path(u,v)}" fill="none" stroke="{color}" stroke-width="2" stroke-dasharray="5 5"/>')
                    bev.append(f'<line x1="{p[0]}" y1="{p[1]}" x2="{q[0]}" y2="{q[1]}" stroke="{color}" stroke-width="3" {dash}/>')
        cam=xy([0,0]);bev.append(f'<circle cx="{cam[0]}" cy="{cam[1]}" r="4" fill="red"/><text x="{cam[0]+6}" y="{cam[1]}">相机</text>')
        for number,e in enumerate(d.get('evidence_pixels',[]),1):
            for key in ['floor_endpoints','points','segment']:
                points=e.get(key,[])
                for x,y in points:
                    overlay.append(f'<circle cx="{x}" cy="{y}" r="3" fill="none" stroke="#f62c91" stroke-width="2"/><text x="{x+4}" y="{y-4}" fill="#f62c91" font-size="12">{number}</text>')
        status_text={'aligned':'视觉对齐候选','uncertain':'深度或范围待定','excluded':'OOS排除','manhattan':'曼哈顿约束切分'}[d['status']]
        for portal in d.get('portal_segments',[]):
            overlay.append(f'<path d="{segment_path(*portal["line"])}" fill="none" stroke="{colors[portal["space"]-1]}" stroke-width="4"/>')
        notes=html.escape(json.dumps(d,ensure_ascii=False,indent=2))
        finding=html.escape(d.get('audit_summary',''))
        sections.append(f'<section id="{c["image"]}"><h2>{c["image"]} · {status_text}</h2><p>{finding}</p><svg viewBox="0 0 1024 512"><image href="{photo}" width="1024" height="512"/>{"".join(overlay)}</svg><svg viewBox="0 0 680 350">{"".join(bev)}</svg><details><summary>逐图视觉证据与限制</summary><pre>{notes}</pre></details></section>')
    save('ALIGNMENT_DECISIONS.json',decisions);save('CHECKS.json',dict(images=20,status_counts=dict(Counter(d['status'] for d in decisions)),checks=audit,changed_automatic_proposals=len(impacts),original_labels_modified=False,ground_truth_modified=False))
    save('SCOPE_IMPACT_CANDIDATES.json',impacts)
    page='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>门框逐图视觉对齐</title><style>body{max-width:1150px;margin:24px auto;padding:12px;font:16px/1.6 system-ui;background:#f4f6f8}section{background:white;margin:24px 0;padding:18px}svg{width:100%;max-height:570px}pre{white-space:pre-wrap;overflow-wrap:anywhere}a{margin-right:14px}</style><h1>门框逐图视觉对齐</h1><p>灰虚线：旧停止边；青：空间1候选；橙：空间2候选；红点：相机。粉色圈：原图视觉证据点（编号对应证据条目；含估计端点，详见说明）。原图默认不叠加GT。俯视灰轮廓仅继承旧GT作为坐标背景，不代表确认GT正确。</p><p>待定图如有彩线，仅展示条件性草案，不代表可靠落地定位。候选投影采用相机高度归一的水平地面；不是直接观测真值。没有可靠深度的图保留待定，不把像素定位硬变成三维切分。原作答裁决未改写。</p>'+''.join(f'<a href="#{c["image"]}">{c["image"]}</a>' for c in cases)+''.join(sections)+'</html>'
    (OUT/'index.html').write_text(page,encoding='utf8')
    print(json.dumps(read(OUT/'CHECKS.json')['status_counts'],ensure_ascii=False))
if __name__=='__main__':main()
