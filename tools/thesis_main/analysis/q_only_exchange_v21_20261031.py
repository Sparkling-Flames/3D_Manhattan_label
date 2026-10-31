"""Outcome-blind Q-only exchange design and frozen-engine evaluation."""
import os
for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
import argparse,gzip,json,sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import maximum_bipartite_matching
from tools.thesis_main.analysis.complete_v21_alliances_20261031 import ROOT,SRC,REPO,module,rows,members

OUT=ROOT/'research/data/releases/v2.1/q_only_exchange_20261031'
UP=ROOT/'research/data/releases/v2.1/admitted_space_extension/image_difficulty_20261030'
def write(name,obj):
    p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
def csv(name,d):d.to_csv(OUT/name,index=False,encoding='utf-8-sig')
def aggregate(d,column):
    return d.groupby(['worker_id','building','image_id','reference_id'])[column].mean().groupby(level=['worker_id','building','image_id']).mean().groupby(level=['worker_id','building']).mean().groupby(level='worker_id').mean()
def choose(candidates,history,column,m):
    return sorted(candidates,key=lambda w:(-float(history.loc[w,column]),w))[:m]
def design():
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'DESIGN.json').exists():raise FileExistsError('Design already frozen; use existing requests')
    e=pd.read_csv(UP/'HALF_EVENT_LEGALITY.csv.gz',low_memory=False);e=e[e.updated_class_legal].copy()
    assert e.groupby('n').size().to_dict()=={14:147,20:61}
    raw=pd.read_csv(UP/'classification/RAW_TARGET_RESPONSE_RECORDS.csv.gz',low_memory=False)
    raw=raw[raw.history_eligible&raw.condition.eq('manual')].copy()
    lab=pd.read_csv(UP/'classification/LABELS_ALL_LOBO.csv.gz');lab=lab[lab.method.eq('TARGET_DSTRUCT_K3')]
    h=[]
    for fold in sorted(e.building.unique()):
        d=raw[raw.building.ne(fold)].dropna(subset=['B8L2','B8L2_peer'])
        x=d.groupby('worker_id').agg(q_images=('image_id','nunique'),q_buildings=('building','nunique'))
        x['raw_q']=aggregate(d,'B8L2');x['peer_q']=aggregate(d,'B8L2_peer');x['heldout_building']=fold
        x=x.reset_index().merge(lab[lab.heldout_building.eq(fold)][['worker_id','known','class_id']],on='worker_id',how='left',validate='one_to_one');h.append(x)
    history=pd.concat(h,ignore_index=True);csv('HISTORY_LOBO.csv',history);csv('LABEL_SNAPSHOT.csv',lab)
    pools={p['pool_id']:p for part in ['pools/INPUT_SNAPSHOT.json','admitted_space_extension/pools/INPUT_SNAPSHOT.json'] for p in json.loads((REPO/'research/data/releases/v2.1'/part).read_text(encoding='utf8'))['images']}
    adapter=module('q_adapter',SRC/'stage02_engine/code/ac_endpoint_runtime.py');requests=[];designs=[];candidates=[];support=[];overlap=[]
    for r in e.to_dict('records'):
        pool=pools[r['pool_id']];hist=history[history.heldout_building.eq(r['building'])].set_index('worker_id')
        D,X,Y,Z=[members(r[k]) for k in ['D','X','Y','Z']];assert not any(a&b for i,a in enumerate([D,X,Y,Z]) for b in [D,X,Y,Z][i+1:])
        legal={v['worker_id'] for v in pool['records']}-D-X-Y
        valid={w for w in legal if w in hist.index and bool(hist.loc[w,'known']) and hist.loc[w,'q_images']>=12 and hist.loc[w,'q_buildings']>=3 and pd.notna(hist.loc[w,'raw_q']) and pd.notna(hist.loc[w,'peer_q'])}
        ok=len(valid)>=r['m'] and Z<=valid
        support.append(dict(event_id=r['event_id'],n=r['n'],image=r['image'],building=r['building'],pool_id=r['pool_id'],candidate_n=len(valid),Z_eligible=Z<=valid,eligible=ok))
        if not ok:continue
        for field in ['reference_id','reference_version']:
            if pd.notna(r[field]):assert pool['meta'][field]==r[field]
            r[field]=pool['meta'][field]
        for w in sorted(valid):candidates.append(dict(event_id=r['event_id'],worker_id=w,class_id=hist.loc[w,'class_id'],raw_q=hist.loc[w,'raw_q'],peer_q=hist.loc[w,'peer_q']))
        c2=sorted(w for w in valid if hist.loc[w,'class_id']=='C2');c3=sorted(w for w in valid if hist.loc[w,'class_id']=='C3')
        matches=0
        if c2 and c3:
            adj=np.abs(hist.loc[c2,'raw_q'].to_numpy()[:,None]-hist.loc[c3,'raw_q'].to_numpy()[None,:])<=3
            matches=int((maximum_bipartite_matching(csr_matrix(adj),perm_type='column')>=0).sum())
        overlap.append(dict(event_id=r['event_id'],n=r['n'],image=r['image'],building=r['building'],C2_candidates=len(c2),C3_candidates=len(c3),matched_people_caliper3=matches,can_match_seven=matches>=7))
        for policy,ws in [('A',sorted(D|X)),('B',sorted(D|Y)),('STRUCTURE',sorted(D|Z)),('Q_RAW',sorted(D|set(choose(valid,hist,'raw_q',r['m'])))),('Q_PEER',sorted(D|set(choose(valid,hist,'peer_q',r['m']))))]:
            assert len(ws)==r['n']
            if policy not in ['A','B']:assert len(set(ws)-D)==r['m'] and not (set(ws)-D)&(X|Y)
            key=adapter.team_key(r['pool_id'],ws)
            requests.append(dict(team_key=key,pool_id=r['pool_id'],members='|'.join(ws),reference_id=r['reference_id'],reference_version=r['reference_version'],n=r['n']))
            z={k:r[k] for k in ['event_id','image','building','pool_id','n','m','block_id','background_id','difficulty','D','X','Y','Z']}
            z.update(policy=policy,team_key=key,incoming_members='|'.join(sorted(set(ws)-D)),incoming_raw_q=float(hist.loc[sorted(set(ws)-D),'raw_q'].mean()),incoming_peer_q=float(hist.loc[sorted(set(ws)-D),'peer_q'].mean()));designs.append(z)
    csv('SUPPORT.csv',pd.DataFrame(support));csv('DESIGN_LINKS.csv',pd.DataFrame(designs));csv('CANDIDATES.csv',pd.DataFrame(candidates));csv('Q_OVERLAP.csv',pd.DataFrame(overlap));csv('TEAM_REQUESTS.csv',pd.DataFrame(requests).drop_duplicates('team_key'))
    write('INPUT_POOLS.json',{'images':[pools[p] for p in sorted({r['pool_id'] for r in requests})]})
    write('DESIGN.json',dict(date='2026-10-31',classification_finalized=False,working_labels='image_difficulty_20261030 TARGET_DSTRUCT_K3 LOBO C2->C3',main_policy='Q_RAW',sensitivity_policy='Q_PEER',q_definition='raw B8L2; peer sensitivity subtracts image/target median; both target->image->building->worker equal means',support='same legal Manual pool; TARGET-known; >=12 scored images and >=3 buildings outside target building',excluded='D,X,Y for both policies; existing Z retained as frozen structural policy',tie_break='worker_id ascending',selection_uses_target_Q=False,conditions=[[14,7],[20,7]],scoreable_filter_before_selection=False,q_matching='descriptive capacity only; raw Q caliper 3, maximum disjoint matching',aggregation='event replicate -> background -> block -> pool -> image; n separately',bootstrap='2000 building cluster resamples; image-equal point estimate; seed 20261031',tails='P10 of image-level paired-available quality; SD of image-level differences; not within-image random-team reliability',labor='compare only full time-source-count vectors that match',unique_requests=len({r['team_key'] for r in requests}),eligible_events=sum(r['eligible'] for r in support)))
    print('Frozen design',len(designs)//5,'events',len({r['team_key'] for r in requests}),'unique teams',flush=True)
def evaluate():
    assert (OUT/'DESIGN.json').exists()
    req=pd.read_csv(OUT/'TEAM_REQUESTS.csv');pools={p['pool_id']:p for p in json.loads((OUT/'INPUT_POOLS.json').read_text(encoding='utf8'))['images']};needed=set(req.team_key);saved={};sources=[]
    def collect(path,kind='jsonl'):
        if not path.exists():return
        sources.append(str(path.relative_to(ROOT)))
        if kind=='json':
            with gzip.open(path,'rt',encoding='utf8') as f:items=[json.load(f)]
        else:items=rows(path)
        for r in items:
            key=r.get('team_key')
            if key not in needed or key in saved:continue
            pool=pools[r['pool_id']];rr=req[req.team_key.eq(key)].iloc[0];by={v['worker_id']:v['object_id'] for v in pool['records']}
            assert set(r['member_workers'])==members(rr.members) and set(r['member_object_ids'])=={by[w] for w in members(rr.members)}
            assert (r['reference_id'],r['reference_version'])==(rr.reference_id,rr.reference_version)
            saved[key]=r
    for pool,g in req.groupby('pool_id'):
        keys=set(g.team_key)
        for path in sorted((SRC/'stage03_endpoints/pools'/pool).glob('part_*.jsonl.gz')):
            collect(path)
            if keys<=saved.keys():break
    comp=ROOT/'research/data/releases/v2.1/closeout_20261030/alliance_completion_20261031'
    collect(comp/'REUSED_ENDPOINTS.jsonl.gz')
    for path in (comp/'new_endpoints').glob('*.json.gz'):collect(path,'json')
    base=ROOT/'research/workers/personnel_v21_reselection_20261029'
    for path in (base/'independent_review/reaudit_20261029/source_archive/stage03_completed_abc').glob('ENDPOINT_GEOMETRY.jsonl.gz'):collect(path)
    # Reuse verified scalar endpoints for the policy comparison; do not replay old teams solely to copy geometry.
    scalar=[]
    for path in base.rglob('ENDPOINT_SCALARS.csv.gz'):
        sources.append(str(path.relative_to(ROOT)))
        for chunk in pd.read_csv(path,chunksize=30000,low_memory=False):
            if 'team_key' not in chunk:continue
            for r in chunk[chunk.team_key.isin(needed-saved.keys())].to_dict('records'):
                rr=req[req.team_key.eq(r['team_key'])].iloc[0]
                if (r.get('reference_id'),r.get('reference_version'))!=(rr.reference_id,rr.reference_version):continue
                if not isinstance(r.get('member_workers'),str) or not isinstance(r.get('member_object_ids'),str):continue
                by={v['worker_id']:v['object_id'] for v in pools[rr.pool_id]['records']}
                assert members(r['member_workers'])==members(rr.members)
                assert members(r['member_object_ids'])=={by[w] for w in members(rr.members)}
                scalar.append({k:r.get(k) for k in ['team_key','B8L2','D10','IoU3D100']})
                r={k:(None if not isinstance(v,(dict,list)) and pd.isna(v) else v) for k,v in r.items()}
                r.update(member_workers=sorted(members(rr.members)),member_object_ids=sorted(members(r['member_object_ids'])),reuse_source=str(path.relative_to(ROOT)),geometry_copied=False)
                saved[r['team_key']]=r
    expectations=pd.DataFrame(scalar,columns=['team_key','B8L2','D10','IoU3D100']).drop_duplicates();csv('SCALAR_EXPECTATIONS.csv',expectations)
    reused=len(saved);missing=req[~req.team_key.isin(saved)].copy();csv('MISSING_TEAMS.csv',missing)
    write('CACHE_CHECKS.json',dict(reused=reused,missing=len(missing),sources=sources))
    sys.path.insert(0,str(REPO/'research/workers/personnel_v21_reselection_20261029/experiment'))
    from benchmark_engine import load_engine,numeric_geometry_difference
    native=load_engine(REPO);(OUT/'new_endpoints').mkdir(exist_ok=True)
    def calc(engine,pool,ws):
        r=engine.evaluate(pool,ws);g=r.get('geometry')
        if g is not None:
            extra=engine.scorecache.get(engine.fr.digest([r['k']==2,r.get('nodes'),g]))
            if extra:r.update(extra)
        r.update(data_release='v2.1',underlying_data_version='v2.1',source_tree=str(REPO.relative_to(ROOT)),endpoint_origin='q_only_exchange_20261031',classification_finalized=False)
        r['native_engine_repository_commit']=r.pop('repository_commit',None)
        return native.gs.clean(r)
    with native.Engine(full_state=False) as engine:
        anchor_path=next((SRC/'stage03_endpoints/pools'/req.iloc[0].pool_id).glob('part_*.jsonl.gz'))
        old=next(r for r in rows(anchor_path) if r.get('B8L2') is not None);new=calc(engine,pools[old['pool_id']],old['member_workers']);gd=numeric_geometry_difference(old['geometry'],new['geometry']);assert gd<1e-8 and abs(old['B8L2']-new['B8L2'])<1e-7;write('ENGINE_PARITY.json',dict(team_key=old['team_key'],source=str(anchor_path.relative_to(ROOT)),geometry_max_difference=gd,passed=True))
        for i,r in enumerate(missing.itertuples()):
            path=OUT/'new_endpoints'/(r.team_key+'.json.gz')
            if path.exists():
                with gzip.open(path,'rt',encoding='utf8') as f:new=json.load(f)
            else:
                new=calc(engine,pools[r.pool_id],sorted(members(r.members)));assert new['team_key']==r.team_key
                with gzip.open(path,'wt',encoding='utf8') as f:json.dump(new,f,ensure_ascii=False,allow_nan=False)
            for old in expectations[expectations.team_key.eq(r.team_key)].to_dict('records'):
                for field in ['B8L2','D10','IoU3D100']:
                    assert pd.isna(old[field])==(new.get(field) is None)
                    if pd.notna(old[field]):assert abs(old[field]-new[field])<1e-7
            saved[r.team_key]=new
            if i%25==0:print('native',i+1,'/',len(missing),flush=True)
    assert set(saved)==needed
    with gzip.open(OUT/'ENDPOINTS.jsonl.gz','wt',encoding='utf8') as f:
        for r in saved.values():f.write(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n')
    write('EVALUATION_CHECKS.json',dict(unique_endpoints=len(saved),reused=reused,native_missing=len(missing),native_parity_calls=1))
def image_means(d,columns):
    keys=['n','building','image','pool_id','block_id','background_id']
    x=d.groupby(keys,dropna=False)[columns].mean().reset_index()
    for key in ['background_id','block_id','pool_id']:
        keys.remove(key);x=x.groupby(keys,dropna=False)[columns].mean().reset_index()
    return x

def cluster_interval(d,column):
    g=d.groupby('building')[column].agg(['sum','count']);rng=np.random.default_rng(20261031)
    ix=rng.integers(0,len(g),size=(2000,len(g)))
    v=g['sum'].to_numpy()[ix].sum(axis=1)/g['count'].to_numpy()[ix].sum(axis=1)
    return np.quantile(v,[.025,.975]).tolist()

def labor(r):
    s=r.get('record_time_by_kind_json')
    if not isinstance(s,str):return None,None
    d=json.loads(s);signature=tuple(sorted((k,v['n']) for k,v in d.items()))
    if not d or any(v['known_n']!=v['n'] or v['total_seconds'] is None for v in d.values()):return signature,None
    return signature,sum(v['total_seconds'] for v in d.values())

def summarize():
    endpoints={r['team_key']:r for r in rows(OUT/'ENDPOINTS.jsonl.gz')}
    links=pd.read_csv(OUT/'DESIGN_LINKS.csv');metrics=['B8L2','D10','IoU3D100','fusion_turn_n','fusion_short_turn_edges','boundary_loss','direction_loss','height_loss','omission','extension','ref_node_recall_5']
    h=pd.read_csv(OUT/'HISTORY_LOBO.csv').set_index(['heldout_building','worker_id']);overlap=[]
    for r in links[links.policy.eq('STRUCTURE')].itertuples():
        a=np.array([h.loc[(r.building,w),'raw_q'] for w in sorted(members(r.X))]);b=np.array([h.loc[(r.building,w),'raw_q'] for w in sorted(members(r.Z))])
        adj=np.abs(a[:,None]-b[None,:])<=3
        overlap.append(dict(event_id=r.event_id,n=r.n,image=r.image,building=r.building,source_mean=a.mean(),target_mean=b.mean(),source_min=a.min(),source_max=a.max(),target_min=b.min(),target_max=b.max(),matched_people_caliper3=int((maximum_bipartite_matching(csr_matrix(adj),perm_type='column')>=0).sum())))
    csv('ORIGINAL_BLOCK_HISTORY_OVERLAP.csv',pd.DataFrame(overlap))
    pairs=[];status=[];selection=[]
    for eid,d in links.groupby('event_id',sort=False):
        by=d.set_index('policy');base=by.loc['STRUCTURE'];s=endpoints[base.team_key]
        for policy in ['A','B','STRUCTURE','Q_RAW','Q_PEER']:
            r=endpoints[by.loc[policy,'team_key']]
            status.append(dict(event_id=eid,n=int(base.n),image=base.image,building=base.building,policy=policy,scored=r.get('B8L2') is not None,complete=r.get('complete_evaluable'),below_four=r.get('below_four'),connection_available=r.get('connection_available'),score_status=r.get('score_status')))
        for policy in ['Q_RAW','Q_PEER','A','B']:
            c=endpoints[by.loc[policy,'team_key']];z={k:base[k] for k in ['n','building','image','pool_id','block_id','background_id']};z.update(event_id=eid,comparator=policy)
            for metric in metrics:
                a,b=s.get(metric),c.get(metric);ok=a is not None and b is not None
                z[metric+'_structure']=a if ok else np.nan;z[metric+'_comparator']=b if ok else np.nan;z[metric+'_delta']=a-b if ok else np.nan
            ls,ts=labor(s);lc,tc=labor(c);ok=ls==lc and ts is not None and tc is not None and tc>0
            z.update(labor_structure_seconds=ts if ok else np.nan,labor_comparator_seconds=tc if ok else np.nan,labor_ratio=ts/tc if ok else np.nan)
            pairs.append(z)
            if policy.startswith('Q_'):
                a=members(base.incoming_members);b=members(by.loc[policy,'incoming_members'])
                selection.append(dict(event_id=eid,n=int(base.n),image=base.image,building=base.building,policy=policy,shared_incoming=len(a&b),same_block=a==b,structure_incoming_raw_q=base.incoming_raw_q,comparator_incoming_raw_q=by.loc[policy,'incoming_raw_q']))
    pair=pd.DataFrame(pairs);csv('PAIRED_EVENTS.csv',pair);csv('OUTPUT_STATUS.csv',pd.DataFrame(status));csv('SELECTION_OVERLAP.csv',pd.DataFrame(selection))
    summaries=[];images=[]
    for (n,policy),d in pair.groupby(['n','comparator']):
        for metric in metrics+['labor']:
            cols=[metric+'_structure',metric+'_comparator',metric+'_delta'] if metric!='labor' else ['labor_structure_seconds','labor_comparator_seconds','labor_ratio']
            valid=d.dropna(subset=cols);im=image_means(valid,cols)
            if im.empty:continue
            effect=cols[-1];ci=cluster_interval(im,effect)
            summaries.append(dict(n=int(n),m=7,comparator=policy,metric=metric,events=len(valid),images=len(im),buildings=im.building.nunique(),structure_mean=im[cols[0]].mean(),comparator_mean=im[cols[1]].mean(),effect=im[effect].mean(),ci_low=ci[0],ci_high=ci[1],positive_images=int((im[effect]>(1 if metric=='labor' else 1e-9)).sum()),negative_images=int((im[effect]<(1 if metric=='labor' else -1e-9)).sum()),structure_p10=im[cols[0]].quantile(.1),comparator_p10=im[cols[1]].quantile(.1)))
            im['comparator']=policy;im['metric']=metric;im=im.rename(columns={cols[0]:'structure',cols[1]:'comparator_value',cols[2]:'effect'});images.append(im)
    summary=pd.DataFrame(summaries);csv('SUMMARY.csv',summary);csv('IMAGE_EFFECTS.csv',pd.concat(images,ignore_index=True))
    st=pd.DataFrame(status);csv('STATUS_SUMMARY.csv',st.groupby(['n','policy']).agg(events=('event_id','size'),scored=('scored','sum'),complete=('complete','sum'),below_four=('below_four','sum'),connection_available=('connection_available','sum')).reset_index())
    print(summary[summary.metric.eq('B8L2')].to_string(index=False))
    figures(summary,pd.concat(images,ignore_index=True))

def figures(summary,images):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size':10,'svg.fonttype':'none','pdf.fonttype':42})
    out=OUT/'figures';out.mkdir(exist_ok=True)
    fig,axes=plt.subplots(1,2,figsize=(11,4.8),layout='constrained')
    for ax,n in zip(axes,[14,20]):
        for j,(policy,color,marker) in enumerate([('Q_RAW','#2166ac','o'),('Q_PEER','#b35806','s')]):
            r=summary[(summary.n==n)&summary.comparator.eq(policy)&summary.metric.eq('B8L2')].iloc[0]
            ax.errorbar(r.effect,j,xerr=[[r.effect-r.ci_low],[r.ci_high-r.effect]],fmt=marker,color=color,capsize=5)
            ax.text(.02,.92-j*.09,f'{policy}: {int(r.events)} events / {int(r.images)} images / {int(r.buildings)} buildings',transform=ax.transAxes,fontsize=9)
            ax.axvline(0,color='black',linestyle='--',linewidth=.8);ax.set_yticks([0,1],['Raw historical Q','Peer-relative Q']);ax.set_ylim(-.7,1.8);ax.set_xlim(-.5,1.4);ax.set_ylabel('Q-only selection rule');ax.set_xlabel('Quality difference: structure − Q-only (Q points)');ax.set_title(f'TARGET working labels: n = {n}, m = 7')
    fig.suptitle('Quality differences between structural and Q-only replacement policies\nwith fixed backgrounds and equal replacement sizes',fontsize=12)
    for ext in ['pdf','svg','png']:fig.savefig(out/f'quality_policy_comparison.{ext}',dpi=300)
    plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(10,4.8),layout='constrained')
    for ax,n in zip(axes,[14,20]):
        d=images[(images.n==n)&images.comparator.eq('Q_RAW')&images.metric.eq('B8L2')]
        ax.scatter(d.comparator_value,d.structure,s=22,color='#2166ac',alpha=.75);ax.plot([0,100],[0,100],'k--',lw=.8);ax.set_xlim(0,100);ax.set_ylim(0,100);ax.set_xlabel('Q-only team quality (Q points)');ax.set_ylabel('Structural team quality (Q points)');ax.set_title(f'n = {n}, m = 7; {len(d)} paired images')
    fig.suptitle('Image-level consensus quality under structural and raw-Q replacement\nusing TARGET working labels and fixed candidate support',fontsize=12)
    for ext in ['pdf','svg','png']:fig.savefig(out/f'paired_image_quality.{ext}',dpi=300)
    plt.close(fig)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['design','evaluate','summarize']);args=ap.parse_args();globals()[args.stage]()
