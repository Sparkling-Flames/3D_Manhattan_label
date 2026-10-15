"""全部已确认新增空间优先用于图片难度；旧范围仅作对照。"""
import copy
import csv
import json
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from ..data_prep.consolidate_research_input import load_current_bundle
from .scope_difficulty_review_20261011 import floor_features

ROOT=Path(__file__).resolve().parents[3]
PRIOR=ROOT/'research/difficulty_user_revision_20261015'
OUT=ROOT/'research/difficulty_scope_received_20261015'
VERSION='scope_preferred_difficulty_received_20261015_v2'


def write(path, value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def main():
    b=load_current_bundle(); scopes={r['image_id']:r for r in b['floor_scope_update']['records']
        if r['image_code'] in {'uNb9QFRL6hY-86','q9vSo1VnCiC-34'}}
    # 此前已确认的两图是独立增量，不能被本次整表导出的旧状态回滚。
    delta=json.loads((ROOT/'research/quality_scope_model_handoff_20261015/TWO_IMAGE_SCOPE_DELTA.json').read_text(encoding='utf-8-sig'))
    opinions=json.loads((ROOT/'research/difficulty_target_integration_20261015/new_target_addendum.json').read_text(encoding='utf-8-sig'))
    old_opinions={r['image_id']:r for r in opinions['records']}
    for s in delta['records']:
        opinion=old_opinions[s['image_id']]
        assert s['new_floor_polygon_xz_h']==opinion['new_floor']
        scopes[s['image_id']]=dict(image_id=s['image_id'],image_code=s['image_code'],
            reference_id=s['new_floor_candidate_id'],floor_xz_h=s['new_floor_polygon_xz_h'],
            evidence=opinion['evidence'],source='research/quality_scope_model_handoff_20261015/TWO_IMAGE_SCOPE_DELTA.json')
    doc=json.loads((PRIOR/'current_259.json').read_text(encoding='utf-8-sig'))
    rows=copy.deepcopy(doc['records']); OUT.mkdir(exist_ok=True)
    for r in rows:
        if r['card']=='7y3sRwLe3Va-26_corrected.jpg':
            r['card']='../difficulty_user_revision_20261015/'+r['card']
        if r['image_id'] not in scopes:continue
        s=scopes[r['image_id']]; f=floor_features(s['floor_xz_h'])
        assert f['N_turn']==4 and f['H']==0 and f['geometry_status']=='valid_camera_inside'
        c=dict(target_id=s['reference_id'],role='confirmed_scope',floor=s['floor_xz_h'],features=f)
        r['candidates'].append(c);r['selected']=c
        r.update(target_version=c['target_id'],current_class='简单',conditional_difficulty='简单',
            N_floor=4,N_turn=4,H=0,inference_burden='low',scope_coordinates_pending=False,
            top_boundary_pending=True,classification_basis='user_confirmed_floor_and_photo_review',
            evidence=s.get('evidence','采用2026-10-15用户确认的主体矩形底面，原小分支不属于此目标；四个主要角位可由现有墙线定位，无几何自遮挡，按既有粗分类为简单。顶界仍未独立确认。'),
            question='',selection_reason='按用户要求以新增空间判定难度，旧范围仅对照',
            H_interpretation='新主体范围H=0；原GT小分支的隐藏角不再计入新目标。',
            scope_source=s.get('source','load_current_bundle.floor_scope_update'),
            user_revision_action='confirmed_new_scope_received')
        im=Image.open(r['photo']).convert('RGB');draw=ImageDraw.Draw(im)
        p=np.array(s['floor_xz_h']);u=(np.arctan2(p[:,0],-p[:,1])/(2*np.pi)+.5)*im.width
        v=(np.arctan2(1,np.linalg.norm(p,axis=1))/np.pi+.5)*im.height
        for n,(x,y) in enumerate(zip(u,v),1):
            draw.ellipse((x-6,y-6,x+6,y+6),fill='cyan');draw.text((x+8,y),str(n),fill='cyan',stroke_width=1,stroke_fill='black')
        name=r['image']+'_confirmed_floor.jpg';im.save(OUT/name,quality=92);r['card']=name
    counts=dict(Counter(r['current_class'] for r in rows))
    adoption=[]
    for r in rows:
        candidates=[c for c in r['candidates'] if c['role']=='confirmed_scope']
        if not candidates:continue
        assert r['selected']['target_id']==candidates[-1]['target_id'], 'difficulty must use newest confirmed scope'
        adoption.append(dict(image=r['image'],image_id=r['image_id'],target_id=r['target_version'],
            new_scope_selected=True,current_class=r['current_class'],N=r['N_turn'],H=r['H']))
    assert len(adoption)==37
    assert counts=={'简单':148,'中等':31,'困难':33,'待复核':5,'单列':42}
    summary=dict(doc['summary'],version=VERSION,counts=counts,accepted_alternatives=37,scope_pending=0,
        new_visual_review_count=4,
        changed_from_previous_scope=sum(r['current_class']!=r['previous_scope_class'] for r in rows),
        changed_from_visual_v2=sum(r['current_class']!=r['previous_visual_class'] for r in rows),
        note='全部37张已确认新增范围均用于难度；旧范围只对照，不以旧质量分数影响分档。259为继承覆盖，本轮检查4张新增范围照片，并非重新逐看259张。')
    result=dict(version=VERSION,base_version=doc['version'],summary=summary,records=rows)
    write(OUT/'current_259.json',result)
    fields=['image','image_id','current_class','conditional_difficulty','target_version','N_floor','N_turn','H','top_boundary_pending','evidence','question']
    with (OUT/'current_259.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
    # 复用上一版已修正的模板，保持用户修订GT及待范围提示的显示语义。
    page=(PRIOR/'review.html').read_text(encoding='utf-8')
    start=page.index('const DATA=')+len('const DATA=');end=page.index(';const rows=DATA.records',start)
    page=page[:start]+json.dumps(result,ensure_ascii=False).replace('</','<\\/')+page[end:]
    page=page.replace('uNb-86/q9-34等待用户补范围，展示的旧GT不代表新空间。','uNb-86/q9-34新主体底面已接入，两图归简单；青色点仅为底面角位，未补造顶角。')
    page=page.replace('先在已接受的候选范围中优先采用 H=0 的范围，再评结构与定位负担。','凡已有用户确认的新增范围，一律按新增范围评结构与定位负担；旧范围仅作对照。')
    (OUT/'review.html').write_text(page,encoding='utf-8')
    pointer=ROOT/'analysis_results/image_difficulty_full_review_20261010/CURRENT.json'
    write(pointer,dict(version=VERSION,table='../../research/difficulty_scope_received_20261015/current_259.csv',
        details='../../research/difficulty_scope_received_20261015/current_259.json',
        review='../../research/difficulty_scope_received_20261015/review.html',
        status='all 37 confirmed new scopes adopted for difficulty; old scopes retained only for comparison'))
    with (OUT/'new_scope_adoption_37.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(adoption[0]));w.writeheader();w.writerows(adoption)
    write(OUT/'CHECKS.json',dict(main_new_scope_records=2,adopted_new_scopes=37,counts=counts,
        all_new_scopes_selected=True,quality_scores_used_for_classification=False,score_recomputed=False))
    print(json.dumps(dict(counts=counts,all_37_new_scopes_adopted=True),ensure_ascii=False))


if __name__=='__main__':main()
