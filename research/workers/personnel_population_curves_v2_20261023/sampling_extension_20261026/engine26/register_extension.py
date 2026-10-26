"""Register the entire independent whole-curve extension before viewing outcomes.

Bounded-memory per-pool registration. Cache identities are checked against frozen
members/reference; scalar values do not enter selection. CSV outputs are streamed
through gzip and atomically committed after their footer is closed.
"""
from pathlib import Path
import argparse,collections,csv,gzip,hashlib,io,json,os,time
import numpy as np

COMMIT='b9bcec809fbaec8ab055931a1abb7baa5db44dac'
MASTER=2026102601
NAMESPACE='population_wholecurve_precision_20261026'
POLICIES=['structure_moreturn_first','structure_dominant_first','joint_highq_first','joint_fast_first']

def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def sha(p):return hashlib.file_digest(Path(p).open('rb'),'sha256').hexdigest()
def seed(pid,i):return int.from_bytes(hashlib.sha256(json.dumps([NAMESPACE,MASTER,pid,i],separators=(',',':')).encode()).digest()[:8],'little')
def team(pid,ws):return pid+'__'+digest(sorted(ws))[:20]
def jsread(p):
    with gzip.open(p,'rt',encoding='utf-8-sig') as f:return json.load(f)
def csvread(p):
    with gzip.open(p,'rt',encoding='utf-8-sig',newline='') as f:yield from csv.DictReader(f)

class Writer:
    def __init__(self,path,fields):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.tmp=self.path.with_name(self.path.name+'.writing');self.fd=os.open(self.tmp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o644)
        self.fields=fields;self.text=io.StringIO(newline='');self.writer=csv.DictWriter(self.text,fieldnames=fields,extrasaction='raise',lineterminator='\n');self.writer.writeheader();self.n=0;self.first=True
    def _flush(self):
        raw=self.text.getvalue().encode('utf-8-sig' if self.first else 'utf-8');self.first=False
        if not raw:return
        data=gzip.compress(raw,compresslevel=4,mtime=0) if self.path.suffix=='.gz' else raw
        view=memoryview(data);offset=0
        while offset<len(view):
            n=os.write(self.fd,view[offset:offset+1024*1024])
            if n<=0:raise IOError('Short write made no progress')
            offset+=n
        self.text.seek(0);self.text.truncate(0)
    def put(self,row):
        self.writer.writerow({k:row.get(k,'') for k in self.fields});self.n+=1
        if self.n%1000==0:self._flush()
    def close(self):
        self._flush();os.fsync(self.fd);os.close(self.fd);self.tmp.replace(self.path)
        with (gzip.open(self.path,'rt',encoding='utf-8-sig',newline='') if self.path.suffix=='.gz' else self.path.open(encoding='utf-8-sig',newline='')) as f:
            rd=csv.reader(f);head=next(rd);n=0
            for r in rd:assert len(r)==len(head);n+=1
        assert n==self.n
        return {'file':str(self.path),'rows':n,'columns':len(head),'bytes':self.path.stat().st_size,'sha256':sha(self.path),'complete_EOF':True}

