"""Check physical AC/BC overlap both within and across classification methods."""
from pathlib import Path
import hashlib,json,gzip
import pandas as pd

OUT=Path(__file__).resolve().parents[1];BASE=OUT.parent

def main():
 old=OUT/'STRICT_EXACT_AC_BC_PAIR_INDEX.csv.gz';new=BASE/'stage01_registered/AC_EVENTS.csv.gz'
 prior=pd.read_csv(old,low_memory=False);keys=set(prior.physical_pair_id)
 hit=[];registered_count=0
 cols=['event_id','physical_pair_id','pool_id','method','n','m','design_family','A_team_key','C_team_key']
 for chunk in pd.read_csv(new,usecols=cols,chunksize=30000,low_memory=False):
  registered_count+=len(chunk)
  part=chunk[chunk.physical_pair_id.isin(keys)]
  if len(part):hit.append(part)
 current=pd.concat(hit,ignore_index=True) if hit else pd.DataFrame(columns=cols)
 matched=current.merge(prior,on=['physical_pair_id','pool_id'],how='inner',suffixes=('_new','_strict'))
 matched['same_classification_method']=matched.method_new.eq(matched.method_strict)
 with gzip.open(OUT/'EXACT_NEW_AC_PRIOR_STRICT_PHYSICAL_PAIR_OVERLAPS.csv.gz','wt',encoding='utf-8-sig',newline='') as f:matched.to_csv(f,index=False)
 r={'registered_new_method_events':registered_count,
    'strict_AC_BC_index_rows':len(prior),'strict_unique_physical_pairs':prior.physical_pair_id.nunique(),
    'new_unique_method_events_matching_any_prior_method':current.event_id.nunique(),
    'new_unique_physical_pairs_matching_any_prior_method':current.physical_pair_id.nunique(),
    'new_unique_method_events_matching_same_prior_method':matched.loc[matched.same_classification_method,'event_id'].nunique(),
    'link_rows':len(matched),'new_registered_sha256':hashlib.sha256(new.read_bytes()).hexdigest(),
    'strict_index_sha256':hashlib.sha256(old.read_bytes()).hexdigest(),
    'unit':'Exact unordered A/C or B/C endpoint pair including pool/target, not an individual cached team.',
    'qualification_rechecked':False,'new_fusions':0,'new_scores':0}
 (OUT/'EXACT_PHYSICAL_PAIR_OVERLAP_RECEIPT.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(r,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
