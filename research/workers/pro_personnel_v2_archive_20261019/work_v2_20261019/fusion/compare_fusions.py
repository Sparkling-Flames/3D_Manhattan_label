"""All registered replacement, same-k and actual-prefix comparisons; failures retained."""
from __future__ import annotations
from collections import defaultdict,Counter
from concurrent.futures import ProcessPoolExecutor,as_completed
from itertools import combinations
from pathlib import Path
import argparse,csv as csv_module,gzip,json,math,time,io,os,uuid,fcntl
import numpy as np
from pool_io import OUT,read,save,clean,canonical,load_pools,save_gz
from fusion_engine import footprint,structural_distance,transition

META=('pool_id','image','image_id','building','room_id','condition','layer','difficulty','difficulty_aligned','reference_id','reference_version')

def value(row,key):
    v=row.get(key)
    return v if isinstance(v,(int,float)) and math.isfinite(v) else None
def difference(a,b,key):
    x,y=value(a,key),value(b,key)
    return y-x if x is not None and y is not None else None
def ring_key(points):
    if points is None:return None
    rows=tuple(tuple(float(x) for x in row) for row in points)
    return min([rows[i:]+rows[:i] for i in range(len(rows))]+[rows[::-1][i:]+rows[::-1][:i] for i in range(len(rows))]) if rows else None

