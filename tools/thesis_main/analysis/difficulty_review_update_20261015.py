"""接入局部人工复核、GT纠错和竖向空间范围；保留规则类与人工类的区别。"""
import copy
import csv
import json
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from ..data_prep.consolidate_research_input import load_current_bundle
from .difficulty_user_revision_20261015 import remove_pairs, floor, floor_features, write

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'research/difficulty_scope_received_20261015'
OUT=ROOT/'research/difficulty_review_update_20261015'
VERSION='scope_preferred_difficulty_review_20261015_v3'
GT_ERRORS={'jtcxE69GiFV-05','jtcxE69GiFV-17','wc2JMjhGNzB-14'}


def attach_review(row, review, gt_error):
    if row['image_id']!=review['image_id'] or row['target_version']!=review['target_version']:
        raise ValueError('review_target_mismatch')
    row['latest_user_review']=review
    row['review_disagreement']=(review['grade']!=row['current_class']) if review['grade'] in {'简单','中等','困难'} else None
    if gt_error:
        row.update(gt_error_excluded=True,reference_status='user_reported_gt_error_unresolved',
            class_before_gt_exclusion=row['current_class'],current_class='待修正GT',conditional_difficulty='待修正GT',
            question='用户指出GT错误，待更正后重新判难度；当前不纳入有效难度分析。')


def save_csv(name, records, fields):
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(records)


