"""用户补充裁定及整空间上下点对显示；预览外推不升级参考资格。"""
import copy
import csv
import json
import re
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from .scope_reference_reconstruction_20261016 import source_archive_reference

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'research/difficulty/difficulty_user_adoption_20261016'
OUT=ROOT/'research/difficulty/difficulty_pair_display_20261016'
VERSION='scope_preferred_difficulty_user_adopted_20261016_v5'
MEDIUM='7y3sRwLe3Va-11 S9hNv5qa7GM-05 UwV83HsGsw3-10 X7HyMhZNoso-19 b8cTxDM8gDG-18 jh4fc5c5qoQ-13 jtcxE69GiFV-09 pa4otMbVnkk-14 q9vSo1VnCiC-03 q9vSo1VnCiC-32 uNb9QFRL6hY-06 uNb9QFRL6hY-67 q9vSo1VnCiC-30 uNb9QFRL6hY-40 x8F5xyUWy9e-03 yqstnuAEVhm-07'.split()
NOTES={'7y3sRwLe3Va-11':'壁炉可以标注','X7HyMhZNoso-19':'隔开的墙可以标注',
    'jh4fc5c5qoQ-13':'遮挡较多','jtcxE69GiFV-09':'遮挡较多'}
for code in ['q9vSo1VnCiC-03','q9vSo1VnCiC-32','uNb9QFRL6hY-06','uNb9QFRL6hY-67']:
    NOTES[code]='用户指出有人标不同空间，可能存在歧义；本轮按当前目标判中等，不据此确认其它标法错误'


def apply_correction(r):
    code=r['image']
    if code not in MEDIUM+['uNb9QFRL6hY-36','zsNo4HB9uLZ-05']:return
    r['class_before_followup']=r['current_class']
    r['followup_user_review']=dict(grade='中等' if code in MEDIUM else '待修正GT' if code=='zsNo4HB9uLZ-05' else '待复核',
        note=NOTES.get(code,''),source='用户2026-10-16补充消息')
    if code in MEDIUM:
        r.update(current_class='中等',conditional_difficulty='中等',classification_basis='user_followup_20261016',
            user_grade_adopted=True,evidence='用户补充裁定中等。'+NOTES.get(code,'本次未补充具体原因，保留既有视觉依据供对照。'))
        if '可能存在歧义' in NOTES.get(code,''):r['user_scope_ambiguity_note']=NOTES[code]
    else:
        error=code=='zsNo4HB9uLZ-05'
        r.update(current_class='待修正GT' if error else '待复核',
            conditional_difficulty='待修正GT' if error else '待复核',difficulty_analysis_eligible=False,
            difficulty_analysis_exclusion='gt_error' if error else 'user_reported_issue_pending',
            classification_basis='user_followup_20261016',
            evidence='用户指出GT有问题，待修复后再评价。' if error else '用户指出此前已有问题，本次明确待定。',
            question='等待修正参考。' if error else '此前问题尚未解决；保持待定，不按简单纳入。')
        if error:r.update(gt_error_excluded=True,reference_status='user_reported_gt_error_unresolved')


def display_pairs(polygon,ref):
    if ref['full_reference_available']:
        return ref['points_1024x512'],'existing_full_reference'
    constructions=ref['evidence']['constructions']
    planes=[c['source_plane']['plane'] for c in constructions]
    if len(planes)!=1:raise ValueError('ambiguous_source_ceiling')
    a,b,c=planes[0];p=np.asarray(polygon);rho=np.linalg.norm(p,axis=1)
    height=a*p[:,0]+b*p[:,1]+c
    if np.any(height<=0):raise ValueError('ceiling_not_above_camera')
    u=(np.arctan2(p[:,0],-p[:,1])/(2*np.pi)+.5)*1024
    top=(.5-np.arctan2(height,rho)/np.pi)*512
    bottom=(.5+np.arctan2(1,rho)/np.pi)*512
    points=np.column_stack([np.repeat(u,2),np.column_stack([top,bottom]).reshape(-1)]).tolist()
    return points,'source_ceiling_extrapolation_preview'


def normalize_source_evidence(evidence,archive_reference):
    result=copy.deepcopy(evidence)
    for construction in result.get('constructions',[]):
        if construction.get('source_plane'):
            construction['source_plane']['archive']=archive_reference
    return result