def run(base,natural=208,stage_n=104,policy_bases=16):
    t=time.monotonic();src=base/'repo/research/workers/personnel_population_curves_v2_20261023';prior=base/'prior_recovered/research/workers/personnel_population_curves_v2_20261023/sampling_precision_20261025';out=base/'design26';out.mkdir(exist_ok=True)
    snap=jsread(src/'inputs/INPUT_SNAPSHOT.json.gz');pools={x['pool_id']:x for x in snap['images'] if x['meta']['layer'] in ('ordinary_manual','doorway_manual')}
    frozen=jsread(prior/'engine/frozen_repo/research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz');fp={x['pool_id']:x for x in frozen['images']}
    assert len(pools)==194
    assert all(pools[k]==fp[k] for k in pools),'Frozen input differs from accessible main'
    roles={};old_paths=collections.Counter()
    for r in csvread(src/'design/EXACT_ORDER_DESIGN.csv.gz'):
        if r['pool_id'] not in pools:continue
        if r['policy']=='natural_random':old_paths[r['pool_id']]+=1
        if r['policy'] in POLICIES and r['layer']=='ordinary_manual' and int(r['pool_n'])>=20:
            key=(r['pool_id'],r['policy'])
            if key in roles:
                assert all(roles[key][f]==r[f] for f in ['target_members','target_class','method','tier'])
            else:roles[key]=r
    policy_pools={pid for pid in pools if all((pid,s) in roles for s in POLICIES)};assert len(policy_pools)==157
    assert all(old_paths[pid]==24 for pid in pools)
    own={pid:{r['worker_id']:r for r in p['records']} for pid,p in pools.items()}
    cache={pid:{} for pid in pools};cache_counts=collections.Counter();cache_sources=[('inherited_population_20261023',base/'inputs_cache26/ENDPOINT_SCALARS_20261023.csv.gz'),('inherited_precision_20261025',base/'inputs_cache26/precision25/NEW_ENDPOINT_SCALARS.csv.gz')]
    for origin,path in cache_sources:
        for r in csvread(path):
            pid=r['pool_id']
            if pid not in pools:continue
            ws=sorted(r['member_workers'].split('|'));assert len(ws)==int(float(r['k']))
            assert set(ws)<=set(own[pid]);assert team(pid,ws)==r['team_key']
            assert sorted(r['member_object_ids'].split('|'))==sorted(own[pid][w]['object_id'] for w in ws)
            assert all(r.get(k,'')==pools[pid]['meta'].get(k,'') for k in ['reference_id','reference_version'])
            assert r['team_key'] not in cache[pid],'Overlapping old scalar sources'
            cache[pid][r['team_key']]=origin;cache_counts[origin]+=1
    meta=list(next(iter(pools.values()))['meta'])
    role_cols=['heldout_building','pool_size','method','tier','target_class','selected_family','target_members','known_members','unknown_members','non_target_capacity','known_capacity','unknown_capacity','full_pool_class_vector','history_people','history_turn_center','history_short_center','history_redundancy_center','history_q_center','history_t_center']
    order_cols=meta+['path_id','base_path_id','replicate','new_index','seed','master_seed','policy','workers','worker_order','base_worker_order','order_kind','generation','seed_rule','sample_kind','batch','stage','sampling_weight_new_batch','final_pool_hash','final_pool_identity','eligible','reason','target_capacity','paired_for_policy','pool_input_sha256','repository_commit']+role_cols
    link_cols=['pool_id','path_id','base_path_id','replicate','policy','order_kind','generation','target_capacity','paired_for_policy','target_class','method','tier','sample_kind','batch','stage','new_index','seed','master_seed','sampling_weight_new_batch','k','team_key','target_present_n','entrant_worker']
    dep_cols=meta+['team_key','n','k','member_workers','member_object_ids','pool_input_sha256','requested_natural','requested_policy','requested_stage1','requested_stage2','first_required_stage','endpoint_source','source_table']
    writers={'orders':Writer(out/'NEW_EXACT_ORDER_DESIGN.csv.gz',order_cols),'links':Writer(out/'NEW_PREFIX_TEAM_LINKS.csv.gz',link_cols),'deps':Writer(out/'ENDPOINT_DEPENDENCIES.csv.gz',dep_cols),'new':Writer(out/'NEW_NATIVE_ENDPOINT_REQUESTS.csv.gz',dep_cols)}
    counts=collections.Counter();plans=[];budgets=[];seed_seen=set()
    for pi,(pid,pool) in enumerate(sorted(pools.items()),1):
        workers=sorted(own[pid]);N=len(workers);ph=digest(pool);fh=hashlib.sha256((pid+'|'+'|'.join(workers)).encode()).hexdigest()[:24];wanted={}
        def add_order(row,order,target=()):
            assert row['workers']==row['worker_order']=='|'.join(order);writers['orders'].put(row);members=[];target=set(target)
            for k,w in enumerate(order,1):
                members.append(w);ws=sorted(members);key=team(pid,ws)
                if key not in wanted:
                    wanted[key]=dict(pool['meta'],team_key=key,n=k,k=k,member_workers='|'.join(ws),member_object_ids='|'.join(own[pid][x]['object_id'] for x in ws),pool_input_sha256=ph,requested_natural=False,requested_policy=False,requested_stage1=False,requested_stage2=False,first_required_stage=row['stage'])
                dep=wanted[key];dep['requested_natural' if row['policy']=='natural_random' else 'requested_policy']=True;dep['requested_stage'+str(row['stage'])]=True;dep['first_required_stage']=min(dep['first_required_stage'],row['stage'])
                link={x:row.get(x,'') for x in link_cols};link.update(k=k,team_key=key,target_present_n=sum(x in target for x in members),entrant_worker=w);writers['links'].put(link)
        for i in range(natural):
            sd=seed(pid,i);assert sd not in seed_seen;seed_seen.add(sd);order=np.random.default_rng(sd).permutation(workers).tolist();stage=1 if i<stage_n else 2
            path=pid+'__wholecurve_20261026__natural_new'+str(i).zfill(3)
            row=dict(pool['meta'],path_id=path,base_path_id=path,replicate=96+i,new_index=i,seed=str(sd),master_seed=str(MASTER),policy='natural_random',workers='|'.join(order),worker_order='|'.join(order),base_worker_order='|'.join(order),order_kind='uniform_without_replacement_within_pool',generation='new_uniform_independent_20261026',seed_rule='sha256(JSON([namespace,master_seed,pool_id,new_index])) first8 bytes little-endian; numpy default_rng permutation',sample_kind='MC',batch='extension_stage'+str(stage)+'_'+str(stage_n),stage=stage,sampling_weight_new_batch=1/stage_n,final_pool_hash=fh,final_pool_identity='same_actual_full_pool',eligible=True,reason='supported',target_capacity=0,paired_for_policy=(pid in policy_pools and i<policy_bases),pool_input_sha256=ph,repository_commit=COMMIT)
            add_order(row,order);counts['natural_orders']+=1
            if pid in policy_pools and i<policy_bases:
                for policy in POLICIES:
                    rr=roles[pid,policy];target=set(rr['target_members'].split('|'));assert target and target<set(workers)
                    po=[w for w in order if w in target]+[w for w in order if w not in target]
                    pr=dict(row,policy=policy,path_id=path+'__'+policy,batch='extension_policy_new'+str(policy_bases),workers='|'.join(po),worker_order='|'.join(po),order_kind='stable_target_class_first_from_paired_uniform_base',generation='new_policy_transform_20261026',sampling_weight_new_batch=1/policy_bases,target_capacity=len(target),paired_for_policy=True)
                    pr.update({c:rr.get(c,'') for c in role_cols});add_order(pr,po,target);counts['policy_orders']+=1
        requests={1:[],2:[]};pc=collections.Counter()
        for key,r in sorted(wanted.items()):
            origin=cache[pid].get(key)
            if origin:r.update(endpoint_source=origin,source_table='inputs_cache26/'+('ENDPOINT_SCALARS_20261023.csv.gz' if origin.endswith('20261023') else 'precision25/NEW_ENDPOINT_SCALARS.csv.gz'))
            else:
                assert r['n'] not in {1,N-1,N};assert N>10
                r.update(endpoint_source='new_native_required_20261026',source_table='new_endpoints26/NEW_ENDPOINT_SCALARS.csv.gz');requests[r['first_required_stage']].append(r);writers['new'].put(r)
            writers['deps'].put(r);counts['unique_teams']+=1;counts[r['endpoint_source']]+=1;pc[(r['endpoint_source'],r['first_required_stage'])]+=1
            if r['n']==N:counts['fullN_teams']+=1
        for stage,rows in requests.items():
            folder=out/'requests_by_pool'/('stage'+str(stage));folder.mkdir(parents=True,exist_ok=True)
            if rows:
                w=Writer(folder/(pid+'.csv.gz'),dep_cols)
                for r in rows:w.put(r)
                w.close()
            counts['stage'+str(stage)+'_new']+=len(rows)
        plans.append(dict(pool['meta'],new_natural_paths=natural,new_stage_paths=stage_n,old_balanced_paths=48,primary_total_paths=48+natural,policy_common_pool=pid in policy_pools,new_policy_bases=policy_bases if pid in policy_pools else 0,primary_policy_total_bases=16+policy_bases if pid in policy_pools else 0,stage1_new_endpoints=len(requests[1]),stage2_new_endpoints=len(requests[2]),pool_input_sha256=ph,all_old_cache_endpoints=len(cache[pid])))
        for (origin,stage),n in pc.items():budgets.append(dict(pool['meta'],endpoint_source=origin,first_required_stage=stage,unique_endpoints=n))
        print(json.dumps({'pool':pi,'pools':len(pools),'pool_id':pid,'new':sum(map(len,requests.values())),'reuse':len(wanted)-sum(map(len,requests.values())),'seconds':time.monotonic()-t}),flush=True)
    outputs={name:w.close() for name,w in writers.items()}
    for name,rows in [('POOL_SAMPLING_PLAN.csv',plans),('EXECUTION_BUDGET_BY_POOL.csv',budgets)]:
        w=Writer(out/name,list(rows[0]))
        for r in rows:w.put(r)
        outputs[name]=w.close()
    rec=dict(source_commit=COMMIT,prior_precision_source_commit='40d0fe62dc62f6f6c12723af10195b7abb7bc9fe',data_version='human_v2',namespace=NAMESPACE,master_seed=str(MASTER),pools=len(pools),ordinary_manual=sum(p['meta']['layer']=='ordinary_manual' for p in pools.values()),doorway_manual=sum(p['meta']['layer']=='doorway_manual' for p in pools.values()),natural_per_pool=natural,stage_paths=stage_n,policy_pools=len(policy_pools),policy_bases=policy_bases,counts=dict(counts),prefix_rows=writers['links'].n,order_rows=writers['orders'].n,cache_available=dict(cache_counts),outputs=outputs,seconds=time.monotonic()-t,old_focus_extra48_in_primary=False,old_focus_extra48_cache_reused=True,no_target_quality_in_design=True,frozen_main_pool_values_equal_prior_engine=True,fullN_new=0,source_snapshot_sha256=sha(src/'inputs/INPUT_SNAPSHOT.json.gz'),geometry_retention='All scalar/compact geometry; complete native state for fixed VFua04/wc2-46/rPc6-06 and deterministic team-key hash mod200=0. No output-based sampling.',stopping_rule='Both preregistered stages complete regardless of Q sign, significance or smoothness. Only resource/runtime constraints can pause execution; planned and completed counts remain distinct.')
    packed=json.dumps(rec,ensure_ascii=False,indent=2).encode();fd=os.open(out/'DESIGN_RECEIPT.json.writing',os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o644);offset=0
    while offset<len(packed):offset+=os.write(fd,packed[offset:offset+1024*1024])
    os.fsync(fd);os.close(fd);(out/'DESIGN_RECEIPT.json.writing').replace(out/'DESIGN_RECEIPT.json');print(json.dumps({k:v for k,v in rec.items() if k!='outputs'},ensure_ascii=False),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,required=True);ap.add_argument('--natural',type=int,default=208);ap.add_argument('--stage-paths',type=int,default=104);ap.add_argument('--policy-bases',type=int,default=16);a=ap.parse_args();assert a.natural==2*a.stage_paths;run(a.base,a.natural,a.stage_paths,a.policy_bases)
