"""Build a searchable full-corpus index and lazily loaded per-image evidence.
Only preserves existing evidence and manually confirmed floor regions. No scoring or gate changes.
"""
import collections,csv,hashlib,json,pathlib,shutil
HERE=pathlib.Path(__file__).resolve().parent; ROOT=HERE.parent; OUT=HERE/'dist'
REPO=ROOT/'quality_scope_current'; INV=ROOT/'scope_full_inventory_20261010'
read=lambda p:json.loads(p.read_text())
old=read(HERE/'fixtures/published-v2.1-data.json'); oldby={c['image_code']:c for c in old['images']}
inv=read(INV/'inventory.json'); rows={c['image_code']:c for c in inv['images']}
if (INV/'scope_by_image.json').exists():rows.update({c['image_code']:c for c in read(INV/'scope_by_image.json')})
evidence=read(REPO/'analysis_results/image_difficulty_full_review_20261010/all_scope_evidence.json'); ev={c['image']:c for c in evidence}
photos=read(ROOT/'scope_photo_manifest_20261010.json')
received_path=ROOT/'manual_scope_review_received_20261010_batch2.json'; received=read(received_path);sha=hashlib.sha256(received_path.read_bytes()).hexdigest()
confirmed={r['image_code']:r for r in received['records']}
original_objects={}
try:
 bundle=read(REPO/'analysis_results/research_input_20260929/preprocessed_source.json')
 original_objects={o['object_id']:o for o in bundle.get('objects',bundle.get('data',{}).get('objects',[]))}
except (ValueError,FileNotFoundError):pass
updates=read(REPO/'analysis_results/research_input_20260929/quality_update_20261010.json')['accepted_records']
local_path=ROOT/'local_scope_verified/integration_verified69.json'
local_rows=read(local_path) if local_path.exists() else []
bycomments=collections.defaultdict(list)
for c in inv['comments']:
 if c.get('image_code'):bycomments[c['image_code']].append(c)
 if not c.get('image_code') and c.get('identity_status')=='exact_historical_image_outside_259' and c.get('image_id'):bycomments[c['image_id']].append(c)
# Local evidence is separately verified, never silently assigned to a person or repository URL.
for local in local_rows:
 assert local['raw_text_verified'] and local['image_code'] in ev
 assert local['image_id']==ev[local['image_code']]['image_id']
 exact=local['binding_level']=='exact_annotation'; pair=local['binding_level']=='exact_pair'
 observations={a['record_id']:a for a in ev[local['image_code']]['observations']}
 if exact:assert observations[local['record_id']]['object_id']==local['object_id']
 if pair:
  assert len(local['pair_bindings'])==2
  for binding in local['pair_bindings']:assert observations[binding['record_id']]['object_id']==binding['object_id']
 status=local['interpretation_status']
 row={'image_code':local['image_code'],'image_id':local['image_id'],'comment':local['comment'],'comment_id':local['local_comment_id'],'record_id':local.get('record_id') if exact else None,'worker_id':None,'is_local_increment':True,'binding_level':local['binding_level'],'pair_bindings':local['pair_bindings'],'content_role':local['content_role'],'reference_version':local.get('reference_version'),'reference_id':local.get('reference_id'),'interpretation_status':status,'keyword_hit':status!='context_requires_manual_semantics','target_difference_candidate':status=='spatial_target_or_extent_candidate_requires_visual_check','boundary_candidate':False,'same_scope_or_negation_context':status=='same_target_or_later_same_wall_correction','detail_context':status=='detail_or_visibility_context','source_occurrences':[{'path':src['source_file'],'pointer':src['json_pointer'],'role':'local_review_increment','source_kind':'local_original','updated_at':src.get('raw_updated_at') or src.get('raw_created_at'),'raw_updated_at':src.get('raw_updated_at'),'raw_created_at':src.get('raw_created_at'),'reported_parent_time':src.get('reported_updated_at'),'raw_record_sha256':src.get('raw_record_sha256'),'reference_version':local.get('reference_version'),'reference_id':local.get('reference_id'),'binding_level':local['binding_level'],'verification_id':local['local_comment_id']} for src in local['sources']]}
 bycomments[local['image_code']].append(row)
