"""保存用户GT增量与难度新版；原始标签、旧版评分和loader均保留。"""
from tools.thesis_main.local_inputs import source_zip
import copy
import csv
import json
import zipfile
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from .difficulty_coarse_closeout_20261014 import floor
from .scope_difficulty_review_20261011 import floor_features

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'analysis_results/difficulty_scope_preferred_20261011'
OUT = ROOT / 'research/difficulty/difficulty_user_revision_20261015'
SOURCE = ROOT / 'data/research_gt_revisions/user_feedback_20261015.json'
VERSION = 'scope_preferred_difficulty_user_revision_20261015_v1'


def remove_pairs(points, removed):
    if len(points) % 2 or len(set(removed)) != len(removed) or any(i < 1 or i > len(points)//2 for i in removed):
        raise ValueError('invalid one-based pair selection')
    return [list(p) for i in range(len(points)//2) if i+1 not in removed for p in points[2*i:2*i+2]]


def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))


def write(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def convert_original(raw):
    p = raw['layoutPoints']['points']
    u = np.array([x['coords'][0] for x in p])*1024
    radius = np.linalg.norm(np.array([x['xyz'] for x in p])[:, [0, 2]], axis=1)
    ceiling = (-np.arctan2(raw['layoutHeight']-raw['cameraHeight'], radius)/np.pi+.5)*512
    bottom = (-np.arctan2(-raw['cameraHeight'], radius)/np.pi+.5)*512
    xy = np.column_stack([np.repeat(u, 2), np.stack([ceiling, bottom], axis=1).reshape(-1)])
    return [[float('%.2f'%x), float('%.2f'%y)] for x, y in xy]


def main():
    base = read(BASE/'current_259.json'); rows = copy.deepcopy(base['records'])
    decisions = {r['image_code']: r for r in read(SOURCE)['records']}
    OUT.mkdir(exist_ok=True)
    provenance = []
    archive_path = source_zip()
    with zipfile.ZipFile(archive_path) as z:
        for r in rows:
            name = 'label_data/'+r['image_id']+'_label.json'
            original = convert_original(json.loads(z.read(name)))
            paths = [p for p in (ROOT/'data/mp3d_layout').glob('*/label_cor/'+r['image_id']+'.txt') if '_no_occ' not in str(p)]
            assert len(paths) == 1
            txt = np.loadtxt(paths[0]).tolist()
            assert original == txt, r['image']
            provenance.append(dict(image=r['image'], image_id=r['image_id'], archive_member=name,
                txt=str(paths[0].relative_to(ROOT)).replace('\\','/'), original_json_conversion_exact=True))
            r['card'] = '../../analysis_results/difficulty_scope_preferred_20261011/'+r['card']
            r['old_card'] = '../../analysis_results/image_difficulty_full_review_20261010/'+r['old_card'].split('image_difficulty_full_review_20261010/',1)[1] if r['old_card'] else None
            if r['scope_comparison']:
                r['scope_comparison'] = '../../analysis_results/scope_difficulty_audit_20261011/cards/'+r['image']+'.jpg'
            r['previous_published_class'] = r['current_class']
            if r['image'] not in decisions:
                continue
            d = decisions[r['image']]
            r['user_revision_source'] = str(SOURCE.relative_to(ROOT)).replace('\\','/')
            r['user_revision_action'] = d['action']
            if d['action'] == 'await_new_scope':
                r.update(current_class='待复核', conditional_difficulty='简单',
                    classification_basis='user_simple_judgment_new_target_coordinates_pending',
                    evidence='用户判断主体空间应为简单，已确认尚无补充范围回执；旧GT仅保留展示，不将旧复杂目标结论套用到新空间。',
                    question='等待用户补交新范围坐标，不需要再次裁定主观难度。',
                    scope_coordinates_pending=True, inference_burden='undetermined')
            elif d['action'] == 'difficulty_override':
                r.update(current_class='中等', conditional_difficulty='中等', inference_burden='moderate',
                    classification_basis='user_adjudicated_difficulty', evidence='用户2026-10-15明确裁定中等；原目标不变。', question='')
            else:
                assert d['action'] == 'remove_gt_pairs' and len(txt) == 16
                assert np.allclose(r['selected']['floor'], floor(txt), atol=1e-10, rtol=0), 'displayed numbering/target must match source'
                corrected = remove_pairs(txt, d['removed_pairs_1based'])
                f = floor_features(floor(corrected))
                assert len(corrected) == 12 and f['H'] == 0 and f['geometry_status'] == 'valid_camera_inside'
                tid = 'gt_user_revision_20261015:'+r['image_id']+':remove_pairs_5_6'
                revision = dict(schema='user_gt_pair_removal_v1', image=r['image'], image_id=r['image_id'],
                    reference_id=tid, source=str(SOURCE.relative_to(ROOT)).replace('\\','/'),
                    original_reference_id=r['selected']['target_id'], original_source=provenance[-1]['txt'],
                    original_points_1024x512=txt, removed_pairs_1based=[5,6], retained_original_pairs_1based=[1,2,3,4,7,8],
                    points_1024x512=corrected, floor_xz_h=floor(corrected).tolist(), features=f,
                    reference_kind='user_revised_gt', top_boundary_pending=False,
                    unchanged_surviving_coordinates=True, scoring_recompute_required=True)
                write(OUT/'user_revised_gt.json', revision)
                np.savetxt(OUT/(r['image']+'_user_gt.txt'), corrected, fmt='%.2f')
                candidate=dict(target_id=tid, role='user_revised_gt', floor=revision['floor_xz_h'], features=f)
                r['candidates'].append(candidate); r['selected']=candidate; r['target_version']=tid
                r.update(N_floor=f['N_floor'], N_turn=f['N_turn'], H=f['H'], current_class='简单',
                    conditional_difficulty='简单', inference_burden='low', top_boundary_pending=False,
                    classification_basis='user_corrected_gt_and_codex_photo_review',
                    evidence='用户删除原5/6对错误角后，六处必要转折无几何自遮挡；主要上下墙线可辨，杂物仅局部挡底边，按既有低遮挡六角规则归简单。',
                    question='', selection_reason='用户明确GT纠错优先，保留原GT供对照',
                    H_interpretation='用户纠错后H由1变0；不把原错误GT形成的遮挡归因于图片难度。')
                # 保留原编号以便核验删除对象；这是一张GT证据叠图，不是原图编辑。
                im=Image.open(r['photo']).convert('RGB'); draw=ImageDraw.Draw(im)
                for k, pair in enumerate(np.asarray(corrected).reshape(-1,2,2)):
                    for x,y in pair:
                        x=x/1024*im.width; y=y/512*im.height
                        draw.ellipse((x-5,y-5,x+5,y+5),fill='cyan')
                        draw.text((x+7,y-12),str([1,2,3,4,7,8][k]),fill='cyan',stroke_width=1,stroke_fill='black')
                im.save(OUT/'7y3sRwLe3Va-26_corrected.jpg', quality=92)
                r['card']='7y3sRwLe3Va-26_corrected.jpg'
    assert len(provenance)==259
    summary=dict(version=VERSION, reviewed=259, counts=dict(Counter(r['current_class'] for r in rows)),
        accepted_alternatives=base['summary']['accepted_alternatives'],
        changed_from_previous_scope=sum(r['current_class']!=r['previous_scope_class'] for r in rows),
        changed_from_visual_v2=sum(r['current_class']!=r['previous_visual_class'] for r in rows),
        oos=base['summary']['oos'], doorway=base['summary']['doorway'],
        scope_pending=2, gt_revisions=1, new_visual_review_count=1,
        note='259为继承覆盖，本轮不是259张重新看图；两张等待新范围的简单判断不绑定旧GT')
    result=dict(version=VERSION, base_version=base['version'], summary=summary, records=rows)
    write(OUT/'current_259.json', result)
    fields=['image','image_id','current_class','conditional_difficulty','previous_published_class','target_version','N_floor','N_turn','H','scope_coordinates_pending','classification_basis','evidence','question']
    with (OUT/'current_259.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    payload=json.dumps(result,ensure_ascii=False).replace('</','<\\/')
    template=(BASE/'review_template.html').read_text(encoding='utf-8')
    template=template.replace('259图 · 固定范围后的难度复核', '259图 · 2026-10-15用户修订')
    template=template.replace('<nav id="filters">', '<p><b>新增：7y-03改中等；7y-26采用用户纠错GT。uNb-86/q9-34等待用户补范围，展示的旧GT不代表新空间。</b></p><nav id="filters">')
    template=template.replace("let role=r.selected.role==='confirmed_scope'?", "let role=r.scope_coordinates_pending?'新范围待补，当前仅展示旧GT':r.selected.role==='user_revised_gt'?'用户修订GT':r.selected.role==='confirmed_scope'?")
    template=template.replace('固定范围内：${esc(r.conditional_difficulty)}', "${r.scope_coordinates_pending?'用户拟定新范围的判断':'固定范围内'}：${esc(r.conditional_difficulty)}")
    template=template.replace("c.role==='confirmed_scope'?'已确认替代范围':'原选定GT'", "c.role==='user_revised_gt'?'用户修订GT':c.role==='confirmed_scope'?'已确认替代范围':'原选定GT'")
    template=template.replace("c.target_id===r.target_version?' · 本轮采用':''", "c.target_id===r.target_version?(r.scope_coordinates_pending?' · 旧范围仅展示':' · 本轮采用'):''")
    (OUT/'review.html').write_text(template.replace('__DATA__',payload),encoding='utf-8')
    write(OUT/'provenance_259.json',dict(source_archive=str(archive_path),
        official_conversion_document='https://github.com/sunset1995/HoHoNet/blob/master/README_prepare_data_mp3d_layout.md',
        live_official_archive_bytes_checked=False, records=provenance))
    write(OUT/'CHANGES.json',dict(version=VERSION, decisions=read(SOURCE), summary=summary,
        historical_quality_scores_not_recomputed=True, formal_loader_not_modified=True))
    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':
    main()
