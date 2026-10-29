"""Rebuild the unequal-class capacity table solely from verified identity inputs.

This targeted regeneration repairs an incomplete generated gzip stream. It does
not rerun eligibility, change labels, or inspect target outcomes.
"""
from pathlib import Path
import csv,gzip,hashlib,json,math
import pandas as pd

OUT=Path(__file__).resolve().parents[1]

def main():
    target=OUT/'WHOLE_CLASS_UNEQUAL_CAPACITY.csv.gz'
    prior_sha256=hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() else None
    caps=pd.read_csv(OUT/'DIRECTED_CLASS_CAPACITY.csv.gz')
    pools={p['pool_id']:p for p in json.loads((OUT/'SCORE_BLIND_POOL_INPUTS.json').read_text())['pools']}
    rows=[]
    for r in caps.to_dict('records'):
        s,t,N=int(r['source_n']),int(r['target_n']),int(r['pool_n'])
        if s==t or min(s,t)==0:continue
        union=set(r['source_workers'].split('|'))|set(r['target_workers'].split('|'))
        candidates=sorted(set(pools[r['pool_id']]['workers'])-union)
        assert len(candidates)==N-s-t
        for d in range(max(0,3-s,3-t),N-s-t+1):
            rows.append(dict(r,D_n=d,n_A=d+s,n_C=d+t,X_n=s,Z_n=t,delta_n=t-s,
                D_candidate_n=len(candidates),D_candidates='|'.join(candidates),
                possible_D_blocks=str(math.comb(len(candidates),d)),
                equal_match_m=min(s,t),equal_match_n=d+min(s,t),
                all_other_members_in_D=d==len(candidates),
                execution_status='capacity_only_not_yet_designed'))
    expected=json.loads((OUT/'CAPACITY_RECEIPT.json').read_text())['whole_unequal_cells']
    assert len(rows)==expected
    temporary=target.with_name(target.name+'.partial')
    pd.DataFrame(rows).to_csv(temporary,index=False,encoding='utf-8-sig',compression='gzip')
    with gzip.open(temporary,'rt',encoding='utf-8-sig',newline='') as f:
        reader=csv.reader(f);header=next(reader);count=0
        for row in reader:
            assert len(row)==len(header)
            count+=1
    assert count==expected
    temporary.replace(target)
    receipt={'file':target.name,'status':'regenerated_and_read_to_eof',
        'prior_generated_file_sha256':prior_sha256,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
        'rows':count,'reason':'initial generated gzip lacked its end-of-stream marker',
        'same_frozen_identity_inputs':True,'fusion_calls':0,'score_calls':0}
    (OUT/'UNEQUAL_TABLE_REGENERATION_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt))

if __name__=='__main__':main()
