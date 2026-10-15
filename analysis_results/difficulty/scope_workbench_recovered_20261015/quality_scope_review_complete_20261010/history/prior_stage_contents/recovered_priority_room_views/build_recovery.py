"""Recover two explicitly requested same-room review views from immutable Git source snapshots.
Does not change the current research corpus, any source annotations, or the Site checkout.
"""
import csv,hashlib,json,subprocess
from pathlib import Path
from urllib.parse import quote
from PIL import Image
BASE=Path(__file__).resolve().parent
REPO=BASE.parent/'current_order_review_20261010'
AUDIT=BASE.parent/'expanded_room_scope_review_20261010'
COMMIT='24360ad8544d76d8aba18a8e641f784a76ca0d42'
REPOSITORY='Sparkling-Flames/3D_Manhattan_label'
SNAP='export_label/人工精标/project-20-at-2026-03-27-14-57-e66c6481.json'
IMP='import_json/groudTruth_458_tasks_import_from_updated_gt_20260701.json'
ORI_AUD='analysis_results/research_input_20260929/final_review/原始与人工GT审计.csv'
OUT_BASE='catalogue/recovered-room-views'
J=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
canonical=lambda x:hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
write=lambda p,x:p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
blob=lambda p:subprocess.check_output(['git','-C',str(REPO),'rev-parse',f'{COMMIT}:{p}'],text=True).strip()
url=lambda p:'https://github.com/'+REPOSITORY+'/blob/'+COMMIT+'/'+quote(p,safe='/')
snapshot=J(BASE/'sources'/Path(SNAP).name);impt=J(BASE/'sources'/Path(IMP).name)
auditrows=list(csv.DictReader((REPO/ORI_AUD).open(encoding='utf-8-sig')))
groups=J(AUDIT/'sources/user_group_review_20260912.json')
external={x['image_code']:x for x in J(AUDIT/'external_related_views.json')}
points_of=lambda o:[[x['value']['x']*1024/100,x['value']['y']*512/100] for x in o['annotations'][0]['result'] if x['type']=='keypointlabels']
entries=[];queue=[];reports=[]
for code,idx in [('q9vSo1VnCiC-21',196),('q9vSo1VnCiC-25',187)]:
 ident=external[code]['image_id'];raw=snapshot[idx];imp=impt[idx]
 assert ident in raw['data']['image'] and ident in imp['data']['image']
 pts=points_of(raw);assert pts==points_of(imp)
 aud=next(x for x in auditrows if x['image_id']==ident)
 assert aud['manual_change']=='roundtrip_only' and aud['original_pair_count']==str(len(pts)//2)
 assert json.loads(aud['source_pair_x'])==[p[0] for p in pts[::2]]
 # This is the unchanged keypoint sequence. Never use data.vis_3d: it is x-sorted.
 rawkeypoints=[x for x in raw['annotations'][0]['result'] if x['type']=='keypointlabels']
 ref=f'gt_snapshot:{ident}:{SNAP}#/{idx}/annotations/0/result'
 original=f'gt:{ident}:{aud["original_source"]}'
 version='recovered_original_equivalent_snapshot'
 photo_src=f'data/mp3d_layout/test/img/{ident}.png';photo=BASE/'sources'/f'{ident}.png'
 with Image.open(photo) as im:
  im.load();dims=list(im.size);assert dims==[2048,1024]
  im.convert('RGB').resize((1536,768),Image.Resampling.LANCZOS).save(BASE/'assets'/f'{code}.jpg',quality=94,subsampling=0)
 raw_out=BASE/'sources'/f'{code}.snapshot-record.json';write(raw_out,raw)
 rawpoints=BASE/'sources'/f'{code}.gt-points.json';write(rawpoints,pts)
 raw_aud=BASE/'sources'/f'{code}.original-manual-audit.json';write(raw_aud,aud)
 notes=[{'source_file':'sources/user_group_review_20260912.json','json_pointer':f'/group_reviews/{n}/current/note','field':'note','role':'original_same_room_user_statement','source_kind':'repository','text':groups['group_reviews'][n]['current']['note']} for n in [154,155,156]]
 assert len(set(n['text'] for n in notes))==1
 evidence={'text':notes[0]['text'],'comment_ids':['same_room_q9_six_view_statement'],'workers':[],'record_ids':[],'sources':notes,'flags':['同房间关系，不是范围票'],'is_local_increment':False,'content_role':'original_user_cross_image_relationship_context','pair_bindings':[],'binding_level':'room_group_only','reference_version':None,'reference_id':None,'interpretation_status':'same_room_relation_not_scope_approval','deduplicated_statement_count':1,'source_occurrence_count':3,'scope_vote_count':0}
 provenance={'repository':REPOSITORY,'source_commit':COMMIT,'recovered_version':version,'raw_original_label_cor_available':False,'raw_original_label_cor_expected_path':aud['original_source'],'raw_original_label_cor_status':'not_tracked_in_complete_current_main_git_tree','raw_original_file_byte_hash':None,'recovery_level':'original_equivalent_geometry_recovered_from_audited_snapshot_not_raw_txt','snapshot':{'path':SNAP,'pointer':f'/{idx}/annotations/0/result','selector':'type=keypointlabels in original result order','git_blob':blob(SNAP),'sha256':sha(BASE/'sources'/Path(SNAP).name),'task_id':raw['id'],'annotation_id':raw['annotations'][0]['id'],'snapshot_ground_truth_flag':raw['annotations'][0]['ground_truth'],'snapshot_updated_at':raw['annotations'][0]['updated_at'],'record_sha256_canonical':canonical(raw),'keypoint_sequence_sha256_canonical':canonical(rawkeypoints),'points_sha256_canonical':canonical(pts),'url':url(SNAP),'site_excerpt':f'{OUT_BASE}/sources/{code}.snapshot-record.json'},'independent_import_crosscheck':{'path':IMP,'pointer':f'/{idx}/annotations/0/result','git_blob':blob(IMP),'sha256':sha(BASE/'sources'/Path(IMP).name),'all_ordered_coordinates_exactly_equal':True,'usage':'provenance_crosscheck_only_not_formal_research_input','url':url(IMP)},'original_manual_audit':{'path':ORI_AUD,'git_blob':blob(ORI_AUD),'row_image_id':ident,'sha256':sha(REPO/ORI_AUD),'record':aud,'original_pair_x_exactly_equal':True,'original_pair_count_equal':True,'manual_change':'roundtrip_only','all_raw_original_coordinates_independently_available':False,'url':url(ORI_AUD)},'photo':{'path':photo_src,'git_blob':blob(photo_src),'sha256':sha(photo),'bytes':photo.stat().st_size,'original_dimensions':dims,'url':url(photo_src),'display_path':f'assets/{code}.jpg','display_dimensions':[1536,768],'display_sha256':sha(BASE/'assets'/f'{code}.jpg')},'order_policy':'Preserve source keypoint ring. No sorting, reordering, polygon repair, or point edits. The x-sorted vis_3d URL is not used.','research_population':'outside_current_259_no_research_annotations_added','geometry_validity_is_not_user_approval':True}
 note='从仓库精标快照恢复的原始等价 GT；原始与人工 GT 审计标记 roundtrip_only。未取得原 label_cor 文本字节，引用绑定快照原始关键点顺序，不使用已按 x 排序的 vis_3d 链接。该视图不属于当前259图研究基集，无研究标注，不继承同房其他图的范围确认。'
 c={'image_code':code,'image_id':ident,'non_orthogonal':False,'reference_object_id':ref,'reference_points_1024x512':pts,'reference_version':version,'original_reference_object_id':original,'reference_version_label':'补回参考 GT（原始等价快照，待范围复核）','photo':f'assets/{code}.jpg','photo_source':photo_src,'photo_git_blob':blob(photo_src),'photo_dimensions':dims,'display_dimensions':[1536,768],'editable':True,'edit_block_reason':'','identity_confirmed':False,'identity_mapping_verified':True,'text_evidence_class':'same_room_relation','text_evidence_summary':'原同房登记明确11/12/15/16/21/25为同一房间；这不等于本图GT范围已获确认。','primary_category':'missing_room_scope_review','categories':['missing_room_scope_review','source_backed_scope_clues','newly_requested_room_review'],'reference_paused':False,'hold_layers':[],'reference_paused_meaning':'no_formal_research_eligibility_for_external_reference_view','historical_snapshot_hold':False,'current_user_quality_reference_hold':False,'formal_quality_hold_observed':False,'gates':[],'annotation_count':0,'comment_count':1,'local_increment_count':0,'latest_local_correction':'','comment_occurrence_count':3,'numeric_candidate_count':0,'detail_file':f'records/{code}.json','evidence_file':f'records/{code}.json','evidence_card':None,'in_current_corpus':False,'newly_user_requested_room_review':True,'recovered_reference_view':True,'historical_read_only_entry':False,'tags':['同房间待核对','研究基集外补回','无研究标注','快照恢复GT'],'preview_comment':notes[0]['text'],'search_text':' '.join([code,ident,'q9_six_view_room',notes[0]['text']]),'question':'请独立复核此视角的目标空间与停止边；同房其他视角的已确认范围不会自动应用。','evidence_summary':note,'room_scope_group_ids':['q9_six_view_room'],'reference_provenance':provenance,'floor_region_confirmed':False,'reference_ready':False,'selected_target':None}
 c['missing_room_scope']={'priority':2,'label':'同房间待核对','reason':'原六视角同房登记中的缺失视图，已补回照片与可追溯GT快照；需逐图判断目标范围。','scope_difference_status':'pending_review','reference_warning':note,'source_queue':'catalogue/missing-room-scope/expanded_queue.json','direct_evidence_count':1,'source_summary':[{'text':notes[0]['text'],'source_pointer':'sources/user_group_review_20260912.json#/group_reviews/154/current/note','record_ids':[],'reference_version':None,'reference_id':None,'source':notes[0]}],'independent_votes':0,'evidence_count_is_not_vote_count':True,'newly_user_requested_room_review':True}
 rec={'image_code':code,'image_id':ident,'evidence_source_commit':COMMIT,'historical_comments':[evidence],'annotations':[],'condition_gate_groups':[],'reference_flags':{},'reference_version':version,'original_reference_object_id':original,'selected_reference_object_id':ref,'original_reference_points_1024x512':pts,'original_reference_points_recovery_status':'audited_original_equivalent_snapshot','historical_reference_note':note,'all_scope_evidence':{},'inventory':{'image_code':code,'image_id':ident,'in_current_corpus':False,'total_records':0,'user_confirmed_floor_region':False,'scope_approval_propagation_allowed':False,'newly_user_requested_room_review':True},'source_comments':[],'note':note,'reference_provenance':provenance,'room_relation_evidence':[evidence]}
 write(BASE/c['detail_file'],rec)
 entries.append(c)
 queue.append({'image_code':code,'image_id':ident,'reference_object_id':ref,'reference_version':version,'original_reference_object_id':original,'reference_version_label':c['reference_version_label'],'in_current_corpus':False,'newly_user_requested_room_review':True,'recovered_reference_view':True,'editable':True,'photo':c['photo'],'detail_file':c['detail_file'],'priority':2,'room_group_id':'q9_six_view_room','queue_label':'同房间待核对','queue_reason':c['missing_room_scope']['reason'],'scope_difference_status':'pending_review','selected_target':None,'floor_region_confirmed':False,'reference_ready':False,'hold_layers':[],'direct_evidence':[{'source_pointer':'sources/user_group_review_20260912.json#/group_reviews/154/current/note',**evidence}],'scope_votes_from_group':0,'reference_provenance':provenance})
 reports.append({'image_code':code,'image_id':ident,'source_snapshot_row':idx,'source_keypoint_count':len(pts),'photo_dimensions':dims,'original_reference_raw_txt_recovered':False,'original_equivalent_snapshot_geometry_recovered':True,'crosscheck_all_coordinates_equal':True,'original_order_crosschecked':True,'research_annotations':0,'floor_region_confirmed':False})
write(BASE/'candidate_entries.json',entries);write(BASE/'candidate_queue_cases.json',queue);write(BASE/'recovery_manifest.json',{'schema':'priority_room_view_recovery_v1','source_commit':COMMIT,'source_main_verified_by_ls_remote':COMMIT,'scope':'q9vSo1VnCiC-21 and -25 only, the two priority 1/2 external views','entries':reports,'missing_raw_paths':[f'data/mp3d_layout/test/label_cor/{e["image_id"]}.txt' for e in entries],'formal_research_corpus_unchanged':True,'source_references':{'snapshot':SNAP,'import_crosscheck':IMP,'audit':ORI_AUD},'no_site_edits_or_upload':True})
print(json.dumps(reports,ensure_ascii=False,indent=2))
