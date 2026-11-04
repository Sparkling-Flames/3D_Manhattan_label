"""Freeze one existing physical pair per image/pair/budget without outcomes.

Reads only the audited metadata registry; neither scores, failure status, labor,
coordinates nor references are inspected. See DIAGNOSTIC_SAMPLE_PROTOCOL.json.
"""
from __future__ import annotations
import hashlib,json
import pandas as pd
from mechanism_core import ROOT,OUT,sha,save_csv,save_json

REGISTRY=OUT.parent/'registry/LEGAL_CURRENT_AC_EVENTS.csv.gz'

def main():
    d=pd.read_csv(REGISTRY,keep_default_na=False,low_memory=False)
    d=d[d.analysis_source.eq('legacy_target_stock_current_label_conditional') &
        d.scope.eq('primary') & d.layer.eq('ordinary_manual') & d.condition.eq('manual') &
        pd.to_numeric(d.current_n).isin([14,20]) & pd.to_numeric(d.current_m).eq(7)].copy()
    assert d.current_ac_legal.astype(str).str.lower().eq('true').all()
    d['n']=pd.to_numeric(d.current_n).astype(int);d['m']=pd.to_numeric(d.current_m).astype(int)
    d['canonical_pair_id']=d.canonical_physical_pair_id
    d['unordered_pair']=d.current_class_pair
    d['selection_hash']=d.canonical_pair_id.map(lambda s:hashlib.sha256(('202611041302|'+s).encode()).hexdigest())
    aliases=d.groupby('canonical_pair_id').event_id.agg(lambda x:'|'.join(sorted(set(x)))).to_dict()
    d=d.sort_values(['canonical_pair_id','event_id']).drop_duplicates('canonical_pair_id')
    strata=['n','m','pool_id','unordered_pair']
    counts=d.groupby(strata).agg(eligible_physical_pairs=('canonical_pair_id','nunique')).reset_index()
    chosen=d.sort_values(strata+['selection_hash','canonical_pair_id']).groupby(strata,sort=True,as_index=False).head(1)
    records=[]
    for r in chosen.to_dict('records'):
        r['source_event_aliases']=aliases[r['canonical_pair_id']]
        for f in ['A_team_key','C_team_key','A_workers','C_workers','X_workers','Z_workers','current_source_class','current_target_class']:
            r['registered_'+f]=r[f]
        if int(r['orientation_sign'])==-1:
            for a,b in [('A_team_key','C_team_key'),('A_workers','C_workers'),('X_workers','Z_workers'),('current_source_class','current_target_class')]:
                r[a],r[b]=r[b],r[a]
        r['source_class_current']=r['current_source_class'];r['target_class_current']=r['current_target_class']
        r['direction']=r['source_class_current']+'_to_'+r['target_class_current']
        r['diagnostic_orientation']='ascending_current_class; registered orientation separately retained'
        assert r['A_team_key']==r['canonical_A_team_key'] and r['C_team_key']==r['canonical_C_team_key']
        records.append(r)
    sample=pd.DataFrame(records).merge(counts,on=strata,validate='one_to_one')
    target=OUT/'DIAGNOSTIC_SAMPLE.csv.gz'
    if target.exists():
        old=pd.read_csv(target,keep_default_na=False,low_memory=False)
        assert old[['canonical_pair_id','selection_hash']].to_dict('records')==sample[['canonical_pair_id','selection_hash']].to_dict('records'),'Frozen sample cannot be silently replaced.'
    else: save_csv(target,sample)
    save_csv(OUT/'DIAGNOSTIC_SAMPLE_STRATUM_CAPACITY.csv',counts)
    receipt=dict(protocol_sha256=sha(OUT/'DIAGNOSTIC_SAMPLE_PROTOCOL.json'),registry=str(REGISTRY.relative_to(ROOT)),registry_sha256=sha(REGISTRY),
                 sample_sha256=sha(target),sample_pairs=len(sample),pools=sample.pool_id.nunique(),images=sample.image.nunique(),buildings=sample.building.nunique(),
                 eligible_physical_pairs=len(d),unique_endpoints=len(set(sample.A_team_key)|set(sample.C_team_key)),
                 conditions=sample.groupby(['n','m','unordered_pair']).agg(pairs=('canonical_pair_id','nunique'),images=('image','nunique'),buildings=('building','nunique')).reset_index().to_dict('records'),
                 no_outcome_status_time_coordinates_or_GT_read=True,selection_reads_registry_metadata_only=True,new_physical_teams=0)
    save_json(OUT/'DIAGNOSTIC_SAMPLE_FREEZE_RECEIPT.json',receipt)
    print(json.dumps(receipt,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
