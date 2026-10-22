from pathlib import Path
import json,sys
import numpy as np
import pandas as pd

ROOT = Path(sys.argv[1])
def read(rel): return pd.read_csv(ROOT / rel, float_precision='round_trip')
panels = read('design/PANELS.csv')
links = read('design/PANEL_TEAM_LINKS.csv.gz')
ep = pd.concat([pd.read_csv(f, float_precision='round_trip') for f in sorted((ROOT/'results/native/parts').glob('*.csv.gz'))], ignore_index=True).set_index('team_key')
assert ep.index.is_unique
assert set(links.team_key_a)|set(links.team_key_b) <= set(ep.index)
for side in ['a','b']:
    assert (ep.loc[links['team_key_'+side], 'member_workers'].to_numpy() == links.member_set_key.to_numpy()).all()
    for metric in ['B8L2','D10','fusion_turn_n']:
        links[metric+'_'+side] = ep.loc[links['team_key_'+side],metric].to_numpy()
mid = np.minimum(np.maximum(panels.known_common_n//2,np.maximum(3,panels.k_selected)),panels.known_common_n-panels.k_selected)
primary=panels[panels.ordinary_comparable & (panels.replicate==0) & (panels.n==mid)].copy()
meta=['panel_id','pair_key','building','groups','n','k_selected']

def aggregate(frame, values):
    pair=frame.groupby(['pair_key','building','groups'],dropna=False)[values].mean().reset_index()
    expanded=pair.assign(group_id=pair.groups.str.split('|')).explode('group_id')
    group=expanded.groupby(['building','group_id'])[values].mean().reset_index()
    building=group.groupby('building')[values].mean()
    return building.mean(), group

def correlation(x,y):
    if len(x)<2 or np.std(x)<1e-10 or np.std(y)<1e-10:return np.nan
    return np.corrcoef(x,y)[0,1]

rows=[];gates=[]
for p in primary.itertuples():
    g=links[links.panel_id==p.panel_id].copy()
    good=g.B8L2_a.notna() & g.B8L2_b.notna()
    z=g[good]
    if len(z)<2: continue
    a=z.B8L2_a.to_numpy();b=z.B8L2_b.to_numpy()
    cells=z.groupby('structure_vector')[['B8L2_a','B8L2_b']].mean()
    ma=z.structure_vector.map(cells.B8L2_a).to_numpy();mb=z.structure_vector.map(cells.B8L2_b).to_numpy()
    ra=a-ma;rb=b-mb
    row={c:getattr(p,c) for c in meta}
    row.update(n_valid=len(z), rho=correlation(ma,mb), residual_rho=correlation(ra,rb),
        va=np.var(ma),vb=np.var(mb),cov=np.mean((ma-ma.mean())*(mb-mb.mean())),
        wva=np.mean(ra**2),wvb=np.mean(rb**2),wcov=np.mean(ra*rb),
        range_a=np.ptp(cells.B8L2_a),range_b=np.ptp(cells.B8L2_b))
    row['positive']=float(np.isfinite(row['rho']) and row['rho']>0)
    row['both_active']=row['range_a']>=2 and row['range_b']>=2
    rows.append(row)
    for side in ['a','b']:
        source=g[g['B8L2_'+side].notna()].groupby('structure_vector')['B8L2_'+side].mean()
        gates.append(dict(panel_id=p.panel_id,side=side,common_range=row['range_'+side],source_full_range=np.ptp(source),source_valid=int(g['B8L2_'+side].notna().sum()),joint_valid=len(z)))
mom=pd.DataFrame(rows)
values=['rho','residual_rho','positive','va','vb','cov','wva','wvb','wcov']
whole,group=aggregate(mom,values)
active= mom[mom.both_active]
act,_=aggregate(active,values)
gate=pd.DataFrame(gates)
changed=gate[(gate.common_range>=2)!=(gate.source_full_range>=2)]
mom.to_csv(ROOT/'INDEPENDENT_PRIMARY_MOMENTS.csv',index=False)
changed.to_csv(ROOT/'INDEPENDENT_SOURCE_GATE_CHANGES.csv',index=False)

# Original class capacities, without the experiment's cap of four.
cap=primary.copy()
cap['lo_capacity']=cap.lo_members_in_common.str.split('|').str.len()
cap['hi_capacity']=cap.hi_members_in_common.str.split('|').str.len()
cap['possible_pure_block']=cap[['lo_capacity','hi_capacity','n']].min(axis=1)
cap['possible_pure_block']=np.minimum(cap.possible_pure_block,cap.known_common_n-cap.n)
cap['selected_fraction_of_team']=cap.k_selected/cap.n
cap['selected_fraction_of_smaller_class']=cap.k_selected/cap[['lo_capacity','hi_capacity']].min(axis=1)
cap.to_csv(ROOT/'INDEPENDENT_BLOCK_CAPACITY.csv',index=False)

# Reconstruct actual replacement events, same timing-and-quality support.
times=read('results/time_transfer/TIMING_INPUT_RECORDS.csv.gz')
time_lookup={(r.pool_id,r.worker_id):(r.snapshot_source_time_seconds,str(r.time_source_kind)) for r in times.itertuples()}
time_rows=[]
for p in primary.itertuples():
    g=links[links.panel_id==p.panel_id].sort_values('selected_mask').reset_index(drop=True)
    masks=g.selected_mask.to_numpy(int);h=g.hi_selected.to_numpy(int)
    ii,jj=np.triu_indices(len(g),1); rev=h[jj]<h[ii]
    i=np.where(rev,jj,ii);j=np.where(rev,ii,jj)
    removed=masks[i]&~masks[j];added=masks[j]&~masks[i]
    m=np.array([int(x).bit_count() for x in removed]);r=h[j]-h[i]
    cand=p.candidates.split('|')
    for kind,select in [('pure_class_block',(m==1)&(r==1)),('same_composition',(m==1)&(r==0))]:
        qt=[];tt=[]
        for k in np.flatnonzero(select):
            old=[w for bit,w in enumerate(cand) if removed[k]&(1<<bit)]
            new=[w for bit,w in enumerate(cand) if added[k]&(1<<bit)]
            timing=[time_lookup[(pid,w)] for pid in [p.pool_id_a,p.pool_id_b] for w in old+new]
            if set(t[1] for t in timing)!={'user_processed_reported_not_raw_log_replayed'} or not all(np.isfinite(t[0]) and t[0]>0 for t in timing):continue
            dq=[g.iloc[j[k]]['B8L2_'+side]-g.iloc[i[k]]['B8L2_'+side] for side in ['a','b']]
            if not np.isfinite(dq).all():continue
            dt=[timing[1][0]-timing[0][0],timing[3][0]-timing[2][0]]
            qt.append(np.sign(dq[0])==np.sign(dq[1]));tt.append(np.sign(dt[0])==np.sign(dt[1]))
        if qt:time_rows.append({**{c:getattr(p,c) for c in meta},'kind':kind,'events':len(qt),'q_same_sign':np.mean(qt),'time_same_sign':np.mean(tt)})
tr=pd.DataFrame(time_rows)
tr.to_csv(ROOT/'INDEPENDENT_TIME_Q_M1.csv',index=False)
time_summary={}
for kind,g in tr.groupby('kind'):
    s,_=aggregate(g,['q_same_sign','time_same_sign'])
    time_summary[kind]={**s.to_dict(),'events':int(g.events.sum()),'panels':len(g)}

# Recompute before/after labor ratios from endpoint totals, then hierarchical means.
adds=read('results/budget/ADDITION_LINKS.csv.gz')
adds=adds[(adds.transition=='low_third__high_two_thirds') & (adds.added_n>0)].copy()
for side in ['a','b']:
    old=ep.loc[adds['team_before_'+side]];new=ep.loc[adds['team_after_'+side]]
    tm=(old.time_source_kinds.to_numpy()==new.time_source_kinds.to_numpy()) & (old.recorded_time_total_seconds.to_numpy()>0)
    rat=new.recorded_time_total_seconds.to_numpy()/old.recorded_time_total_seconds.to_numpy()
    adds['ratio_'+side]=np.where(tm,rat,np.nan)
    saved=adds['labor_ratio_'+side].to_numpy()
    assert np.allclose(adds['ratio_'+side],saved,equal_nan=True)
budget_rows=[]
for key,g in adds.groupby(['series_id','pair_key','building','groups']):
    a=np.r_[g.ratio_a,g.ratio_b];a=a[np.isfinite(a)]
    budget_rows.append(dict(zip(['series_id','pair_key','building','groups'],key))|{'ratio_arithmetic':a.mean() if len(a) else np.nan,'logratio':np.log(a).mean() if len(a) else np.nan})
bs,_=aggregate(pd.DataFrame(budget_rows),['ratio_arithmetic','logratio'])
summary={
 'endpoints':len(ep),'complete_evaluable':int(ep.complete_evaluable.sum()),'all_panels':len(panels),'primary_panels':len(primary),'primary_q_panels':len(mom),
 'group_positive':int((group.rho>0).sum()),'group_total':len(group),'positive_hierarchical':float(whole.positive),
 'active_panels':len(active),'active_positive_raw':int(active.positive.sum()),'active_positive_hierarchical':float(act.positive),
 'pooled_composition_rho':float(whole['cov']/np.sqrt(whole.va*whole.vb)),
 'pooled_member_rho':float(whole.wcov/np.sqrt(whole.wva*whole.wvb)),
 'gate_changed_rows':changed.to_dict('records'),
 'capacity_gt4_panels':int((cap.possible_pure_block>4).sum()),'capacity_gt4_pairs':int(cap.loc[cap.possible_pure_block>4,'pair_key'].nunique()),
 'capacity_max':int(cap.possible_pure_block.max()),'selected_fraction_quantiles':cap.selected_fraction_of_team.quantile([0,.25,.5,.75,1]).to_dict(),
 'selected_ge_half_panels':int((cap.selected_fraction_of_team>=.5).sum()),
 'full_smaller_class_replaced_panels':int((cap.selected_fraction_of_smaller_class==1).sum()),
 'time_quality':time_summary,'labor_ratio_arithmetic':float(bs.ratio_arithmetic),'labor_ratio_geometric':float(np.exp(bs.logratio))}
(ROOT/'INDEPENDENT_CHECKS.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