def card(row, points, paired=False):
    im=Image.open(row['photo']).convert('RGB');d=ImageDraw.Draw(im)
    for i,(x,y) in enumerate(points):
        x=x*im.width/1024;y=y*im.height/512
        d.ellipse((x-5,y-5,x+5,y+5),fill='cyan');d.text((x+7,y),str(i//2+1 if paired else i+1),fill='cyan',stroke_width=1,stroke_fill='black')
    name=row['image']+'_current.jpg';im.save(OUT/name,quality=92);row['card']=name


def main():
    OUT.mkdir(exist_ok=True)
    receipt=OUT/'user_review_receipt.json'
    if not receipt.exists():
        receipt.write_bytes(Path('C:/Users/ASUS/Downloads/image_difficulty_scope_preferred_my_review.json').read_bytes())
    review=json.loads(receipt.read_text(encoding='utf-8-sig'))
    base=json.loads((BASE/'current_259.json').read_text(encoding='utf-8-sig'))
    assert review['review_version']==base['version']
    rows=copy.deepcopy(base['records']);byid={r['image_id']:r for r in rows}
    assert len({r['image_id'] for r in review['records']})==len(review['records'])
    for r in rows:
        r.update(gt_error_excluded=False,reference_status='no_unresolved_gt_error_recorded',latest_user_review=None,
            review_disagreement=None,scope_semantics='whole_space_vertical_boundary',
            applicability_note='范围为整个空间的竖向边界；顶角坐标是否完整是独立的几何表示状态。')
        for key in ['card','old_card','scope_comparison']:
            if r.get(key):r[key]='../difficulty_scope_received_20261015/'+r[key]
    for v in review['records']:
        attach_review(byid[v['image_id']],v,v['image'] in GT_ERRORS)
    # 明确的错误与未决目标先排除；不把主观换档直接当作机器规则验证。
    for r in rows:
        r['difficulty_analysis_exclusion']='gt_error' if r['gt_error_excluded'] else ''
        if r['image']=='S9hNv5qa7GM-09':
            r['difficulty_analysis_exclusion']='target_scope_unresolved'
            r['question']='用户指出两个空间，尚无新增范围坐标；本次有效难度分析暂排除。'
        if r['image'] in {'pRbA3pwrgk9-16','uNb9QFRL6hY-51'}:
            r['oos_subtype']='suspected_user_review'
            r['scene']=r['scene']+';oos_suspected'
            r['difficulty_analysis_exclusion']='special_applicability_pending'
        if r['image'] in {'q9vSo1VnCiC-24','uNb9QFRL6hY-32'}:
            r['current_class']='单列'
            r['special_review_status']='user_requested_separate_discussion'
            if r['image']=='q9vSo1VnCiC-24':
                r['doorway_status']='suspected_user_review'
                r['scene']=r['scene']+';doorway_suspected'
    scopes=load_current_bundle()['floor_scope_update']['records']
    for s in scopes:
        if s['image_code'] not in {'pa4otMbVnkk-11','uNb9QFRL6hY-54'}:continue
        r=byid[s['image_id']];f=floor_features(s['floor_xz_h'])
        assert f['N_turn']==4 and f['H']==0 and f['geometry_status']=='valid_camera_inside'
        c=dict(target_id=s['reference_id'],role='confirmed_scope',floor=s['floor_xz_h'],features=f)
        r['candidates'].append(c);r['selected']=c
        r.update(target_version=c['target_id'],current_class='简单',conditional_difficulty='简单',
            N_floor=4,N_turn=4,H=0,inference_burden='low',space_scope_confirmed=True,top_boundary_pending=True,
            classification_basis='confirmed_vertical_space_and_photo_review',
            evidence='采用本次确认的主体矩形空间，整空间竖向裁切后排除原入口分支；四处主要角位有墙线依据，H=0，局部家具不造成分支未知。',
            question='',selection_reason='用户已确认新增空间，整个高度范围一起采用')
        p=np.asarray(s['floor_xz_h']);uv=np.column_stack([(np.arctan2(p[:,0],-p[:,1])/(2*np.pi)+.5)*1024,(np.arctan2(1,np.linalg.norm(p,axis=1))/np.pi+.5)*512])
        card(r,uv)
    r=next(r for r in rows if r['image']=='x8F5xyUWy9e-03')
    source=next((ROOT/'data/mp3d_layout').glob('test/label_cor/'+r['image_id']+'.txt'))
    original=np.loadtxt(source).tolist();assert len(original)==16
    assert np.allclose(floor(original),r['selected']['floor'],rtol=0,atol=1e-10)
    corrected=remove_pairs(original,[7,8]);f=floor_features(floor(corrected))
    assert f['N_turn']==6 and f['H']==0 and f['geometry_status']=='valid_camera_inside'
    tid='gt_user_revision_20261015:'+r['image_id']+':remove_pairs_7_8'
    revision=dict(image=r['image'],image_id=r['image_id'],reference_id=tid,original_reference_id=r['target_version'],
        source='user message 2026-10-15',original_points_1024x512=original,points_1024x512=corrected,
        removed_pairs_1based=[7,8],retained_original_pairs_1based=[1,2,3,4,5,6],features=f,
        original_source=str(source.relative_to(ROOT)),historical_gt_preserved=True)
    write(OUT/'x8F5xyUWy9e-03_user_gt.json',revision)
    np.savetxt(OUT/'x8F5xyUWy9e-03_user_gt.txt',corrected,fmt='%.2f')
    c=dict(target_id=tid,role='user_revised_gt',floor=floor(corrected).tolist(),features=f)
    r['candidates'].append(c);r['selected']=c
    r.update(target_version=tid,N_floor=6,N_turn=6,H=0,current_class='简单',conditional_difficulty='简单',
        reference_status='user_corrected_gt',inference_burden='low',top_boundary_pending=False,
        classification_basis='user_corrected_gt_and_photo_review',
        evidence='按用户指示删除原第7、8对点，保留第1至6对坐标和顺序；六转折H=0，墙顶及竖向接缝提供主要定位线索，床柜只局部挡底边，归简单。',
        selection_reason='采用用户纠错GT，错误原版本仅保留对照',question='')
    card(r,corrected,paired=True)
    comparisons=[]
    for r in rows:
        if r['current_class'] not in {'简单','中等','困难'} and not r['difficulty_analysis_exclusion']:
            r['difficulty_analysis_exclusion']='special_or_pending'
        r['difficulty_analysis_eligible']=not bool(r['difficulty_analysis_exclusion'])
        v=r['latest_user_review']
        if v:comparisons.append(dict(image=r['image'],target_version=v['target_version'],
            prior_class=v['proposed_class'],user_grade=v['grade'],note=v['note'],
            current_class=r['current_class'],analysis_exclusion=r['difficulty_analysis_exclusion'],
            receipt_present=True,explicit_grade=bool(v['grade'])))
        if r['selected']['role']=='confirmed_scope':
            r['space_scope_confirmed']=True
            assert r['selected']['target_id']==[c for c in r['candidates'] if c['role']=='confirmed_scope'][-1]['target_id']
    counts=dict(Counter(r['current_class'] for r in rows));eligible=[r for r in rows if r['difficulty_analysis_eligible']]
    summary=dict(base['summary'],version=VERSION,counts=counts,accepted_alternatives=39,gt_revisions=2,
        scope_pending=1,
        changed_from_previous_scope=sum(r['current_class']!=r['previous_scope_class'] for r in rows),
        changed_from_visual_v2=sum(r['current_class']!=r['previous_visual_class'] for r in rows),
        oos=sum('oos' in r['scene'] for r in rows),doorway=sum('doorway' in r['scene'] for r in rows),
        new_visual_review_count=3,note='仅3张几何变更图本轮重新看图；用户报告主要审核中等/困难，36条回执不等于完整覆盖或盲审。',
        user_receipt_records=len(comparisons),gt_error_excluded=3,analysis_counts=dict(Counter(r['current_class'] for r in eligible)))
    result=dict(version=VERSION,base_version=base['version'],summary=summary,records=rows)
    write(OUT/'current_259.json',result)
    fields=['image','image_id','target_version','current_class','conditional_difficulty','N_turn','H','scope_semantics','reference_status','gt_error_excluded','difficulty_analysis_eligible','difficulty_analysis_exclusion','evidence']
    save_csv('current_259.csv',rows,fields);save_csv('analysis_eligible.csv',eligible,fields)
    save_csv('excluded.csv',[r for r in rows if not r['difficulty_analysis_eligible']],fields)
    save_csv('user_review_comparison.csv',comparisons,list(comparisons[0]))
    page=(BASE/'review.html').read_text(encoding='utf-8');a=page.index('const DATA=')+len('const DATA=');b=page.index(';const rows=DATA.records',a)
    page=page[:a]+json.dumps(result,ensure_ascii=False).replace('</','<\\/')+page[b:]
    page=page.replace('新范围仅底面已确认。','新范围确认的是整个空间的竖向边界，不只是地面；精确顶角坐标另记。')
    page=page.replace('<nav id="filters">','<p><b>本次：x8-03删原7/8对点；pa4-11、uNb-54采用新增空间。GT错误单列排除；你的复核与规则分类并列显示。</b></p><nav id="filters">')
    page=page.replace("['全部','简单'","['全部','待修正GT','简单'")
    page=page.replace('<b>你此前的审核</b>', '<b>本次你的审核</b><pre>${esc(opinion(r.latest_user_review))}</pre><p>分析状态：${r.difficulty_analysis_eligible?\'可用\':esc(r.difficulty_analysis_exclusion)}</p><b>你此前的审核</b>')
    (OUT/'review.html').write_text(page,encoding='utf-8')
    write(ROOT/'analysis_results/image_difficulty_full_review_20261010/CURRENT.json',dict(version=VERSION,
        table='../../research/difficulty_review_update_20261015/current_259.csv',details='../../research/difficulty_review_update_20261015/current_259.json',
        review='../../research/difficulty_review_update_20261015/review.html',analysis_table='../../research/difficulty_review_update_20261015/analysis_eligible.csv',
        status='vertical whole-space targets; unresolved GT errors excluded; user review separate from rule class'))
    assert sum(counts.values())==259 and sum(r['selected']['role']=='confirmed_scope' for r in rows)==39
    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':main()
