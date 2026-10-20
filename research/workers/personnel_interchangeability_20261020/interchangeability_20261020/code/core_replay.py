"""Prepare and actually re-fuse the compact, named core-result replay panel.

prepare reads prior native outputs only to freeze small expected final-result
fingerprints. run must use a new cache directory and performs native fusion and
fixed scoring; it compares the results, then recomputes the paired main tables.
No whole-team state, distance matrices, or source image archive is included.
"""
from __future__ import annotations
import argparse, collections, copy, gzip, hashlib, json, math, os, subprocess, sys
from pathlib import Path
import numpy as np
import pandas as pd
from design_history_panel import read, write, digest, team_key
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'analysis/composition'))
sys.path.insert(0,str(ROOT/'interchangeability_20261020/independent'))
import pair_diagnostics
from replay_cases import compare

FIELDS=['B8L2','D10','IoU3D100','iou_2d','omission','extension','nodes','node_supports',
 'minimum_support','complete_evaluable','complete_floor_evaluable','score_status',
 'geometry_reason','reference_id','reference_version','member_object_ids','member_workers',
 'pool_id','team_key','k','image','image_id','building','layer','condition',
 'ref_node_recall_9','ref_edge_recall_9','height_mean_ratio',
 'source_time_known_n','source_time_total_seconds','target_time_known_n','target_time_total_seconds']
PAIR_FIELDS=['joint_stable_strict','joint_stable_main','joint_stable_wide',
 'geometry_noQ_main','geometry_shape_main','floor_jaccard_difference',
 'bottom_y_absdiff_deg_p95','top_y_absdiff_deg_p95','abs_B8L2_change']


def select_batches(study):
    out=[]
    d=read(study/'assessment/direction_requests.json.gz')
    names={'F20_highQ23_T_qK2':{'C02>C01':'F01_time'},
      'F20_all_QTG_balanced_medoids_K4':{'C04>C02':'F04_QTG_down','C02>C04':'F05_QTG_up'}}
    for mid,dirs in names.items():
        for direction,name in dirs.items():
            ev=[e for e in d['events'] if e['method_id']==mid and e['direction']==direction and e['context_id']=='fixed_n13_m2']
            out.append((name,'assessment/native_directions',d,ev))
    d=read(study/'assessment/nested_new2_requests.json.gz')
    co=read(study/'reverse/assessment_interpretation/nested_new2/METADATA_COHORTS.json')
    eligible=set(next(c['pools'] for c in co if c['cohort']=='fixed_capacity_both_m_n13'))
    for direction in ['C01>C02','C02>C01']:
        for m in [2,5]:
            ev=[e for e in d['events'] if e['n']==13 and e['m']==m and e['direction']==direction and e['pool_id'] in eligible]
            assert len(ev)==58
            out.append(('Rnew2_'+direction+'_m'+str(m),'assessment/native_nested_new2',d,ev))
    d=read(study/'independent/baseline/REQUESTS.json.gz')
    eventdf=pd.read_csv(study/'independent/baseline/EVENT_DESIGN.csv.gz')
    req={r['team_key']:r for r in d['requests']}
    for target,n,m in [('G',17,8),('R',13,2)]:
        rows=eventdf[(eventdf.target==target)&(eventdf.k==n)&(eventdf.m==m)&(eventdf.historical_phase=='validation')]
        ev=[]
        for e in rows.to_dict('records'):
            # only finite, used metadata enters this compact event.
            e={k:v for k,v in e.items() if not(isinstance(v,float) and math.isnan(v))}
            e['n']=int(e['k']);e['phase']='assessment_reused_v2'
            for arm in 'ABC':
                e[arm+'_workers']=req[e[arm+'_team_key']]['worker_ids']
                e[arm+'_counts']={k:int(v) for k,v in (z.split(':') for z in e[arm+'_counts'].split('|')) if int(v)}
            e['core_workers']=sorted(set(e['A_workers'])&set(e['B_workers']));ev.append(e)
        out.append(('old_'+target+'_anchor','independent/baseline/native_runs',d,ev))
    d=read(study/'independent/mixed_challenge/assessment_requests.json.gz')
    ev=[e for e in d['events'] if e['method_id']=='F20_highQ23_T_qK2' and e['n']==7 and e['m']==7 and e['A_counts']=={'C01':5,'C02':2}]
    out.append(('mixed_highQ23_5fast_2slow','independent/mixed_challenge/native_assessment',d,ev))
    for name,request,native in [
      ('ratio_assessment_all5','ratio_grid/assessment_requests.json.gz','ratio_grid/native_assessment'),
      ('finite_census_P05','ratio_grid/local_census/requests.json.gz','ratio_grid/local_census/native'),
      ('W132_fixed_support_probe','assessment/w132_probe_requests.json.gz','assessment/native_w132_probe')]:
        d=read(study/request);out.append((name,native,d,d.get('events',[])))
    return out


