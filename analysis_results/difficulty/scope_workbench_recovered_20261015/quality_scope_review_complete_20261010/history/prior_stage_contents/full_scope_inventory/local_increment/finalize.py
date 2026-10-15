exec(open('local_scope_verified/verify.py').read().split('verified=[]')[0])
a=json.load(open(L/'complete_bound_candidates.json'));outsidecloud=csvread('historical_outside_259_comments.csv');ct={(x['image_id'],x['comment'].strip()) for x in c+outsidecloud}
recent=json.load(open(O/'verified_recent36.json'));extra=json.load(open(O/'additional_current_user_comments.json'));outside=json.load(open(O/'additional_outside259_user_comments.json'));pending=json.load(open(O/'additional_full_original_field_pending.json'))
for x in extra+outside:
 x['cloud_status']='present_historical_outside259' if (x['image_id'],x['text'].strip()) in ct else x['cloud_status']
 x['pair_bindings']=[{'object_id':obj,'record_id':next((z['record_id'] for z in g if z['object_id']==obj and z['image_id']==x['image_id']),None)} for obj in x['related_object_ids']]
 x['times_are_missing_not_inferred_from_mtime']=True
outside=[x for x in outside if x['cloud_status']=='absent_image_text'];dump('additional_outside259_user_comments.json',outside);dump('additional_current_user_comments.json',extra)
# Compact, provenance-preserving integration view. Raw sources remain in verified full outputs.
compact=[]
for n,x in enumerate(recent+extra):
 ss=[]
 for s in x['sources']:
  raw=s['raw_record'];ss.append({'source_file':s['source_file'],'json_pointer':s['json_pointer'],'reported_updated_at':s.get('updated_at'),'raw_updated_at':raw.get('updatedAt',raw.get('updated_at')),'raw_created_at':raw.get('created_at'),'raw_record_sha256':hashlib.sha256(json.dumps(raw,ensure_ascii=False,sort_keys=True).encode()).hexdigest()})
 compact.append({'local_comment_id':x.get('verification_id',f'LOCAL_EXTRA_{n-35:02}'),'image_code':x['image_code'],'image_id':x['image_id'],'object_id':x.get('object_id'),'record_id':x.get('record_id'),'comment':x['text'],'binding_level':x.get('binding_level','exact_pair' if x.get('related_object_ids') else 'image_or_cross_image_context'),'pair_bindings':x.get('pair_bindings',[]),'content_role':x.get('content_role','original_recent_human_review'),'schema':x.get('schema'),'reference_version':x.get('reference_version'),'reference_id':x.get('reference_id'),'interpretation_status':x.get('interpretation_status','context_requires_manual_semantics'),'cloud_status':x['cloud_status'],'raw_text_verified':x['raw_text_verified'],'sources':ss,'scope_difference_confirmed':False,'no_gt_score_or_eligibility_change':True})
dump('integration_verified69.json',compact);outcsv('integration_verified69.csv',compact)
# Group-level history should not become independent per-image votes.
groups=collections.defaultdict(list)
for x in pending:groups[x['text']].append(x)
groupout=[]
for text,xx in groups.items():
 groupout.append({'text':text,'candidate_ids':[z['candidate_id'] for z in xx],'associated_images':[{'image_id':z['image_id'],'image_code':z['image_code']} for z in xx],'binding_level':'historical_group_comment_mirrored_to_images','status':'original_raw_record_not_embedded_in_complete_candidates; group_referent_not_individual_scope_verdict','source_examples':[s for s in xx[0]['sources'] if '/raw_current/note' in (s.get('json_pointer') or '')][:3]})
dump('group_history_provenance_pending.json',groupout)
# Audit every candidate's coverage/provenance without using text keyword votes.
known={(x['image_id'],x['text'].strip()) for x in recent+extra+outside};pid={x['candidate_id'] for x in pending};pointids={f'bound_local_{i:06}' for i in range(11563,11567)};aud=[]
for x in a:
 key=(x['image_id'],x['text'].strip())
 if key in ct:st='cloud_image_text_present_identity_level_still_matters'
 elif key in known:st='verified_local_original_or_context'
 elif x['candidate_id'] in pid:st='group_history_original_field_pending'
 elif x['candidate_id'] in pointids:st='point109_reviewer_mirror_pending'
 else:st='not_promoted_derived_or_unresolved_provenance'
 aud.append({'candidate_id':x['candidate_id'],'image_id':x['image_id'],'image_code':x['image_code'],'object_id':x['object_id'],'in_259':x['image_id'] in ii,'status':st,'source_count':len(x['sources'])})
outcsv('all11705_coverage_audit.csv',aud)
es=json.load(open(L/'search_errors.json'));ea=[]
for e in es:
 b=e['path'].split('\\')[-1];legacy='archived_pre_v17_20260802' in e['path'];matches=[s['source_file'] for x in a for s in x['sources'] if s['source_file'].split('\\')[-1]==b] if not legacy else []
 ea.append({'path':e['path'],'basename':b,'path_chars':len(e['path']),'error':e['error'],'category':'legacy_C1_assignment_prescreen_audit' if legacy else 'potential_review_or_same_room_source','relevance':'not_proven_irrelevant; no_contents_read' if legacy else 'potential_comment_gap_requires_source_recovery','same_basename_read_elsewhere':sorted(set(matches)),'byte_equality_verified':False})
outcsv('search_errors123_audit.csv',ea)
summary={'recent36':{'absent_cloud_image_text':36,'exact_annotation_bindings':22,'image_or_wall_group_bindings':14,'raw_text_verified':36,'same_time_field_exact':34,'issue_created_vs_parent_updated_distinct':2},'additional_current259':{'total':len(extra),'original_image_or_pair_comment':sum(x['content_role']=='original_user_comment' for x in extra),'cross_image_relationship_context':sum(x['content_role']!='original_user_comment' for x in extra),'pair_bindings':sum(bool(x['related_object_ids']) for x in extra)},'additional_outside259':len(outside),'pending_group_history':{'image_bindings':len(pending),'distinct_texts':len(groups)},'point109_mirrors_pending':4,'complete11705':dict(collections.Counter(x['status'] for x in aud)),'search_errors123':dict(collections.Counter(x['category'] for x in ea)),'scope':'Exhaustive candidate provenance/coverage census, bounded manual examination of original-field families; not proof that all 11705 candidate meanings or all disk files were adjudicated.','identity_fact':'uNb9QFRL6hY-88 is user-confirmed remembered image; no new polygon approval.','mutations':'No GT, qualification, score, or inventory input mutations.'}
dump('verification_summary.json',summary);print(json.dumps(summary,ensure_ascii=False,indent=2))
