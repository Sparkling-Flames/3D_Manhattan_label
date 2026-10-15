from pathlib import Path
import json,csv,re,hashlib,collections,subprocess,statistics
OUT=Path(__file__).parent; REPO=OUT.parent/'quality_scope_current'; SRC=OUT/'sources'; COMMIT='d905d7dbb31dccabb3b190cb317d38b034b7cd65'
GP='analysis_results/image_difficulty_full_review_20261010/all_scope_evidence.json'
G=json.load(open(REPO/GP)); IM={x['image_id']:x for x in G}; CODE={x['image']:x for x in G}; O={o['object_id']:o for x in G for o in x['observations']}; RID={o['record_id']:o for o in O.values()}
I_PATH='analysis_results/final_review_summary_20260929/历史评语_去重来源索引.csv'
I=list(csv.DictReader(open(SRC/I_PATH,encoding='utf-8-sig')))
COVER=list(csv.DictReader(open(SRC/'analysis_results/final_review_summary_20260929/逐图分类及覆盖.csv',encoding='utf-8-sig'))); COV={r['image_id']:r for r in COVER}
CASE={}
for p in SRC.rglob('*.json'):
 try:d=json.load(open(p))
 except:continue
 def cc(x):
  if isinstance(x,dict):
   if x.get('case_id') and isinstance(x.get('image_id'),str):CASE[x['case_id']]=x['image_id']
   for y in x.values():cc(y)
  elif isinstance(x,list):
   for y in x:cc(y)
 cc(d)
KEYWORDS=['空间','范围','玻璃','内外','内侧','外侧','门后','门外','门内','门洞','后面','房间','漏标','多标','深处','墙后','区域','停止','截止','边界','连通','走廊','浴缸','马桶','柜子','scope','extent','enclosed','extended']
KW=re.compile('|'.join(KEYWORDS),re.I)
DETAIL=re.compile(r'细节|墙面|凸[起出]|壁炉|柱子|拐角|墙角|一对点|角点|p\d',re.I)
ERR=re.compile(r'错|标歪|标差|很差|标的不好|没标好|不太对|不是空间|定位|误导|漏标.*点|多标.*点')
NEG=re.compile(r'空间.{0,8}(一致|类似|相似|没.{0,4}问题|差不多|准确|正确|是对的)|范围.{0,6}(一致|差不多|无歧义)|无.{0,4}(空间|范围).{0,4}歧义|不是空间的问题|没有.{0,6}范围.{0,6}不同')
TARGET=re.compile(r'(空间|范围|区域).{0,10}(不同|不一样|不一致|不太同|不太一样|歧义|有差异|有些差异|缩小|减小|小了一|偏大)|不同.{0,8}(空间|范围|区域)|两种.{0,8}(标法|范围)|多个标注空间|只标.{0,15}(房间|区域|空间)|最小.{0,4}(空间|区域)|标.{0,8}(门外|门内|门里|外面|里面).{0,10}(空间|区域)|玻璃.{0,24}(内侧|外侧|内实际|里面|外围|外面)|标.{0,12}(玻璃|柜子|浴缸).{0,8}停止|(gt|GT).{0,22}(整个|完整|很大|全的|走廊都标|都没有标|门口的区域)|其他房间|连通的空间')
BOUND=re.compile(r'停止|截止|终止|柜子当成墙|柜子当做墙|门内|门外|门后|墙后|内侧|外侧|enclosed|extended',re.I)
MEMORY=re.compile(r'(gt|GT).{0,50}(很大|范围是偏大|范围很大|范围.*大|整个|完整|全的|走廊都标).{0,70}(没有标注者|没人|无人|都没有|都没)|目前没有标注者这样标|目前所有标注者都没标|目前的标注者都没有标')
def label(t):
 return dict(keyword_hit=bool(KW.search(t)),matched_keywords=';'.join(k for k in KEYWORDS if re.search(re.escape(k),t,re.I)),target_difference_candidate=bool(TARGET.search(t)),boundary_candidate=bool(BOUND.search(t)),detail_context=bool(DETAIL.search(t)),ordinary_error_context=bool(ERR.search(t)),same_scope_or_negation_context=bool(NEG.search(t)),memory_match_candidate=bool(MEMORY.search(t)))