def event_stats(event,rows):
    A,B,C=[rows[event[a+'_team_key']] for a in 'ABC']
    ab=pair_diagnostics.pair_metrics(A,B,cache={});ac=pair_diagnostics.pair_metrics(A,C,cache={})
    def finite(x):return x is not None and math.isfinite(x)
    def delta(x,y):return float(x-y) if finite(x) and finite(y) else None
    r=dict(group=event['replay_group'],event_id=event['event_id'],pool_id=event['pool_id'],
      image=A['image_id'],building=A['building'],n=int(event['n']),m=int(event['m']),
      net_B8L2_change=delta(C.get('B8L2'),B.get('B8L2')),net_D10_change=delta(C.get('D10'),B.get('D10')),
      A_complete=A.get('complete_evaluable'),B_complete=B.get('complete_evaluable'),C_complete=C.get('complete_evaluable'))
    for side,pair in [('within',ab),('cross',ac)]:
        r.update({side+'_'+k:pair.get(k) for k in PAIR_FIELDS})
    return r


def aggregate(stats):
    df=pd.DataFrame(stats);cols=[c for c in df if c not in ['group','event_id','pool_id','image','building','n','m']]
    if not len(df):return pd.DataFrame()
    image=df.groupby(['group','building','image'],dropna=False)[cols].mean()
    out=image.groupby(['group','building']).mean().groupby('group').mean().reset_index()
    support=df.groupby('group').agg(events=('event_id','size'),images=('image','nunique'),buildings=('building','nunique')).reset_index()
    return out.merge(support,on='group')


def assert_event(e):
    if 'A_team_key' not in e:return
    sets={a:set(e[a+'_workers']) for a in 'ABC'}
    assert all(len(ws)==e['n'] for ws in sets.values())
    assert sets['A']&sets['B']==sets['A']&sets['C']==set(e['core_workers'])
    assert len(sets['A']-sets['B'])==len(sets['A']-sets['C'])==e['m']
    assert e['A_counts']==e['B_counts'] and e['A_counts']!=e['C_counts']
    for arm in 'ABC':assert team_key(e['pool_id'],sets[arm])==e[arm+'_team_key']


