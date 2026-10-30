"""Complete only missing current-candidate alliances using the frozen native engine."""
import os
for name in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:os.environ[name]='1'
import argparse,gzip,importlib.util,json,sys
from pathlib import Path
import pandas as pd
from tools.thesis_main.analysis.audit_v21_closeout_identity_20261030 import ROOT,SRC,members

OUT=ROOT/'research/data/releases/v2.1/closeout_20261030/alliance_completion_20261031'
REPO=SRC/'stage07_reproduction/minimum_source/repo'
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def write(name,obj):
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
def rows(path):
    with gzip.open(path,'rt',encoding='utf-8-sig') as f:
        for line in f:yield json.loads(line)
def prepare():
    OUT.mkdir(parents=True,exist_ok=True)
    adapter=module('ac_adapter',SRC/'stage02_engine/code/ac_endpoint_runtime.py')
    a=pd.read_csv(SRC/'stage01_capacity/ALL_CLASS_ALLIANCE_TEAMS.csv.gz');a=a[a.method.eq('TARGET_DSTRUCT_K3')].copy()
    change=pd.read_csv(OUT.parent/'ALLIANCE_414_TRACE.csv').set_index(['pool_id','classes'])
    requests=[]
    for r in a.itertuples():
        key=(r.pool_id,r.alliance_classes);new=change.loc[key,'new_members'] if key in change.index else r.members
        for version,ws in [('frozen',r.members),('updated',new)]:
            ws=sorted(members(ws));requests.append(dict(version=version,pool_id=r.pool_id,image=r.image,building=r.building,condition=r.condition,scope=r.scope,classes=r.alliance_classes,unknown_background_included=r.unknown_background_included,n=len(ws),members='|'.join(ws),reference_id=r.reference_id,reference_version=r.reference_version,team_key=adapter.team_key(r.pool_id,ws)))
    req=pd.DataFrame(requests);req.to_csv(OUT/'REQUESTS.csv',index=False)
    wanted=set(req.loc[req.n.ge(3),'team_key']);saved={}
    for pool,g in req[req.n.ge(3)].groupby('pool_id'):
        keys=set(g.team_key)
        for path in sorted((SRC/'stage03_endpoints/pools'/pool).glob('part_*.jsonl.gz')):
            for r in rows(path):
                if r['team_key'] in keys:saved[r['team_key']]=r
            if keys<=saved.keys():break
    with gzip.open(OUT/'REUSED_ENDPOINTS.jsonl.gz','wt',encoding='utf8') as f:
        for r in saved.values():f.write(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n')
    missing=wanted-saved.keys();scalar=[];sources=[]
    base=ROOT/'research/workers/personnel_v21_reselection_20261029'
    for p in sorted(base.rglob('ENDPOINT_SCALARS.csv.gz')):
        sources.append(str(p.relative_to(ROOT)))
        for chunk in pd.read_csv(p,chunksize=30000,low_memory=False):
            if 'team_key' not in chunk:continue
            for r in chunk[chunk.team_key.isin(missing)].to_dict('records'):
                request=req[req.team_key.eq(r['team_key'])].iloc[0]
                if r.get('reference_id')==request.reference_id and r.get('reference_version')==request.reference_version:
                    scalar.append({k:r.get(k) for k in ['team_key','B8L2','D10','IoU3D100','score_status']})
    pd.DataFrame(scalar,columns=['team_key','B8L2','D10','IoU3D100','score_status']).drop_duplicates().to_csv(OUT/'SCALAR_REPLAY_EXPECTATIONS.csv',index=False)
    missing_req=req[req.team_key.isin(missing)].drop_duplicates('team_key')
    missing_req.to_csv(OUT/'MISSING_TEAM_REQUESTS.csv',index=False)
    write('PREPARE_CHECKS.json',dict(request_rows=len(req),unique_scoreable_teams=len(wanted),reused_teams=len(saved),missing_teams=len(missing),scalar_cache_hits=len({r['team_key'] for r in scalar}),searched_scalar_sources=sources))
    print('prepared',len(saved),'reused;',len(missing),'require native geometry',flush=True)
def evaluate():
    sys.path.insert(0,str(REPO/'research/workers/personnel_v21_reselection_20261029/experiment'))
    from benchmark_engine import load_engine,numeric_geometry_difference
    native=load_engine(REPO)
    pools={p['pool_id']:p for part in ['pools/INPUT_SNAPSHOT.json','admitted_space_extension/pools/INPUT_SNAPSHOT.json'] for p in json.loads((REPO/'research/data/releases/v2.1'/part).read_text(encoding='utf8'))['images']}
    req=pd.read_csv(OUT/'MISSING_TEAM_REQUESTS.csv');expected=pd.read_csv(OUT/'SCALAR_REPLAY_EXPECTATIONS.csv')
    old_saved=list(rows(OUT/'REUSED_ENDPOINTS.jsonl.gz'));parity=[]
    # Validate this environment against one complete and one incomplete saved endpoint first.
    anchors=[]
    for complete in [True,False]:
        candidates=[r for r in old_saved if bool(r.get('complete_evaluable'))==complete]
        if candidates:anchors.append(candidates[0])
    def calc(engine,pool,ws):
        r=engine.evaluate(pool,ws);geometry=r.get('geometry')
        if geometry is not None:
            extra=engine.scorecache.get(engine.fr.digest([r['k']==2,r.get('nodes'),geometry]))
            if extra:r.update(extra)
        r.update(data_release='v2.1',underlying_data_version='v2.1',endpoint_origin='image_grade_alliance_completion_20261031',source_tree=str(REPO.relative_to(ROOT)),classification_finalized=False)
        return native.gs.clean(r)
    (OUT/'new_endpoints').mkdir(exist_ok=True)
    with native.Engine(full_state=False) as engine:
        for old in anchors:
            new=calc(engine,pools[old['pool_id']],old['member_workers'])
            diff=numeric_geometry_difference(old.get('geometry'),new.get('geometry'));assert diff<1e-8
            for field in ['B8L2','D10','IoU3D100']:
                a,b=old.get(field),new.get(field);assert (a is None)==(b is None)
                if a is not None:assert abs(a-b)<1e-7
            assert old.get('score_status')==new.get('score_status')
            parity.append(dict(team_key=old['team_key'],geometry_max_diff=diff,score_status=new.get('score_status')))
        write('ENGINE_PARITY.json',dict(passed=True,anchors=parity))
        for i,r in enumerate(req.itertuples()):
            path=OUT/'new_endpoints'/(r.team_key+'.json.gz')
            if path.exists():continue
            pool=pools[r.pool_id];ws=sorted(members(r.members))
            assert (pool['meta']['reference_id'],pool['meta']['reference_version'])==(r.reference_id,r.reference_version)
            new=calc(engine,pool,ws);assert new['team_key']==r.team_key
            for old in expected[expected.team_key.eq(r.team_key)].to_dict('records'):
                for field in ['B8L2','D10','IoU3D100']:
                    assert pd.isna(old[field])==(new.get(field) is None),(r.team_key,field)
                    if pd.notna(old[field]):assert abs(new[field]-old[field])<1e-7,(r.team_key,field)
            with gzip.open(path,'wt',encoding='utf8') as f:json.dump(new,f,ensure_ascii=False,allow_nan=False)
            if i%20==0:print('native teams',i+1,'/',len(req),flush=True)
    write('EVALUATION_CHECKS.json',dict(requested=len(req),completed=len(list((OUT/'new_endpoints').glob('*.json.gz'))),parity_passed=True,classification_finalized=False))
def summarize():
    endpoints={r['team_key']:r for r in rows(OUT/'REUSED_ENDPOINTS.jsonl.gz')}
    for p in (OUT/'new_endpoints').glob('*.json.gz'):
        with gzip.open(p,'rt',encoding='utf8') as f:r=json.load(f);endpoints[r['team_key']]=r
    req=pd.read_csv(OUT/'REQUESTS.csv');result=[]
    metrics=['B8L2','D10','IoU3D100','fusion_turn_n','fusion_short_turn_edges','boundary_loss','direction_loss','height_loss','omission','extension','source_time_total_seconds','recorded_time_total_seconds']
    for r in req.to_dict('records'):
        e=endpoints.get(r['team_key']);assert r['n']<3 or e is not None
        r.update({m:e.get(m) if e else None for m in metrics});r['complete_evaluable']=e.get('complete_evaluable') if e else None;r['status']='capacity_only' if e is None else e.get('score_status');result.append(r)
    d=pd.DataFrame(result);d.to_csv(OUT/'ALLIANCE_RESULTS.csv',index=False)
    trace=pd.read_csv(OUT.parent/'ALLIANCE_414_TRACE.csv')
    current=d[d.version.eq('updated')&~d.unknown_background_included]
    resolution=trace.merge(current[['pool_id','classes','team_key','status','B8L2']],on=['pool_id','classes'],how='left',validate='one_to_one')
    assert resolution.status.notna().all()
    resolution['resolved']=True;resolution.to_csv(OUT/'ALLIANCE_414_RESOLUTION.csv',index=False)
    strata=[]
    for keys,g in d.groupby(['version','scope','condition','unknown_background_included','classes']):
        base=dict(zip(['version','scope','condition','unknown_background_included','classes'],keys))
        for metric in metrics:
            im=g.groupby('image')[metric].mean().dropna()
            strata.append(dict(**base,metric=metric,registered_pools=len(g),eligible_pools=int(g.n.ge(3).sum()),valid_images=len(im),mean=im.mean()))
    pd.DataFrame(strata).to_csv(OUT/'CLASS_METRIC_SUMMARY.csv',index=False)
    pair=d.pivot(index=['pool_id','image','building','scope','condition','classes','unknown_background_included'],columns='version',values=metrics)
    pair.columns=['_'.join(c) for c in pair.columns]
    for m in metrics:pair[m+'_delta']=pair[m+'_updated']-pair[m+'_frozen']
    pair.reset_index().to_csv(OUT/'PAIRED_ALLIANCE_CHANGES.csv',index=False)
    comparisons=[]
    for (version,pool,unknown),g in d.groupby(['version','pool_id','unknown_background_included']):
        full=g.loc[g.n.idxmax()];pure=g[g.classes.isin(['C1','C2','C3'])&g.n.ge(3)]
        assert members(full.members)==set().union(*(members(v) for v in g.members))
        if pd.isna(full.B8L2) or pure.B8L2.notna().sum()==0:continue
        best=pure.B8L2.max()
        comparisons.append(dict(version=version,pool_id=pool,unknown_background_included=unknown,image=full.image,scope=full.scope,condition=full.condition,full_Q=full.B8L2,best_pure_Q=best,full_minus_best_pure=full.B8L2-best,scoreable_pure_classes=int(pure.B8L2.notna().sum())))
    c=pd.DataFrame(comparisons);c.to_csv(OUT/'FULL_VS_BEST_PURE.csv',index=False)
    both=c.pivot(index=['pool_id','image','scope','condition','unknown_background_included'],columns='version',values=['full_Q','best_pure_Q','full_minus_best_pure']).dropna();both.columns=['_'.join(x) for x in both.columns];both=both.reset_index();both.to_csv(OUT/'FULL_VS_BEST_PURE_COMMON.csv',index=False)
    stats=[]
    for (scope,condition,unknown),g in both.groupby(['scope','condition','unknown_background_included']):
        images=g.groupby('image').mean(numeric_only=True)
        for version in ['frozen','updated']:
            x=images['full_minus_best_pure_'+version]
            stats.append(dict(scope=scope,condition=condition,unknown_background_included=unknown,version=version,pools=len(g),images=len(images),mean_full_minus_best_pure=x.mean(),pure_better_images=int((x< -1e-8).sum()),full_better_images=int((x>1e-8).sum()),tied_images=int((x.abs()<=1e-8).sum())))
    pd.DataFrame(stats).to_csv(OUT/'FULL_VS_BEST_PURE_SUMMARY.csv',index=False)
    both[(both.full_minus_best_pure_frozen< -1e-8)!=(both.full_minus_best_pure_updated< -1e-8)].to_csv(OUT/'FULL_VS_PURE_DIRECTION_CHANGES.csv',index=False)
    write('SUMMARY_CHECKS.json',dict(request_rows=len(d),unique_endpoints=len(endpoints),capacity_only=int(d.status.eq('capacity_only').sum()),classification_finalized=False))
    print(pd.DataFrame(stats).to_string(index=False))
def verify():
    sys.path.insert(0,str(SRC/'code'))
    from reproduce_one_team import maximum_difference
    req=pd.read_csv(OUT/'MISSING_TEAM_REQUESTS.csv');expected=pd.read_csv(OUT/'SCALAR_REPLAY_EXPECTATIONS.csv')
    pools={p['pool_id']:p for part in ['pools/INPUT_SNAPSHOT.json','admitted_space_extension/pools/INPUT_SNAPSHOT.json'] for p in json.loads((REPO/'research/data/releases/v2.1'/part).read_text(encoding='utf8'))['images']}
    new={}
    for p in (OUT/'new_endpoints').glob('*.json.gz'):
        with gzip.open(p,'rt',encoding='utf8') as f:r=json.load(f)
        new[r['team_key']]=r
    assert set(new)==set(req.team_key)
    for r in req.itertuples():
        e=new[r.team_key];pool=pools[r.pool_id];by={v['worker_id']:v['object_id'] for v in pool['records']}
        assert set(e['member_workers'])==members(r.members)
        assert set(e['member_object_ids'])=={by[w] for w in members(r.members)}
        assert (e['reference_id'],e['reference_version'])==(r.reference_id,r.reference_version)
    for e in rows(OUT/'REUSED_ENDPOINTS.jsonl.gz'):
        pool=pools[e['pool_id']];by={v['worker_id']:v['object_id'] for v in pool['records']}
        assert set(e['member_object_ids'])=={by[w] for w in e['member_workers']}
        assert (e['reference_id'],e['reference_version'])==(pool['meta']['reference_id'],pool['meta']['reference_version'])
    for r in expected.to_dict('records'):
        e=new[r['team_key']]
        for field in ['B8L2','D10','IoU3D100']:
            assert pd.isna(r[field])==(e.get(field) is None)
            if pd.notna(r[field]):assert abs(r[field]-e[field])<1e-7
    key='q9vSo1VnCiC-15__manual__6d5ae69ee8__d77423a531f8204aab29'
    historical=None
    for r in rows(ROOT/'research/data/releases/v2.1/current_exchange_endpoints/REUSED_ENDPOINTS.jsonl.gz'):
        if r['team_key']==key:historical=r;break
    assert historical is not None
    diff=maximum_difference(historical['geometry'],new[key]['geometry']);assert diff<1e-8
    assert abs(historical['B8L2']-new[key]['B8L2'])<1e-7
    d=pd.read_csv(OUT/'ALLIANCE_RESULTS.csv')
    unchanged=d.pivot(index=['pool_id','classes','unknown_background_included'],columns='version',values=['team_key','B8L2'])
    z=unchanged[unchanged[('team_key','frozen')].eq(unchanged[('team_key','updated')])]
    assert z[('B8L2','frozen')].fillna(-999).eq(z[('B8L2','updated')].fillna(-999)).all()
    write('VERIFICATION.json',dict(passed=True,completed_native_requests=len(new),frozen_baseline_requests=int(req.version.eq('frozen').sum()),updated_requests=int(req.version.eq('updated').sum()),saved_scalar_teams_checked=expected.team_key.nunique(),historical_endpoint_geometry_max_diff=diff,historical_endpoint_contract_resolved_by_replay=True,unchanged_alliance_rows=len(z),manual_review_required=False))
def figures():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'DejaVu Sans','pdf.fonttype':42,'svg.fonttype':'none'})
    d=pd.read_csv(OUT/'FULL_VS_BEST_PURE_COMMON.csv');d=d[d.scope.eq('primary')&~d.unknown_background_included]
    fig,ax=plt.subplots(figsize=(7,6),layout='constrained')
    ax.scatter(d.full_minus_best_pure_frozen,d.full_minus_best_pure_updated,s=18,alpha=.65,color='#236b83')
    ax.axhline(0,color='black',lw=.7);ax.axvline(0,color='black',lw=.7)
    lo=min(d.full_minus_best_pure_frozen.min(),d.full_minus_best_pure_updated.min())-2;hi=max(d.full_minus_best_pure_frozen.max(),d.full_minus_best_pure_updated.max())+2
    ax.plot([lo,hi],[lo,hi],'--',color='gray',lw=1)
    ax.set(xlim=(lo,hi),ylim=(lo,hi),xlabel='Frozen labels: all-class minus best pure-class Q (points)',ylabel='Updated labels: all-class minus best pure-class Q (points)',title='Quality of all-class teams relative to the best pure-class team\nunder frozen and updated TARGET K3 labels (205 images)')
    for ext in ['png','pdf','svg']:fig.savefig(OUT/('ALL_CLASS_VS_PURE.'+ext),dpi=300,bbox_inches='tight')
    plt.close(fig)
    (OUT/'FIGURE.html').write_text('<!doctype html><meta charset="utf-8"><title>All-class versus pure-class quality</title><style>body{font:17px sans-serif;max-width:1050px;margin:30px auto}img{width:100%}</style><h1>Complete-alliance comparison after updating candidate labels</h1><img src="ALL_CLASS_VS_PURE.png"><p>Primary Manual targets; 205 common scoreable images. Negative values favor the best scoreable pure-class team (at least three members). This is a retrospective comparison, not a deployable selection policy. Class capacity and pure-team membership can change; all-class membership does not. Unknown-background variants and other targets are reported separately. No uncertainty interval is implied.</p><p><a href="FULL_VS_BEST_PURE_COMMON.csv">Source rows</a> | <a href="ALL_CLASS_VS_PURE.pdf">PDF</a> | <a href="ALL_CLASS_VS_PURE.svg">SVG</a></p>',encoding='utf8')
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['prepare','evaluate','summarize','verify','figures']);args=ap.parse_args();globals()[args.stage]()
