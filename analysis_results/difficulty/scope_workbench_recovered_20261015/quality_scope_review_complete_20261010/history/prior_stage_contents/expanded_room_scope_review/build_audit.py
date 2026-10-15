from pathlib import Path
import json,gzip,hashlib,shutil,collections,re
ROOT=Path('/workspace/scratch/a365811da80c'); OUT=ROOT/'expanded_room_scope_review_20261010'; W=ROOT/'scope-crop-workbench/dist'
def read(p):return json.load(open(p))
def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
D=read(OUT/'sources/workbench_data_snapshot.json'); images={r['image_code']:r for r in D['images']}; code_by_id={r['image_id']:r['image_code'] for r in D['images']}
GFILE=ROOT/'audit_materials_20261010/extracted/图片分类与复审来源/analysis_results/scene_image_exploration_20260910_v1/user_group_review_20260912.json';G=read(GFILE)['group_reviews']
REGFILE=ROOT/'audit_materials_20261010/extracted/原清单123项/004_same_room_selection_registry_v2_20260912.json';REG=read(REGFILE)
for g in REG['groups']:
 for iid,n in zip(g['image_ids'],g['numbers']):code_by_id.setdefault(iid,f"{g['building']}-{n:02d}")
for src,dst in [(GFILE,OUT/'sources/user_group_review_20260912.json'),(REGFILE,OUT/'sources/same_room_registry.json'),(ROOT/'scope_return_latest_20261010/空间范围人工审核_2026-10-10(2).json',OUT/'sources/latest_scope_return.json')]:shutil.copyfile(src,dst)
UNB=['uNb9QFRL6hY-'+s for s in ['88','18','26','41','50','59','60','66','67']];RPC=['rPc6DW4iMge-'+s for s in ['06','22','05']]
groups=[]
for gid,idx,codes,title,vis in [('unb_bathroom_9',183,UNB,'88所在浴室的9个视角','白色浴缸、黑白软凳、圆弧台阶和双玻璃门、白色梳妆台，9图布局互证；67为淋浴玻璃内相机位置。'),('rpc_bathroom_3',165,RPC,'另一间浴室的3个视角','棕色淋浴墙、弧形淋浴底座、金色台面与白色柜体，05/06/22布局互证。')]:
 g=G[idx]
 groups.append(dict(group_id=gid,title=title,image_codes=codes,physical_room_status='visually_corroborated_same_room',physical_room_confidence='high',visual_verification=vis,visual_contact_sheet=f'previews/{"uNb" if idx==183 else "rPc"}_bathroom.jpg',room_source={'path':'sources/user_group_review_20260912.json','pointer':f'/group_reviews/{idx}','raw_record':g},not_user_confirmation_of_all_fields=True,scope_approval_propagation_allowed=False,scope_votes_from_group=0))
confirmed={x['image_code']:x['confirmed_review'] for x in images.values() if x.get('confirmed_review') and x['confirmed_review'].get('completed')}
# Snapshot may predate parent integration; merge explicit incoming latest confirmations while preserving prior five.
latest=read(OUT/'sources/latest_scope_return.json')
for r in latest['records']:
 if r.get('floor_region_confirmed') and r.get('completed') and r.get('confirmed_version'):confirmed[r['image_code']]=r['confirmed_version']
 if r.get('received_confirmed_version') and r.get('confirmed_version'):confirmed.setdefault(r['image_code'],r['confirmed_version'])

def case(c,priority=1,gid=None,label='原评论明确范围差异',reason='原始评语明确描述不同目标范围；尚未确认本轮目标轮廓。'):
 im=images[c];det=read(W/im['detail_file']);ev=[]
 for i,e in enumerate(det.get('historical_comments',[])):
  if any(s.get('role') in ['raw_review_export','local_review_increment','original_human_image_comment_historical','archive_original'] or s.get('source_kind')=='local_original' for s in e['sources']):
   if True:ev.append({'source_pointer':f"{im['detail_file']}#/historical_comments/{i}",**e})
 return {'image_code':c,'image_id':im['image_id'],'reference_object_id':im['reference_object_id'],'reference_version':im['reference_version'],'original_reference_object_id':im.get('original_reference_object_id'),'reference_version_label':im.get('reference_version_label'),'in_current_corpus':im['in_current_corpus'],'editable':im['editable'],'photo':im.get('photo'),'detail_file':im.get('detail_file'),'priority':priority,'room_group_id':gid,'queue_label':label,'queue_reason':reason,'scope_difference_status':'explicit_original_comment_not_new_geometry_approval' if label=='原评论明确范围差异' else 'pending_review','selected_target':None,'floor_region_confirmed':False,'reference_ready':False,'hold_layers':im.get('hold_layers',[]),'direct_evidence':ev,'independent_votes':None,'evidence_count_is_not_vote_count':True,'historical_comment_GT_version_warning':'评论绑定历史查看版本；当前编辑参考及原始参考单列，不把旧评语自动转成当前GT结论。','old_queue_category':im['primary_category'],'new11_member':'user_scope_batch11' in im['categories']}
