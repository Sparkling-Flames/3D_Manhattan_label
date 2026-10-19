#!/usr/bin/env python3
"""Sequential, explicit replay of audited inputs. Defaults to read-only verification.

Run from an independent extraction of all four delivery ZIPs:
  python work_v2_20261019/REPRODUCE.py --stage verify
  python work_v2_20261019/REPRODUCE.py --stage profiles --execute
  python work_v2_20261019/REPRODUCE.py --stage all --execute --fresh-fusion

The replay begins with audited frozen coordinates, never original collection.
"""
from pathlib import Path
import argparse,datetime,gzip,hashlib,json,os,shutil,subprocess,sys,time
WORK=Path(__file__).resolve().parent;ROOT=WORK.parent

def sha(p):
    h=hashlib.sha256()
    with open(p,'rb')as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()

def verify(full=False):
    path=WORK/'delivery/DELIVERY_MANIFEST.json'
    if not path.exists():raise SystemExit('DELIVERY_MANIFEST.json is required; extract the methods/data archive first.')
    manifest=json.loads(path.read_text());checks=[]
    for row in manifest['files']:
        p=ROOT/row['path'];exists=p.is_file()
        if not full and not(row['path'].startswith('repo_main_20261019/') or row['path'].endswith('.py')):continue
        actual=sha(p)if exists else None;checks.append({'path':row['path'],'exists':exists,'sha256_match':actual==row['sha256']})
    ok=all(r['sha256_match']for r in checks)
    out={'verification_only':True,'recomputed_models_or_fusions':False,'full_payload':full,'checked_files':len(checks),'all_passed':ok,'failures':[r for r in checks if not r['sha256_match']]}
    print(json.dumps(out,ensure_ascii=False,indent=2));return 0 if ok else 1

