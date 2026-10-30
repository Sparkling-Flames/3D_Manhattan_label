"""Publish the full inventory audit; keep GT observations separate from derived scopes."""
import copy
import json
from shapely.geometry import Polygon, box
import build_doorframe_alignment_20261031 as view

OUT=view.PREP/'full_review_20261031'

def main():
    cases=json.loads((view.BASE/'data.js').read_text(encoding='utf8').split('=',1)[1][:-1])['cases']
    prior=view.read(view.PREP/'new_geometry_review_20261031/ALIGNMENT_DECISIONS.json')
    decisions=copy.deepcopy(prior);by={r['image']:r for r in decisions}
    cb={c['image']:c for c in cases};before={r['image']:r for r in prior}
    adopted_dir=view.ROOT/'research/data/scope_quality_rescore_20261016/vertical_cut_audit_20261028/extension_v1/adopted_references_20261028'
    adopted=view.read(adopted_dir/'ADOPTED_REFERENCES.json')
    ceilings=view.read(adopted_dir/'ceiling_adopted_20261028/ADOPTED_REFERENCES.json')
    for c in cases:
        matches=[a for a in adopted if a['image_id']==c['image_id'] and a['floor_xz_h']==c['floor']]
        if len(matches)==1:
            ref=matches[0];current=next((a for a in ceilings if a['target_id']==ref['target_id']),ref)
            r=by[c['image']];r['reference_id']=current['target_id'];r['reference_version']=current['reference_version']
            r['adopted_axis_radians']=ref['axis_radians']
            r['reference_source']=str(adopted_dir.relative_to(view.ROOT))
    reviews=sum((view.read(OUT/f'group_{group}.json') for group in 'abc'),[])
    assert len(reviews)==20 and len({r['image'] for r in reviews})==20
    ledger=[]
    for review in reviews:
        name=review['image'];r=by[name];c=cb[name];gt=Polygon(c['floor'])
        cuts=review.get('cuts',review.get('recommended_cuts'))
        regions=review.get('space_polygons',review.get('recommended_space_polygons'))
        if isinstance(regions,dict):regions=[regions[k] for k in ['空间1','空间2']]
        issues=review.get('issues',[review.get('finding','')])
        summary='；'.join(i.get('detail',str(i)) if isinstance(i,dict) else str(i) for i in issues)
        r['audit_summary']=summary;r['full_inventory_review']=review
        if r['status']=='excluded':
            ledger.append(dict(image=name,status='OOS_diagnostic_only',issues=issues,formal_gt_error=False));continue
        assert cuts and regions,name
        cuts=copy.deepcopy(cuts)
        if name=='7y3sRwLe3Va-06':
            # The previous filled rectangle was contained; its separately drawn plane was not its edge.
            edge=max(p[0] for p in regions[0])
            for point in cuts[0]['line']:point[0]=edge
            r['audit_summary']='收尾核验：填色区域未超GT；此前另画的平均停止面与填色右边不一致。现将蓝色停止面与GT内区域边界对齐。GT外面积小于1e-9。'
        if name=='7y3sRwLe3Va-18':
            regions=[view.clip(c['floor'],cut) for cut in cuts]
            r['audit_summary']='按用户确认的蓝线到点1更新实际空间区域：空间1、空间2直接沿这两条边界裁剪GT。旧保守矩形已替换；空间2包含橙线之后的原GT连接颈段，不再遗漏，也不向GT外填平。'
        if name=='jtcxE69GiFV-12':
            r['doorway_adjudication']='用户确认可标的门洞交界'
            r['audit_summary']='用户收尾确认本图属于可标门洞交界；少数作答只标空间1可作为合法范围差异，不自动视为不符合。具体数量以逐份归属台账为准。'
        r['closeout_display_and_scope_note']=r['audit_summary']
        if r['scope_pending']:
            r['cuts']=None;r['provisional_cuts']=cuts
        else:r['cuts']=cuts
        r['space_polygons']=regions
        if 'display_yaw' in review:r['display_yaw']=review['display_yaw']
        if 'portal_segments' in review:r['portal_segments']=[dict(p,space=i+1) for i,p in enumerate(review['portal_segments'])]
        polygons=[Polygon(p) for p in regions]
        assert all(p.is_valid and p.area>0 for p in polygons),name
        outside=[p.difference(gt).area for p in polygons]
        assert max(outside)<1e-9,(name,outside)
        assert polygons[0].intersection(polygons[1]).area<1e-9,name
        old=before[name];oldcuts=old['cuts'] or old['provisional_cuts']
        oldregions=old.get('space_polygons') or [view.clip(c['floor'],cut) for cut in oldcuts]
        oldpolys=[Polygon(p) for p in oldregions]
        removed=[a.difference(b) for a,b in zip(oldpolys,polygons)]
        record=dict(image=name,status='pending' if r['scope_pending'] else 'doorway_candidate',
            issues=issues,formal_gt_error=False,old_outside_gt_areas=[p.difference(gt).area for p in oldpolys],
            new_outside_gt_areas=outside,removed_from_previous_areas=[p.area for p in removed],
            removed_from_previous_geometry=[p.__geo_interface__ for p in removed],
            cuts_changed=cuts!=oldcuts,regions_changed=any(a.symmetric_difference(b).area>1e-9 for a,b in zip(oldpolys,polygons)),
            raw_gt_modified=False,human_answers_modified=False)
        if 'doorway_band' in review:
            band=review['doorway_band'];lo,hi=band['near'],band['far']
            bandpoly=gt.intersection(box(-100,lo,100,hi))
            residual=gt.difference(polygons[0].union(polygons[1])).difference(bandpoly)
            r['diagnostic_regions']=[dict(polygon=list(bandpoly.exterior.coords)[:-1],color='#b59300',label='用户指定门框带')]
            pieces=list(residual.geoms) if hasattr(residual,'geoms') else [residual]
            for p in pieces:
                if p.geom_type=='Polygon' and p.area>.005:r['diagnostic_regions'].append(dict(polygon=list(p.exterior.coords)[:-1],color='#a65786',label='GT连接段待解释'))
            r['doorway_band']=band
            record['unassigned_gt_connection_geometry']=residual.__geo_interface__
            r['audit_summary']+='；黄色仅表示用户指定门框带；GT局部不齐的历史证据仍保留在问题记录中。'
        r['reference_adopted']=False
        r['source']='full_review_20261031逐图复核'
        ledger.append(record)
    view.main(decisions,OUT,cases)
    view.save('ISSUE_LEDGER.json',ledger)
    view.save('FULL_AUDIT_CHECKS.json',dict(images=20,doorway=17,pending=1,oos=2,
        verified_regions=36,all_regions_within_gt=True,changed_region_images=sum(r.get('regions_changed',False) for r in ledger),
        previous_outside_gt_images=sum(max(r.get('old_outside_gt_areas',[0]))>1e-9 for r in ledger),
        formal_gt_error_auto_classification=False,raw_gt_modified=False,scoring_executed=False))
    p=OUT/'index.html';text=p.read_text(encoding='utf8').replace('门框逐图视觉对齐','门洞全量复核：区域与GT问题')
    text=text.replace('<h1>门洞全量复核：区域与GT问题</h1>','<h1>门洞全量复核：区域与GT问题</h1><p><strong>20图逐图复核。彩色区域是GT范围内的保守候选；原图虚线是闭合边投影，实线才是单独定位的门洞段。异常已单独登记，不因整理为矩形就认定GT错误。</strong></p>')
    p.write_text(text,encoding='utf8')
    print(json.dumps(view.read(OUT/'FULL_AUDIT_CHECKS.json'),ensure_ascii=False))

if __name__=='__main__':main()
