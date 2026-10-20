"""Independent fixed P05 replication and finite-population mechanism audit.

Only jtcx-03, frozen n5 1:3:1 and the three pure constituents. No new fusion,
ratio search, reference or score. Wall offsets are a descriptive local view.
"""
from __future__ import annotations
import collections,hashlib,itertools,json,math,os,random,sys
from pathlib import Path
for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from shapely.geometry import Polygon
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'interchangeability_20261020';OUT=BASE/'independent/p05_local'
sys.path.insert(0,str(ROOT/'analysis/composition'));sys.path.insert(0,str(BASE/'independent'));sys.path.insert(0,str(BASE/'code'))
from design_history_panel import read,write,digest,team_key
from design_blocks import labels_from,counts
from summarize_blocks import csv_write
import pair_diagnostics as px
import geometry_diagnostics as gd
PID='jtcxE69GiFV-03__manual__cff6e9a2b3';METHOD='F20_newCommon_Full_balanced_K3'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def vkey(v):return '|'.join(f'{c}:{v.get(c,0)}' for c in ['C01','C02','C03'])

def geometry(t,ref,refpoints):
    footprint=(t.get('geometry') or {}).get('footprint');points=(t.get('geometry') or {}).get('points')
    diag=gd.diagnose(footprint,ref);row={k:diag.get(k) for k in ['diag_status','diag_wall_coverage_03','diag_wall_coverage_05','diag_corner_recall_05']};walls=[]
    if footprint is None:return row,walls
    cand=np.asarray(footprint,float);rp=np.asarray(ref,float);scale=math.sqrt(Polygon(rp).area)
    row['area_ratio']=Polygon(cand).area/Polygon(rp).area if Polygon(cand).is_valid else None
    if len(cand)!=4 or len(rp)!=4:return row,walls
    ii,jj=linear_sum_assignment(np.linalg.norm(rp[:,None,:]-cand[None,:,:],axis=2));mapping=dict(zip(ii,jj))
    adjacent=all((mapping[(i+1)%4]-mapping[i])%4 in [1,3] for i in range(4));row['four_corner_adjacency_preserved']=adjacent
    if not adjacent:return row,walls
    signed=np.sum(rp[:,0]*np.roll(rp[:,1],-1)-rp[:,1]*np.roll(rp[:,0],-1));orientation=1 if signed>0 else -1
    pts=np.asarray(points,float) if points is not None else None
    coverage={x['reference_ring_edge_index']:x['coverage'] for x in (diag.get('diag_wall_details_05') or [])}
    for i in range(4):
        j=(i+1)%4;a,b=rp[i],rp[j];u=(b-a)/np.linalg.norm(b-a);normal=orientation*np.array([u[1],-u[0]])
        p,q=cand[mapping[i]],cand[mapping[j]];cv=q-p
        angle=math.degrees(math.acos(np.clip(abs(np.dot(u,cv))/np.linalg.norm(cv),0,1)))
        offset=float((np.dot(p-a,normal)+np.dot(q-b,normal))/2)
        z=dict(reference_edge=i,reference_node_start=i,reference_node_end=j,reference_start=a.tolist(),reference_end=b.tolist(),direction_difference_deg=angle,signed_outward_offset_camera_h=offset,signed_outward_offset_ref_scale=offset/scale,parallel_within_10deg=angle<=10,wall_coverage_05=coverage.get(i))
        if pts is not None:
            z['bottom_y_signed_deg_at_start']=float((pts[2*mapping[i]+1,1]-refpoints[2*i+1][1])*180/512)
            z['top_y_signed_deg_at_start']=float((pts[2*mapping[i],1]-refpoints[2*i][1])*180/512)
        walls.append(z)
    return row,walls

