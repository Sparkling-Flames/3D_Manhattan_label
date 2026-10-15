"""Append the user's latest scope queue without altering any review polygon or GT."""
from pathlib import Path
import json,copy,hashlib,shutil
HERE=Path(__file__).resolve().parent; ROOT=HERE.parent
REPO=ROOT/'current_order_review_20261010'; SRC=REPO/'analysis_results/image_difficulty_full_review_20261010/user_review_20261010';OUT=HERE/'dist';REV='24360ad8544d76d8aba18a8e641f784a76ca0d42'
read=lambda p:json.loads(p.read_text())
d=read(OUT/'data.json');q=read(SRC/'scope_queue.json');raw=read(SRC/'source_review.json');assert len(q['cases'])==11 and len(raw['records'])==26
by={c['image_code']:c for c in d['images']};objs={o['object_id']:o for o in read(REPO/'analysis_results/research_input_20260929/preprocessed_source.json')['objects']};user={r['image']:r for r in raw['records']}
confirmed={c['image_code']:copy.deepcopy(c.get('confirmed_review')) for c in d['images'] if c.get('confirmed_review')};assert len(confirmed)==5
warnings={'S9hNv5qa7GM-04':'你这次说GT取了柜边／门扇边；旧评论却描述GT到柜后墙角。两段方向不同，请直接看原图确定应取的墙面，不预设向里或向外。','wc2JMjhGNzB-26':'当前基底是修订GT，旧评论提到部分人员多标走廊。可保留、裁剪或补空间，不预设GT必须裁小；可勾选历史原GT作对照。'}
for i,r in enumerate(q['cases']):
 c=by[r['image']];assert c['image_id']==r['image_id'] and c['reference_object_id']==r['gt_object_id'];assert c['reference_points_1024x512']==objs[r['gt_object_id']]['points_1024x512'];assert c['editable'] and (OUT/c['photo']).is_file();assert r['image'] not in confirmed
 latest={**copy.deepcopy(user[r['image']]),'queue_reason':r['queue_reason'],'case_type':r['case_type'],'source_commit':REV,'source_path':'analysis_results/image_difficulty_full_review_20261010/user_review_20261010/source_review.json','source_pointer':'/records/'+str(raw['records'].index(user[r['image']])),'source_file_sha256':hashlib.sha256((SRC/'source_review.json').read_bytes()).hexdigest(),'floor_region_confirmed':False,'adjudication_status':'awaiting_user_target_decision','is_independent_scope_vote':False}
 c['latest_user_scope_review']=latest;c['scope_batch_id']='user_scope_batch11_20261010';c['scope_batch_index']=i+1;c['scope_review_warning']=warnings.get(r['image'],'')
 c['categories']=['user_scope_batch11']+[x for x in c['categories'] if x!='user_scope_batch11'];c['primary_category']='user_scope_batch11';c['preview_comment']=r['note'];c['question']=f"本轮 {i+1}/11 · {r['queue_reason']}。请画出你认可的目标边界；已有GT可保留，也可切割、直角调整或补空间。"
 c['search_text']+=' '+r['note']+' '+r['queue_reason'];c['tags']=[t for t in c.get('tags',[]) if t!='本轮11图范围重划']+['本轮11图范围重划']
 detail=read(OUT/c['detail_file']);detail['latest_user_scope_review']=latest;detail['scope_review_warning']=c['scope_review_warning'];detail['scope_batch_id']=c['scope_batch_id'];(OUT/c['detail_file']).write_text(json.dumps(detail,ensure_ascii=False,separators=(',',':')))
# Restore historical reference coordinates; do not change the editing reference.
restored=0
for c in d['images']:
 oid=c.get('original_reference_object_id')
 if c.get('reference_version')=='selected_revised' and oid in objs:
  old=objs[oid];assert old['image_id']==c['image_id'];c['original_reference_points_1024x512']=old['points_1024x512'];c['historical_reference_note']='历史原GT坐标已从经哈希核验的正式源恢复，仅作灰色对照，不替换当前编辑基底。'; detail=read(OUT/c['detail_file']);detail['original_reference_points_1024x512']=old['points_1024x512'];detail['historical_reference_note']=c['historical_reference_note'];(OUT/c['detail_file']).write_text(json.dumps(detail,ensure_ascii=False,separators=(',',':')));restored+=1
assert restored==28
assert {c['image_code']:c.get('confirmed_review') for c in d['images'] if c.get('confirmed_review')}==confirmed
d['editor_data_revision']='full_scope_catalogue_batch11_20261010';d['editor_version']='3.1';d['latest_scope_review_source_commit']=REV;d['initial_image']=q['cases'][0]['image'];d['default_category']='user_scope_batch11';d['counts']['new_user_scope_queue']=11;d['counts']['restored_historical_references']=restored;d['new_scope_batch']={'id':'user_scope_batch11_20261010','images':[r['image'] for r in q['cases']],'excluded_by_user':q['excluded_by_user'],'source_commit':REV,'source_path':'analysis_results/image_difficulty_full_review_20261010/user_review_20261010/scope_queue.json','scope':'User reported target/boundary differences; polygons remain unconfirmed until edited and confirmed.'}
d['candidate_notice']='本轮11图来自你最新的范围意见，等待你重划边界；原GT、之前5张确认和本地草稿均保留。其他分类仍为历史检索线索。'
(OUT/'data.json').write_text(json.dumps(d,ensure_ascii=False,separators=(',',':')))
for name in ['scope_queue.json','source_review.json']:
 shutil.copyfile(SRC/name,OUT/'catalogue'/('user_scope_batch11_'+name))
print('Added11 unconfirmed cases; preserved5 confirmations; restored28 historical GT layers; legacy storage identity unchanged.')
