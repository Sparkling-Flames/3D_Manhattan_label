"""No-replacement replay. Recluster each prefix; order changes paths, not fixed-set endpoints."""
import common as c
import itertools,collections,json,time,math
import numpy as np,pandas as pd
from concurrent.futures import ProcessPoolExecutor

TAILS=[2,3,5]
PROFILES=[('uncapped',None,None),('cap2_s10',2,.1),('cap3_s10',3,.1),('cap3_s20',3,.2),('cap4_s20',4,.2)]
EPS=[.05,.10,.20]

def comparisons(left,right):
    mask=0
    for g in left:mask|=g
    k=mask.bit_count();n=sum(g.bit_count() for g in right)
    ins=[(g&mask).bit_count() for g in right]
    ch=lambda n:n*(n-1)//2
    a=sum(ch(g.bit_count()) for g in left);b=sum(ch(s) for s in ins)
    both=sum(ch((x&y).bit_count()) for x in left for y in right)
    relation=(a+b-2*both)/ch(k)
    tv=.5*sum(abs(s/k-g.bit_count()/n) for g,s in zip(right,ins))
    promotion=any(s<2<=g.bit_count() for g,s in zip(right,ins))
    repeated=any(g.bit_count()>=2 for g in left)
    return relation,tv,promotion,repeated

def run(job):
    v,orders=job;n=v['N'];worker_index={w:j for j,w in enumerate(v['workers'])}
    arrivals=[[worker_index[w] for w in order if w in worker_index] for order in orders]
    curves=[];seq=[];reasons=[];stop=[]
    if n<2:return curves,seq,reasons,stop
    for kind in ['complete','representative']:
        cache={};states={};consistency=0
        settings=[(e,t,p[0],p[1],p[2],False) for e in EPS for t in TAILS for p in PROFILES if e==.1 or p[0]=='uncapped']
        settings += [(.1,t,'allow_rare_new_modes',None,None,True) for t in TAILS]
        count={s:np.zeros((max(0,n-s[1]-1),3),dtype=int) for s in settings}
        for oi,order in enumerate(arrivals):
            mask=0;parts={};ks=[]
            for k,j in enumerate(order,1):
                mask|=1<<j
                if k<2:continue
                if mask not in cache:
                    ix=[j for j in range(n) if mask&(1<<j)];labels,_=c.part(v['d'][np.ix_(ix,ix)],[v['ids'][j] for j in ix],kind)
                    gg=collections.defaultdict(int)
                    for j,l in zip(ix,labels):gg[int(l)]|=1<<j
                    cache[mask]=tuple(gg.values())
                parts[k]=cache[mask]
            anchors={k:[comparisons(parts[k],parts[j]) for j in range(k+1,n+1)] for k in range(2,n)}
            anchor_cache={}
            for eps in EPS:
                for allow in ([False,True] if eps==.1 else [False]):
                    anchor_cache[eps,allow]={k:max(1 if not rep else 2 if rel>eps+1e-12 or tv>eps+1e-12 or (pro and not allow) else 0 for rel,tv,pro,rep in vals) for k,vals in anchors.items()}
            for setting in settings:
                eps,tail,profile,cap,single,allow=setting
                aa=anchor_cache[eps,allow]
                bad={k:int(cap is not None and (len(g)>cap or sum(x.bit_count()==1 for x in g)/k>single+1e-12))*2 for k,g in parts.items()}
                badtail=max((bad[j] for j in range(max(2,n-tail+1),n+1)),default=0)
                onset=None;possible=None;status=badtail
                for k in range(n-tail,1,-1):
                    status=max(status,aa[k],bad[k])
                    count[setting][k-2,status]+=1
                    if status==0:onset=k
                    if status!=2:possible=k
                if eps==.1 and tail==3 and profile in ['uncapped','allow_rare_new_modes']:
                    stop.append(dict(image_id=v['image_id'],code=v['code'],building=v['building'],N=n,method=kind,profile=profile,order_id=oi,
                        earliest_observed_stable=onset,earliest_not_ruled_out=possible,
                        first8_workers=';'.join(v['workers'][j] for j in order[:8])))
            # Fixed-k prefix statistics, using REAL subsets and local reclustering only.
            for k in [3,5,8,12,15,18,20]:
                if k>=n or k<2:continue
                ix=order[:k];rest=order[k:];groups=parts[k]
                unseen=(v['d'][np.ix_(rest,ix)].min(1)>c.CUT).mean()
                seq.append(dict(image_id=v['image_id'],code=v['code'],building=v['building'],N=n,method=kind,order_id=oi,k=k,
                    clusters=len(groups),singleton_mass=sum(g.bit_count()==1 for g in groups)/k,
                    pair_disagreement=float(np.mean(v['d'][np.ix_(ix,ix)][np.triu_indices(k,1)]>c.CUT)),remaining_uncovered=unseen))
                vals=anchors[k]
                reasons.append(dict(image_id=v['image_id'],code=v['code'],building=v['building'],N=n,method=kind,order_id=oi,k=k,
                    no_repeat_support=not vals[0][3],membership_change=any(a>.1+1e-12 for a,_,_,_ in vals),
                    proportion_change=any(b>.1+1e-12 for _,b,_,_ in vals),supported_new_mode=any(pro for _,_,pro,_ in vals)))
        for setting,cts in count.items():
            eps,tail,profile,cap,single,allow=setting
            L=cts[:,0]/len(orders);U=(cts[:,0]+cts[:,1])/len(orders);ks=np.arange(2,n-tail+1)
            assert np.all(np.diff(L)>=-1e-12) and np.all(np.diff(U)>=-1e-12)
            lo=next((int(k) for k,p in zip(ks,U) if p>=.8-1e-12),None)
            hi=next((int(k) for k,p in zip(ks,L) if p>=.8-1e-12),None)
            status='identified' if lo is not None and lo==hi else 'bounded_unknown' if hi is not None else 'possible_only' if lo is not None else 'insufficient_tail' if not len(ks) else 'not_reached'
            curves.append(dict(image_id=v['image_id'],code=v['code'],building=v['building'],N=n,method=kind,epsilon=eps,tail=tail,profile=profile,
                possible_onset=lo,conservative_onset=hi,status=status,ks=ks,L=L,U=U,
                final_stable_probability=L[-1] if len(L) else None,final_unknown_probability=(U-L)[-1] if len(L) else None))
    return curves,seq,reasons,stop