def role(path,pointer):
 if '/evidence/' in path and any(t in path for t in ['review_final','review_return','review_reconciliation','review_closeout','new_manual']):return 'raw_review_export'
 if '原始' in path or 'human_review_export' in path:return 'raw_review_export'
 if '历史评语_去重来源索引' in path:return 'historical_deduplicated_index'
 if 'source_review_comments' in path:return 'compiled_source_comments'
 if 'reconciled_records' in path:return 'raw_embedded_in_reconciliation' if '/human_record/' in pointer else 'derived_reconciliation'
 if 'scope_comment_readings' in path:return 'derived_scope_reading_quote' if pointer.endswith('/quote') else 'derived_scope_reading'
 return 'derived_review_or_classification'
occ=[]
def put(text,path,pointer,ctx,field='comment',extra=None):
 if not isinstance(text,str) or not text.strip():return
 iid=ctx.get('image_id',''); code=ctx.get('image_code',''); oid=ctx.get('object_id','')
 if iid not in IM and code in CODE:iid=CODE[code]['image_id']
 if oid in O:
  ob=O[oid];iid=ob['image_id'];code=ob['image']
 elif iid in IM:code=IM[iid]['image']
 ob=O.get(oid,{})
 kind='annotation' if oid in O or ctx.get('object_kind')=='annotation' else 'image' if iid and (not oid or oid==iid or ctx.get('object_kind')=='image') else ctx.get('object_kind','unresolved')
 oid=oid or (iid if kind=='image' else '')
 r=dict(image_code=code,image_id=iid,object_kind=kind,object_id=oid,record_id=ob.get('record_id',''),worker_id=ob.get('worker_id',ctx.get('worker_id','')),condition=ob.get('condition',ctx.get('condition','')),current_gate=ob.get('gate',''),in_current_manual_pool=ob.get('in_current_manual_pool',''),source_path=path,source_pointer=pointer,source_field=field,source_role=role(path,pointer),source_record_key=ctx.get('source_record_key',''),historical_verdict=ctx.get('verdict',''),historical_category=ctx.get('category',''),historical_updated_at=ctx.get('updated_at',''),comment=text,identity_status='exact_object_id' if oid in O else 'exact_image_id' if iid in IM else 'exact_historical_image_outside_259' if re.match(r'^[A-Za-z0-9]+_[0-9a-f]{32}$',iid) else 'unresolved',source_commit=COMMIT)
 if extra:r.update(extra)
 r['reviewer_hint']='yizheng' if ('yizheng' in path or '一正' in path or field=='peer_image_note') else 'user' if ('/user.json' in path or '/user_review.json' in path or '用户' in path or 'human_record' in pointer or field=='user_image_note') else 'not_explicit_in_this_source'
 r['reference_binding_status']='historical_version_pending' if iid in IM and IM[iid]['gt_object_id']!=IM[iid]['original_gt_object_id'] else 'historical_view_version_not_guaranteed'
 r['current_selected_gt_object_id']=IM.get(iid,{}).get('gt_object_id','')
 r['current_original_gt_object_id']=IM.get(iid,{}).get('original_gt_object_id','')
 r.update(label(text));r['comment_id']='C'+hashlib.sha256(json.dumps([iid,kind,oid,text],ensure_ascii=False).encode()).hexdigest()[:16];occ.append(r)
for i,r in enumerate(I):
 put(r['comment'],I_PATH,f'/rows/{i}',dict(image_id=r['image_id'],image_code=r['image_code'],object_kind=r['object_kind'],object_id=r['object_id'],worker_id=r['worker_id']),extra={'index_source_fields':r['source_fields'],'index_current_cleaning_disposition':r['current_cleaning_disposition'],'index_topics':r['topics']})
# Traverse all selected source JSON. JSON Pointer is RFC6901 escaped.
def esc(k):return str(k).replace('~','~0').replace('/','~1')
def map_key(k,ctx):
 c=ctx.copy();s=str(k)
 for prefix in ['annotation:','image:']:
  if s.startswith(prefix):s=s[len(prefix):]
 if s in O:c.update(object_id=s,object_kind='annotation',image_id=O[s]['image_id'])
 elif s in IM:c.update(image_id=s,object_id=s,object_kind='image')
 elif s in CODE:c.update(image_id=CODE[s]['image_id'],image_code=s)
 elif re.match(r'^[A-Za-z0-9]+_[0-9a-f]{32}[:|]',s):
  iid=re.split('[:|]',s)[0];c.update(image_id=iid,object_kind='image',object_id=iid)
 elif s in CASE:c['image_id']=CASE[s]
 if c!=ctx:c['source_record_key']=str(k)
 return c