def prepare(study,out):
    out.mkdir(parents=True,exist_ok=True);requests={};expected={};events=[];coverage=[];expected_stats=[]
    for name,native_rel,payload,selected in select_batches(study):
        selected=copy.deepcopy(selected)
        keys={e[a+'_team_key'] for e in selected if 'A_team_key' in e for a in 'ABC'}
        keys|={e['team_key'] for e in selected if 'team_key' in e}
        # Probe includes parent baseline teams in its request payload as well.
        if name=='W132_fixed_support_probe':keys={team_key(r['pool_id'],r['worker_ids']) for r in payload['requests']}
        requestmap={team_key(r['pool_id'],r['worker_ids']):r for r in payload['requests']}
        bypool=collections.defaultdict(set)
        for k in keys:
            r=requestmap[k];requests[k]=dict(request_id=k,pool_id=r['pool_id'],k=r['k'],worker_ids=sorted(r['worker_ids']));bypool[r['pool_id']].add(k)
        rows={}
        for pid,wanted in sorted(bypool.items()):
            native=read(study/native_rel/'pools'/(pid+'.json.gz'))
            available={t['team_key']:t for t in native['teams']}
            for tk in wanted:
                t=available[tk];r=requests[tk]
                assert t['member_workers']==r['worker_ids'] and len(r['worker_ids'])==r['k']
                e={k:t.get(k) for k in FIELDS};e['geometry_sha256']=digest(t.get('geometry'))
                if tk in expected:assert expected[tk]==e
                expected[tk]=e;rows[tk]=t
        for e in selected:
            e['replay_group']=name
            if 'A_team_key' in e:
                assert_event(e)
                if name!='W132_fixed_support_probe':expected_stats.append(event_stats(e,rows))
            events.append(e)
        coverage.append(dict(group=name,events=len(selected),unique_fusion_tasks=len(keys),pools=len(bypool),
          images=len({r['image_id'] for r in rows.values()}),buildings=len({r['building'] for r in rows.values()}),
          people=len({w for r in rows.values() for w in r['member_workers']}),original_native_directory=native_rel))
        print(name,len(keys),'teams',flush=True)
    ordered=[requests[k] for k in sorted(requests)]
    write(out/'CORE_REQUESTS.json.gz',dict(schema='core_final_directory_replay_v1',requests=ordered,events=events,
      scope='Named F01/F04/F05, Rnew2 n13 fixed-capacity four cells, old G/R anchor redraws, high-Q whole-team n7, all five ratio assessment populations, full local census, and W132 same-support probe.'))
    write(out/'EXPECTED_FINAL_FIELDS.json.gz',[expected[k] for k in sorted(expected)])
    pd.DataFrame(expected_stats).to_csv(out/'EXPECTED_PAIRED_EVENTS.csv.gz',index=False,compression='gzip')
    aggregate(expected_stats).to_csv(out/'EXPECTED_CORE_AGGREGATES.csv',index=False)
    pd.DataFrame(coverage).to_csv(out/'CORE_REPLAY_COVERAGE.csv',index=False)
    write(out/'CORE_PREPARATION.json',dict(coverage=coverage,unique_fusion_tasks=len(requests),
      unique_crews=len({tuple(r['worker_ids']) for r in ordered}),
      requests_sha256=hashlib.sha256((out/'CORE_REQUESTS.json.gz').read_bytes()).hexdigest(),
      expected_sha256=hashlib.sha256((out/'EXPECTED_FINAL_FIELDS.json.gz').read_bytes()).hexdigest(),
      numerical_and_final_geometry_fingerprints_only=True,full_native_states_included=False))


