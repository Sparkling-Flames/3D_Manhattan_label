import json,gzip,pathlib,math
P=pathlib.Path('/workspace/shared/personnel_partA_audit_20261019');O=P/'extracted/work_personnel_typing_A_20261019/events/native_runs/pools';N=P/'independent_fresh/pools'
maxerr=0.;bad=[];n=0

def comp(a,b,path):
 global maxerr
 if isinstance(a,(int,float)) and not isinstance(a,bool) and isinstance(b,(int,float)):
  e=abs(a-b);maxerr=max(maxerr,e)
  if e>1e-9:bad.append(path)
 elif isinstance(a,dict) and isinstance(b,dict):
  if a.keys()!=b.keys():bad.append(path+':keys')
  for k in a.keys()&b.keys():comp(a[k],b[k],path+'/'+k)
 elif isinstance(a,list) and isinstance(b,list):
  if len(a)!=len(b):bad.append(path+':length')
  for i,(x,y) in enumerate(zip(a,b)):comp(x,y,path+'/'+str(i))
 elif a!=b:bad.append(path)
for f in N.glob('*/states.json.gz'):
 old={s['subset']:s['automatic'] for s in json.load(gzip.open(O/f.parent.name/'states.json.gz','rt'))['states']}
 for s in json.load(gzip.open(f,'rt'))['states']:
  comp(s['automatic'],old[s['subset']],f.parent.name+'/'+s['subset']);n+=1
r={'n_fresh_states_compared':n,'max_numeric_absolute_difference':maxerr,'mismatch_paths':bad,'tolerance':1e-9};(P/'independent_fresh/STATE_COMPARISON.json').write_text(json.dumps(r,indent=2));print(r)
