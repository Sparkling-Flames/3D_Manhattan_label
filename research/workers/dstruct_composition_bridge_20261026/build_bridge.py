"""Frozen-team composition bridge; no fusion, scoring, or classifier fitting.
Run from any directory: python research/workers/dstruct_composition_bridge_20261026/build_bridge.py
Dependencies: Python 3, numpy, pandas. Input paths are repository-relative.
"""
from pathlib import Path
import json
from collections import Counter
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
C=ROOT/'research/workers/personnel_mixture_comparison_20261022/configurations'
LABELS=ROOT/'research/workers/personnel_classification_guide_20261025/sources/NEW_METHOD_LABELS_ALL_LOBO.csv.gz'
METRICS=['B8L2','D10','fusion_turn_n','log_recorded_time','not_complete_evaluable']
METHODS=['DSTRUCT_K2','DSTRUCT_K3','OLD_STRUCTURE_COARSE','OLD_STRUCTURE_FINE']

def decompose(values,configuration):
    f=pd.DataFrame({'y':values,'c':configuration}).dropna(subset=['y'])
    if not len(f): return dict(valid_teams=0,configurations=0,singleton_configurations=0,total_variance=np.nan,within_variance=np.nan,between_variance=np.nan,between_share=np.nan)
    means=f.groupby('c').y.transform('mean');mu=f.y.mean()
    total=float(((f.y-mu)**2).mean())
    within=float(((f.y-means)**2).mean())
    between=float(((means-mu)**2).mean())
    return dict(valid_teams=len(f),configurations=f.c.nunique(),singleton_configurations=int((f.groupby('c').size()==1).sum()),total_variance=total,within_variance=within,between_variance=between,between_share=between/total if total>1e-12 else np.nan)

def macro(rows):
    fields=['total_variance','within_variance','between_variance']
    out=[]
    scopes=[('all','all',rows)]+[('difficulty',k,g) for k,g in rows.groupby('difficulty')]+[('n',str(k),g) for k,g in rows.groupby('n')]+[('source_domain',k,g) for k,g in rows.groupby('source_domain')]
    for scope,value,frame in scopes:
      for (method,metric),g in frame.groupby(['method','metric']):
        valid=g.dropna(subset=['total_variance'])
        b=valid.groupby(['building','image'])[fields].mean().groupby('building').mean()
        vals=b.mean().to_dict();total=vals['total_variance']
        out.append(dict(scope=scope,value=value,method=method,metric=metric,panels=valid.panel_id.nunique(),images=valid.image.nunique(),buildings=len(b),valid_team_links=int(valid.valid_teams.sum()),**vals,between_share=vals['between_variance']/total if total>1e-12 else np.nan,constant_panels=int((valid.total_variance<=1e-12).sum()),singleton_configurations=int(valid.singleton_configurations.sum())))
    return pd.DataFrame(out)

