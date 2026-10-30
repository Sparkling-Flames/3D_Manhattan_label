"""Check reconstructed original selection and affected stopping scores against v2.

Reuse saved current team geometry and the frozen scoring function with its old
reference; this does not rerun fusion and never changes current output scores.
"""
from pathlib import Path
import os,sys,importlib.util,json,gzip,hashlib
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
import pandas as pd
import numpy as np
from selection_stop_prepare import OUT,PORT,INP,OLD,REPLAY,read,save,native_pools,teamkey
from selection_stop_endpoints import iterjson

def main():
    pools=native_pools();oldpools={p['pool_id']:p for p in read(INP/'research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz')['images']}
    oldreplay={p['pool_id']:p for p in read(INP/REPLAY/'REPLAY_POOLS.json.gz')}
    req=pd.read_csv(OUT/'design/SELECTION_DESIGN.csv.gz');req=req[req.version=='v2_fixed_selection_current_score'];wanted=set(req.team_key)
    stop=pd.read_csv(INP/REPLAY/'replay_nodes.csv.gz',low_memory=False);stop['team_key']=[teamkey(p,ws.split('|')) for p,ws in zip(stop.pool_id,stop.member_workers)]
    affected=read(OUT/'design/STOPPING_CONTRACT.json')['affected_pools'];stop=stop[stop.pool_id.isin(affected)&(stop.k!=2)];wanted|=set(stop.team_key)
    os.environ['HOHONET_REPO']=str(PORT);p=PORT/'research/workers/personnel_v21_reselection_20261029/experiment/benchmark_engine.py';spec=importlib.util.spec_from_file_location('validated_frozen_engine',p);b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b);native=b.load_engine(PORT)
    rows=[];computed=0
    with native.Engine(full_state=False) as eng:
        for path in sorted((OUT/'endpoints/pools').glob('*.jsonl.gz')):
            pid=path.name[:-9];op=oldpools.get(pid,oldreplay.get(pid));assert op is not None,pid
            changed=op['reference']['points_1024x512']!=pools[pid]['reference']['points_1024x512']
            for r in iterjson(path):
                if r['team_key'] not in wanted:continue
                if changed and r.get('geometry') is not None:
                    state={'n':r['k'],'node_consensus':{'nodes':[{}]*int(r['nodes'])},'candidate':r['geometry']}
                    oldscore=eng.fe.compute_score(state,op,eng.engine,eng.models);computed+=1
                else:oldscore=r
                rows.append(dict(team_key=r['team_key'],pool_id=pid,v2_B8L2=oldscore.get('B8L2'),v2_D10=oldscore.get('D10'),reference_changed=changed,geometry_fusion_replayed=False))
    ep=pd.DataFrame(rows);assert ep.team_key.is_unique;save('validation/V2_REFERENCE_SCORES_FROM_SAVED_GEOMETRY.csv.gz',ep)
    z=req.merge(ep,on='team_key',validate='many_to_one');z['policy']=z.policy.str.replace(r'random_\d$','random',regex=True)
    keys=['condition','layer','scope_comparable','domain','n','policy']
    images=z.groupby(keys+['building','target_image'])[['v2_B8L2','v2_D10']].mean().reset_index();buildings=images.groupby(keys+['building'])[['v2_B8L2','v2_D10']].mean().reset_index();summary=buildings.groupby(keys)[['v2_B8L2','v2_D10']].mean().reset_index()
    historical=pd.read_csv(INP/OLD/'native_teams/POLICY_SUMMARY.csv');check=summary.merge(historical,on=keys,validate='one_to_one');check['error_B8L2']=check.v2_B8L2-check.B8L2;check['error_D10']=check.v2_D10-check.D10
    save('validation/ORIGINAL_POLICY_REPRODUCTION.csv',check)
    assert check.error_B8L2.abs().max()<1e-8 and check.error_D10.abs().max()<1e-8,check.nlargest(5,'error_B8L2')[keys+['error_B8L2']].to_dict('records')
    z=stop.merge(ep,on='team_key',validate='many_to_one');z['error_B8L2']=z.v2_B8L2-z.B8L2;z['error_D10']=z.v2_D10-z.D10
    assert z.v2_B8L2.notna().eq(z.B8L2.notna()).all() and z.v2_D10.notna().eq(z.D10.notna()).all()
    assert z.error_B8L2.abs().max()<1e-8 and z.error_D10.abs().max()<1e-8
    save('validation/STOPPING_OLD_SCORE_PARITY.csv.gz',z[['request_id','team_key','B8L2','v2_B8L2','error_B8L2','D10','v2_D10','error_D10']])
    save('validation/NUMERIC_RECONSTRUCTION_CHECKS.json',{'original_policy_summary_cells':len(check)*2,'policy_B8L2_max_error':float(check.error_B8L2.abs().max()),'policy_D10_max_error':float(check.error_D10.abs().max()),'affected_stopping_prefixes':len(z),'stopping_B8L2_max_error':float(z.error_B8L2.abs().max()),'stopping_D10_max_error':float(z.error_D10.abs().max()),'old_reference_score_computations_only':computed,'additional_fusion_calls':0,'all_passed':True})
    print('original selection and stopping reconstruction validated',flush=True)

if __name__=='__main__':main()
