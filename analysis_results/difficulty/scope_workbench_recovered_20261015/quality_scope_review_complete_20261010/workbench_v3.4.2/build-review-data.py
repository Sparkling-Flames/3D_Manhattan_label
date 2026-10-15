"""Extend the existing workbench without changing its source/GT bindings."""
import csv, hashlib, json, pathlib, shutil
HERE=pathlib.Path(__file__).resolve().parent
ROOT=HERE.parent
PRO=ROOT/'pro_review_20261010/unpacked/quality_four_tasks_20261010'
REPO=ROOT/'quality_integration_20261010'
OUT=HERE/'dist'
read=lambda p:json.loads(p.read_text())
data=read(OUT/'data.json')
evidence={x['image']:x for x in read(REPO/'analysis_results/image_difficulty_full_review_20261010/all_scope_evidence.json')}
geometry={x['code']:x for x in read(PRO/'shared/data/current_geometry.json')['images']}
comments=read(PRO/'01_scope_screening/source/source_comments_union24.json')
metrics={r['record_id']:r for r in csv.DictReader((PRO/'01_scope_screening/results/scope_records_3152_replayed.csv').open(encoding='utf-8-sig'))}
received=read(ROOT/'manual_scope_review_received_20261010.json')
confirmed=read(ROOT/'manual_scope_confirmation_20261010.json')
assert hashlib.sha256((ROOT/confirmed['source_file']).read_bytes()).hexdigest()==confirmed['source_sha256']
assert received['source_commit']==data['source_commit']==confirmed['source_commit']
questions={
'e9zR4mvMWw7-17':'主体能否不包含侧方分支？你已确认的底面范围已保留，顶部封口仍待核实。',
'e9zR4mvMWw7-09':'相机附近主体与餐厨连通处在哪里停止？你已确认的底面范围已保留。',
'b8cTxDM8gDG-18':'大小范围是否可以并存？你已确认的小范围已保留，原大 GT 不变。',
'q9vSo1VnCiC-29':'梳妆台小前室是否可以作为独立目标？请确认与相邻房间开口处的停止范围。',
'pRbA3pwrgk9-02':'玻璃淋浴隔间是否可以单独作为目标？请确认玻璃内外的范围边界。'}
summaries={
'q9vSo1VnCiC-29':'当前正式质量资格为 hold_scene_or_reference（unconfirmed），本页确认范围不会自动恢复资格。现存全部 5 份 manual 都集中在相机附近的小前室，没有覆盖原 GT 延伸至相邻房间的大翼部。旧评论提到“四位”，当前完整清单为 5 位。新范围尚未批准，编辑起点为原 GT。',
'pRbA3pwrgk9-02':'当前质量门槛为 candidate_pending_geometry，仍待范围及几何审核。现存全部 6 份 manual 都只画相机所在的玻璃淋浴隔间；原 GT 还覆盖隔间外的浴室。玻璃内外是否允许不同目标尚待判断，编辑起点为原 GT。'}
for code in questions:
    e=evidence[code];g=geometry[code]
    c=next((x for x in data['images'] if x['image_code']==code),None)
    ref=next(t for t in g['groundtruths'] if t['id']==g['defaultReferenceId'] and t['version']==g['defaultReferenceVersion'])
    if c is None:
        c={'image_code':code,'image_id':g['imageId'],'reference_object_id':e['gt_object_id'],'reference_points_1024x512':ref['points'],'photo':None}
        data['images'].append(c)
    assert c['reference_points_1024x512']==ref['points']==e['selected_gt_points']
    assert c['reference_object_id']==e['gt_object_id']
    c['question']=questions[code];c['batch']='confirmed_first_batch' if code in [r['image_code'] for r in confirmed['records']] else 'pending_second_batch'
    c['evidence_summary']=summaries.get(code,'首轮底面范围已由你在对话中确认。下方仍保留原评论和全部现存标注记录，供追溯比较。')
    c['reference_record_id']=ref['id'];c['reference_version']=ref['version']
    anns={a['id']:a for a in g['annotations']}
    assert set(anns)=={o['record_id'] for o in e['observations']}
    c['annotations']=[]
    for o in e['observations']:
        a=anns[o['record_id']];m=metrics[o['record_id']]
        assert a['points']==o['points']
        c['annotations'].append({'record_id':o['record_id'],'points':a['points'],'gate':o['gate'],'condition':o['condition'],'worker_id':o['worker_id'],'current_worker_id':m['worker'],'cleaning_disposition':m['cleaning_disposition'],'geometry_status':o['geometry_status'],'formal_quality_gate':a['source_record'].get('worker_quality_gate'),'coverage_full':float(m['coverage_full']),'precision_full':float(m['precision_full']),'annotation_area_over_gt':float(m['annotation_area_over_gt']),'source':o['source']})
    # Group identical historical text, preserving all comments and record scopes in the evidence download.
    grouped={}
    image_comments=[r for r in comments['comments'] if r['image_code']==code]
    image_occurrences=[r for r in comments['occurrence_sources'] if r['image_code']==code]
    for r in image_comments:
        item=grouped.setdefault(r['text'],{'text':r['text'],'comment_ids':[],'workers':[],'sources':[]})
        item['comment_ids'].append(r['comment_id'])
        if r['worker_id'] and r['worker_id'] not in item['workers']:item['workers'].append(r['worker_id'])
        candidates=[o for o in image_occurrences if o['occurrence_id'] in r['occurrence_ids']]
        candidates.sort(key=lambda o:('review_final_20260928/evidence' not in o['source_file'],len(o['source_file']),o['occurrence_id']))
        if candidates:
            o=candidates[0]
            src={k:o.get(k) for k in ['source_file','json_pointer','occurrence_id','updated_at']}
            if src not in item['sources']:item['sources'].append(src)
    c['historical_comments']=list(grouped.values())
    (OUT/'evidence').mkdir(exist_ok=True)
    c['evidence_card']='evidence/'+code+'.jpg'
    shutil.copyfile(REPO/'analysis_results/image_difficulty_full_review_20261010/all_cards'/f'{code}.jpg',OUT/c['evidence_card'])
    c['evidence_file']='evidence/'+code+'.json'
    (OUT/c['evidence_file']).write_text(json.dumps({'image_code':code,'source_commit':data['source_commit'],'reference_record_id':ref['id'],'reference_version':ref['version'],'reference_points_1024x512':ref['points'],'all_scope_evidence':e,'current_annotations':c['annotations'],'historical_comments':image_comments,'comment_occurrence_sources':image_occurrences,'note':'历史证据不构成新的范围批准；覆盖率为既有固定GT结果，不是本次新参考分数。'},ensure_ascii=False,indent=2)+'\n')
    for folder in ['additional_original_photos','shared/selected_original_photos']:
        p=PRO/folder/g['imageInternalPath']
        if p.is_file():
            c['photo']='assets/'+code+'.png';shutil.copyfile(p,OUT/c['photo']);c['photo_source']=folder+'/'+g['imageInternalPath'];break
    if code=='q9vSo1VnCiC-29' and (ROOT/'q9_original.png').is_file():
        c['photo']='assets/'+code+'.png';shutil.copyfile(ROOT/'q9_original.png',OUT/c['photo']);c['photo_source']='repository data/mp3d_layout/test/img/q9vSo1VnCiC_dc320b1236f741a98303db9f89bc68a2.png';c['photo_git_blob']='0a58e5564cbafb8723faf5238be62d76d93169f5'
    conf=next((r for r in confirmed['records'] if r['image_code']==code),None)
    if conf:
        r=next(r for r in received['records'] if r['image_code']==code)
        assert r['polygon']==conf['polygon'] and r['decision']==conf['decision']
        c['confirmed_review']={k:r[k] for k in ['polygon','operations','cuts','decision','note','top_boundary_pending','axis_angle','updated_at']}
        c['confirmed_review'].update({'completed':True,'confirmed_at':confirmed['confirmed_at_utc'],'source':'user_chat','confirmation_message_id':confirmed['confirmation_message_id'],'source_sha256':confirmed['source_sha256'],'floor_region_confirmed':True,'top_boundary_validation':conf['top_boundary_validation']})
    else:
        assert 'confirmed_review' not in c
    if not c['photo']:print('MISSING ORIGINAL PHOTO:',code)
data['editor_data_revision']='scope_batch2_20261010'
data['confirmation_notice']='首轮 3 张底面范围已按 2026-10-10 的明确确认同步；顶部边界不在此次确认范围内。'
(OUT/'data.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
print('Prepared',len(data['images']),'images;',sum(len(c['annotations']) for c in data['images']),'annotation records')