priority=[case(c,1,g['group_id']) for g in groups for c in g['image_codes']]
for c in priority:
 c['queue_reason']='既有原始评语明确指出范围差异，但仅11图的默认队列遗漏；同房关系由历史登记与本次原图互证。'
 if c['image_code']=='uNb9QFRL6hY-88':c['identity_confirmed']=True;c['queue_reason']='此前已认出所找图片，却未列入新11图默认队列；原GT包括两侧走廊，玻璃/马桶/浴缸也有范围取舍。'
 if c['image_code']=='uNb9QFRL6hY-67':c['camera_region_caveat']='相机在淋浴玻璃内。不能把其他8图的目标区域或坐标直接沿用到67。'
 if c['image_code']=='uNb9QFRL6hY-41':c['latest_comment_caveat']='墙线分组的较新评语允许部分组可合并；仍保留另一句“停止的范围确实有点不同”，不推断整个空间都已合并。'
write(OUT/'priority_queue.json',{'schema':'source_backed_room_scope_queue_v1','initial_image':'uNb9QFRL6hY-88','default_category':'missing_room_scope_review','source_commit':D['source_commit'],'evidence_source_commit':D['evidence_source_commit'],'latest_scope_review_source_commit':D['latest_scope_review_source_commit'],'cases':priority,'room_groups':groups,'preserve_confirmed_image_codes':sorted(confirmed),'preserved_confirmations':confirmed,'label_definition':{'原评论明确范围差异':'原评语明确记录存在不同空间标法，尚不是用户对新轮廓的确认。','同房间待核对':'只有房间关联或历史范围线索，不代表已证实该图有不同范围。'},'invariants':['保留已有16份底面确认，不覆盖polygon、operations、cuts、decision、confirmed_version。','群组上下文只记一次，不复制为多张图的独立范围证据。','不改GT、人员资格、质量hold、正式难度或reference_ready。','不得仅凭建筑前缀认定同房；不得跨图复制范围坐标。']})
write(OUT/'preserved_confirmations16.json',confirmed)
print('priority_ready',len(priority),'confirmed',len(confirmed))
# Bounded second pass: read every inventory comment and all available historical/local increments.
INVFILE=ROOT/'quality_scope_batch_ready_20261010/contents/full_scope_inventory/cloud_inventory/inventory.json.gz'
I=json.load(gzip.open(INVFILE,'rt'));shutil.copyfile(INVFILE,OUT/'sources/inventory.json.gz')
ARCH=ROOT/'audit_materials_20261010/comment_review/portable'
for p in ARCH.glob('*.json'):
 if p.name not in ['original_123_content_groups.json','original_123_path_index.json','FILE_MANIFEST.json']:shutil.copyfile(p,OUT/'sources'/p.name)