def main():
    p=c.main_parser();p.add_argument('--orders',type=int,default=200);p.add_argument('--jobs',type=int,default=4);p.add_argument('--start',type=int,default=0);p.add_argument('--end',type=int,default=240);p.add_argument('--aggregate',action='store_true');args=p.parse_args();c.configure(args.source_root)
    _,_,views,_,_=c.load();workers=sorted(set(w for v in views.values() for w in v['workers']))
    rng=np.random.default_rng(c.SEED);orders=[list(rng.permutation(workers)) for _ in range(args.orders)]
    c.save('replay_orders.json',dict(seed=c.SEED,n_orders=args.orders,workers=workers,orders=orders))
    jobs=[({k:v[k] for k in ['image_id','code','building','N','ids','workers','d']},orders) for v in views.values()]
    curves=[];sequences=[];reasons=[];stops=[]
    cache_dir=c.ROOT/'results/replay_image_cache';cache_dir.mkdir(exist_ok=True)
    import hashlib
    manifest={'source_responses_sha256':hashlib.sha256((c.SOURCE/'analysis_results/new_manual_reviewed_20260921/responses.jsonl.gz').read_bytes()).hexdigest(),
              'seed':c.SEED,'orders':args.orders,'algorithm_version':'20260921_v1'}
    manifest_path=c.ROOT/'results/replay_cache_manifest.json'
    if manifest_path.exists() and json.loads(manifest_path.read_text())!=manifest:
        raise ValueError('Replay cache differs in source, seed, or order count. Use a separate output copy or delete this cache before changing settings.')
    manifest_path.write_text(json.dumps(manifest,indent=2),encoding='utf8')
    if not args.aggregate:
        selected=[(j,job) for j,job in enumerate(jobs) if args.start<=j<args.end and not (cache_dir/f'{j:03d}.json.gz').exists()]
        with ProcessPoolExecutor(max_workers=args.jobs) as pool:
            for (index,_),result in zip(selected,pool.map(run,[job for _,job in selected])):
                import gzip
                with gzip.open(cache_dir/f'{index:03d}.json.gz','wt',encoding='utf8') as f:json.dump(c.clean(result),f,ensure_ascii=False)
                print('image saved',index,flush=True)
        return
    import gzip
    for j in range(len(jobs)):
        with gzip.open(cache_dir/f'{j:03d}.json.gz','rt',encoding='utf8') as f:a,b,d,e=json.load(f)
        curves.extend(a);sequences.extend(b);reasons.extend(d);stops.extend(e)
    c.save('replay_curves.json',curves)
    scalar=pd.DataFrame([{k:v for k,v in x.items() if k not in ['ks','L','U']} for x in curves]);c.save('replay_onsets.csv',scalar)
    sq=pd.DataFrame(sequences);rs=pd.DataFrame(reasons);st=pd.DataFrame(stops)
    c.save('replay_prefixes.csv.gz',sq);c.save('replay_reasons.csv.gz',rs);c.save('replay_order_onsets.csv.gz',st)
    summaries=[]
    for key,g in scalar.groupby(['method','epsilon','tail','profile']):
        for scope,z in [('all',g),('N_ge8',g[g.N>=8]),('N_ge15',g[g.N>=15])]:
            summaries.append(dict(method=key[0],epsilon=key[1],tail=key[2],profile=key[3],scope=scope,
                images=len(z),statuses=z.status.value_counts().to_dict(),median_identified_onset=z.loc[z.status=='identified','conservative_onset'].median()))
    c.save('replay_summary.json',summaries)
    summary=[]
    for (kind,k),g in rs.groupby(['method','k']):
        gi=g.groupby(['image_id','building'])[['no_repeat_support','membership_change','proportion_change','supported_new_mode']].mean().reset_index()
        summary.append(dict(method=kind,k=k,images=len(gi),means=gi.iloc[:,2:].mean().to_dict()))
    c.save('replay_failure_reasons.json',summary)
    # Quantify order variation without assigning statistical independence to permutations.
    os=st.groupby(['image_id','code','building','N','method','profile']).agg(
        probability_observed_stable=('earliest_observed_stable',lambda x:x.notna().mean()),
        onset_q10=('earliest_observed_stable',lambda x:x.quantile(.1)),onset_q50=('earliest_observed_stable','median'),onset_q90=('earliest_observed_stable',lambda x:x.quantile(.9))).reset_index()
    c.save('order_variability.csv',os)
    print(json.dumps(c.clean([x for x in summaries if x['epsilon']==.1 and x['profile']=='uncapped']),ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