def main():
    base=json.loads((BASE/'current_259.json').read_text(encoding='utf-8'))
    rows=copy.deepcopy(base['records']);OUT.mkdir(exist_ok=True)
    refs=json.loads((ROOT/'research/data/scope_quality_rescore_20261016/reference_catalog.json').read_text(encoding='utf-8'))
    refs={r['target_id']:r for r in refs};display=[];changes=[]
    archive_reference=source_archive_reference(ROOT/'data/external/label_data.zip')
    assert set(MEDIUM+['uNb9QFRL6hY-36','zsNo4HB9uLZ-05'])<={r['image'] for r in rows}
    for r in rows:
        old=r['current_class'];apply_correction(r)
        if r['current_class']!=old:
            changes.append(dict(image=r['image'],before=old,after=r['current_class'],reason=r['evidence']))
        for k in ['card','old_card','scope_comparison']:
            if r.get(k):r[k]='../difficulty_user_adoption_20261016/'+r[k]
        if r['selected']['role']!='confirmed_scope':continue
        ref=refs[r['target_version']]
        assert ref['image_id']==r['image_id'] and np.allclose(ref['floor_xz_h'],r['selected']['floor'],atol=1e-8,rtol=0)
        points,status=display_pairs(r['selected']['floor'],ref)
        assert len(points)==2*len(r['selected']['floor'])
        preview=status!='existing_full_reference'
        source_evidence=normalize_source_evidence(ref['evidence'],archive_reference) if preview else dict(method=ref['method'],sources=ref['sources'])
        record=dict(image=r['image'],target_version=r['target_version'],points_1024x512=points,status=status,
            display_only=True,full_reference_available=ref['full_reference_available'],
            source_catalog='research/data/scope_quality_rescore_20261016/reference_catalog.json',
            source_evidence=source_evidence)
        display.append(record)
        r['pair_display_status']=status
        r['pair_display_note']='上下同号为一对。黄色虚线顶点为原顶平面外推预览，尚未核验其对新空间的适用性，不作为完整GT或评分输入。' if preview else '上下同号为一对；使用已重建的当前空间完整参考。'
        im=Image.open(r['photo']).convert('RGB');draw=ImageDraw.Draw(im)
        font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',22)
        for n,pair in enumerate(np.asarray(points).reshape(-1,2,2),1):
            top,bottom=pair*np.array([im.width/1024,im.height/512]);color='#ffd15c' if preview else '#00edff'
            if preview:
                for y in np.arange(top[1],bottom[1],18):draw.line((top[0],y,top[0],min(y+9,bottom[1])),fill=color,width=2)
            else:draw.line((*top,*bottom),fill=color,width=2)
            for pos,is_top in [(top,True),(bottom,False)]:
                x,y=pos;point_color=color if is_top else '#00edff'
                draw.ellipse((x-5,y-5,x+5,y+5),fill=point_color)
                draw.text((min(x+9,im.width-35),y-12),str(n),font=font,fill=point_color,stroke_width=2,stroke_fill='black')
        draw.rectangle((0,0,im.width,36),fill='#152535')
        draw.text((10,4),'CEILING EXTRAPOLATION PREVIEW - NOT VERIFIED GT' if preview else 'CURRENT SPACE - AVAILABLE FULL REFERENCE',font=font,fill='#ffd15c' if preview else '#00edff')
        name=r['image']+'_pairs.jpg';im.save(OUT/name,quality=92);r['card']=name
    assert len(display)==39 and len(changes)==18
    assert all(r['target_version']==old['target_version'] and r['selected']==old['selected'] for r,old in zip(rows,base['records']))
    eligible=[r for r in rows if r['difficulty_analysis_eligible']]
    summary=dict(base['summary'],version=VERSION,counts=dict(Counter(r['current_class'] for r in rows)),
        analysis_counts=dict(Counter(r['current_class'] for r in eligible)),gt_error_excluded=sum(r['gt_error_excluded'] for r in rows),
        changed_in_this_version=len(changes),followup_medium=16,display_pairs=dict(Counter(r['status'] for r in display)),
        changed_from_previous_scope=sum(r['current_class']!=r['previous_scope_class'] for r in rows),
        changed_from_visual_v2=sum(r['current_class']!=r['previous_visual_class'] for r in rows),
        note='用户补充16图中等、1图待定、1图GT错误；39裁切图显示上下点对。27图顶点为外推预览，几何真源与评分资格不因显示升级。')
    result=dict(version=VERSION,base_version=base['version'],summary=summary,records=rows)
    for name,value in [('current_259',result),('display_pairs_39',display),('changes',changes)]:
        (OUT/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    fields=['image','image_id','target_version','current_class','conditional_difficulty','classification_basis','N_turn','H',
        'gt_error_excluded','difficulty_analysis_eligible','difficulty_analysis_exclusion','pair_display_status','pair_display_note','evidence']
    for name,rs in [('current_259',rows),('analysis_eligible',eligible),('excluded',[r for r in rows if not r['difficulty_analysis_eligible']])]:
        with (OUT/(name+'.csv')).open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rs)
    page=(BASE/'review.html').read_text(encoding='utf-8');a=page.index('const DATA=')+len('const DATA=');b=page.index(';const rows=DATA.records',a)
    page=page[:a]+json.dumps(result,ensure_ascii=False).replace('</','<\\/')+page[b:]
    page=re.sub(r'<p><b>(?:新增：|本次：|v4：).*?</b></p>','',page)
    page=re.sub(r'<h1>.*?</h1>','<h1>图片难度 v5 · 复核与上下点对</h1>',page,count=1)
    page=page.replace('<nav id="filters">','<p><b>v5：补充16图中等、1图待定、1图GT错误。39张裁切图均有上下同号点对；黄色虚线为顶界外推预览。</b></p><nav id="filters">')
    page=page.replace('<p class="muted">${esc(r.applicability_note)}</p>','<p><b>${esc(r.pair_display_note||\'\')}</b></p><p class="muted">${esc(r.applicability_note)}</p>')
    page=page.replace('<b>本次你的审核</b>','<b>最新补充裁定</b><pre>${esc(opinion(r.followup_user_review))}</pre><b>此前回执审核</b>')
    # 旧底点图说明会误导已修复的点对显示。
    page=page.replace('青色点仅为底面角位，未补造顶角。','点对显示状态以当前图卡说明为准。')
    (OUT/'review.html').write_text(page,encoding='utf-8')
    prefix='../../research/difficulty/difficulty_pair_display_20261016/'
    pointer=dict(version=VERSION,table=prefix+'current_259.csv',details=prefix+'current_259.json',review=prefix+'review.html',analysis_table=prefix+'analysis_eligible.csv',
        status='user followup adopted; pending/error excluded; display-only ceiling extrapolation explicitly separated')
    (ROOT/'analysis_results/image_difficulty_full_review_20261010/CURRENT.json').write_text(json.dumps(pointer,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':main()
