"""Per AC cell member exposure and fixed cores, using frozen identities only."""
from pathlib import Path
from collections import Counter
import argparse,csv,gzip,hashlib,json
import pandas as pd
from analyze_population_sensitivity import save,pipe,digest


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--design',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    base=Path(a.design);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    lg=pd.read_csv(base/'DESIGN_LINKS.csv.gz',usecols=['event_id','cell_id','design_family','background_profile'],low_memory=False)
    lg=lg[lg.design_family.isin(['A_equal_AC','B_equal_whole_class','S_equal_whole_class']) & lg.background_profile.eq('neutral_members_0')]
    lg=lg[['event_id','cell_id']].drop_duplicates()
    ids=set(lg.event_id)
    fields=['event_id','physical_pair_id','pool_id','image','building','scope','condition','layer','method','n','m',
        'source_class','target_class','source_role_rank','target_role_rank','source_class_available_n','target_class_available_n',
        'X_workers','Z_workers','D_workers','A_team_key','C_team_key']
    parts=[]
    for d in pd.read_csv(base/'AC_EVENTS.csv.gz',usecols=lambda c:c in fields,chunksize=50000,low_memory=False):
        parts.append(d[d.event_id.isin(ids)])
    events=pd.concat(parts,ignore_index=True);del parts
    d=events.merge(lg,on='event_id',how='inner',validate='one_to_many')
    # Semi registration uses event links without Manual's cell_id field.
    # Preserve every actual event and construct a descriptive analysis key;
    # this does not create, select or relabel any team.
    d['cell_id_origin']='frozen_registration'
    missing=d.cell_id.isna() | d.cell_id.astype(str).eq('')
    keyfields=['pool_id','method','n','m','source_class','target_class']
    d.loc[missing,'cell_id']=d.loc[missing,keyfields].apply(lambda row:digest(['analysis_cell_without_registered_id',row.tolist()])[:24],axis=1)
    d.loc[missing,'cell_id_origin']='derived_from_exact_condition_for_missing_registration_id'
    result=[]
    for cell,g in d.groupby('cell_id',sort=False):
        r={k:g.iloc[0][k] for k in fields if k not in ['event_id','physical_pair_id','X_workers','Z_workers','D_workers','A_team_key','C_team_key']}
        r.update(cell_id=cell,cell_id_origin=g.iloc[0].cell_id_origin,physical_pairs=g.physical_pair_id.nunique(),events=g.event_id.nunique(),
            distinct_XZ_blocks=g[['X_workers','Z_workers']].drop_duplicates().shape[0],
            distinct_A_teams=g.A_team_key.nunique(),distinct_C_teams=g.C_team_key.nunique(),distinct_D=g.D_workers.fillna('').nunique())
        for side,col in [('source','X_workers'),('target','Z_workers')]:
            sets=[set(pipe(x)) for x in g[col]];counts=Counter(w for ws in sets for w in ws)
            core=set.intersection(*sets);union=set.union(*sets)
            r.update({side+'_distinct_blocks':g[col].nunique(),side+'_members_seen_n':len(union),
                side+'_fixed_core_n':len(core),side+'_fixed_core_workers':'|'.join(sorted(core)),
                side+'_worker_event_frequency_json':json.dumps(dict(sorted(counts.items())),sort_keys=True,separators=(',',':')),
                side+'_every_block_identical':g[col].nunique()==1,
                side+'_all_available_in_every_block':len(core)==int(float(r[side+'_class_available_n']))})
        result.append(r)
    frame=pd.DataFrame(result);dest=out/'AC_CELL_MEMBER_CORES_AND_FREQUENCIES.csv.gz';save(frame,dest)
    summary=[]
    for key,g in frame.groupby(['scope','condition','layer','method','n','m'],dropna=False,sort=False):
        r=dict(zip(['scope','condition','layer','method','n','m'],key));r.update(cells=len(g),images=g.image.nunique(),buildings=g.building.nunique(),
            source_block_fixed_cells=int(g.source_every_block_identical.sum()),target_block_fixed_cells=int(g.target_every_block_identical.sum()),
            both_blocks_fixed_cells=int((g.source_every_block_identical&g.target_every_block_identical).sum()),
            any_fixed_core_cells=int((g.source_fixed_core_n.gt(0)|g.target_fixed_core_n.gt(0)).sum()),
            all_source_available_always_used_cells=int(g.source_all_available_in_every_block.sum()),
            all_target_available_always_used_cells=int(g.target_all_available_in_every_block.sum()))
        summary.append(r)
    save(pd.DataFrame(summary),out/'AC_CELL_CORE_COVERAGE_SUMMARY.csv.gz')
    validation=[]
    for p in [dest,out/'AC_CELL_CORE_COVERAGE_SUMMARY.csv.gz']:
        with gzip.open(p,'rt',encoding='utf-8-sig',newline='') as f:
            rr=csv.reader(f);header=next(rr);n=0
            for row in rr:assert len(row)==len(header);n+=1
        validation.append({'file':p.name,'rows':n,'columns':len(header),'full_gzip_eof':True,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    receipt={'cells':len(frame),'events':events.event_id.nunique(),'physical_pairs':events.physical_pair_id.nunique(),
        'manual_cells':int(frame.condition.eq('manual').sum()),'semi_cells':int(frame.condition.eq('semi').sum()),
        'selection':'All frozen A/B equal and Semi equal neutral-members-0 cells; no outcome values read',
        'exposure_denominator':'distinct registered AC events within a cell; not independent people or repetitions',
        'source_event_sha256':hashlib.sha256((base/'AC_EVENTS.csv.gz').read_bytes()).hexdigest(),
        'source_links_sha256':hashlib.sha256((base/'DESIGN_LINKS.csv.gz').read_bytes()).hexdigest(),
        'new_teams':0,'new_fusions':0,'files':validation}
    (out/'CORE_MEMBER_COVERAGE_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k!='files'},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
