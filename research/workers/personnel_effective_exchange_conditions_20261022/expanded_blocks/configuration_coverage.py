#!/usr/bin/env python3
"""Separate exact class-vector coverage from actual member-set coverage."""
from register_expanded import *

def positive(s):return '|'.join(f'{k}:{v}' for k,v in sorted((x.split(':')[0],int(x.split(':')[1])) for x in s.split('|')) if v)

def main():
    full=pd.read_csv(HERE/'ALL_FEASIBLE_CLASS_CONFIGURATIONS.csv.gz',dtype=str,keep_default_na=False)
    idx=pd.read_csv(HERE/'REGISTERED_EVENT_PARTS.csv',keep_default_na=False)
    rows=[];cells=[]
    for part in idx.to_dict('records'):
        f=full[full.cell_id.eq(part['cell_id'])];theory={}
        for x in f.to_dict('records'):
            for arm in ['A','C']:theory[positive(x[arm+'_counts'])]=int(x['concrete_'+arm+'_teams'])
        r=pd.read_csv(REPO/part['path'],usecols=['team_A','team_B','team_C','A_counts','B_counts','C_counts','physical_triple_id','common_background'],dtype=str)
        registered=collections.defaultdict(set)
        for arm in 'ABC':
            for vec,g in r.groupby(arm+'_counts'):registered[positive(vec)].update(g['team_'+arm])
        assert registered.keys()<=theory.keys()
        for vec,total in theory.items():
            got=len(registered[vec]);rows.append(dict(cell_id=part['cell_id'],method_id=part['method_id'],n=part['n'],m=part['m'],
                pool_id=part['pool_id'],class_counts=vec,possible_member_sets=str(total),registered_member_sets=got,
                missing_member_sets=str(total-got),configuration_covered=got>0))
        cells.append(dict(cell_id=part['cell_id'],method_id=part['method_id'],n=part['n'],m=part['m'],pool_id=part['pool_id'],
            feasible_configurations=len(theory),covered_configurations=sum(bool(registered[v]) for v in theory),
            all_configs_covered=all(bool(registered[v]) for v in theory),
            possible_unique_member_sets=str(sum(theory.values())),registered_unique_member_sets=len(set(r.team_A)|set(r.team_B)|set(r.team_C)),
            oriented_ABC=len(r),physical_triples=r.physical_triple_id.nunique(),backgrounds=r.common_background.nunique()))
    write_csv(HERE/'CLASS_CONFIG_MEMBER_COVERAGE.csv.gz',rows)
    write_csv(HERE/'CELL_CONFIG_MEMBER_COVERAGE.csv',cells)
    print(pd.DataFrame(cells).groupby(['method_id','m']).agg(cells=('cell_id','size'),all_configs=('all_configs_covered','sum'),
        feasible_configs=('feasible_configurations','sum'),covered_configs=('covered_configurations','sum')).to_string())

if __name__=='__main__':main()
