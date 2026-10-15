exec(open('local_scope_verified/verify.py').read().split('verified=[]')[0])
import re
sel=json.load(open(O/'original_field_candidates.json'));a=json.load(open(L/'complete_bound_candidates.json'));go={v['object_id']:v for v in g};ct={(x['image_id'],x['comment'].strip()) for x in c};allrows=[]
for x in sel:
 x=dict(x);s=x['sources'][0];p=s['json_pointer'];rid=x.get('record_id');oid=x.get('object_id');iid=x.get('image_id');pairs=[]
 if '/traits/annotation:' in p:
  oid=p.split('/traits/annotation:')[1].split('/')[0]
  if oid in go:iid=go[oid]['image_id'];rid=go[oid]['record_id']
 if not iid:
  m=re.search(r'([A-Za-z0-9]{11}_[a-f0-9]{32})',p)
  if m:iid=m.group(1)
 if '|manual|' in p:pairs=p.split('|manual|')[1].split('/')[0].split('|')
 x.update(image_id=iid,object_id=oid,record_id=rid,image_code=ii[iid]['image_code'] if iid in ii else None,related_object_ids=pairs)
 x['in_current_259']=iid in ii;x['cloud_status']='present_image_text_trimmed' if (iid,x['text'].strip()) in ct else 'absent_image_text'
 ps=[s['json_pointer'] for s in x['sources']]
 x['content_role']='original_user_comment'
 if any('/source_comment' in p for p in ps):x['content_role']='original_user_cross_image_relationship_context'
 x['raw_text_verified']=all(s['raw_record'].get(s['json_pointer'].split('/')[-1])==x['text'] for s in x['sources'])
 x['reference_scope_verified']=False;x['no_gt_score_or_eligibility_change']=True
 allrows.append(x)
# coalesce only exact resolved identity+text; keep source records/times
co={}
for x in allrows:
 k=(x['image_id'],x['object_id'],tuple(x['related_object_ids']),x['text'])
 if k in co:co[k]['sources']+=x['sources']
 else:co[k]=x
rows=list(co.values());new=[x for x in rows if x['cloud_status']=='absent_image_text'];current=[x for x in new if x['in_current_259']];outside=[x for x in new if not x['in_current_259']]
dump('additional_original_comments_resolved.json',rows);dump('additional_current_user_comments.json',current);dump('additional_outside259_user_comments.json',outside)
flat=lambda x:{k:x[k] for k in ['image_code','image_id','object_id','record_id','text','schema','related_object_ids','in_current_259','cloud_status','content_role','raw_text_verified']}
outcsv('additional_current_user_comments.csv',[flat(x) for x in current]);outcsv('additional_outside259_user_comments.csv',[flat(x) for x in outside])
print('resolved',len(rows),'covered',len(rows)-len(new),'current new',len(current),'outside',len(outside))
for x in current: print(x['image_code'],x['content_role'],x['record_id'],repr(x['text']))
# reported reviewer_note mirrors lack original raw record in returned package, not promote to verified
sus=[]
for x in a:
 if x['candidate_id'] in [f'bound_local_{i:06}' for i in range(11563,11567)]:
  x=dict(x);x['record_id']=next((s['record_id'] for s in x['sources'] if s.get('record_id')),None);z=gi.get(x['record_id'],{});x['identity_verified']=z.get('image_id')==x['image_id'] and z.get('object_id')==x['object_id'];x['cloud_status']='present' if (x['image_id'],x['text'].strip()) in ct else 'absent';x['original_raw_record_available']=False;x['verification_status']='reviewer_note_mirrors_only_original_109_export_needed';sus.append(x)
dump('point109_provenance_pending4.json',sus)