def run(bundle,restored,native_out,report,jobs):
    report.mkdir(parents=True,exist_ok=True)
    if native_out.exists() and list(native_out.glob('pools/*.json.gz')):
        raise ValueError('Use a new native-out directory: the delivery check must actually re-fuse every core team.')
    cmd=[sys.executable,str(ROOT/'analysis/composition/fusion_runner.py'),'--restored',str(restored.resolve()),
      '--requests',str((bundle/'CORE_REQUESTS.json.gz').resolve()),'--out',str(native_out.resolve()),'--jobs',str(jobs)]
    subprocess.run(cmd,check=True)
    payload=read(bundle/'CORE_REQUESTS.json.gz');expected={t['team_key']:t for t in read(bundle/'EXPECTED_FINAL_FIELDS.json.gz')}
    bypool=collections.defaultdict(list)
    for r in payload['requests']:bypool[r['pool_id']].append(r)
    allrows={};failures=[];maxdiff=0.;counts=collections.Counter()
    for pid,requests in sorted(bypool.items()):
        native=read(native_out/'pools'/(pid+'.json.gz'));rows={t['team_key']:t for t in native['teams']}
        for r in requests:
            tk=team_key(pid,r['worker_ids']);t=rows[tk];old=expected[tk]
            assert len(r['worker_ids'])==len(set(r['worker_ids']))==r['k']
            assert t['member_workers']==r['worker_ids']
            for field in FIELDS:
                ok,diff=compare(old[field],t.get(field))
                if not ok:failures.append(dict(team_key=tk,field=field))
                if diff is not None:maxdiff=max(maxdiff,diff)
            if digest(t.get('geometry'))!=old['geometry_sha256']:failures.append(dict(team_key=tk,field='exact_geometry_sha256'))
            counts[t['score_status']]+=1;allrows[tk]=t
    stats=[]
    for e in payload['events']:
        if 'A_team_key' in e:
            assert_event(e)
            if e['replay_group']!='W132_fixed_support_probe':stats.append(event_stats(e,allrows))
    got=aggregate(stats);wanted=pd.read_csv(bundle/'EXPECTED_CORE_AGGREGATES.csv')
    assert got.group.tolist()==wanted.group.tolist()
    for col in wanted:
        if col=='group':continue
        if not np.allclose(got[col].to_numpy(float),wanted[col].to_numpy(float),equal_nan=True,atol=1e-9,rtol=0):
            failures.append(dict(field='aggregate:'+col))
    got.to_csv(report/'REPLAYED_CORE_AGGREGATES.csv',index=False)
    pd.DataFrame(stats).to_csv(report/'REPLAYED_PAIRED_EVENTS.csv.gz',index=False,compression='gzip')
    comps=[]
    for e in payload['events']:
        if 'team_key' in e and e['replay_group'] in ['finite_census_P05','ratio_assessment_all5']:
            t=allrows[e['team_key']];comps.append(dict(group=e['replay_group'],composition_id=e['composition_id'],
              pool_id=e['pool_id'],class_counts=json.dumps(e['class_counts'],sort_keys=True),B8L2=t['B8L2'],D10=t['D10'],complete=t['complete_evaluable']))
    pd.DataFrame(comps).groupby(['group','pool_id','composition_id','class_counts']).agg(
      teams=('B8L2','size'),scored=('B8L2','count'),B8L2_mean=('B8L2','mean'),D10_mean=('D10','mean'),
      B8L2_min=('B8L2','min'),complete=('complete','mean')).reset_index().to_csv(report/'REPLAYED_COMPOSITIONS.csv.gz',index=False,compression='gzip')
    native_receipt=read(native_out/'RUN_CORE_REQUESTS.json')
    result=dict(all_passed=not failures,failures=failures,unique_fusion_tasks=len(allrows),
      unique_crews=len({tuple(t['member_workers']) for t in allrows.values()}),pools=len(bypool),
      true_images=len({t['image_id'] for t in allrows.values()}),buildings=len({t['building'] for t in allrows.values()}),
      people=len({w for t in allrows.values() for w in t['member_workers']}),
      checked_native_fields_per_team=len(FIELDS),final_geometry_sha256_checked_every_team=True,
      max_numeric_difference=maxdiff,status_counts=dict(counts),paired_events_recomputed=len(stats),
      fields_tolerance=1e-9,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
      package_code_root=str(ROOT),native_receipt=native_receipt,
      scope='Fresh native replay of exactly the compact core panel from the final lean code directory. Full search was not re-fused at delivery. Source frozen snapshot/scientific engine supplied by --restored; old outcome caches not read by run.')
    write(report/'CORE_REPLAY_RECEIPT.json',result)
    assert result['all_passed'],failures[:10]
    print(json.dumps({k:result[k] for k in ['all_passed','unique_fusion_tasks','true_images','buildings','people','max_numeric_difference']},ensure_ascii=False),flush=True)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['prepare','run']);ap.add_argument('--study',type=Path)
    ap.add_argument('--bundle',type=Path,required=True);ap.add_argument('--restored',type=Path);ap.add_argument('--native-out',type=Path)
    ap.add_argument('--report',type=Path);ap.add_argument('--jobs',type=int,default=3);a=ap.parse_args()
    if a.mode=='prepare':prepare(a.study,a.bundle)
    else:run(a.bundle,a.restored,a.native_out,a.report,a.jobs)


if __name__=='__main__':main()