TEXT_FIELDS={'comment','notes','note','reason','quote','user_image_note','peer_image_note','original_note','user_note','final_comment','human_note','review_comment','image_comment','scope_note','scope_comment'}
def visit(v,p,ctx,path,field=''):
 if isinstance(v,dict):
  c=ctx.copy()
  for k in ['image_id','image_code','worker_id','condition','verdict','category','updated_at','object_kind']:
   if isinstance(v.get(k),(str,int)):c[k]=v[k]
  if v.get('code') in CODE:c['image_code']=v['code'];c['image_id']=CODE[v['code']]['image_id']
  if v.get('image') in CODE:c['image_code']=v['image'];c['image_id']=CODE[v['image']]['image_id']
  if v.get('case_id') in CASE:c['image_id']=CASE[v['case_id']]
  for k in ['object_id','annotation_id','id']:
   if isinstance(v.get(k),str) and v[k] in O:c.update(object_id=v[k],object_kind='annotation',image_id=O[v[k]]['image_id'])
  if c.get('object_id') in O and c.get('image_id')!=O[c['object_id']]['image_id']:c.pop('object_id',None);c.pop('object_kind',None)
  for k,x in v.items():
   pp=p+'/'+esc(k);cc=map_key(k,c)
   if isinstance(x,str) and (k in TEXT_FIELDS or k.endswith('_comment') or k.endswith('_note')):put(x,path,pp,c,k)
   elif isinstance(x,list) and k in TEXT_FIELDS|{'comments'}:
    for j,t in enumerate(x):
     if isinstance(t,str):put(t,path,pp+'/'+str(j),c,k)
   visit(x,pp,cc,path,k)
 elif isinstance(v,list):
  for i,x in enumerate(v):visit(x,p+'/'+str(i),ctx,path,field)