class ComparisonPool:
    def __init__(self,pool):
        self.pool=pool;target=OUT/'pools'/pool['pool_id'];self.rows=read(target/'request_results.json.gz')['results']
        self.byid={r['request_id']:r for r in self.rows};self.states={r['team_id']:r['automatic'] for r in read(target/'states.json.gz')['states']}
        observations=[(r['object_id'],i) for r in pool['records'] for i in range(len(r['points'])//2)]
        self.obs={x:i for i,x in enumerate(observations)};self.M=len(observations);self.signatures={};self.comparison_cache={}
    def signature(self,tid):
        if tid in self.signatures:return self.signatures[tid]
        state=self.states[tid]
        if state is None:self.signatures[tid]=None;return None
        groups={g['feature_id']:set(self.obs[(m['id'],m['pair_index'])] for m in g['members']) for g in state['identity_groups']}
        obs=set().union(*groups.values());selected=set().union(*(groups[g['feature_id']] for g in state['identity_groups'] if g['selected']))
        paired=set()
        for members in groups.values():
            paired.update(a*self.M+b for a,b in combinations(sorted(members),2))
        ring=state['candidate'].get('feature_ids',[]);edges=set()
        if state['candidate']['points'] is not None:
            for a,b in zip(ring,ring[1:]+ring[:1]):
                for x in groups[a]:
                    for y in groups[b]:
                        if x!=y:edges.add(min(x,y)*self.M+max(x,y))
        else:edges=None
        candidate=state['candidate'];floor=footprint(candidate['footprint'])
        points=candidate['points'];pair_points=None if points is None else [points[i]+points[i+1] for i in range(0,len(points),2)]
        signature=dict(state=state,obs=obs,selected=selected,coidentity=paired,edges=edges,floor=floor,
            floor_key=ring_key(candidate['footprint']),full_key=ring_key(pair_points),points=points,nodes=len(state['node_consensus']['nodes']))
        self.signatures[tid]=signature;return signature
    def pair(self,aid,bid):
        a,b=self.byid[aid],self.byid[bid];sa,sb=self.signature(a['team_id']),self.signature(b['team_id'])
        wa,wb=set(a['member_workers'].split('|')),set(b['member_workers'].split('|'))
        out={k:a.get(k) for k in META}
        out.update(request_a=aid,request_b=bid,team_id_a=a['team_id'],team_id_b=b['team_id'],k_a=a['k'],k_b=b['k'],k=a['k'] if a['k']==b['k'] else None,
            shared_workers=len(wa&wb),same_subset=wa==wb,member_workers_a=a['member_workers'],member_workers_b=b['member_workers'],
            complete_a=a['complete_evaluable'],complete_b=b['complete_evaluable'],both_complete=a['complete_evaluable'] and b['complete_evaluable'],
            score_status_a=a.get('score_status'),score_status_b=b.get('score_status'),B8L2_a=a.get('B8L2'),B8L2_b=b.get('B8L2'),D10_a=a.get('D10'),D10_b=b.get('D10'),
            B8L2_change=difference(a,b,'B8L2'),D10_change=difference(a,b,'D10'),IoU3D100_change=difference(a,b,'IoU3D100'),
            floor_iou_change=difference(a,b,'iou_2d'),omission_change=difference(a,b,'omission'),extension_change=difference(a,b,'extension'),
            Hmean_change=difference(a,b,'Hmean'),Hcenter_change=difference(a,b,'Hcenter'),
            source_time_change_seconds=difference(a,b,'source_time_total_seconds'),target_time_change_seconds=difference(a,b,'target_time_total_seconds'),
            source_time_complete_a=a.get('source_time_missing_n')==0,source_time_complete_b=b.get('source_time_missing_n')==0,
            target_time_complete_a=a.get('target_time_missing_n')==0,target_time_complete_b=b.get('target_time_missing_n')==0,
            complete_to_incomplete=a['complete_evaluable'] and not b['complete_evaluable'],incomplete_to_complete=not a['complete_evaluable'] and b['complete_evaluable'],
            node_count_difference=abs(a['nodes']-b['nodes']) if a['nodes'] is not None and b['nodes'] is not None else None,
            node_count_change=difference(a,b,'nodes'),floor_jaccard_difference=None,floor_symdiff_h2=None,
            structure_bound_cyclic_deg=None,structure_available=False,structure_reason='fusion_exception',
            structure_reverse_allowed_deg=None,structure_best_orientation=None,common_observations=0,changed_coidentity_pairs=None,
            common_pair_comparisons=0,edge_relation_jaccard_difference=None,selected_shared_observation_difference=None,
            floor_geometry_exactly_equal=None,full_geometry_exactly_equal=None,mean_height_prism_pair_iou=None,height_ratio_pair_abs_logdiff=None)
        if sa is not None and sb is not None:
            pa,pb=sa['floor'],sb['floor'];shared=sa['obs']&sb['obs'];M=self.M
            restricted=lambda codes:{x for x in codes if x//M in shared and x%M in shared}
            diff=sa['coidentity']^sb['coidentity']
            changed=sum(x//M in shared and x%M in shared for x in diff)
            out.update(common_observations=len(shared),common_pair_comparisons=len(shared)*(len(shared)-1)//2,changed_coidentity_pairs=changed,
                selected_shared_observation_difference=len((sa['selected']^sb['selected'])&shared)/len(shared) if shared else None,
                floor_geometry_exactly_equal=sa['floor_key']==sb['floor_key'] if sa['floor_key'] is not None and sb['floor_key'] is not None else None,
                full_geometry_exactly_equal=sa['full_key']==sb['full_key'] if sa['full_key'] is not None and sb['full_key'] is not None else None,
                **structural_distance(sa['points'],sb['points']))
            if sa['edges'] is not None and sb['edges'] is not None:
                ea,eb=restricted(sa['edges']),restricted(sb['edges']);eu=ea|eb
                out.update(edge_relation_jaccard_difference=len(ea^eb)/len(eu) if eu else None,
                    edge_relation_symmetric_difference=len(ea^eb),edge_relation_union_n=len(eu))
            if out['structure_available']:
                reversed_points=np.asarray(sb['points']).reshape(-1,2,2)[::-1].reshape(-1,2).tolist()
                reverse=structural_distance(sa['points'],reversed_points)['structure_bound_cyclic_deg'];forward=out['structure_bound_cyclic_deg']
                out.update(structure_reverse_allowed_deg=min(forward,reverse),structure_best_orientation='reversed' if reverse<forward else 'forward')
            if pa is not None and pb is not None and a['complete_floor_evaluable'] and b['complete_floor_evaluable']:
                inter=pa.intersection(pb).area;union=pa.area+pb.area-inter
                out.update(floor_jaccard_difference=1-inter/union if union>0 else None,floor_symdiff_h2=pa.area+pb.area-2*inter)
                ha,hb=value(a,'height_mean_ratio'),value(b,'height_mean_ratio')
                if ha is not None and hb is not None and ha>0 and hb>0:
                    vi=inter*min(ha,hb);vu=pa.area*ha+pb.area*hb-vi
                    out.update(mean_height_prism_pair_iou=vi/vu if vu>0 else None,height_ratio_pair_abs_logdiff=abs(math.log(ha/hb)))
        dq=out['B8L2_change'];out['abs_B8L2_change']=abs(dq) if dq is not None else None
        out['abs_D10_change']=abs(out['D10_change']) if out['D10_change'] is not None else None
        out['quality_comparable']=dq is not None
        for q in (1,2,5):out[f'quality_within_{q}']=abs(dq)<=q if dq is not None else None
        for name,q,f,s in [('strict',1,.02,2),('main',2,.05,3),('wide',5,.10,5)]:
            out['joint_stable_'+name]=bool(out['both_complete'] and dq is not None and abs(dq)<=q and out['node_count_difference']==0
                and out['floor_jaccard_difference'] is not None and out['floor_jaccard_difference']<=f
                and out['structure_bound_cyclic_deg'] is not None and out['structure_bound_cyclic_deg']<=s)
            out['joint_stable_'+name+'_orientation_invariant']=bool(out['both_complete'] and dq is not None and abs(dq)<=q and out['node_count_difference']==0
                and out['floor_jaccard_difference'] is not None and out['floor_jaccard_difference']<=f
                and out['structure_reverse_allowed_deg'] is not None and out['structure_reverse_allowed_deg']<=s)
        out['joint_geometric_stable']=out['joint_stable_main']
        out['joint_with_shared_connections']=bool(out['joint_stable_main'] and out['edge_relation_jaccard_difference']==0)
        out['joint_with_shared_connections_and_retention']=bool(out['joint_with_shared_connections'] and out['selected_shared_observation_difference']==0)
        return clean(out)

def write_csv_gz(path,rows):
    rows=list(rows);fields=list(dict.fromkeys(k for r in rows for k in r));path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    buffer=io.StringIO(newline='');w=csv_module.DictWriter(buffer,fieldnames=fields);w.writeheader();w.writerows(rows)
    raw=buffer.getvalue().encode('utf-8-sig');packed=gzip.compress(raw,compresslevel=6,mtime=0)
    temporary=path.with_name(path.name+'.tmp.'+uuid.uuid4().hex)
    with temporary.open('wb') as f:f.write(packed);f.flush();os.fsync(f.fileno())
    assert gzip.decompress(temporary.read_bytes())==raw,'compressed_comparison_write_readback_failed'
    temporary.replace(path)
    return len(rows)

def process_pool(pool,initial_only=False):
    start=time.monotonic();cp=ComparisonPool(pool);rows=cp.rows
    if initial_only:rows=[r for r in rows if r['request_family'] in ('uniform_prefix','independent_random_team','fixed_background')]
    target=OUT/('comparisons_initial' if initial_only else 'comparisons')/pool['pool_id'];target.mkdir(parents=True,exist_ok=True)
    lookup={r['worker_id']:r for r in pool['records']};counts={}
    groups=defaultdict(list)
    for r in rows:
        if r['request_family']=='fixed_background':groups[r['background_id']].append(r)
    replacements=[]
    for bid,g in groups.items():
        for a,b in combinations(sorted(g,key=lambda r:r['entrant_worker_id']),2):
            out=cp.pair(a['request_id'],b['request_id']);ea,eb=a['entrant_worker_id'],b['entrant_worker_id']
            out.update(comparison_family='single_replacement',background_id=bid,background_draw_id=a['draw_id'],entrant_a=ea,entrant_b=eb,
                entrant_object_id_a=lookup[ea]['object_id'],entrant_object_id_b=lookup[eb]['object_id'],
                background_workers='|'.join(sorted(set(a['member_workers'].split('|'))&set(b['member_workers'].split('|')))))
            for prefix,key in [('source','source_time_seconds'),('target','target_time_seconds')]:
                ta,tb=lookup[ea][key],lookup[eb][key];out[prefix+'_entrant_time_a']=ta;out[prefix+'_entrant_time_b']=tb
                out[prefix+'_entrant_time_change_seconds']=tb-ta if ta is not None and tb is not None else None
            replacements.append(out)
    counts['replacements']=write_csv_gz(target/'replacements.csv.gz',replacements)
    paths=defaultdict(list)
    for r in rows:
        if 'path_id' in r:paths[r['path_id']].append(r)
    changes=[]
    for path,g in paths.items():
        g.sort(key=lambda r:r['k'])
        for a,b in zip(g,g[1:]):
            assert b['k']==a['k']+1 and set(a['member_workers'].split('|'))<set(b['member_workers'].split('|')),'non_nested_prefix'
            out=cp.pair(a['request_id'],b['request_id']);out.update(comparison_family='true_prefix_addition',path_id=path,path_family=a['request_family'],
                path_strategy=a.get('strategy'),threshold=a.get('threshold'),k_from=a['k'],k_to=b['k'],added_worker=b.get('added_worker'))
            sa,sb=cp.states[a['team_id']],cp.states[b['team_id']]
            if sa is not None and sb is not None:out.update(transition(sa,sb))
            changes.append(out)
    counts['prefix_transitions']=write_csv_gz(target/'prefix_transitions.csv.gz',changes)
    # Random same-k panel: exactly the registered independent draws and true uniform prefixes, duplicate teams collapsed.
    random=defaultdict(dict)
    for r in rows:
        if r['request_family'] in ('uniform_prefix','independent_random_team'):random[r['k']].setdefault(r['team_id'],r)
    pairs=[]
    for k,g in random.items():
        for a,b in combinations(sorted(g.values(),key=lambda r:r['team_id']),2):
            out=cp.pair(a['request_id'],b['request_id']);out.update(comparison_family='random_same_k',random_family_a=a['request_family'],random_family_b=b['request_family']);pairs.append(out)
    counts['random_same_k']=write_csv_gz(target/'random_same_k.csv.gz',pairs)
    # Explicit controlled vectors: compare all actual member variants, retaining same/different vector labels.
    composition_groups=defaultdict(list)
    for r in rows:
        if r['request_family'] in ('cluster_oracle','profile_composition'):
            key=(r['request_family'],r['k'],r.get('threshold'),r.get('scheme'),r.get('candidate_pool'))
            composition_groups[key].append(r)
    composition_pairs=[]
    for key,g in composition_groups.items():
        seen=set()
        for a,b in combinations(sorted(g,key=lambda r:r['request_id']),2):
            sig=(min(a['team_id'],b['team_id']),max(a['team_id'],b['team_id']))
            if sig in seen:continue
            seen.add(sig);out=cp.pair(a['request_id'],b['request_id'])
            out.update(comparison_family=key[0]+'_comparison',threshold=key[2],scheme=key[3],candidate_pool=key[4],
                strategy_a=a.get('strategy'),strategy_b=b.get('strategy'),composition_a=a.get('composition'),composition_b=b.get('composition'),
                same_composition=a.get('composition')==b.get('composition'),draw_a=a.get('draw_id'),draw_b=b.get('draw_id'))
            composition_pairs.append(out)
    counts['composition_comparisons']=write_csv_gz(target/'composition_comparisons.csv.gz',composition_pairs)
    # Any forward/origin/behavior policy: compare within its exact candidate pool and metric, then registered all-pool random as separately named baseline.
    policies=defaultdict(list)
    for r in rows:
        if r['request_family'] in ('profile_policy','behavior_policy','origin_random'):
            policies[(r['k'],r.get('selection_metric'),r.get('candidate_pool'))].append(r)
    policy_pairs=[]
    for key,g in policies.items():
        for a,b in combinations(sorted(g,key=lambda r:r['request_id']),2):
            out=cp.pair(a['request_id'],b['request_id']);out.update(comparison_family='policy_same_candidate_pool',
                strategy_a=a.get('strategy'),strategy_b=b.get('strategy'),selection_metric=key[1],candidate_pool=key[2]);policy_pairs.append(out)
        if key[2]=='Q_history_supported_all_origins':
            baseline=[r for r in rows if r['request_family']=='independent_random_team' and r['k']==key[0]]
            for a in g:
                for b in baseline:
                    out=cp.pair(a['request_id'],b['request_id']);out.update(comparison_family='policy_vs_full_pool_random',
                        strategy_a=a.get('strategy'),strategy_b='full_pool_random',selection_metric=key[1],candidate_pool=key[2]);policy_pairs.append(out)
    counts['policy_comparisons']=write_csv_gz(target/'policy_comparisons.csv.gz',policy_pairs)
    receipt=dict(pool_id=pool['pool_id'],**counts,seconds=time.monotonic()-start);save(target/'DONE.json',receipt)
    return receipt

def merge_files(family,initial_only=False):
    files=sorted((OUT/('comparisons_initial' if initial_only else 'comparisons')).glob('*/'+family+'.csv.gz'));fields=[];n=0
    for p in files:
        with gzip.open(p,'rt',encoding='utf-8-sig',newline='') as f:
            fields.extend(k for k in next(csv_module.reader(f),[]) if k not in fields)
    destination=OUT/(('INITIAL_' if initial_only else '')+family+'.csv.gz')
    temporary=destination.with_name(destination.name+'.tmp.'+uuid.uuid4().hex)
    # Materialize the complete compressed stream before touching a disk file.
    # This does not retain all uncompressed rows and prevents an incomplete
    # compression stream from becoming a partially synchronized artifact.
    memory=io.BytesIO()
    with gzip.GzipFile(fileobj=memory,mode='wb',compresslevel=6,mtime=0) as gz:
        with io.TextIOWrapper(gz,encoding='utf-8-sig',newline='') as f:
            writer=csv_module.DictWriter(f,fieldnames=fields);writer.writeheader()
            for p in files:
                with gzip.open(p,'rt',encoding='utf-8-sig',newline='') as rf:
                    for row in csv_module.DictReader(rf):writer.writerow(row);n+=1
    packed=memory.getvalue()
    with temporary.open('wb') as f:
        assert f.write(packed)==len(packed)
        f.flush();os.fsync(f.fileno())
    # A finished, CRC-valid file is published only after the compressor closes.
    actual=0
    with gzip.open(temporary,'rt',encoding='utf-8-sig',newline='') as f:
        reader=csv_module.DictReader(f)
        for _ in reader:actual+=1
    assert actual==n,'merged_comparison_row_count_mismatch'
    temporary.replace(destination)
    return n

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--jobs',type=int,default=3);ap.add_argument('--pilot',action='store_true');ap.add_argument('--pool',action='append');ap.add_argument('--merge-only',action='store_true');ap.add_argument('--initial-only',action='store_true');args=ap.parse_args()
    writer_lock=(OUT/('comparison_writer_initial.lock' if args.initial_only else 'comparison_writer_full.lock')).open('a+')
    try:fcntl.flock(writer_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:raise RuntimeError('another comparison writer holds this output namespace; wait for it to finish rather than overwrite it')
    if not args.merge_only:
        pools=load_pools();wanted=set(args.pool) if args.pool else set(read(OUT/'DESIGN.json')['pilot_pool_ids']) if args.pilot else None
        pools=[p for p in pools if (OUT/'pools'/p['pool_id']/'context.json').exists() and (wanted is None or p['pool_id'] in wanted)]
        started=time.monotonic();done=[]
        if args.jobs==1:
            for p in pools:done.append(process_pool(p,args.initial_only));print(json.dumps(done[-1]),flush=True)
        else:
            with ProcessPoolExecutor(max_workers=args.jobs) as ex:
                futures={ex.submit(process_pool,p,args.initial_only):p['pool_id'] for p in pools}
                for future in as_completed(futures):
                    r=future.result();done.append(r)
                    if len(done)%10==0 or len(done)==len(pools):print('comparison_pools',len(done),len(pools),'elapsed',round(time.monotonic()-started,1),flush=True)
    families=('replacements','prefix_transitions','random_same_k','composition_comparisons','policy_comparisons')
    totals={family:merge_files(family,args.initial_only) for family in families};save(OUT/(('INITIAL_' if args.initial_only else '')+'COMPARISON_COVERAGE.json'),totals);print(totals,flush=True)

if __name__=='__main__':main()