(OUT/'records').mkdir(exist_ok=True)
(OUT/'catalogue').mkdir(exist_ok=True)
if local_rows:shutil.copyfile(local_path,OUT/'catalogue/integration_verified69.json')
outside_local=ROOT/'local_scope_verified/additional_outside259_user_comments.json'
if outside_local.exists():shutil.copyfile(outside_local,OUT/'catalogue/additional_outside259_user_comments.json')
for f in ['all_259_images.csv','unique_comments.csv','all_comment_occurrences.csv','source_manifest.json','summary.json','scope_by_image.json.gz','historical_outside_259_comments.csv']:
 if (INV/f).is_file():shutil.copyfile(INV/f,OUT/'catalogue'/f)
result=[]
for code in sorted(set(ev)|set(bycomments)):
 e=ev.get(code,{});oldc=oldby.get(code,{});r=rows.get(code,{});cs=bycomments.get(code,[]);pm=photos.get(code,{})
 imageid=e.get('image_id') or next((x.get('image_id') for x in cs if x.get('image_id')),'')
 refs=e.get('reference_flags',{})
 target=any(c.get('target_difference_candidate') or c.get('boundary_candidate') for c in cs)
 keyword=any(c.get('keyword_hit') for c in cs)
 numeric=bool(r.get('has_any_geometry_candidate'))
 gates=sorted({o.get('gate','') for o in e.get('observations',[])}|{c.get('current_gate','') for c in cs if c.get('current_gate')})
 gates=sorted(set(gates)|{a['formal_quality_gate'] for a in oldc.get('annotations',[]) if a.get('formal_quality_gate')})
 paused=bool(r.get('reference_paused',False) or any('hold' in g for g in gates))
 cats=[]
 if target or str(refs.get('scope_explicit_tag')).lower()=='true' or str(refs.get('scope_existing_ledger')).lower()=='true':cats.append('scope_comment')
 if numeric:cats.append('numeric_candidate')
 if keyword and not target:cats.append('detail_or_locator')
 if paused:cats.append('reference_paused')
 if not cats:cats.append('unclassified')
 local_cs=[x for x in cs if x.get('is_local_increment')]
 if local_cs:cats.append('local_increment')
 if code in confirmed:cats.insert(0,'confirmed')
 primary=cats[0]; grouped={}
 for item in cs:
  text=item['comment'];g=grouped.setdefault((text,bool(item.get('is_local_increment')),item.get('binding_level'),item.get('reference_version'),item.get('reference_id'),item.get('content_role'),tuple(x['record_id'] for x in item.get('pair_bindings',[]))), {'text':text,'comment_ids':[],'workers':[],'record_ids':[],'sources':[],'flags':[],'is_local_increment':bool(item.get('is_local_increment')),'content_role':item.get('content_role'),'pair_bindings':item.get('pair_bindings',[]),'binding_level':item.get('binding_level'),'reference_version':item.get('reference_version'),'reference_id':item.get('reference_id'), 'interpretation_status':item.get('interpretation_status')})
  g['comment_ids'].append(item['comment_id'])
  for dest,key in [('workers','worker_id'),('record_ids','record_id')]:
   if item.get(key) and item[key] not in g[dest]:g[dest].append(item[key])
  for flag,label in [('target_difference_candidate','目标范围措辞'),('boundary_candidate','停止边／边界措辞'),('same_scope_or_negation_context','相同范围／否定语境'),('ordinary_error_context','普通标注误差语境'),('detail_context','细节语境')]:
   if item.get(flag) and label not in g['flags']:g['flags'].append(label)
  for s in item.get('source_occurrences',[]):
   src={'source_file':s['path'],'json_pointer':s.get('pointer',''),'occurrence_id':item['comment_id'],'role':s.get('role',''),'source_kind':s.get('source_kind','repository'),'updated_at':s.get('updated_at'),'raw_updated_at':s.get('raw_updated_at'),'raw_created_at':s.get('raw_created_at'),'raw_record_sha256':s.get('raw_record_sha256'),'reported_parent_time':s.get('reported_parent_time'),'reference_version':s.get('reference_version'),'reference_id':s.get('reference_id'),'binding_level':s.get('binding_level'),'verification_id':s.get('verification_id'),'field':s.get('field','')}
   if src not in g['sources']:g['sources'].append(src)
 comments=sorted(grouped.values(),key=lambda x:(not any(y['role']=='raw_review_export' for y in x['sources']),not any(f in x['flags'] for f in ['目标范围措辞','停止边／边界措辞']),not ('左右' in x['text'] and 'gt' in x['text'].lower()),x['text']))
 points=oldc.get('reference_points_1024x512') or e.get('selected_gt_points',[])
 anns=[]
 for o in e.get('observations',[]):
  rid=o['record_id'];prior=next((a for a in oldc.get('annotations',[]) if a['record_id']==rid),{})
  anns.append({**prior,**o,'current_worker_id':prior.get('current_worker_id',''),'points':o['points'],'historical_geometry':True,'subsequent_point_review':rid in updates,'point_review_revision':'quality_review_20261010_v1' if rid in updates else None,'point_review_source':'analysis_results/research_input_20260929/quality_update_20261010.json' if rid in updates else None})
 ref=e.get('gt_object_id','');orig=e.get('original_gt_object_id',ref);revised=ref!=orig
 c={'image_code':code,'image_id':imageid,'non_orthogonal':code in ['x8F5xyUWy9e-01','x8F5xyUWy9e-09'],'reference_object_id':oldc.get('reference_object_id',ref),'reference_points_1024x512':points,'reference_version':'selected_revised' if revised else 'original','original_reference_object_id':orig,'reference_version_label':'当前有效选定 GT（修订版）' if revised else '当前有效选定 GT（原始版）','photo':pm.get('photo') or oldc.get('photo'),'photo_source':pm.get('path') or oldc.get('photo_source'),'photo_git_blob':pm.get('blob') or oldc.get('photo_git_blob'),'photo_dimensions':pm.get('original_dimensions'),'display_dimensions':pm.get('display_dimensions'),'editable':bool(points and (pm.get('photo') or oldc.get('photo'))),'edit_block_reason':'' if points and (pm.get('photo') or oldc.get('photo')) else '历史条目未绑定当前有效 GT／原始全景，只供查证，不可编辑或确认范围。','identity_confirmed':bool(r.get('memory_identity_confirmed')),'text_evidence_class':r.get('text_evidence_class'),'text_evidence_summary':r.get('text_evidence_summary'),'primary_category':primary,'categories':cats,'reference_paused':paused,'hold_layers':r.get('hold_layers',[]),'reference_paused_meaning':r.get('reference_paused_meaning'),'historical_snapshot_hold':bool(r.get('historical_snapshot_hold')),'current_user_quality_reference_hold':bool(r.get('current_user_quality_reference_hold')),'formal_quality_hold_observed':bool(r.get('formal_quality_hold_observed')),'gates':gates,'annotation_count':len(anns),'comment_count':len(comments),'local_increment_count':len(local_cs),'latest_local_correction':next((x['comment'] for x in sorted(local_cs,key=lambda x:max((y.get('updated_at') or '' for y in x['source_occurrences']),default=''),reverse=True) if x['interpretation_status']=='same_target_or_later_same_wall_correction'),'') ,'comment_occurrence_count':sum(len(x['sources']) for x in comments),'numeric_candidate_count':r.get('geometry_gt_symdiff_ge_0.3_all_historical',0),'detail_file':'records/'+code+'.json','evidence_file':'records/'+code+'.json','evidence_card':oldc.get('evidence_card'),'in_current_corpus':bool(e),'tags':['参考暂停' if paused else '', '历史基集外' if not e else '', '单条／单人仍保留' if len(anns)<=1 else '', '修订参考' if revised else ''],'preview_comment':comments[0]['text'] if comments else '未检索到直接范围原评论。数值偏差仅是机器候选，需看图判断。','search_text':' '.join([imageid,*gates,*[x['comment'] for x in cs],*[o['record_id']+' '+o.get('worker_id','') for o in anns]])}
 c['question']='请结合原评论和原图，判断目标空间及停止边；无需因机器候选而裁剪。'
 if code=='uNb9QFRL6hY-88':c['question']='你已确认这就是待找的图。接下来只需确定认可的边界；认出图片不等于批准当前范围。';c['identity_confirmed']=True
 if code in confirmed:
  rr=confirmed[code];assert rr['reference_object_id']==c['reference_object_id'];assert rr['original_GT_points_1024x512']==points;assert rr['floor_region_confirmed'] and rr['completed']
  c['confirmed_review']={**rr['confirmed_version'],'source_sha256':sha};c['question']='已收到并保留你的范围确认，无需重做。若本地有较新的修改，会保留为待确认草稿。'
 extra=[]
 if paused:extra.append('检索到暂停证据（历史、用户现行要求与正式gate分别展示）；底面确认不会恢复质量资格。')
 if revised:extra.append('当前使用有效修订 GT。旧评论当时所看的 GT 版本未必相同，不能直接当作当前范围问题。')
 if any(a['subsequent_point_review'] for a in anns):extra.append('部分点位已有 2026-10-10 后续复核；这里保留历史图证并逐条标识，不把旧无效点当作当前结论。')
 c['evidence_summary']=f"{len(anns)} 份历史标注，{len(comments)} 条按原文合并的证据，其中本地审核增量 {len(local_cs)} 条来源记录（含比较／上下文，不是独立范围票）。范围措辞、数值偏差都只是待人工辨认的线索。"+''.join(extra)
 detail={'image_code':code,'image_id':imageid,'evidence_source_commit':inv['source_commit'],'historical_comments':comments,'annotations':anns,'condition_gate_groups':e.get('condition_gate_groups',[]),'reference_flags':refs,'reference_version':c['reference_version'],'original_reference_object_id':orig,'selected_reference_object_id':ref,'original_reference_points_1024x512':original_objects.get(orig,{}).get('points_1024x512') if revised else points,'historical_reference_note':('原始 GT 仅作历史层，灰色显示；不更换当前修订基底。' if original_objects.get(orig,{}).get('points_1024x512') else '原始 GT 坐标尚未在本次可用证据中解析；不伪造历史层。') if revised else '原始与当前选定 GT 相同。','all_scope_evidence':e,'inventory':r,'source_comments':cs,'note':'该页只支持人工范围复核。候选不是错误裁定，旧指标不是新参考分数，所有正式资格保持原状。'}
 detail_json=json.dumps(detail,ensure_ascii=False,separators=(',',':'))
 (OUT/c['detail_file']).write_text(detail_json)
 (OUT/c['detail_file'].replace('.json','.js')).write_text('window.__SCOPE_REVIEW_DETAILS__=window.__SCOPE_REVIEW_DETAILS__||{};window.__SCOPE_REVIEW_DETAILS__['+json.dumps(code)+']='+detail_json+';')
 result.append(c)
