"""追溯剩余参考绑定，复用冻结底面路由；不拟合、不评分、不替换既有裁决。"""
from collections import Counter
from itertools import combinations
import csv
import json
import numpy as np
from shapely.geometry import Polygon

from tools.thesis_main.analysis.quality_manual_expansion_20261013 import ROOT, ARCHIVE, read, engine, module
from tools.thesis_main.analysis.quality_frozen_fusion_rescore_20261013 import project
from tools.thesis_main.analysis.quality_height_correspondence_20261013 import ray_depth_diagnostic
from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle

OUT = ROOT/'research/quality_scope_resolution_20261013'


def review_questions(card):
    if card['group']!='height':
        return [dict(id='fusion_extent',title='只看围住的空间，橙线更像哪一种参考？',
            view='看照片和底面俯视图；先忽略顶部高低及角点标得准不准。',
            purpose='用于选择应比较的空间范围，不据此认定橙线标得好，也不比较总分。',
            options=[(r['candidate_id'],'范围更像：'+r['label']) for r in card['references']]+[
                ('mixed','拼在一起了：一部分像一种参考，另一部分像另一种'),
                ('none','都不像，或这些参考本身有问题'),('uncertain','看不出来／现有图片不足以判断')])]
    questions=[
        dict(id='space_extent',title='1. 橙线和绿线围住的是同一段空间吗？',
            view='先看照片和左下俯视图。走廊看两端分别停在哪里，房间看是否包含同一个角落或旁边的小空间。小幅位置误差不算换了空间。',
            purpose='先区分范围选择不同与同一空间内的高度误差，避免把“走廊截取长度不同”直接当作高度标错。',
            options=[('same','基本是同一段空间'),('orange_more','橙线包含得更多／停得更远'),
                ('orange_less','橙线包含得更少／停得更近'),('different','选的区域不同，不能简单说谁大谁小'),('uncertain','看不出来')]),
        dict(id='top_in_photo',title='2. 对照照片，哪条顶部线标得更合理？',
            view='看上方照片中的橙线和绿线，是否沿着各自所标位置的墙顶与天花板交界。可以开关参考线，绿色参考也可能错。',
            purpose='核实高度差是否真有标注错误依据；不能仅因橙线离绿色GT远，就认定橙线错误。',
            options=[('orange_better','橙线更符合照片里的墙顶'),('reference_better','绿线更符合照片里的墙顶'),
                ('both_similar','两条都合理，差异不明显'),('both_different','两条标的是不同位置，各自都有道理'),
                ('both_wrong','两条都有明显问题'),('uncertain','被遮挡或看不清，无法判断')]),
        dict(id='height_in_3d',title='3. 只看三维形状，橙线与绿线的高度差主要是哪一种？',
            view='看右下三维图，可拖动旋转和俯仰滑块。这题只描述线框形状，不表示绿色参考一定正确。',
            purpose='区分算法的“整体高度偏差”和“局部高度不一致”两项，不请你决定扣多少分。',
            options=[('uniform_lower','橙线大致平，但整体更低'),('uniform_higher','橙线大致平，但整体更高'),
                ('local_uneven','主要是部分角点忽高忽低'),('both','整体高低偏差和局部不平均明显'),
                ('no_clear_difference','没有明显高度差'),('uncertain','三维图中也看不出来')])]
    if card['image_code']=='uNb9QFRL6hY-36':
        questions.append(dict(id='floor_steps',title='补充：橙色底点有没有分别落在台阶上、台阶下？',
            view='只看照片里的地面和底点，不从已经画平的三维底面推断。',
            purpose='若地面本来有高低差，现算法把所有底点画在同一高度可能造成假高度差，不能都算作顶部标错。',
            options=[('same_level','看起来都在同一层地面'),('different_levels','有的在台阶上，有的在台阶下'),('uncertain','看不清／不能确定')]))
    return questions