manifest=[]
for p in sorted(SRC.rglob('*')):
 if not p.is_file():continue
 rel=str(p.relative_to(SRC));data=p.read_bytes();entry=dict(path=rel,bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
 if data.startswith(b'version https://git-lfs'):entry['state']='lfs_pointer_not_content';manifest.append(entry);continue
 if p.suffix=='.json' and any(x in p.name.lower() for x in ['field_contract','summary','manifest','template','verification','validation','qa']):entry['state']='metadata_preserved_not_comments'
 elif p.suffix=='.json':
  try:d=json.loads(data);visit(d,'',{},rel);entry['state']='parsed_json'
  except Exception as e:entry['state']='parse_error';entry['error']=str(e)
 elif p.suffix=='.csv':entry['state']='read_csv' if rel==I_PATH or 'final_review_summary_20260929' in rel else 'preserved_not_extracted'
 else:entry['state']='preserved_not_extracted'
 manifest.append(entry)
# Do not treat machine geometry or visual interpretations as original human comments.
notes={}
for nf in ['scope_visual_notes.json','scope_extra_notes.json']:
 d=json.load(open(REPO/'analysis_results/image_difficulty_full_review_20261010'/nf))
 for k,val in d.items():
  for code,t in val.items():notes.setdefault(code,[]).append(dict(category=k,note=t,source='analysis_results/image_difficulty_full_review_20261010/'+nf,pointer='/'+k+'/'+esc(code)))
confirmed=json.load(open(OUT.parent/'manual_scope_review_received_20261010_batch2.json'))['records']; CONF={r['image_code']:r for r in confirmed}
# group exact comment object+text; source occurrences retained separately, never independent votes
D={}
for r in occ:
 k=r['comment_id']
 if k not in D:D[k]={**{a:b for a,b in r.items() if not a.startswith('source_') and not a.startswith('historical_')},'source_occurrences':[],'source_roles':set(),'source_paths':set()}
 D[k]['source_occurrences'].append({'path':r['source_path'],'pointer':r['source_pointer'],'field':r['source_field'],'record_key':r['source_record_key'],'role':r['source_role']})
 D[k]['source_roles'].add(r['source_role']);D[k]['source_paths'].add(r['source_path'])
for d in D.values():
 d['source_roles']=sorted(d['source_roles']);d['source_paths']=sorted(d['source_paths']);d['source_occurrence_count']=len(d['source_occurrences'])
byim=collections.defaultdict(list)
for d in D.values():byim[d['image_id']].append(d)
rawroles={'raw_review_export','historical_deduplicated_index','compiled_source_comments','raw_embedded_in_reconciliation','derived_scope_reading_quote'}
images=[]; groups=[]; geom=[]
for i,g in enumerate(G):
 cs=byim[g['image_id']];human=[c for c in cs if set(c['source_roles'])&rawroles];hits=[c for c in human if c['keyword_hit']];target=[c for c in hits if c['target_difference_candidate']];bound=[c for c in hits if c['boundary_candidate']];unknown=[c for c in hits if not c['target_difference_candidate'] and not c['boundary_candidate']];obs=g['observations']
 row=dict(image_code=g['image'],image_id=g['image_id'],current178=g['in_current178'],legacy137=g['legacy137'],total_records=len(obs),condition_gate_counts=json.dumps(g['condition_gate_groups'],ensure_ascii=False),valid_geometry=g['valid_geometry'],invalid_geometry=g['invalid_geometry'],selected_gt_object_id=g['gt_object_id'],original_gt_object_id=g['original_gt_object_id'],gt_geometry_status=g['gt_status'],reference_flags=json.dumps(g['reference_flags'],ensure_ascii=False),user_confirmed_floor_region=g['image'] in CONF,confirmed_reference_ready=CONF.get(g['image'],{}).get('reference_ready',''),confirmed_review_scope=CONF.get(g['image'],{}).get('review_scope',''),all_unique_comments=len(cs),historical_unique_comments=len(human),keyword_comments=len(hits),target_wording_candidate_comments=len(target),boundary_wording_candidate_comments=len(bound),detail_only_or_context_comments=len(unknown),historical_comment_record_ids=';'.join(sorted({c['record_id'] for c in hits if c['record_id']})),keyword_comment_ids=';'.join(c['comment_id'] for c in hits),target_candidate_comment_ids=';'.join(c['comment_id'] for c in target),memory_match_comment_ids=';'.join(c['comment_id'] for c in human if c['memory_match_candidate']),image_comment='\n'.join(dict.fromkeys(c['comment'] for c in human if c['object_kind']=='image')),machine_visual_notes=json.dumps(notes.get(g['image'],[]),ensure_ascii=False),geometry_source_pointer=f'/{i}',geometry_source_path=GP,scope_explicit_tag=COV.get(g['image_id'],{}).get('scope_explicit_tag',''),scope_existing_ledger=COV.get(g['image_id'],{}).get('scope_existing_ledger',''),source_coverage='259-image supplied geometry corpus; selected Git-tracked historical exports and full 1157-comment index; not all true scope differences established')
 for threshold in [.2,.3,.4]:
  for gatekey,pred in [('all_historical',lambda o:True),('current_manual_pool',lambda o:o.get('in_current_manual_pool')),('excluded',lambda o:o['gate']=='excluded')]:
   subset=[o for o in obs if pred(o)];vv=[o for o in subset if o.get('selected_gt_metrics')]
   row[f'geometry_gt_symdiff_ge_{threshold}_{gatekey}']=sum(o['selected_gt_metrics']['symmetric_difference']>=threshold for o in vv)
 row['reference_paused']=any(o['gate'] in ['hold_all_analysis','hold_main_analysis','inner_space_only_reference_hold'] for o in obs)
 row['historical_excluded_records']=sum(o['gate']=='excluded' for o in obs)
 row['scope_comment']=bool(target or bound)
 row['detail_or_locator']=bool(hits) and not(target or bound)
 row['has_any_geometry_candidate']=row['geometry_gt_symdiff_ge_0.3_all_historical']>0
 row['broad_review_queue']=bool(hits or row['has_any_geometry_candidate'] or row['scope_explicit_tag']=='true' or row['scope_existing_ledger']=='true' or g['image'] in CONF)
 row['historical_reference_version_pending']=g['gt_object_id']!=g['original_gt_object_id']
 row['historical_comments_reference_scope']='Historical comments may refer to original or earlier revised GT; compare with current selected reference before asserting current scope difference' if row['historical_reference_version_pending'] else 'Exact historical GT viewing version not guaranteed; current selected object preserved'
 row['initial_triage']='user_confirmed_floor_only' if g['image'] in CONF else 'historical_target_or_boundary_candidate' if target or bound else 'broad_comment_or_prior_ledger_candidate' if hits or row['scope_explicit_tag']=='true' or row['scope_existing_ledger']=='true' else 'geometry_only_candidate' if row['has_any_geometry_candidate'] else 'no_retrieval_hit_not_proof_of_same_scope'
 images.append(row)
 for cg in g['condition_gate_groups']:
  subset=[o for o in obs if o['condition']==cg['condition'] and o['gate']==cg['gate']];d=dict(image_code=g['image'],image_id=g['image_id'],condition=cg['condition'],gate=cg['gate'],n_records=len(subset),n_workers=len({o['worker_id'] for o in subset}),valid_geometry=sum(o['geometry_status']=='valid' for o in subset),invalid_geometry=sum(o['geometry_status']!='valid' for o in subset),record_ids=';'.join(o['record_id'] for o in subset),geometry_only_no_semantic_vote=True)
  for t in [.2,.3,.4]:d[f'symdiff_ge_{t}']=sum((o.get('selected_gt_metrics') or {}).get('symmetric_difference',-1)>=t for o in subset)
  groups.append(d)
 for j,o in enumerate(obs):
  dd={k:v for k,v in o.items() if k not in ['points','footprint','source','selected_gt_metrics','original_gt_metrics']};dd.update(geometry_source_path=GP,geometry_source_pointer=f'/{i}/observations/{j}',annotation_source=json.dumps(o['source'],ensure_ascii=False),selected_gt_object_id=g['gt_object_id'],original_gt_object_id=g['original_gt_object_id'])
  for m in ['selected_gt_metrics','original_gt_metrics']:
   for z in ['symmetric_difference','missing','excess']:dd[m+'_'+z]=(o.get(m) or {}).get(z,'')
  geom.append(dd)
def writecsv(name,rows):
 if not rows:
  (OUT/name).write_text('comment_id,image_id,image_code,comment\n',encoding='utf-8-sig');return
 keys=list(dict.fromkeys(k for r in rows for k in r))
 with open(OUT/name,'w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,keys);w.writeheader()
  for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list,set)) else v for k,v in r.items()})
