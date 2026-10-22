from core import *
inputs={x['record']['id']:x for x in json.load(open(OUT/'round_c_inputs.json'))};artifacts=json.load(open(OUT/'round_c_fit_artifacts.json'));rows=[]
for item in artifacts:
 f=item['fits']['equal_node'];r=inputs[item['expression_id']]['record']
 if f['status']=='ok' or prepare(r)['status']!='ok':continue
 new=fit_node(r,starts=3)
 rows.append(dict(image=item['image'],expression_id=r['id'],original_status=f['status'],original_reason=f.get('reason'),three_start_status=new['status'],three_start_reason=new.get('reason'),objectives=json.dumps(new.get('starts',[]))))
 save_csv('round_c_equalnode_failure_retries.csv',rows)
print('retried',len(rows),'rescued',sum(r['three_start_status']=='ok' for r in rows))