def run():
    panels=pd.read_csv(C/'PANELS_USED.csv');panels=panels[panels.condition=='manual'].copy()
    links=pd.read_csv(C/'PANEL_TEAMS.csv.gz');links=links[links.panel_id.isin(panels.panel_id)].copy()
    members=pd.read_csv(C/'TEAM_MEMBERS.csv.gz');members=members[members.condition=='manual'].set_index('team_key')
    end=pd.read_csv(C/'ENDPOINT_OUTCOMES_manual.csv.gz').set_index('team_key')
    assert members.index.is_unique and end.index.is_unique
    assert not links.duplicated(['panel_id','team_key']).any()
    assert links.groupby('panel_id').size().eq(924).all()
    end['log_recorded_time']=np.log(end.recorded_time_total_seconds.where(end.recorded_time_eligible & (end.recorded_time_total_seconds>0)))
    end['not_complete_evaluable']=(~end.complete_evaluable).astype(float)
    labels=pd.read_csv(LABELS);old=pd.read_csv(C/'LOBO_LABELS_USED.csv.gz')
    maps={}
    for method in METHODS:
      if method.startswith('DSTRUCT'):
        f=labels[(labels.method==method)&labels.known&labels.heldout_building.ne('ALL')];col='class_id'
      else:
        f=old[(old.condition=='manual')&(old.method=='V3_BEHAVIOR')&old.known];col='fine_label' if method.endswith('FINE') else 'coarse_label'
      assert not f.duplicated(['heldout_building','worker_id']).any()
      maps[method]={(b,w):str(c) for b,w,c in f[['heldout_building','worker_id',col]].itertuples(index=False,name=None)}
    nested=[]
    for b in panels.building.unique():
      pairs={(maps['DSTRUCT_K3'][(b,w)],maps['DSTRUCT_K2'][(b,w)]) for bb,w in maps['DSTRUCT_K3'] if bb==b}
      assert all(len({k2 for k3,k2 in pairs if k3==c})==1 for c in {x[0] for x in pairs})
      nested.extend(dict(building=b,k3=k3,k2=k2) for k3,k2 in sorted(pairs))
    cover=[];decomps=[];configs=[];team_vectors=[]
    for panel in panels.itertuples():
      pp=links[links.panel_id==panel.panel_id]
      keys=pp.team_key.tolist();ys=end.loc[keys].copy();ms=members.loc[keys]
      assert ys.image.eq(panel.image).all() and ys.building.eq(panel.building).all() and ys.k.eq(panel.n).all()
      for wr,sel in zip(ms.member_workers,pp.selected_variable_workers):
        assert set(wr.split('|'))==set(panel.background_workers.split('|'))|set(sel.split('|'))
        assert len(wr.split('|'))==panel.n
      shared=np.ones(len(keys),dtype=bool);vectors={}
      for method in METHODS:
        lm=maps[method];classes=sorted({v for (b,w),v in lm.items() if b==panel.building})
        vs=[];known=[];missing=set()
        for wr in ms.member_workers:
          ws=wr.split('|');absent=[w for w in ws if (panel.building,w) not in lm];missing.update(absent)
          known.append(not absent)
          count=Counter(lm[(panel.building,w)] for w in ws if (panel.building,w) in lm)
          vs.append('|'.join(f'{c}:{count[c]}' for c in classes) if not absent else None)
        shared &= np.array(known)
        vectors[method]=vs
        cover.append(dict(panel_id=panel.panel_id,image=panel.image,building=panel.building,n=panel.n,method=method,teams=len(keys),label_known_teams=sum(known),unknown_teams=len(keys)-sum(known),missing_workers='|'.join(sorted(missing))))
      # Comparison support is explicit, shared by all four methods, and checked.
      meta={k:getattr(panel,k) for k in ['panel_id','image','building','n','difficulty','source_domain']}
      for method in METHODS:
        vec=np.asarray(vectors[method],dtype=object)[shared];z=ys.iloc[np.flatnonzero(shared)]
        for key,v in zip(z.index,vec):team_vectors.append(dict(panel_id=panel.panel_id,team_key=key,method=method,class_counts=v))
        for metric in METRICS:
          vals=z[metric].to_numpy(dtype=float)
          r=decompose(vals,vec);decomps.append(dict(**meta,method=method,metric=metric,teams=len(z),**r))
          for v in sorted(set(vec)):
            sel=vec==v;y=vals[sel];y=y[np.isfinite(y)];count=len(y)
            q=np.quantile(y,[.05,.25,.5,.75,.95]) if count else [np.nan]*5
            configs.append(dict(**meta,method=method,metric=metric,class_counts=v,teams=int(sel.sum()),valid_teams=count,missing_teams=int(sel.sum())-count,mean=float(np.mean(y)) if count else np.nan,p05=q[0],p25=q[1],median=q[2],p75=q[3],p95=q[4],sd=float(np.std(y,ddof=0)) if count>1 else np.nan,member_variation_estimable=count>1))
    d=pd.DataFrame(decomps);cov=pd.DataFrame(cover);cg=pd.DataFrame(configs)
    assert cov.unknown_teams.eq(0).all()
    assert np.allclose(d.total_variance,d.within_variance+d.between_variance,atol=1e-10,equal_nan=True)
    pivot=d.pivot(index=['panel_id','metric'],columns='method',values='between_variance')
    delta=pivot.DSTRUCT_K3-pivot.DSTRUCT_K2
    assert delta.dropna().ge(-1e-9).all()
    # Independently reconstruct previously saved new_coarse/new_fine endpoint variances.
    historical=pd.read_csv(ROOT/'research/workers/personnel_mixture_audit_20261022/source_response/manual/geometry_common/PANEL_CONFIGURATION_DECOMPOSITION.csv.gz')
    hist=historical[historical.method.isin(['new_coarse','new_fine']) & historical.outcome.isin(['B8L2','D10'])].copy()
    hist['method']=hist.method.map({'new_coarse':'OLD_STRUCTURE_COARSE','new_fine':'OLD_STRUCTURE_FINE'})
    checks=d.merge(hist,on=['panel_id','method'],suffixes=('','_historic'))
    checks=checks[checks.metric==checks.outcome]
    errors={a:float(np.max(np.abs(checks[a]-checks[b]))) for a,b in [('total_variance','total_variance_historic'),('within_variance','within_configuration_variance'),('between_variance','between_configuration_variance')]}
    assert max(errors.values())<1e-8
    for name,frame in [('PANEL_COVERAGE.csv',cov),('FOLD_NESTING.csv',pd.DataFrame(nested)),('PANEL_VARIANCE.csv',d),('SUMMARY.csv',macro(d)),('CONFIGURATIONS.csv',cg)]:frame.to_csv(HERE/name,index=False)
    for method, frame in pd.DataFrame(team_vectors).groupby('method'):
        frame.to_csv(HERE/f'TEAM_CONFIGURATION_LINKS_{method}.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    status=end.loc[links.team_key.unique()].groupby(['complete_evaluable','score_status','geometry_status'],dropna=False).size().reset_index(name='unique_endpoints')
    status.to_csv(HERE/'ENDPOINT_STATUS.csv',index=False)
    audit=dict(source_ref='f4f8903798279291ad0e8e461d107e824892ce81',condition='manual',panels=len(panels),images=panels.image.nunique(),buildings=panels.building.nunique(),team_links=len(links),unique_endpoints=links.team_key.nunique(),unknown_label_team_links=int(cov.unknown_teams.sum()),not_complete_evaluable_links=int((~end.loc[links.team_key].complete_evaluable).sum()),historical_q_d10_rows_compared=len(checks),historical_max_abs_errors=errors,nested_folds=len(set(x['building'] for x in nested)),nested_monotonicity_min=float(delta.min()),variance_identity_max_error=float((d.total_variance-d.within_variance-d.between_variance).abs().max()),new_fusions=0,new_classifications=0,new_scores=0)
    (HERE/'CHECKS.json').write_text(json.dumps(audit,indent=2)+'\n');print(json.dumps(audit,indent=2));print(macro(d).query('scope=="all"').to_string(index=False))
if __name__=='__main__':run()
