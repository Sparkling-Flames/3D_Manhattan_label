"""接收两图新空间，并把范围变化与同范围等级裁定分开记录。"""
import copy
import csv
import json
from collections import Counter
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from ..data_prep.consolidate_research_input import load_current_bundle
from ..data_prep.floor_scope_update_20261015 import validate_update
from .scope_difficulty_review_20261011 import floor_features
from .scope_reference_reconstruction_20261016 import source_planes, reconstruct_scope
from .difficulty_pair_display_20261016 import display_pairs

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'research/difficulty/difficulty_pair_display_20261016'
OUT=ROOT/'research/difficulty/difficulty_scope_resolution_20261016'
VERSION='scope_preferred_difficulty_scope_resolved_20261016_v6'
TARGETS={'S9hNv5qa7GM-09','zsNo4HB9uLZ-13'}


def receive_records(receipt):
    records=[]
    for i,r in enumerate(receipt['records']):
        if r['image_code'] not in TARGETS:continue
        regions=r['space_regions']['regions']
        if len(regions)!=1:raise ValueError('ambiguous_region')
        s=regions[0];c=s['confirmed_version']
        if not s['floor_region_confirmed'] or not c['floor_region_confirmed'] or s['polygon']!=c['polygon']:
            raise ValueError('unconfirmed_or_changed_scope')
        records.append(dict(image_id=r['image_id'],image_code=r['image_code'],
            reference_id='user_space_20261016:'+r['image_code'],original_reference_id=r['editing_reference_object_id'],
            original_points_1024x512=r['editing_reference_points_1024x512'],floor_xz_h=c['polygon'],
            floor_region_confirmed=True,space_scope_confirmed=True,scope_semantics='whole_space_vertical_boundary',
            top_boundary_pending=True,reference_ready=False,confirmed_at=c['confirmed_at'],
            source_receipt='scope_receipt_20261016.json',source_pointer=f'/records/{i}/space_regions/regions/0',
            confirmed_snapshot=c,answer_to_candidate_assignments=[]))
    if len(records)!=2 or {r['image_code'] for r in records}!=TARGETS:raise ValueError('wrong_scope_population')
    return records