# Strong matching clue first, then previously confirmed images, then grouped candidates.
priority={'scope_comment':1,'numeric_candidate':2,'detail_or_locator':3,'reference_paused':4,'unclassified':5}
result.sort(key=lambda c:(-2 if c['image_code']=='uNb9QFRL6hY-88' else -1 if c['image_code'] in confirmed else priority.get(c['primary_category'],5),c['image_code']))
data={**{k:v for k,v in old.items() if k!='images'},'images':result,'editor_data_revision':'full_scope_catalogue_20261010','editor_version':'3.0','evidence_source_commit':inv['source_commit'],'initial_image':'uNb9QFRL6hY-88','default_category':'scope_comment','confirmation_notice':'已接回 5 张明确确认的底面范围；更新不会覆盖有效的本地修改。','counts':{'current_corpus':len(evidence),'catalogue_images':len(result),'historical_only':len(result)-len(evidence),'annotations':sum(c['annotation_count'] for c in result),'confirmed_received':len(confirmed),'comments':len(inv['comments']),'comment_occurrences':len(inv['occurrences']),'local_verified_increment':len(local_rows),'local_exact_annotation':sum(x['binding_level']=='exact_annotation' for x in local_rows),'local_image_or_wall_group':sum(x['binding_level']=='image_or_wall_group_only' for x in local_rows),'local_exact_pairs':sum(x['binding_level']=='exact_pair' for x in local_rows),'local_cross_image_contexts':sum(x['content_role']=='original_user_cross_image_relationship_context' for x in local_rows),'local_recent_records':sum(x['content_role']=='original_recent_human_review' for x in local_rows),'local_other_original_records':sum(x['content_role']=='original_user_comment' for x in local_rows),'local_outside_separate':len(read(outside_local)) if outside_local.exists() else 0},'candidate_notice':'机器检索与数值筛查只帮助定位证据，不代表范围错误或必须裁剪；未命中也不证明范围一致。'}
(OUT/'data.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')))
(OUT/'data.js').write_text('window.__SCOPE_REVIEW_DATA__='+json.dumps(data,ensure_ascii=False,separators=(',',':'))+';')
print(json.dumps(data['counts'],ensure_ascii=False));print('index bytes',(OUT/'data.json').stat().st_size)