LOCF=ROOT/'quality_scope_batch_ready_20261010/contents/full_scope_inventory/local_increment/integration_verified69.json';LOC=read(LOCF);shutil.copyfile(LOCF,OUT/'sources/local_increment69.json')
raw_cand={c['image_code'] for c in I['comments'] if c['image_code'] and 'raw_review_export' in c['source_roles'] and (c['target_difference_candidate'] or c['boundary_candidate'])}
# These exclusions are semantic review decisions on the full raw wording, not on numeric area candidates.
excluded_semantic={
 'jtcxE69GiFV-05':'原话明确“大体范围…无歧义”，差别属于小柱子/柜子和点位；不靠关键词“范围”强行重划。',
 'e9zR4mvMWw7-16':'原话明确原始Matterport范围不同但人工修正后已无问题；当前选定修订GT，不把原始版问题自动套到修订版。',
 'wc2JMjhGNzB-60':'原话说开口通向其他房间但都没有误标、两簇无明显区别；不足以认定目标范围不同。',
 'wc2JMjhGNzB-67':'最新具体复核是漏标/补点与门框多点，保留单点复核，不能仅凭早期Q36概括当作另一个空间目标。'
}
local_detail={
 '7y3sRwLe3Va-11':'壁炉凸起的局部结构是否纳入，与整房裁剪分开。',
 'X7HyMhZNoso-19':'隔间/凸墙局部结构及GT修订问题；与扩大或裁剪整房目标分开。',
 'pRbA3pwrgk9-12':'GT左墙凸起及高度错误，属于参考/局部结构复核。',
 'wc2JMjhGNzB-30':'凸墙阶梯细节遗漏，不据此认为另一个房间目标。',
 'x8F5xyUWy9e-03':'左侧墙面细节变化；无明确不同房间范围。',
 'yqstnuAEVhm-09':'仅笼统小幅空间细节差异，未给出具体目标范围切分。'
}
reconciled={'uNb9QFRL6hY-72':'较新LOCAL36_34：虽然旧评语称不同范围，现在认为可以合并同一个墙线；保留同房核对，不能沿用旧结论强制重画。','uNb9QFRL6hY-78':'LOCAL36_31/35允许墙线合并，同时LOCAL36_32仍记录柜前/柜后边界；同墙线合并不证明整房范围相同，列待核对。'}
potential={'7y3sRwLe3Va-21','q9vSo1VnCiC-13','uNb9QFRL6hY-19','uNb9QFRL6hY-47','rPc6DW4iMge-20','yqstnuAEVhm-02','b8cTxDM8gDG-19'}
direct=raw_cand-set(excluded_semantic)-set(local_detail)-set(reconciled)
direct.update(['7y3sRwLe3Va-03','uNb9QFRL6hY-56'])
# Additional text-only uncertain candidates missed by narrow inventory flags.
extra_pending={
 '7y3sRwLe3Va-22':'原话“走廊空间是否包括”，另有OOS/多平面背景；只列待核对。',
 'UwV83HsGsw3-01':'原话“疑似oos,标注范围确实不太确定”，不视为已证实双目标。',
 'b8cTxDM8gDG-04':'原话原始/修订GT均可能有争议，范围“也可能”争议；需先看参考版本。',
 'jtcxE69GiFV-28':'有一份被认为不良的较小空间标注；不能直接宣布为合理的另一种范围。',
 'pRbA3pwrgk9-16':'OOS与最低层内空间的条件性讨论，单独保留参考/用途暂停。'
}
# Source groups: explicit same-room statements, user-confirmed group status, or a changed human group note.
# Untouched prefilled supported physical_same is never promoted to a verified same-room fact.
room_groups=list(groups)
used_indices={165,183}
for idx,g in enumerate(G):
 ids=g.get('image_ids',[]); codes=[code_by_id.get(x,x) for x in ids]
 if not (set(codes)&(direct|set(confirmed))):continue
 if idx in used_indices:continue
 cur=g['current'];rev=g.get('user_revision',{});note=cur.get('note','')
 if cur.get('physical_same')!='支持':continue
 if not rev:continue
 level='human_group_context_pending_room_identity'
 if rev.get('status')=='已确认':level='human_confirmed_group'
 if re.search('同一房间|同房|一间房',note) and '不是' not in note and '不算同房' not in note:level='human_same_room_statement'
 room_groups.append({'group_id':f'historical_group_{idx:03d}','title':f"历史房间组 {idx:03d}",'image_codes':codes,'physical_room_status':level,'physical_room_confidence':'high' if level!='human_group_context_pending_room_identity' else 'medium','room_source':{'path':'sources/user_group_review_20260912.json','pointer':f'/group_reviews/{idx}','raw_record':g},'scope_approval_propagation_allowed':False,'scope_votes_from_group':0})