def write(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')


def main():
    OUT.mkdir(exist_ok=True)
    receipt_path=ROOT/'analysis_results/research_input_20260929/scope_receipt_20261016.json'
    if not receipt_path.exists():raise FileNotFoundError(receipt_path)
    received=receive_records(json.loads(receipt_path.read_text(encoding='utf-8-sig')))
    bundle=load_current_bundle();update=copy.deepcopy(bundle['floor_scope_update'])
    merged={r['image_id']:r for r in update['records']};merged.update({r['image_id']:r for r in received})
    update.update(records=list(merged.values()),revision='six_confirmed_space_scopes_20261016_v3')
    validate_update(update,bundle['data'])
    write(ROOT/'analysis_results/research_input_20260929/floor_scope_update_20261015.json',update)
    loaded=load_current_bundle();assert loaded['data']==bundle['data'] and loaded['research']==bundle['research']
    planes=source_planes(bundle)
    base=json.loads((BASE/'current_259.json').read_text(encoding='utf-8'));rows=copy.deepcopy(base['records'])
    scopes={s['image_id']:s for s in received};changes=[];refs=[]
    for r in rows:
        for k in ['card','old_card','scope_comparison']:
            if r.get(k):r[k]='../difficulty_pair_display_20261016/'+r[k]
        if r['image'] not in TARGETS|{'7y3sRwLe3Va-19'}:continue
        old=dict(image=r['image'],before=r['current_class'],old_target=r['target_version'],old_N=r['N_turn'],old_H=r['H'])
        r['evidence_before_scope_resolution']=r['evidence']
        if r['image_id'] in scopes:
            s=scopes[r['image_id']];f=floor_features(s['floor_xz_h'])
            assert f['geometry_status']=='valid_camera_inside' and f['N_turn']==4 and f['H']==0
            candidate=dict(target_id=s['reference_id'],role='confirmed_scope',floor=s['floor_xz_h'],features=f)
            r['candidates'].append(candidate);r['selected']=candidate
            r.update(target_version=s['reference_id'],N_turn=f['N_turn'],N_floor=f['N_floor'],H=f['H'],
                space_scope_confirmed=True,scope_semantics='whole_space_vertical_boundary',scope_source=str(receipt_path.relative_to(ROOT)),
                question='',selection_reason='采用本次明确确认的新空间，原空间仅对照')
            if r['difficulty_analysis_exclusion']=='target_scope_unresolved':
                r.update(difficulty_analysis_eligible=True,difficulty_analysis_exclusion='')
            plane=planes[s['original_reference_id']]
            ref=reconstruct_scope(s['floor_xz_h'],s['original_points_1024x512'],plane['plane'])
            ref.update(target_id=s['reference_id'],image_id=r['image_id'],image_code=r['image'],
                evidence=dict(constructions=[dict(source_plane=plane)]))
            points,status=display_pairs(s['floor_xz_h'],ref);preview=status!='existing_full_reference'
            r['top_boundary_pending']=preview
            r['pair_display_status']=status
            r['pair_display_note']='黄色顶点为原顶平面外推预览，未认证新空间完整GT。' if preview else '上下同号为一对，采用新空间重建参考。'
            refs.append(dict(reference=ref,display_points=points,display_status=status))
            im=Image.open(r['photo']).convert('RGB');draw=ImageDraw.Draw(im);font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',22)
            for n,pair in enumerate(np.asarray(points).reshape(-1,2,2),1):
                top,bottom=pair*np.array([im.width/1024,im.height/512]);color='#ffd15c' if preview else '#00edff'
                for y in np.arange(top[1],bottom[1],18):draw.line((top[0],y,top[0],min(y+(9 if preview else 18),bottom[1])),fill=color,width=2)
                for x,y in [top,bottom]:
                    draw.ellipse((x-5,y-5,x+5,y+5),fill=color);draw.text((min(x+8,im.width-35),y-12),str(n),font=font,fill=color,stroke_width=2,stroke_fill='black')
            name=r['image']+'_pairs.jpg';im.save(OUT/name,quality=92);r['card']=name
            r['evidence']='新范围已固定，原跨空间隐藏分支不再计入；四转折H=0仅说明结构简化，按用户裁定为中等。'
            r['disagreement_resolution']='target_changed_not_same_task_relabel'
        else:
            r['evidence']='原空间不变。壁炉凸墙及两侧墙顶/竖线可辨，局部背向角仍需推断；H=2不能直接等同高难，按用户裁定为中等。'
            r['disagreement_resolution']='same_target_inference_burden_recalibrated'
        r.update(current_class='中等',conditional_difficulty='中等',classification_basis='user_scope_and_grade_adjudication_20261016',
            followup_user_review=dict(grade='中等',note=r['evidence'],source='用户本次空间回执及消息'))
        changes.append(dict(old,after='中等',new_target=r['target_version'],new_N=r['N_turn'],new_H=r['H'],resolution=r['disagreement_resolution']))
    assert len(changes)==3 and sum(r['selected']['role']=='confirmed_scope' for r in rows)==41
    eligible=[r for r in rows if r['difficulty_analysis_eligible']]
    summary=dict(base['summary'],version=VERSION,counts=dict(Counter(r['current_class'] for r in rows)),
        analysis_counts=dict(Counter(r['current_class'] for r in eligible)),accepted_alternatives=41,scope_pending=0,
        changed_from_previous_scope=sum(r['current_class']!=r['previous_scope_class'] for r in rows),
        changed_from_visual_v2=sum(r['current_class']!=r['previous_visual_class'] for r in rows),
        display_pairs=dict(Counter(r.get('pair_display_status') for r in rows if r['selected']['role']=='confirmed_scope')),
        changed_in_this_version=3,new_visual_review_count=3,note='两图目标变化与一图同目标等级修正分开；只解除S9-09的范围未定门。历史质量须重新匹配新目标。')
    result=dict(version=VERSION,base_version=base['version'],summary=summary,records=rows)
    write(OUT/'current_259.json',result);write(OUT/'scope_changes.json',changes);write(OUT/'new_scope_references.json',refs)
    ledger=[]
    for r in rows:
        v=r.get('latest_user_review')
        if not v or (v['proposed_class'],v['grade']) not in [('中等','困难'),('困难','中等')]:continue
        ledger.append(dict(image=r['image'],old_class=v['proposed_class'],user_class=v['grade'],adopted_class=r['current_class'],
            target=r['target_version'],N=r['N_turn'],H=r['H'],label_status='user_adjudication_adopted',
            explanation='解释候选：整体表达/辨认负担原先估低' if v['grade']=='困难' else '解释候选：局部隐藏角对整图负担原先估高',
            prior_evidence=r.get('evidence_before_user_adoption',r.get('old_visual_evidence','')),
            evidence_limit='原因归纳依据既有记录与裁定，非本轮独立盲审；不等同重新计算的推断量'))
    assert len(ledger)==22
    write(OUT/'disagreement_22.json',ledger)
    fields=['image','image_id','target_version','current_class','conditional_difficulty','N_turn','H','classification_basis','difficulty_analysis_eligible','difficulty_analysis_exclusion','gt_error_excluded','pair_display_status','evidence']
    for name,rs in [('current_259',rows),('analysis_eligible',eligible),('excluded',[r for r in rows if not r['difficulty_analysis_eligible']])]:
        with (OUT/(name+'.csv')).open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rs)
    page=(BASE/'review.html').read_text(encoding='utf-8');a=page.index('const DATA=')+len('const DATA=');b=page.index(';const rows=DATA.records',a)
    page=page[:a]+json.dumps(result,ensure_ascii=False).replace('</','<\\/')+page[b:]
    page=page.replace('图片难度 v5','图片难度 v6').replace('<nav id="filters">','<p><b>v6：7y-19、S9-09、zsNo-13采用中等；后两图为新目标空间，旧角位仅对照。</b></p><nav id="filters">')
    (OUT/'review.html').write_text(page,encoding='utf-8')
    prefix='../../research/difficulty/difficulty_scope_resolution_20261016/'
    write(ROOT/'analysis_results/image_difficulty_full_review_20261010/CURRENT.json',dict(version=VERSION,table=prefix+'current_259.csv',details=prefix+'current_259.json',review=prefix+'review.html',analysis_table=prefix+'analysis_eligible.csv',status='two new spaces and three medium adjudications; target changes separated from same-target disagreements'))
    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':main()
