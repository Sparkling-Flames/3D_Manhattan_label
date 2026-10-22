from pathlib import Path
import sys, pandas as pd,numpy as np,gzip,csv,json,io
root=Path(sys.argv[1]).resolve();data=root/'research/workers/personnel_population_curves_v2_20261023';pkg=data;out=root/'analysis_results/pro_return_review_20261023';out.mkdir(parents=True,exist_ok=True);sys.path.insert(0,str(pkg/'code'))
from analyze_policy_curves import paired_events,METRICS,FLAGS,META
cols=set(METRICS+FLAGS+META+['team_key','source_time_known_n','target_time_known_n','member_workers'])
s=pd.read_csv(data/'results/ENDPOINT_SCALARS.csv.gz',usecols=lambda c:c in cols,low_memory=False)
l=pd.read_csv(data/'results/PREFIX_TEAM_LINKS.csv.gz');orders=pd.read_csv(data/'design/EXACT_ORDER_DESIGN.csv.gz')
shared=[c for c in s if c in l and c!='team_key']
d=l.merge(s.drop(columns=shared),on='team_key',how='left',validate='many_to_one')
p,_,_=paired_events(d,orders,pkg/'inputs/IMAGE_DIFFICULTY_OPPORTUNITIES.csv');p['source_row_1based']=np.arange(1,len(p)+1)
lookup={r.team_key:set(r.member_workers.split('|')) for r in s[['team_key','member_workers']].itertuples()}
added=[];removed=[];common=[]
for a,b in zip(p.priority_team_key,p.natural_team_key):
 aa,bb=lookup[a],lookup[b];added.append('|'.join(sorted(aa-bb)));removed.append('|'.join(sorted(bb-aa)));common.append(len(aa&bb))
p['members_added']=added;p['members_removed']=removed;p['members_added_n']=p.actual_m;p['members_removed_n']=p.actual_m;p['members_shared_n']=common
src=data/'source_original/04C/POLICY_PAIRED_PREFIX_EVENTS_LINKED.csv.gz.truncated'
with gzip.open(src,'rt',encoding='utf-8-sig',newline='') as f:cols=next(csv.reader(f))
p=p[cols];assert len(p)==229050
# Read every complete original CSV record. A gzip EOF is retained in the receipt, never treated as success.
count=0;numeric_errors={};text_errors={};null_errors={};eof=None;chunk=[]
numcols=set(p.select_dtypes(include='number').columns);boolcols=set(p.select_dtypes(include='bool').columns)
def check(rows,start):
 a=pd.DataFrame(rows,columns=cols).replace('',np.nan);b=p.iloc[start:start+len(rows)].reset_index(drop=True)
 for c in cols:
  if c in numcols:
   x=pd.to_numeric(a[c]);y=pd.to_numeric(b[c]);missing=(x.isna()!=y.isna()).sum()
   if missing:null_errors[c]=null_errors.get(c,0)+int(missing)
   err=np.abs(x-y).max()
   if pd.notna(err):numeric_errors[c]=max(numeric_errors.get(c,0.),float(err))
  elif c in boolcols:
   x=a[c].astype(str).str.lower().map({'true':True,'false':False,'1':True,'0':False});bad=(x!=b[c]).sum()
   if bad:text_errors[c]=text_errors.get(c,0)+int(bad)
  else:
   bad=(a[c].fillna('').astype(str)!=b[c].fillna('').astype(str)).sum()
   if bad:text_errors[c]=text_errors.get(c,0)+int(bad)
try:
 with gzip.open(src,'rt',encoding='utf-8-sig',newline='') as f:
  reader=csv.reader(f);next(reader)
  for row in reader:
   assert len(row)==len(cols)
   chunk.append(row)
   if len(chunk)==10000:check(chunk,count);count+=len(chunk);chunk=[]
except EOFError as e:eof=str(e)
if chunk:check(chunk,count);count+=len(chunk)
print('original_complete_rows',count,'missing',len(p)-count,'EOF',eof,flush=True)
print('comparison',{'max_numeric_error':max(numeric_errors.values()),'text_errors':text_errors,'null_errors':null_errors},flush=True)
assert not text_errors and not null_errors and max(numeric_errors.values())<1e-9
# Generated from complete archived source orders and endpoints, not filled with estimates.
dst=out/'POLICY_PAIRED_PREFIX_EVENTS_LINKED_REBUILT.csv.gz';p.to_csv(dst,index=False,encoding='utf-8-sig',compression={'method':'gzip','compresslevel':6,'mtime':0})
with gzip.open(dst,'rt',encoding='utf-8-sig',newline='') as f:
 reader=csv.reader(f);assert next(reader)==cols;n=sum(1 for row in reader if len(row)==len(cols))
assert n==229050
receipt={'source_file':src.name,'source_complete_rows':count,'source_error':eof,'reconstructed_rows':n,'reconstructed_missing_rows':n-count,'columns':len(cols),'max_numeric_error_on_existing_rows':max(numeric_errors.values()),'text_errors':text_errors,'null_errors':null_errors,'native_fusion_calls':0,'rescoring_calls':0,'output':dst.name,'method':'Recompute paired events from complete exact orders, prefix links and stored endpoint scalars; check every complete original row before replacing any delivery.'}
(out/'EVENT_RECONSTRUCTION_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf8');print('DONE',receipt,flush=True)