writecsv('all_259_images.csv',images);writecsv('all_3152_geometry_records.csv',geom);writecsv('condition_gate_groups.csv',groups);writecsv('all_comment_occurrences.csv',occ);writecsv('unique_comments.csv',list(D.values()));writecsv('keyword_comment_candidates.csv',[c for c in D.values() if c['keyword_hit']]);writecsv('historical_outside_259_comments.csv',[c for c in D.values() if c['identity_status']=='exact_historical_image_outside_259']);writecsv('unresolved_comment_identities.csv',[c for c in D.values() if c['identity_status']=='unresolved']);writecsv('broad_review_queue.csv',[r for r in images if r['broad_review_queue']]);writecsv('source_manifest.csv',manifest)
(OUT/'inventory.json').write_text(json.dumps(dict(source_commit=COMMIT,images=images,comments=list(D.values()),occurrences=occ,condition_gate_groups=groups,geometry_records=geom),ensure_ascii=False,indent=2))
(OUT/'source_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
sumry=dict(source_commit=COMMIT,images=len(images),geometry_records=len(geom),input_historical_index_rows=len(I),all_unique_comments=len(D),all_source_occurrences=len(occ),keyword_comments=sum(c['keyword_hit'] for c in D.values()),keyword_images=sum(r['keyword_comments']>0 for r in images),target_or_boundary_candidate_images=sum(r['target_wording_candidate_comments']>0 or r['boundary_wording_candidate_comments']>0 for r in images),broad_queue_images=sum(r['broad_review_queue'] for r in images),no_hit_images=sum(not r['broad_review_queue'] for r in images),unresolved_comments=sum(c['identity_status']=='unresolved' for c in D.values()),outside_259_comments=sum(c['identity_status']=='exact_historical_image_outside_259' for c in D.values()),outside_259_images=len({c['image_id'] for c in D.values() if c['identity_status']=='exact_historical_image_outside_259'}),confirmed_images=list(CONF),parsed_source_json=sum(r['state']=='parsed_json' for r in manifest),lfs_pointers=[r['path'] for r in manifest if r['state']=='lfs_pointer_not_content'],source_files=len(manifest))
(OUT/'summary.json').write_text(json.dumps(sumry,ensure_ascii=False,indent=2));print(json.dumps(sumry,ensure_ascii=False,indent=2))