def main():
    OUT.mkdir(parents=True,exist_ok=True);census=BASE/'ratio_grid/local_census';request=census/'requests.json.gz';cd=read(request)
    snap_path=ROOT/'restored/work_personnel_typing_A_20261019/recovered/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz';pool=next(p for p in read(snap_path)['images'] if p['pool_id']==PID)
    labels=labels_from([BASE/'forward/worker_labels.csv.gz'])[METHOD,'all'];origin={r['worker_id']:r['origin'] for r in pool['records']}
    groups={cl:sorted(w for w in labels if labels[w]==cl and origin.get(w)=='new') for cl in ['C01','C02','C03']}
    assert {c:len(w) for c,w in groups.items()}=={'C01':8,'C02':8,'C03':8}
    vectors=[{'C01':1,'C02':3,'C03':1}]+[{cl:5} for cl in groups]
    expected={}
    for v in vectors:
        populations=[itertools.combinations(groups[cl],n) for cl,n in sorted(v.items())]
        expected[vkey(v)]={tuple(sorted(w for part in parts for w in part)) for parts in itertools.product(*populations)}
    nativefile=census/'native/pools'/(PID+'.json.gz');native={t['team_key']:t for t in read(nativefile)['teams']}
    events=collections.defaultdict(list)
    for e in cd['events']:
        assert e['method_id']==METHOD and e['pool_id']==PID and e['n']==5 and e['reference_id']==pool['meta']['reference_id']
        assert counts(e['workers'],labels)==e['class_counts'];assert e['team_key']==team_key(PID,e['workers'])
        t=native[e['team_key']];assert t['member_workers']==e['workers']
        events[vkey(e['class_counts'])].append(e)
    assert set(native)=={e['team_key'] for e in cd['events']}
    for key,es in events.items():assert len(es)==len(expected[key]) and {tuple(e['workers']) for e in es}==expected[key]
    replicafile=BASE/'ratio_grid/replication_requests.json.gz';rd=read(replicafile)
    re=[e for e in rd['events'] if e['method_id']==METHOD and e['pool_id']==PID and e['n']==5]
    rnfile=BASE/'ratio_grid/native_replication/pools'/(PID+'.json.gz');rn={t['team_key']:t for t in read(rnfile)['teams']}
    assert len(re)==64 and all(len([e for e in re if vkey(e['class_counts'])==key])==16 for key in expected)
    parity=0.0
    for e in re:
        a,b=rn[e['team_key']],native[e['team_key']];assert a['geometry']==b['geometry'] and a['member_workers']==b['member_workers']
        for key in ['B8L2','D10','nodes','ref_node_recall_9','ref_edge_recall_9']:
            assert a[key] is not None and b[key] is not None;parity=max(parity,abs(float(a[key])-float(b[key])))
    assert parity<=1e-10
    rows=[];wallrows=[];summary=[]
    for phase,es,teams in [('replication16',re,rn),('census',cd['events'],native)]:
        for e in es:
            t=teams[e['team_key']];vec=vkey(e['class_counts']);diag,walls=geometry(t,pool['reference']['floor_xz_h'],pool['reference']['points_1024x512'])
            record=dict(phase=phase,vector=vec,team_key=e['team_key'],workers='|'.join(e['workers']),**{k:t.get(k) for k in ['B8L2','D10','IoU3D100','nodes','complete_evaluable','score_status','ref_node_recall_9','ref_edge_recall_9','omission','extension','height_mean_ratio','S_bottom_deg']},**diag);rows.append(record)
            wallrows.extend(dict(phase=phase,vector=vec,team_key=e['team_key'],**w) for w in walls)
    frame=pd.DataFrame(rows);walls=pd.DataFrame(wallrows)
    for (phase,vector),g in frame.groupby(['phase','vector']):
        q=g.B8L2.dropna();row=dict(phase=phase,vector=vector,actual_teams=len(g),Q_known=len(q),failure_teams=int((~g.complete_evaluable).sum()),Q_mean=q.mean(),Q_min=q.min(),Q_p10=q.quantile(.1),Q_p90=q.quantile(.9),Q_population_sd=q.std(ddof=0),nodes_distribution=json.dumps(g.nodes.value_counts().sort_index().to_dict()))
        for key in ['D10','IoU3D100','ref_node_recall_9','ref_edge_recall_9','omission','extension','height_mean_ratio','S_bottom_deg','diag_wall_coverage_05','diag_corner_recall_05','area_ratio']:row[key+'_mean']=pd.to_numeric(g[key],errors='coerce').mean()
        summary.append(row)
    summary=pd.DataFrame(summary);csv_write(summary,OUT/'TEAM_COMPOSITION_SUMMARY.csv');csv_write(frame,OUT/'FINAL_TEAM_GEOMETRY_DIAGNOSTICS.csv.gz')
    w=walls.groupby(['phase','vector','reference_edge']).agg(teams=('team_key','size'),signed_outward_offset_camera_h=('signed_outward_offset_camera_h','mean'),signed_outward_offset_ref_scale=('signed_outward_offset_ref_scale','mean'),parallel_within_10deg_fraction=('parallel_within_10deg','mean'),wall_coverage_05=('wall_coverage_05','mean'),bottom_y_signed_deg_at_start=('bottom_y_signed_deg_at_start','mean'),top_y_signed_deg_at_start=('top_y_signed_deg_at_start','mean')).reset_index();csv_write(w,OUT/'REFERENCE_WALL_OFFSETS.csv')
    # Validate declared finite pair set and a hash-chosen small metric sample.
    pairfile=census/'results/declared_pair_sample.csv.gz';pairs=pd.read_csv(pairfile);sample=[];maxerr=0.0;cache={}
    bycid=collections.defaultdict(list)
    for e in cd['events']:bycid[e['composition_id']].append(e)
    for cid,es in bycid.items():
        n=len(es);pop=math.comb(n,2);target=min(pop,2000)
        if pop<=2000:indices=list(itertools.combinations(range(n),2))
        else:
            rng=random.Random(int(digest([cd['spec']['pair_seed'],cid])[:16],16));seen=set()
            while len(seen)<target:seen.add(tuple(sorted(rng.sample(range(n),2))))
            indices=sorted(seen)
        desired={(es[i]['team_key'],es[j]['team_key']) for i,j in indices};g=pairs[pairs.composition_id==cid]
        assert len(g)==target and set(zip(g.a_team_key,g.b_team_key))==desired
        sample.extend(g.assign(hash=[digest([a,b]) for a,b in zip(g.a_team_key,g.b_team_key)]).sort_values('hash').head(3).to_dict('records'))
    for s in sample:
        m=px.pair_metrics(native[s['a_team_key']],native[s['b_team_key']],cache=cache)
        for key in ['both_complete','turnover','B8L2_change','abs_B8L2_change','joint_stable_main','geometry_noQ_main','geometry_shape_main','floor_jaccard_difference','bottom_y_absdiff_deg_p95','top_y_absdiff_deg_p95','mean_height_prism_pair_iou']:
            a,b=s[key],m[key]
            if pd.isna(a):assert b is None
            else:maxerr=max(maxerr,abs(float(a)-float(b)))
    assert maxerr<=1e-10
    parent=pd.read_csv(census/'results/finite_population_summary.csv');scerr=0
    for _,r in parent.iterrows():
        e=bycid[r.composition_id][0];g=summary[(summary.phase=='census')&(summary.vector==vkey(e['class_counts']))].iloc[0]
        for a,b in [('B8L2_mean','Q_mean'),('D10_mean','D10_mean'),('Q_min','Q_min'),('Q_p10','Q_p10'),('Q_p90','Q_p90'),('Q_population_sd','Q_population_sd')]:scerr=max(scerr,abs(r[a]-g[b]))
    assert scerr<=1e-10
    gains=[]
    for phase,g in summary.groupby('phase'):
        mix=g[g.vector=='C01:1|C02:3|C03:1'].iloc[0];pure=g[g.vector!='C01:1|C02:3|C03:1'];best=pure.loc[pure.Q_mean.idxmax()]
        gains.append(dict(phase=phase,mixed_mean=mix.Q_mean,best_pure_vector=best.vector,best_pure_mean=best.Q_mean,gain=mix.Q_mean-best.Q_mean,mixed_min=mix.Q_min,best_pure_by_mean_min=best.Q_min,mixed_p10=mix.Q_p10,best_pure_by_mean_p10=best.Q_p10))
    receipt=dict(schema='independent_p05_fixed_local_mechanism_audit_v1',pool_id=PID,method_id=METHOD,independent_images=1,independent_buildings=1,workers=24,reference_id=pool['meta']['reference_id'],reference_nodes=4,exact_census_teams=len(native),exact_mixture_population=3584,pure_populations=56,all_concrete_team_sets_verified=True,replication16_teams=64,replication_vs_census_geometry_exact=True,replication_vs_census_max_Q_D10_node_error=parity,declared_pairs_verified=len(pairs),independently_recomputed_pair_metrics=12,pair_max_error=maxerr,independently_reaggregated_census_max_error=scerr,gains=gains,all_native_fusion_rerun_by_this_audit=False,sources={str(p.relative_to(ROOT)):sha(p) for p in [request,nativefile,replicafile,rnfile,pairfile,snap_path,Path(__file__)]},limitations='Result-driven local mechanism study, not another validation set. Signed wall offsets use minimum-distance one-to-one correspondence only for four-corner adjacency-preserving rings; positive is outward, units are frozen camera height, not metres. They are not a changed score or necessary-structure truth. Native uses medoid-anchored coordinate medians, not arithmetic mean fusion. Final geometry cannot establish net correction without each initial geometry.')
    write(OUT/'P05_LOCAL_AUDIT.json',receipt);write(OUT/'REFERENCE_WALL_INDEX.json',dict(reference_id=pool['meta']['reference_id'],floor_xz_h=pool['reference']['floor_xz_h'],points_1024x512=pool['reference']['points_1024x512'],wall_i='floor ring vertex i to (i+1)%4, matching the fixed reference array',signed_offset='Positive outward from reference; per candidate endpoints averaged along fixed reference normal. No registration/alignment or reference change.'))
    print(json.dumps({'gains':gains,'census_teams':len(native),'pair_error':maxerr,'summary_error':scerr},ensure_ascii=False))

if __name__=='__main__':main()