def command(script,*args):return [sys.executable,str(WORK/script),*map(str,args)]

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--stage',choices=['verify','audit','profiles','clusters','fusion','comparisons','summaries','reverse','report','viewer','all'],default='verify')
    ap.add_argument('--execute',action='store_true',help='Execute derived-output writes in this extracted copy; otherwise print the exact planned commands.')
    ap.add_argument('--full-hash',action='store_true',help='For verify, include all delivered results instead of only pinned source and code.')
    ap.add_argument('--fresh-fusion',action='store_true',help='Move this copy of fusion/pools to a dated backup before replay; no deletion. This forces actual new native fusions.')
    ap.add_argument('--fetch-originals',action='store_true',help='For viewer only, fetch Release bytes with existing hash checks; not needed for numerical replay or opening delivered HTML.')
    ap.add_argument('--jobs',type=int,default=3);a=ap.parse_args()
    if a.stage=='verify':raise SystemExit(verify(a.full_hash))
    plan={
      'audit':[command('audit/evidence_audit.py'),command('audit/replay_geometry.py'),command('audit/review_exclusion_text.py'),command('audit/analyze_semi.py'),command('audit/replay_integrated_statistics.py')],
      'profiles':[command('profiles/reproduce_forward_profiles.py','--repo',ROOT/'repo_main_20261019','--out',WORK/'profiles','--evidence',WORK/'audit/person_evidence_62.csv')],
      'clusters':[command('clusters/'+s)for s in ['build_clusters.py','audit_algorithms.py','summarize_clusters.py','reverse_ring_partition_sensitivity.py','version_cluster_sensitivity.py']],
      'fusion':[command('fusion/run_reproduction.py','--stage','initial','--jobs',a.jobs),command('fusion/run_reproduction.py','--stage','extension','--jobs',a.jobs),command('fusion/run_reproduction.py','--stage','verification')],
      'comparisons':[command('fusion/run_reproduction.py','--stage','comparisons','--jobs',a.jobs)],
      'summaries':[command('fusion/run_reproduction.py','--stage','summaries')],
      'reverse':[command('clusters/'+s)for s in ['cluster_transfer.py','swap_transfer.py','summarize_swap_transfer.py','forward_swap_labels.py','conditional_dtype_diagnostic.py','prefix_cluster_analysis.py','pair_history_diagnostic.py','expand_contrast_summaries.py','room_sensitivities.py','compact_swap_predictions.py']],
      'report':[command('presentation/build_cases.py'),command('presentation/make_figures.py'),command('presentation/build_delivery_evidence.py'),command('presentation/build_report.py')],
      'viewer':([command('fetch_original_images.py')]if a.fetch_originals else[])+[command('presentation/build_cases.py'),command('presentation/build_viewer.py')]
    }
    plan['reverse'][3:3]=[command('clusters/analyze_fusion_clusters.py','--replacements-only'),command('clusters/analyze_cluster_composition.py')]
    plan['reverse'] += [command('clusters/select_cluster_cases.py'),command('clusters/build_cluster_report.py')]
    stages=['audit','profiles','clusters','fusion','comparisons','summaries','reverse','report']if a.stage=='all'else[a.stage]
    if not a.execute:
        print(json.dumps({'execute':False,'stages':stages,'commands':[cmd for stage in stages for cmd in plan[stage]],'fresh_fusion_if_executed':a.fresh_fusion,'note':'Add --execute in an independent extracted copy. Existing native caches otherwise remain reusable; receipt reports actual new calls.'},ensure_ascii=False,indent=2));return
    if a.jobs<1:raise SystemExit('--jobs must be positive')
    if a.stage=='viewer':
        families=['replacements','random_same_k','composition_comparisons','policy_comparisons','prefix_transitions']
        with gzip.open(WORK/'clusters/CLUSTER_API.json.gz','rt')as f:pool_ids=[p['meta']['pool_id']for p in json.load(f)['pools']]
        missing=[str(Path(pid)/(family+'.csv.gz'))for pid in pool_ids for family in families if not(WORK/'fusion/comparisons'/pid/(family+'.csv.gz')).is_file()]
        if missing:
            raise SystemExit(f'Viewer requires the per-pool comparison tables ({len(missing)} missing). First run --stage comparisons --execute --jobs {a.jobs}. Delivered standalone HTML already contains its validated browse subset; no regeneration is needed just to open it.')
    lock=WORK/'REPRODUCE.running.lock'
    try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError:raise SystemExit('Another replay lock exists. Do not run concurrent writers; inspect the prior replay before removing a stale lock.')
    os.close(fd)
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');logdir=WORK/'replay_logs'/stamp;logdir.mkdir(parents=True)
    receipt={'started_utc':stamp,'stage':a.stage,'fresh_fusion':a.fresh_fusion,'audited_input_only':True,'original_collection_rebuilt':False,'steps':[]}
    try:
        if a.fresh_fusion:
            if 'fusion'not in stages:raise ValueError('--fresh-fusion requires --stage fusion or all')
            pool=WORK/'fusion/pools'
            if pool.exists():
                backup=WORK/'fusion'/('pools.before_replay_'+stamp);shutil.move(pool,backup);receipt['preserved_old_cache']=str(backup)
        for stage in stages:
            if stage=='reverse':
                old=WORK/'fusion/INITIAL_replacements.csv.gz'
                if not old.exists():
                    # Every fixed-background request is in the initial design. No
                    # extension creates such requests; the final replacement table
                    # is the same logical table, audited by the delivery receipts.
                    shutil.copy2(WORK/'fusion/replacements.csv.gz',old)
                    receipt['initial_replacement_alias']='Copied final replacement table; extensions contain no fixed-background requests.'
            for cmd in plan[stage]:
                num=len(receipt['steps'])+1;name=Path(cmd[1]).stem;start=time.monotonic();log=logdir/f'{num:02d}_{name}.log'
                print(f'[{num}] {stage}: {name}',flush=True)
                with log.open('w')as f:
                    cp=subprocess.run(cmd,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=False)
                receipt['steps'].append({'stage':stage,'command':cmd,'returncode':cp.returncode,'seconds':time.monotonic()-start,'log':str(log.relative_to(ROOT)),'script_sha256':sha(cmd[1])})
                (logdir/'REPLAY_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
                if cp.returncode:raise SystemExit(f'Replay stopped: {log}; prior results retained. Exit {cp.returncode}')
        print('Completed the requested stages. Inspect actual_new_fusions in native receipts; cache reuse is not fresh fusion.',flush=True)
    finally:lock.unlink(missing_ok=True)

if __name__=='__main__':main()
