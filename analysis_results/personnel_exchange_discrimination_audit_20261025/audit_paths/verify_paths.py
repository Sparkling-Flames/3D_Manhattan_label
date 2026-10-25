"""Independent arithmetic/member audit of saved paths; does not run fusion."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
B = ROOT / 'unpacked'
OUT = Path(__file__).resolve().parent
checks = {}

def read(path):
    return pd.read_csv(B/path, low_memory=False)

def members(x):
    return set() if pd.isna(x) else set(x.split('|'))

def equal(a,b,tag):
    aa=np.asarray(a,dtype=float);bb=np.asarray(b,dtype=float)
    assert np.allclose(aa,bb,rtol=1e-10,atol=1e-8,equal_nan=True),tag

def audit_sets(d,arms='ABC'):
    assert not d.event_id.duplicated().any()
    for r in d.itertuples(index=False):
        ds=members(r.D);blocks=[members(getattr(r,k)) for k in ('XYZ' if arms=='ABC' else 'XZ')]
        assert len(ds)==r.n-r.m
        assert all(len(x)==r.m for x in blocks)
        assert len(set.union(ds,*blocks))==len(ds)+sum(map(len,blocks))
        for arm,x in zip(arms,blocks):
            assert members(getattr(r,arm+'_members'))==ds|x
        if arms=='ABC':assert r.A_class_vector==r.B_class_vector

def arithmetic(d,arms='ABC'):
    ms=[c[2:] for c in d if c.startswith('A_') and c[2:]+'_CA' in d and 'C_'+c[2:] in d]
    for m in ms:
        a=pd.to_numeric(d['A_'+m]);c=pd.to_numeric(d['C_'+m])
        equal(c-a,d[m+'_CA'],m+' CA')
        if arms=='ABC':
            b=pd.to_numeric(d['B_'+m]);valid=a.notna()&b.notna()&c.notna()
            w=(b-a).abs().where(valid);x=((c-a).abs()+(c-b).abs()).div(2).where(valid)
            for key,v in [('BA',b-a),('CB',c-b),('within',w),('cross',x),('gap',x-w)]:equal(v,d[m+'_'+key],m+key)
    for arm in arms:assert d[arm+'_failed'].eq(d[arm+'_B8L2'].isna()).all()
    return len(ms)

size=read('05/design/size_paths/EVENTS_EXACT.csv.gz');sm=read('05/results/size_paths/EVENT_METRICS.csv.gz')
assert set(size.event_id)==set(sm.event_id)
audit_sets(size)
for pid,g in size.groupby('path_id'):
    g=g.sort_values('n');assert g.X.nunique()==g.Y.nunique()==g.Z.nunique()==1
    assert g.n.tolist()==list(range(10,int(g.pool_n.iloc[0])-13))
    old=None
    for r in g.itertuples(index=False):
        assert r.m==7 and r.nominal_minimum_support==(r.n+1)//2
        if old:
            for arm in 'ABC':assert members(getattr(r,arm+'_members'))-members(getattr(old,arm+'_members'))=={r.entrant_worker}
            assert members(r.D)-members(old.D)=={r.entrant_worker}
        old=r
checks['size_design']={'events':len(size),'paths':size.path_id.nunique(),'images':size.image.nunique(),'buildings':size.building.nunique(),'n_min':int(size.n.min()),'n_max':int(size.n.max()),'arithmetic_metrics':arithmetic(sm)}
sc=read('05/results/size_paths/NATIVE_ENDPOINT_SCALARS.csv.gz').set_index('team_key')
for arm in 'ABC':
    linked=sc.loc[sm[arm+'_team_key']].reset_index(drop=True)
    assert linked.member_workers.map(members).eq(sm[arm+'_members'].map(members)).all()
    for col in ['B8L2','D10','nodes','iou_2d','IoU3D100','source_time_total_seconds']:equal(linked[col],sm[arm+'_'+col],arm+col)
checks['size_scalar_link_rows']=len(sc)

# Rebuild all per-image curves directly, without calling the author's reducers.
saved=read('05/analysis/size_paths/CURVE_BY_IMAGE.csv.gz')
keys=['cohort','method','phase','pool_id','image','building','difficulty','n']
cols=[c for c in saved if c in sm and c not in keys and pd.api.types.is_numeric_dtype(sm[c])]
parts=[]
for co,cap in [('all_available',None),('fixed_capacity_n20',20),('fixed_capacity_n21',21)]:
    d=sm.copy() if cap is None else sm[(sm.pool_n-14>=cap)&(sm.n<=cap)].copy()
    d['cohort']=co;parts.append(d)
curves=pd.concat(parts).groupby(keys,dropna=False)[cols].mean().sort_index()
sv=saved.set_index(keys).sort_index()
assert curves.index.equals(sv.index)
equal(curves[cols],sv[cols],'all size per-image curves')
checks['size_curve_rows_columns']=[len(curves),len(cols)]

summary=[]
for phase in ['ALL_PHASES','selection_heldout_building']:
 for method in sorted(sm.method.unique()):
  for n in [10,14,20,21]:
   d=sm[(sm.pool_n==35)&(sm.method==method)&(sm.n==n)]
   if phase!='ALL_PHASES':d=d[d.phase==phase]
   p=d.groupby(['image','building'])[['B8L2_within','B8L2_cross','B8L2_gap','B8L2_CA','B8L2_CB']].mean()
   bu=p.groupby('building').mean()
   summary.append(dict(method=method,phase=phase,n=n,events=len(d),images=d.image.nunique(),within=p.B8L2_within.mean(),cross=p.B8L2_cross.mean(),CA=p.B8L2_CA.mean(),CB=p.B8L2_CB.mean(),gap_positive_images=int(p.B8L2_gap.gt(0).sum()),gap_valid_images=int(p.B8L2_gap.notna().sum()),gap_positive_buildings=int(bu.B8L2_gap.gt(0).sum()),gap_valid_buildings=int(bu.B8L2_gap.notna().sum()),A_failed=int(d.A_failed.sum()),B_failed=int(d.B_failed.sum()),C_failed=int(d.C_failed.sum())))
summary=pd.DataFrame(summary);summary.to_csv(OUT/'SIZE_FIXED_N21_RECALCULATED.csv',index=False,encoding='utf-8-sig')
for file,ph in [('KEY_FIXED_N21_ALL_PHASES.csv','ALL_PHASES'),('KEY_FIXED_N21_HELDOUT_BUILDINGS.csv','selection_heldout_building')]:
 for r in read('05/analysis/size_paths/'+file).to_dict('records'):
  v=summary[(summary.method==r['方法'])&(summary.phase==ph)&(summary.n==r['n'])].iloc[0]
  for name,k in [('C−A','CA'),('C−B','CB'),('同类幅度','within'),('跨类幅度','cross')]:equal(r[name],v[k],file+name)
  assert r['跨幅更大图/楼']==f"{v.gap_positive_images}/{v.gap_valid_images}; {v.gap_positive_buildings}/{v.gap_valid_buildings}"
failures=read('05/analysis/size_paths/KEY_FAILURE_AND_LARGE_LOSS_COUNTS.csv')
for r in failures.itertuples(index=False):
 d=sm[(sm.pool_n==35)&(sm.method==r.method)&(sm.n==r.n)]
 if r.phase!='ALL_PHASES':d=d[d.phase==r.phase]
 assert len(d)==r.paths
 for arm in 'ABC':assert int(d[arm+'_failed'].sum())==getattr(r,arm+'_failed')
 for arm in 'AB':
  comp='C'+arm;valid=d[arm+'_B8L2'].notna();risk=d.C_failed|(d.C_B8L2-d[arm+'_B8L2'] < -10)
  assert int((risk&valid).sum())==getattr(r,'C_failure_or_loss10_'+comp+'_events')
  assert int(valid.sum())==getattr(r,'C_failure_or_loss10_'+comp+'_valid_events')
checks['size_failure_summary_rows']=len(failures)

# Large-team AC deliberately has no B arm.
ac=read('05/design/large_team_ac_tail/EVENTS_EXACT.csv.gz');am=read('05/results/large_team_ac_tail/EVENT_METRICS.csv.gz')
audit_sets(ac,'AC');assert set(ac.event_id)==set(am.event_id)
assert 'B_team_key' not in ac and not ac.same_class_B_control_available.any()
tail=size.set_index('event_id')
for pid,g in ac.groupby('path_id'):
 g=g.sort_values('n');assert g.tail_step.tolist()==list(range(8))
 assert g.X.nunique()==g.Z.nunique()==1
 first=g.iloc[0];oldtail=tail.loc[first.strict_tail_event_id]
 assert first.A_team_key==oldtail.A_team_key and first.C_team_key==oldtail.C_team_key
 assert first.n==first.pool_n-14 and g.iloc[-1].n==first.pool_n-7
 assert members(g.iloc[-1].D)-members(first.D)==members(first.original_Y7)
 for i in range(1,len(g)):
  for arm in 'AC':assert members(g.iloc[i][arm+'_members'])-members(g.iloc[i-1][arm+'_members'])=={g.iloc[i].entrant_worker}
checks['ac_design']={'events':len(ac),'paths':ac.path_id.nunique(),'n_max':int(ac.n.max()),'arithmetic_metrics':arithmetic(am,'AC')}
rows=[]
for phase in ['ALL_PHASES','selection_heldout_building']:
 for method in sorted(am.method.unique()):
  for n in range(21,29):
   d=am[(am.pool_n==35)&(am.method==method)&(am.n==n)]
   if phase!='ALL_PHASES':d=d[d.phase==phase]
   vals=(d.C_B8L2-d.A_B8L2).rename('CA');x=d[['image','building']].join(vals).groupby(['image','building']).CA.mean();bu=x.groupby('building').mean()
   rows.append(dict(method=method,phase=phase,n=n,CA=x.mean(),valid_images=x.notna().sum(),positive_images=x.gt(0).sum(),valid_buildings=bu.notna().sum(),positive_buildings=bu.gt(0).sum(),events=len(d),A_failed=d.A_failed.sum(),C_failed=d.C_failed.sum()))
ar=pd.DataFrame(rows);ar.to_csv(OUT/'AC_FIXED_N35_RECALCULATED.csv',index=False,encoding='utf-8-sig')
savedac=read('05/analysis/large_team_ac_tail/KEY_N35_AC_CONDITIONS.csv')
for r in savedac.to_dict('records'):
 v=ar[(ar.method==r['method'])&(ar.phase==r['phase'])&(ar.n==r['n'])].iloc[0]
 equal(r['B8L2_CA'],v.CA,'AC CA')
 for k in ['images','buildings']:assert r['positive_'+k+'/valid_'+k]==f"{v['positive_'+k]}/{v['valid_'+k]}"
checks['ac_key_rows']=len(savedac)

# Target leave-one-out: the original A is fixed, all seven target omissions exist.
om=read('04A1/results/target_omissions/EVENT_METRICS.csv.gz');audit_sets(om);arithmetic(om)
parents=sm[sm.n==10].set_index('parent_event_id')
assert not parents.index.duplicated().any()
rows=[]
for aid,g in om.groupby('anchor_id'):
 assert len(g)==7 and g.Z_omitted_worker.nunique()==7
 p=parents.loc[g.paired_m7_event_id.iloc[0]]
 assert set(g.Z_omitted_worker)==members(p.Z)
 for r in g.itertuples(index=False):
  assert r.A_team_key==p.A_team_key and members(r.A_members)==members(p.A_members)
  assert members(r.Z)==members(p.Z)-{r.Z_omitted_worker}
  assert members(r.D)==members(p.D)|{r.x_retained_in_D}
  assert members(r.X)==members(p.X)-{r.x_retained_in_D}
  assert members(r.Y)==members(p.Y)-{r.y_removed_from_B}
  assert r.n==10 and r.m==6
 cb=g.C_B8L2-g.B_B8L2;valid=cb.notna().sum()==7
 risk=g.C_failed|((p.C_B8L2-g.C_B8L2)>10);riskvalid=pd.notna(p.C_B8L2)
 common=g.C_B8L2.notna()&g.B_B8L2.notna()&pd.notna(p.C_B8L2)&pd.notna(p.B_B8L2)
 rows.append(dict(anchor_id=aid,method=g.method.iloc[0],phase=g.phase.iloc[0],image=g.image.iloc[0],building=g.building.iloc[0],complete_CB=valid,all_positive=bool(valid and cb.gt(0).all()),majority_positive=bool(valid and cb.gt(0).sum()>=4),risk_complete=riskvalid,no_risk=bool(riskvalid and not risk.any()),C7_minus_C6=(p.C_B8L2-g.C_B8L2).where(common).mean(),B7_minus_B6=(p.B_B8L2-g.B_B8L2).where(common).mean()))
ob=pd.DataFrame(rows);ob.to_csv(OUT/'OMISSION_ANCHORS_RECALCULATED.csv',index=False,encoding='utf-8-sig')
os=[]
for method,g in ob[ob.phase=='selection_heldout_building'].groupby('method'):
 pi=g.groupby('image')[['C7_minus_C6','B7_minus_B6']].mean()
 os.append(dict(method=method,anchors=len(g),complete_CB=int(g.complete_CB.sum()),all_positive=int(g.all_positive.sum()),majority_positive=int(g.majority_positive.sum()),risk_complete=int(g.risk_complete.sum()),no_risk=int(g.no_risk.sum()),C7_minus_C6=pi.C7_minus_C6.mean(),B7_minus_B6=pi.B7_minus_B6.mean(),net=pi.C7_minus_C6.mean()-pi.B7_minus_B6.mean()))
pd.DataFrame(os).to_csv(OUT/'OMISSION_HELDOUT_RECALCULATED.csv',index=False,encoding='utf-8-sig');checks['omissions']=os
checks['omission_design']={'events':len(om),'anchors':len(ob),'images':om.image.nunique()}
(OUT/'CHECKS.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2,default=int),encoding='utf8')
print(json.dumps(checks,ensure_ascii=False,indent=2,default=int))