# Merge the explicitly cross-referenced six-image room; do not let registry's separate pair groups hide four views.
qcodes=['q9vSo1VnCiC-'+s for s in ['11','12','15','16','21','25']]
room_groups=[g for g in room_groups if g['group_id'] not in {'historical_group_154','historical_group_155','historical_group_156'}]
room_groups.append({'group_id':'q9_six_view_room','title':'q9六视角房间','image_codes':qcodes,'physical_room_status':'explicit_human_same_room_statement','physical_room_confidence':'high','room_source':{'path':'sources/user_group_review_20260912.json','pointers':['/group_reviews/154/current/note','/group_reviews/155/current/note','/group_reviews/156/current/note'],'raw_text':G[154]['current']['note']},'scope_approval_propagation_allowed':False,'scope_votes_from_group':0,'deduplication':'同一句原文出现在三个两图组，只计一条房间关系陈述。'})
# The human image notes explicitly bind rPc22 to05, and rPc06 to the preceding 05.
H=read(ARCH/'historical_image_notes_39_reconfirmed.json')
room_groups[1]['additional_human_room_evidence']=[{'path':'sources/historical_image_notes_39_reconfirmed.json','pointer':f'/{i}','raw_record':H[i]} for i in [21,26]]
room_groups[1]['physical_room_status']='explicit_human_room_statement_and_visual_corroboration'
room_map=collections.defaultdict(list)
for g in room_groups:
 for c in g['image_codes']:room_map[c].append(g['group_id'])
related=set(room_map)
pending_codes=((direct|set(extra_pending)|related)-set(confirmed))-set(excluded_semantic)-set(local_detail)
# Excluded fireplace and latest user reference/OOS holds are retained separately, not silently reopened.
user_excluded={'yqstnuAEVhm-07':'用户本轮接受GT并暂不处理壁炉细节；不能通过同房传播重新打开。'}
latest_holds={'jtcxE69GiFV-10':'本轮用户“有可能算作oos”，保留独立用途/参考复核。','jtcxE69GiFV-05':'本轮用户“这gt是错误的”，保留独立参考复核。'}
pending_codes-=set(user_excluded)|set(latest_holds)
priority_order=UNB+RPC
priority2=['q9vSo1VnCiC-16','q9vSo1VnCiC-15','q9vSo1VnCiC-21','q9vSo1VnCiC-25','wc2JMjhGNzB-03','wc2JMjhGNzB-54','wc2JMjhGNzB-61']
ordered=priority_order+[c for c in priority2 if c in pending_codes and c not in priority_order]+sorted(pending_codes-set(priority_order)-set(priority2))
all_cases=[];external=[]
for c in ordered:
 if c not in images or not images[c].get('editable'):
  external.append({'image_code':c,'image_id':next((i for i,v in code_by_id.items() if v==c),None),'room_group_ids':room_map[c],'disposition':'related_view_not_editable_in_current_catalogue','queue_label':'同房间待核对','reason':'原同房组关联到此图，但当前目录缺图或仅有不可编辑历史条目；不可伪称可编辑或已审核。'});continue
 pr=1 if c in priority_order else (2 if c in priority2 else 3)
 label='原评论明确范围差异' if c in direct and c not in potential else '同房间待核对' if c in related and c not in direct else '范围线索待核对'
 reason='原始评语明确描述空间或截止区域不同；尚需逐图选择最终轮廓。' if label=='原评论明确范围差异' else '存在具体文字范围线索或房间关联；尚未证实本图需要不同范围，不继承其他图结论。'
 if c in extra_pending:reason=extra_pending[c]
 if c in reconciled:reason=reconciled[c]
 r=case(c,pr,room_map[c][0] if room_map[c] else None,label,reason);r['room_group_ids']=room_map[c];r['direct_scope_text_seed']=c in direct;r['related_room_context_only']=c not in direct and c in related
 if c in potential:r['scope_difference_status']='scope_possibility_or_reference_conflict_not_confirmed'
 if c in reconciled:r['later_comment_reconciliation']=reconciled[c]
 if c in priority_order:
  prior=next(x for x in priority if x['image_code']==c)
  for k in ['queue_reason','identity_confirmed','camera_region_caveat','latest_comment_caveat']:
   if k in prior:r[k]=prior[k]
 # Append archive original image notes omitted from some workbench historical summaries.
 for i,h in enumerate(H):
  if h['image_code']==c:r.setdefault('archive_image_evidence',[]).append({'source_path':'sources/historical_image_notes_39_reconfirmed.json','source_pointer':f'/{i}',**h})
 all_cases.append(r)
