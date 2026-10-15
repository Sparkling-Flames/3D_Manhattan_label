import json,csv,collections,hashlib
from pathlib import Path
L=Path('local_scope_return/extracted'); C=Path('scope_full_inventory_20261010'); O=Path('local_scope_verified')
def csvread(n): return list(csv.DictReader(open(C/n,encoding='utf-8-sig')))
def dump(n,x): (O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2))
def outcsv(n,rows):
 if not rows:return
 with open(O/n,'w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows([{k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()} for r in rows])
c=csvread('unique_comments.csv');g=csvread('all_3152_geometry_records.csv');im=csvread('all_259_images.csv');r=json.load(open(L/'incremental_recent_human_records.json'));gi={v['record_id']:v for v in g};ii={v['image_id']:v for v in im}
verified=[]
for n,x in enumerate(r):
 v=dict(x); v['verification_id']=f'LOCAL36_{n+1:02}';v['comment']=x['text'];v['cloud_exact_matches']=[y['comment_id'] for y in c if y['image_id']==x['image_id'] and y['comment']==x['text']];v['cloud_status']='absent_exact_image_text' if not v['cloud_exact_matches'] else 'present'
 v['image_identity_verified']=x['image_id'] in ii and ii[x['image_id']]['image_code']==x['image_code']
 v['object_identity_verified']=bool(x.get('record_id') and x['record_id'] in gi and gi[x['record_id']]['image_id']==x['image_id'] and gi[x['record_id']]['object_id']==x['object_id'])
 v['binding_level']='exact_annotation' if v['object_identity_verified'] else 'image_or_wall_group_only'
 checks=[]
 for s in x['sources']:
  rr=s['raw_record'];field=s['json_pointer'].split('/')[-1];t=rr.get('updatedAt',rr.get('updated_at',rr.get('created_at')))
  checks.append({'source_file':s['source_file'],'pointer':s['json_pointer'],'raw_text_exact':rr.get(field)==x['text'],'raw_time':t,'reported_time':s.get('updated_at'),'time_match':t==s.get('updated_at'),'timestamp_basis':'raw_record' if t else 'parent_context_not_embedded'})
 v['source_checks']=checks;v['raw_text_verified']=all(a['raw_text_exact'] for a in checks);v['time_verified']=all(a['time_match'] for a in checks)
 v['no_gt_score_or_eligibility_change']=True;v['scope_difference_confirmed']=False
 verified.append(v)
dump('verified_recent36.json',verified)
outcsv('verified_recent36.csv',[{k:v[k] for k in ['verification_id','image_code','image_id','object_id','record_id','comment','schema','reference_version','reference_id','interpretation_status','cloud_status','image_identity_verified','object_identity_verified','binding_level','raw_text_verified','time_verified','source_checks']} for v in verified])
print('36 summary',collections.Counter(v['cloud_status'] for v in verified),collections.Counter(v['binding_level'] for v in verified),'image',sum(v['image_identity_verified'] for v in verified),'raw',sum(v['raw_text_verified'] for v in verified),'time',sum(v['time_verified'] for v in verified))
for v in verified:
 if not v['time_verified']:print('TIME GAP',v['verification_id'],v['source_checks'])
