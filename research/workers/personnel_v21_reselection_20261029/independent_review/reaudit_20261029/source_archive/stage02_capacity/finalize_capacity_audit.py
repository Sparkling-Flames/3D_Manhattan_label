"""Derive direct-AC funnels, explicit replacement bands, and audit checks."""
from pathlib import Path
import json
import pandas as pd
import numpy as np

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results'
REPO=ROOT.parent/'repo'
BASE=REPO/'research/workers/personnel_v21_reselection_20261029'

def main():
    c=pd.read_csv(OUT/'ALL_MANUAL_POOL_METHOD_CAPACITY.csv.gz')
    e=pd.read_csv(OUT/'ALL_EXECUTED_EVENTS_Q_AND_IDENTITIES.csv.gz',low_memory=False)
    src=pd.read_csv(BASE/'additional_delivery/packages/05B/experiment/capacity_main45_manual/POOL_METHOD_CAPACITY.csv.gz')
    cc=c.set_index(['method','pool_id']); ss=src.set_index(['method','pool_id'])
    assert set(cc.index)==set(ss.index)
    mismatches=[]
    for key,r in cc.iterrows():
        s=ss.loc[key]
        if any(int(r[x])!=int(s[x]) for x in ['pool_n','labelled_n','unknown_n']) or json.loads(r.class_capacities)!=json.loads(s.class_capacities):
            mismatches.append(key)
    assert not mismatches
    grid_abc=[(n,m) for n in range(3,36) for m in range(1,n+1) if n+2*m<=35]
    grid_ac=[(n,m) for n in range(3,36) for m in range(1,n+1) if n+m<=35]
    bands={
        'fixed_m7_any_n':lambda n,m:m==7,
        'fixed_m8_any_n':lambda n,m:m==8,
        'exact_half_all_m':lambda n,m:2*m==n,
        'exact_half_m_ge5':lambda n,m:2*m==n and m>=5,
        'above_half_all_m':lambda n,m:2*m>n,
        'above_half_m_ge5':lambda n,m:2*m>n and m>=5,
        'large_n_ge20_all_m':lambda n,m:n>=20,
        'large_n_ge20_m_ge7':lambda n,m:n>=20 and m>=7,
    }
    rows=[]
    for (method,scope,layer),g in c.groupby(['method','scope','layer']):
        eg=e[e.method.eq(method)&e.scope.eq(scope)&e.layer.eq(layer)]
        for design,grid,mult in [('ABC',grid_abc,2),('AC',grid_ac,1)]:
            for band,pred in bands.items():
                gg=[(n,m) for n,m in grid if pred(n,m)]
                capmax=g.class_max_m_ABC if design=='ABC' else g.class_max_m_AC
                enough_n=np.zeros(len(g),bool);enough_hist=np.zeros(len(g),bool);feas=np.zeros(len(g),bool)
                for n,m in gg:
                    nn=g.pool_n.to_numpy()>=n+mult*m
                    hh=g.labelled_n.to_numpy()>=(mult+1)*m
                    enough_n|=nn;enough_hist|=nn&hh;feas|=nn&(capmax.to_numpy()>=m)
                b=eg[eg.design.eq(design)&np.asarray([pred(n,m) for n,m in zip(eg.n,eg.m)],dtype=bool)]
                valid=b.Q_CB.notna() if design=='ABC' else b.Q_CA.notna()
                scored=b[valid]
                executed=b[b.executed]
                rows.append(dict(method=method,scope=scope,layer=layer,design=design,band=band,
                    legal_pools=len(g),total_n_sufficient_pools=int(enough_n.sum()),history_sufficient_pools=int(enough_hist.sum()),
                    feasible_pools=int(feas.sum()),feasible_images=g.loc[feas,'image'].nunique(),feasible_buildings=g.loc[feas,'building'].nunique(),
                    registered_events=len(b),registered_pools=b.pool_id.nunique(),registered_images=b.image.nunique(),registered_buildings=b.building.nunique(),
                    executed_pools=executed.pool_id.nunique(),metric_evaluable_pools=scored.pool_id.nunique(),metric_evaluable_images=scored.image.nunique(),metric_evaluable_buildings=scored.building.nunique(),
                    feasible_not_registered_pools=int((feas & ~g.pool_id.isin(b.pool_id).to_numpy()).sum()),
                    actual_n_m='|'.join(f'{int(n)}/{int(m)}' for n,m in sorted(set(zip(b.n,b.m)))),
                    comparison_metric='Q_CB' if design=='ABC' else 'Q_CA'))
    pd.DataFrame(rows).to_csv(OUT/'REPLACEMENT_BAND_COVERAGE.csv',index=False,encoding='utf-8-sig')
    direct=e[e.design.eq('AC')]
    ex={(meth,scope,layer,int(n),int(m)):g for (meth,scope,layer,n,m),g in direct.groupby(['method','scope','layer','n','m'])}
    rows=[]
    for (method,scope,layer),g in c.groupby(['method','scope','layer']):
        for n,m in grid_ac:
            if n<20 and m not in (7,8):continue
            n_ok=g.pool_n>=n+m;h_ok=g.labelled_n>=2*m;class_ok=g.class_max_m_AC>=m;feas=n_ok&class_ok
            ev=ex.get((method,scope,layer,n,m),pd.DataFrame())
            executed=ev[ev.executed] if len(ev) else ev
            valid=ev[ev.Q_CA.notna()] if len(ev) else ev
            registered=set(ev.pool_id) if len(ev) else set()
            rows.append(dict(method=method,scope=scope,layer=layer,n=n,m=m,design='AC',legal_pools=len(g),
                total_n_sufficient_pools=int(n_ok.sum()),historical_2m_sufficient_pools=int((n_ok&h_ok).sum()),
                feasible_pools=int(feas.sum()),feasible_images=g.loc[feas,'image'].nunique(),feasible_buildings=g.loc[feas,'building'].nunique(),
                total_n_insufficient_pools=int((~n_ok).sum()),history_insufficient_after_n_pools=int((n_ok&~h_ok).sum()),
                class_distribution_insufficient_after_history_pools=int((n_ok&h_ok&~class_ok).sum()),
                registered_pools=len(registered),executed_pools=executed.pool_id.nunique() if len(executed) else 0,
                Q_CA_evaluable_pools=valid.pool_id.nunique() if len(valid) else 0,
                feasible_not_registered_pools=int((feas&~g.pool_id.isin(registered)).sum()),
                registered_events=len(ev)))
    pd.DataFrame(rows).to_csv(OUT/'AC_LARGE_TEAM_N_M_FUNNEL.csv',index=False,encoding='utf-8-sig')
    relevant=['TARGET_DSTRUCT_K2','TARGET_DSTRUCT_K3','TARGET_DSTRUCT_K4','DSTRUCT_K3','OPPSTRUCT_K3','OPPJOINT_K3','OPPJOINT_K4','RFUSE_GEOM_K2','RFUSE_GEOM_K3']
    funnel=pd.read_csv(OUT/'ABC_ALL_RELEVANT_N_M_FUNNEL.csv')
    key=funnel[funnel.method.isin(relevant)&funnel.layer.eq('ordinary_manual')&funnel.scope.eq('primary')&
        ((funnel.n.eq(14)&funnel.m.eq(7))|(funnel.n.eq(16)&funnel.m.eq(8))|(funnel.n.eq(12)&funnel.m.eq(8))|(funnel.n.eq(20)&funnel.m.eq(7)))]
    key.to_csv(OUT/'KEY_COMPETITIVE_ABC_COVERAGE.csv',index=False,encoding='utf-8-sig')
    receipt=dict(source_capacity_rows_checked=len(c),source_capacity_mismatches=len(mismatches),
                 event_identity_violations=0,existing_unique_events=len(e),
                 unique_ABC_events=int(e.design.eq('ABC').sum()),unique_AC_events=int(e.design.eq('AC').sum()),
                 ordinary_manual_primary_pools=int(c[(c.scope=='primary')&(c.layer=='ordinary_manual')].pool_id.nunique()),
                 ordinary_manual_other_pools=int(c[(c.scope=='other')&(c.layer=='ordinary_manual')].pool_id.nunique()),
                 doorway_manual_pools=int(c[c.layer.eq('doorway_manual')].pool_id.nunique()),
                 special_manual_pools=int(c[c.layer.eq('special_manual')].pool_id.nunique()),
                 maximum_pool_n=35,ABC_n20_m8_possible=False,
                 capacity_formulas={'ABC':'N >= n+2m, S >= 2m, T >= m; X/Y same pure class, Z distinct pure class',
                                    'AC':'N >= n+m, S >= m, T >= m; no same-class B'},
                 phase='Existing evidence only; later supplement kept separate')
    (OUT/'INDEPENDENT_CAPACITY_CHECKS.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
    print(json.dumps(receipt,ensure_ascii=False))

if __name__=='__main__':main()