def write_review(cards):
    for card in cards:
        card['questions']=review_questions(card)
        card['question']=('本例要查清：高度差是标注错误，还是选的空间／边界不同。请按下面三题分别描述看到的情况。'
            if card['group']=='height' else '本例只需判断橙线围住的空间更像哪一种参考，不评价总分。')
    payload=dict(schema='quality_scope_review_20261013_v2',cards=cards,
        policy='记录视觉观察，不自动授予资格或转换为分数；v1回执保留原意，不自动迁移到v2问题。')
    (OUT/'REVIEW_MANIFEST.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    template=(ROOT/'tools/thesis_main/analysis/quality_scope_review_20261013.html').read_text(encoding='utf8')
    (OUT/'REVIEW.html').write_text(template.replace('__DATA__',json.dumps(cards,ensure_ascii=False).replace('</','<\\/')),encoding='utf8')


def calibration_stage(scene,condition):
    if scene in ('oos','oos_and_doorway','oos_pending') or condition=='oos':
        return 'oos_diagnostic_only_never_fit'
    if scene in ('doorway_difficult','doorway_annotatable'):
        return 'doorway_second_stage_review_before_small_adjustment'
    return 'ordinary_first_stage_candidate'


def floor_equivalence(a,b):
    p,q=Polygon(a),Polygon(b)
    if not p.is_valid or not q.is_valid or min(p.area,q.area)<=0:
        raise ValueError('invalid reference floor')
    area=p.symmetric_difference(q).area/p.union(q).area
    distance=p.boundary.hausdorff_distance(q.boundary)/np.sqrt(p.union(q).area)
    # 仅消除浮点重复几何，不是接受范围差异的阈值。
    return dict(relative_symmetric_difference=float(area),relative_boundary_hausdorff=float(distance),
                equivalent=bool(area<=1e-10 and distance<=1e-10))


def route_disposition(route):
    local=route['route_reason']=='local_differentiating_structure'
    return dict(status='frozen_local_structure_conditional' if local else 'ambiguous_floor_fallback',
        conditional_candidate_id=route['candidate_id'] if local else None,
        confirmed_target_id=None,human_review_required_for_single_target=not local,
        semantic_target_certified=False,formal_eligibility_changed=False)


def serial_geometry(g):
    return {k:np.asarray(g[k]).tolist() for k in ('bottom3d','top3d') if k in g}


def main():
    data=load_current_bundle()['data'];objects={o['object_id']:o for o in data['objects']}
    images={im['image_id']:im for im in data['images']};e=engine()
    with (ROOT/'analysis_results/difficulty_scope_preferred_20261011/current_259.csv').open(encoding='utf-8-sig') as f:
        scenes={r['image_id']:r for r in csv.DictReader(f)}
    router=module(ARCHIVE/'routing/router.py','scope_existing_router')
    cfg=read(ARCHIVE/'routing/config.json')
    pro={r['image_id']:r for r in read(ARCHIVE/'routing/inputs/prepared_input.json')['candidate_images']}
    gaps=read(ROOT/'research/quality_downstream_audit_20261013/REFERENCE_GAP_AUDIT.json')['records']
    pending=[r for r in gaps if r['classification']=='existing_reference_not_bound_to_fused_target']
    restricted=[r for r in gaps if r['classification']=='no_unrestricted_full_reference']
    rows=[];cards=[];versions={}
    photo_paths={p.stem:p for p in (ROOT/'data/mp3d_layout').glob('*/img/*')}
    def photo(iid):
        return '../../'+photo_paths[iid].relative_to(ROOT).as_posix() if iid in photo_paths else None
    def candidate(cid,oid,g,label):
        return dict(candidate_id=cid,reference_object_id=oid,geometry=serial_geometry(g),label=label)
    for old in pending:
        iid=old['image_id'];key=old['image_code']+':'+old['version']
        source=read(ROOT/old['source']);a,state=project(source[old['version']]['candidate']['points'])
        if a is None:raise ValueError((key,state))
        floor=np.asarray(a['bottom3d'])[:,[0,2]].tolist()
        pc=[c for c in pro.get(iid,{}).get('candidates',[]) if c['admitted_for_routing']]
        refs=[];route=None
        if pc:
            prepared=router.prepare_reference_set(pc,cfg);route=router.route_floor(floor,prepared)
            disposition=route_disposition(route)
            distinct=router.export_distinguishing_regions(prepared)
            for c in pc:
                g=c['full_geometry'] if c['full_reference_available'] else {'bottom3d':[[x,-1,z] for x,z in c['floor_xz_h']]}
                refs.append(candidate(c['candidate_id'],c['reference_object_id'],g,c['space_label']+('（完整参考）' if c['full_reference_available'] else '（仅确认底面）')))
        else:
            for c in old['current_references']:
                if c['restrictions']:continue
                g=e['geometry'](objects[c['reference_id']]['points_1024x512'])
                refs.append(candidate(c['version'],c['reference_id'],g,'原始GT' if c['version']=='gt_original' else '修订GT（未找到融合目标验收）'))
            distinct=[]
            comparisons=[dict(a=x['candidate_id'],b=y['candidate_id'],**floor_equivalence(
                np.asarray(x['geometry']['bottom3d'])[:,[0,2]],np.asarray(y['geometry']['bottom3d'])[:,[0,2]])) for x,y in combinations(refs,2)]
            versions[iid]=dict(image_code=old['image_code'],comparisons=comparisons)
            disposition=dict(status='version_sensitivity_no_admitted_space_selection',conditional_candidate_id=None,
                confirmed_target_id=None,human_review_required_for_single_target=True,semantic_target_certified=False,
                formal_eligibility_changed=False,all_reference_floors_equivalent=all(c['equivalent'] for c in comparisons))
        measurements=[]
        for c in refs:
            g=c['geometry'];rf=np.asarray(g['bottom3d'])[:,[0,2]]
            m=router.floor_metrics(floor,rf)
            m['symmetric_boundary_distance_h']=router.boundary_distance(floor,rf,cfg['boundary_fallback_samples'])
            if 'top3d' in g:
                am=e['hm'].height_moments(a);gm=e['hm'].height_moments(g)
                m['Hmean']=abs(am['height_mean_h']/gm['height_mean_h']-1)
                m['Hcenter']=e['center'].centered_height_components(a,g,samples=4096,height_module=e['hm'])['Hcenter']
            else:m.update(Hmean=None,Hcenter=None)
            measurements.append(dict(candidate_id=c['candidate_id'],reference_id=c['reference_object_id'],metrics=m))
        row=dict(endpoint_id=key,image_id=iid,image_code=old['image_code'],version=old['version'],
            source=old['source'],disposition=disposition,route=route,distinguishing_regions=distinct,
            candidate_measurements=measurements,member_barriers=old['current_member_barriers'],
            original_holdout_member_ids=old['original_holdout_member_ids'],individual_decisions_inherited=False,
            scores_computed=False,calibration_admission=False)
        rows.append(row)
        cards.append(dict(id=key,group='fusion',image_code=old['image_code'],image_id=iid,version=old['version'],
            special_scene=scenes[iid]['scene'] not in ('clear','unflagged'),scene_review=scenes[iid],
            priority=2 if disposition['status']=='frozen_local_structure_conditional' else 1,
            image=photo(iid),annotation=serial_geometry(a),references=refs,source=old['source'],
            question='融合结果表达哪个参考范围？请看区别候选的转折、延伸和封口。若为混合或残缺表达，请选无法单一对应；无需判分。',
            comments=images[iid]['image_comment'],disposition=disposition))
    height=read(ROOT/'research/quality_height_correspondence_20261013/RESULTS.json')['mechanism_cases']
    height_rows=[]
    for r in height:
        obj=objects[r['object_id']];iid=obj['image_id'];a=e['geometry'](obj['points_1024x512'])
        g=e['geometry'](objects[r['reference_object_id']]['points_1024x512'])
        ray=ray_depth_diagnostic(a,g,e['hm'].height_moments(g)['height_mean_h'])
        # 最近底边与同视线交点分别记录；相同边号也不证明同一物理墙。
        floor=np.asarray(a['bottom3d'])[:,[0,2]];rf=np.asarray(g['bottom3d'])[:,[0,2]]
        distance,_,segment=router.point_boundary_distance(floor,rf)
        corners=[]
        for i,c in enumerate(ray['corners']):
            start=rf[segment[i]];edge=rf[(segment[i]+1)%len(rf)]-start
            nearest=start+np.clip(np.dot(floor[i]-start,edge)/np.dot(edge,edge),0,1)*edge
            point_gap=float(np.linalg.norm(nearest-floor[i]/np.linalg.norm(floor[i])*c['reference_radius'])) if 'reference_radius' in c else None
            corners.append(dict(**c,nearest_reference_segment_index=int(segment[i]),
                nearest_floor_distance_h=float(distance[i]),same_segment_as_ray=(int(segment[i])==c['reference_segment_index']) if 'reference_segment_index' in c else None))
            corners[-1]['nearest_vs_ray_point_distance_h']=point_gap
        height_rows.append(dict(record_id=r['record_id'],image_code=r['image_code'],reference_object_id=r['reference_object_id'],
            corners=corners,review_evidence=r['review_evidence'],physical_wall_correspondence_confirmed=False))
        cards.append(dict(id=r['record_id'],group='height',image_code=r['image_code'],image_id=iid,version='manual',priority=0,
            special_scene=scenes[iid]['scene'] not in ('clear','unflagged'),scene_review=scenes[iid],
            image=photo(iid),annotation=serial_geometry(a),references=[candidate('current',r['reference_object_id'],g,'既定参考（允许指出问题）')],
            source=r['object_id'],question='作答与参考是否表达同一范围、同一底平面和同一顶界？有台阶时尤其核对底点高程；若不同，请指出停止面、横梁/吊顶或墙顶的位置。若相同，再判断明显整体偏低还是局部不平。',
            comments=r['review_evidence'],disposition={'status':'height_scope_and_top_semantics_pending'},corner_correspondence=corners))
    summary=dict(schema='quality_scope_resolution_20261013_v1',pending_fusion_endpoints=len(rows),
        images=len({r['image_id'] for r in rows}),classifications=dict(Counter(r['disposition']['status'] for r in rows)),
        version_only_images=len(versions),equivalent_version_floor_images=sum(all(c['equivalent'] for c in v['comparisons']) for v in versions.values()),
        restricted_reference_endpoints=len(restricted),restricted_action='retain_existing_exclusion_new_reference_required',
        height_records=len(height_rows),height_images=len({r['image_code'] for r in height_rows}),
        missing_review_photos=[c['id'] for c in cards if c['image'] is None],
        old_220_single_reference_numeric_coverage_unchanged=True,no_new_scores=True,no_parameters_changed=True,
        no_semantic_approval_inferred=True,original_holdout_members_not_promoted=True)
    OUT.mkdir(exist_ok=True,parents=True)
    def dump(name,value):
        (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
    dump('RESULTS.json',dict(summary=summary,fusion=rows,version_comparisons=list(versions.values()),restricted=restricted,height=height_rows))
    write_review(cards)
    dump('SUMMARY.json',summary)
    gate=read(ROOT/'research/quality_data_admission_audit_20261013/FULL_ADMISSION.json')
    stage_rows=[]
    for r in gate['records']:
        scene=scenes[r['image_id']]['scene']
        stage=calibration_stage(scene,r['condition'])
        stage_rows.append(dict(record_id=r['record_id'],image_code=r['image_code'],stage=stage,scene=scene,
            current_role=r['role'],current_fit_view=r['record_id'] in gate['primary_calibration_ids'],
            condition=r['condition'],ordinary_status_is_explicit=scene=='clear',
            existing_holds=r['context_barriers']+r['personnel_barriers']))
    assert not any(r['current_fit_view'] and r['stage']!='ordinary_first_stage_candidate' for r in stage_rows)
    dump('STAGE_LEDGER.json',dict(schema='quality_calibration_stages_20261013_v1',records=stage_rows,
        counts=dict(Counter(r['stage'] for r in stage_rows)),user_direction='普通图先锁定大致参数；门洞第二步逐图核查后可小幅微调；OOS因GT可靠性不纳入调参。',
        score_ordering_is_hypothesis_not_target=True,no_new_calibration_performed=True))
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