# Exhaustive included/excluded disposition for every current catalogue image.
case_map={r['image_code']:r for r in all_cases};audit=[]
for im in D['images']:
 c=im['image_code'];dis='excluded_no_source_backed_scope_target';why='无已核到的明确范围原话或经过人工审核的房间关联；数值偏差/面积筛查不足以入新队列。'
 if c in confirmed:dis='already_confirmed_preserve';why='已有明确底面范围确认，本轮保留，不要求重复。'
 elif c in user_excluded:dis='excluded_user_instruction';why=user_excluded[c]
 elif c in latest_holds:dis='separate_reference_or_oos_review';why=latest_holds[c]
 elif c in excluded_semantic:dis='excluded_semantic_or_reference_reconciliation';why=excluded_semantic[c]
 elif c in local_detail:dis='separate_local_detail_or_reference_review';why=local_detail[c]
 elif c in case_map:dis='new_pending_review';why=case_map[c]['queue_reason']
 elif not im['in_current_corpus']:dis='historical_only_not_scope_seed';why='仅历史图目录，未发现足够直接范围证据进入本轮默认待划队列。'
 audit.append({'image_code':c,'image_id':im['image_id'],'in_current_corpus':im['in_current_corpus'],'disposition':dis,'reason':why,'old_primary_category':im['primary_category'],'old_categories':im['categories'],'numeric_candidate_count':im.get('numeric_candidate_count',0),'numeric_signal_used_to_include':False,'room_group_ids':room_map.get(c,[]),'reference_version':im['reference_version'],'reference_object_id':im['reference_object_id'],'original_reference_object_id':im.get('original_reference_object_id'),'hold_layers':im.get('hold_layers',[]),'case_pointer':f"expanded_queue.json#/cases/{ordered.index(c)}" if c in case_map else None,'detail_file':im['detail_file']})
# Preserve all source detail files, including exclusions, so the audit is portable.
shutil.copytree(W/'records',OUT/'records',dirs_exist_ok=True)
# Record rejected/untouched registry relationships independently; these do not expand the queue.
relations_audit=[]
for idx,g in enumerate(G):
 codes=[code_by_id.get(x,x) for x in g.get('image_ids',[])];cur=g['current'];rev=g.get('user_revision',{})
 relations_audit.append({'source_pointer':f'sources/user_group_review_20260912.json#/group_reviews/{idx}','image_codes':codes,'physical_same_raw':cur.get('physical_same'),'status_raw':cur.get('status'),'user_revision':rev,'note':cur.get('note'),'used_in_expansion':any(x['group_id']==f'historical_group_{idx:03d}' for x in room_groups) or idx in [165,183,154,155,156],'relation_status':'not_same_room' if cur.get('physical_same')=='不支持' else 'untouched_prefill_not_confirmation' if not rev else 'human_reviewed_context','scope_votes':0})
# Correct machine pointers after cases outside catalogue were routed to external.
for a in audit:
 if a['image_code'] in case_map:a['case_pointer']=f"expanded_queue.json#/cases/{next(i for i,c in enumerate(all_cases) if c['image_code']==a['image_code'])}"
counts={'catalogue_audited':len(audit),'current_corpus_audited':sum(x['in_current_corpus'] for x in audit),'historical_only_audited':sum(not x['in_current_corpus'] for x in audit),'source_inventory_comments':len(I['comments']),'source_inventory_occurrences':len(I['occurrences']),'source_group_records':len(G),'local_increment_source_contexts':len(LOC),'preserved_confirmed':len(confirmed),'new_pending_available':len(all_cases),'priority_missing_bathrooms':12,'raw_original_text_candidate_images':len(raw_cand),'explicit_scope_text_seed_images':len(direct),'new_pending_labels':dict(collections.Counter(x['queue_label'] for x in all_cases)),'external_related_views':len(external),'catalogue_dispositions':dict(collections.Counter(x['disposition'] for x in audit))}
q=read(OUT/'priority_queue.json');q.update({'cases':all_cases,'room_groups':room_groups,'counts':counts,'external_related_views':external,'audit_manifest':'all_280_dispositions.json','room_relation_audit':'all_260_room_relation_dispositions.json','stopping_condition':'已覆盖当前280图目录、259研究图、1648库存评语、69本地增量、260历史房间关系及列明的原始档案文本；没有穷举所有照片做新范围裁定。'})
write(OUT/'expanded_queue.json',q);write(OUT/'all_280_dispositions.json',audit);write(OUT/'all_260_room_relation_dispositions.json',relations_audit);write(OUT/'external_related_views.json',external);write(OUT/'summary.json',counts)
print(json.dumps(counts,ensure_ascii=False,indent=2))
