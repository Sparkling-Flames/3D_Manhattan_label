#!/usr/bin/env python3
"""Part A replay coordinator. Default is read-only verification and a summary.

All execution occurs in a new explicitly named workspace. No source data,
retained result or cache is removed. Scientific methods live in their original
scripts; this module only copies the documented input layout and runs them.
"""
from __future__ import annotations
import argparse,csv,datetime,gzip,hashlib,importlib.metadata,json,os,shutil,subprocess,sys,time
from pathlib import Path

HERE=Path(__file__).resolve().parent
DEFAULT_SOURCE=HERE.parent
LEAF='work_personnel_typing_A_20261019'
PANELS={'Pro_exact_fixed_background_v1':270370,'A_nested_even_v1':16296}
CONFIG_FILES={
 'forward':['REGISTRATION.json','FEATURE_DOMAINS.json'],
 'reverse':['REGISTRATION.json','FROZEN_BUILDING_SPLITS.json','DESIGN_FREEZE_SHA256.json','EXPLANATION_REGISTRATION.json'],
 'assessment':['REGISTRATION.json'],
 'events':['DESIGN.json','REGISTRATION_RECEIPT.json','FIELD_CONTRACT.json','REQUESTS.json.gz','event_design.csv.gz','pool_members.csv.gz','nested_chains.csv.gz','nested_coverage.csv.gz','PILOT_REQUESTS_100.json.gz'],
}
AGGREGATE_FILES=[
 'forward/selected_classes_by_fold.csv.gz','forward/selected_classes_by_fold_D10.csv.gz',
 'forward/fold_features.csv.gz','reverse/explanations/rule_classes.csv.gz',
 'forward/full_selected_worker_portraits.csv.gz','reverse/results/worker_classmate_stability.csv',
]
REUSED_EVENT_FILES=['events/common_events.csv.gz','events/native_runs/team_results.csv']

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb')as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()
def savej(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp')
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf8');os.replace(tmp,path)
def loadj(path):return json.loads(Path(path).read_text(encoding='utf8'))
def csv_open(path):return gzip.open(path,'rt',encoding='utf-8-sig',newline='')if str(path).endswith('.gz')else Path(path).open('r',encoding='utf-8-sig',newline='')
def csv_header(path):
    with csv_open(path)as f:return next(csv.reader(f))
def runtime(root):
    pins={line.split('==')[0]:line.split('==')[1]for line in (root/'recovered/work_v2_20261019/requirements.txt').read_text().splitlines()if '=='in line}
    local={d.metadata['Name'].lower().replace('_','-'):d.version for d in importlib.metadata.distributions(path=[str(root/'deps')])}if (root/'deps').exists()else{}
    rows=[]
    for name,version in pins.items():
        lname=name.lower().replace('_','-');got=local.get(lname);source='workspace/deps'if got else 'active_python'
        if not got:
            try:got=importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:got=None
        rows.append({'package':name,'expected':version,'observed':got,'source':source,'matches':got==version})
    try:import fcntl  # noqa: F401
    except ImportError:posix_lock=False
    else:posix_lock=True
    return {'python':sys.version.split()[0],'platform':sys.platform,'fcntl_available':posix_lock,'packages':rows,'all_pins_match':all(x['matches']for x in rows),'tested_python_minor':'3.12'}

def verify(root,contract,deep=False):
    rows=[];errors=[]
    for name,want in contract['key_input_sha256'].items():
        p=root/name
        if not p.is_file():rows.append({'path':name,'status':'missing'});errors.append('missing '+name);continue
        got=sha(p);ok=got==want;rows.append({'path':name,'status':'match'if ok else'mismatch','sha256':got})
        if not ok:errors.append('SHA mismatch '+name)
    schemas=[]
    for name,spec in contract['verification_tables'].items():
        p=root/name
        if not p.exists():schemas.append({'path':name,'status':'absent_optional_result'if spec.get('optional')else'missing'});continue
        try:
            head=csv_header(p);missing=sorted(set(spec['required_columns'])-set(head))
            row={'path':name,'header_columns':len(head),'missing_required_columns':missing,'status':'schema_ok'if not missing else'schema_mismatch'}
            if missing:errors.append('schema '+name)
            if deep:
                n=0;keys=set();keycols=spec.get('unique_key',[])
                with csv_open(p)as f:
                    for value in csv.DictReader(f):
                        n+=1
                        if keycols:
                            key=tuple(value[c]for c in keycols)
                            if key in keys:raise ValueError('duplicate '+str(key))
                            keys.add(key)
                row.update(rows=n,full_crc_read=True)
                if 'expected_rows'in spec and n!=spec['expected_rows']:errors.append('row count '+name)
            schemas.append(row)
        except Exception as exc:errors.append(str(p)+': '+str(exc));schemas.append({'path':name,'status':'read_failure','error':str(exc)})
    br=root/'recovered/BOOTSTRAP_RECEIPT.json'
    boot=loadj(br)if br.exists()else None
    if boot and (boot.get('source_files_verified')!=824 or boot.get('retained_files_verified')!=519):errors.append('unexpected bootstrap receipt counts')
    return {'operation':'read_only_verify','created_utc':now(),'source_root':str(root),'main_pin':contract['pins']['main_commit'],
            'scientific_source_pin':contract['pins']['scientific_source_commit'],'key_inputs':rows,'schemas':schemas,'bootstrap_receipt':boot,
            'runtime':runtime(root)if (root/'recovered/work_v2_20261019/requirements.txt').exists()else None,
            'depth':'key source SHA + full named CSV CRC/row/key checks'if deep else'key source SHA + CSV headers; completed-run receipts are provenance, not a new complete replay',
            'errors':errors,'passed':not errors,'full_collection_reproduced':False,'Dot_complete_payload_reproduced':False}

def plan(level,root,jobs):
    py=sys.executable;steps=[]
    def add(name,path,*args):steps.append({'step':name,'command':[py,str(root/path),*map(str,args)]})
    if level=='verify':return steps
    if level=='fresh':
        add('exact_native_events','events/run_events.py','--stage','full','--jobs',jobs)
        add('exact_event_verification','events/verify_replay.py')
    add('event_design_opportunity_tables','events/summarize_design.py')
    if level in ('refit','fresh'):
        for metric in ['B8L2','D10']:add('forward_features_'+metric,'forward/build_features.py','--metric',metric)
        for metric in ['B8L2','D10']:add('forward_partitions_'+metric,'forward/discover_forward.py','--stage','partition','--metric',metric)
        add('forward_selection_original','forward/discover_forward.py','--stage','select','--implementation','original')
        add('forward_partition_stability','forward/explain_and_audit.py','--stage','stability')
        add('forward_explanation','forward/explain_and_audit.py','--stage','explain')
        add('forward_all_D10_sensitivity','forward/metric_sensitivity.py')
        add('forward_fixed_selection_profiles','forward/final_profile_sensitivities.py')
        add('forward_descriptive_summary','forward/summarize_forward.py')
        add('reverse_historical_geometry','reverse/discover_reverse_types.py','--stage','geometry')
        add('reverse_selection_original','reverse/run_discovery_batch.py','--events',root/'events/common_events.csv.gz','--jobs',jobs,'--implementation','original')
        add('reverse_consolidation','reverse/discover_reverse_types.py','--stage','consolidate')
        add('reverse_partition_stability','reverse/analyze_partition_stability.py')
        add('reverse_explanations','reverse/explain_reverse_types.py')
        add('reverse_exchange_summaries','reverse/make_exchange_summaries.py')
    add('common_recalibration_and_summary','assessment/evaluate_common.py','--stage','all')
    add('class_and_last_seat_analysis','assessment/selection_and_classes.py')
    add('room_duplicate_four_node_sensitivity','assessment/additional_sensitivity.py')
    add('frozen_rule_and_D10_sensitivity','assessment/metric_and_rule_sensitivity.py')
    add('paired_policies_practical_coverage_origin_diagnostic','assessment/final_diagnostics.py')
    add('combined_portraits_four_node_and_ablation_tables','assessment/report_tables.py')
    add('representative_case_catalog','assessment/select_cases.py')
    return steps

def copy_one(source,target,rel):
    a=source/rel;b=target/rel
    if not a.is_file():raise FileNotFoundError('Required replay input '+str(a))
    b.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(a,b)

def readiness(source,level):
    required=[]
    for folder,names in CONFIG_FILES.items():required.extend(folder+'/'+name for name in names)
    required.extend(['recovered/BOOTSTRAP_RECEIPT.json','recovered/work_v2_20261019/requirements.txt',
                     'recovered/work_v2_20261019/fusion/fusion_engine.py','recovered/work_v2_20261019/fusion/compare_fusions.py'])
    required.extend(str(Path(x['command'][1]).relative_to(source))for x in plan(level,source,1))
    if level!='fresh':required.extend(REUSED_EVENT_FILES)
    if level=='aggregate':
        required.extend(AGGREGATE_FILES)
        splits=source/'reverse/FROZEN_BUILDING_SPLITS.json'
        if splits.exists():required.extend('reverse/results/folds/'+fold+'/classes.csv.gz'for fold in loadj(splits)['folds'])
    missing=sorted(set(x for x in required if not(source/x).is_file()))
    return {'required_file_count':len(set(required)),'missing':missing,'files_ready':not missing,
            'note':'Input availability only; run pinned-runtime check before numerical execution.'}

def prepare(source,target,level,contract):
    if target.exists():raise FileExistsError('Workspace already exists; choose a NEW directory or explicitly --resume a workspace created by this entry. Nothing was deleted: '+str(target))
    if target.name!=LEAF:raise ValueError('Preserve the package directory name: '+LEAF)
    if target==source or target.is_relative_to(source)or source.is_relative_to(target):raise ValueError('Replay workspace must be outside and separate from the source tree')
    target.mkdir(parents=True,exist_ok=False);started=now()
    try:
        for folder in ['events','forward','reverse','assessment','reproducibility']:
            (target/folder).mkdir(exist_ok=True)
            for p in (source/folder).glob('*.py'):copy_one(source,target,str(p.relative_to(source)))
            for p in (source/folder).glob('*.md'):copy_one(source,target,str(p.relative_to(source)))
        for p in (source/'reproducibility').glob('*.json'):copy_one(source,target,str(p.relative_to(source)))
        for folder,names in CONFIG_FILES.items():
            for name in names:copy_one(source,target,folder+'/'+name)
        shutil.copytree(source/'recovered',target/'recovered')
        if (source/'deps').exists():shutil.copytree(source/'deps',target/'deps',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        if level!='fresh':
            for name in REUSED_EVENT_FILES:copy_one(source,target,name)
        if level=='aggregate':
            for name in AGGREGATE_FILES:copy_one(source,target,name)
            files=sorted((source/'reverse/results/folds').glob('*/classes.csv.gz'))
            if len(files)!=23:raise ValueError('aggregate needs FULL + 22 reverse class files; got '+str(len(files)))
            for p in files:copy_one(source,target,str(p.relative_to(source)))
        state={'status':'PREPARED','created_utc':started,'source_root':str(source),'workspace_root':str(target),'level':level,
               'contract_sha256':sha(HERE/'EXCHANGE_FIELD_CONTRACT.json'),'source_key_inputs':contract['key_input_sha256'],
               'copied_script_sha256':{str(p.relative_to(target)):sha(p)for folder in ['events','forward','reverse','assessment','reproducibility']for p in(target/folder).glob('*.py')},
               'copied_prior_PartA_event_states':False,'copied_PartA_learned_labels':level=='aggregate','copied_PartA_feature_fit_cache':False,
               'copied_native_team_result_table':level!='fresh','copied_FULL_personnel_portrait_and_classmate_tables':level=='aggregate',
               'fresh_event_workspace_at_creation':level=='fresh','preserved_source_tree':True,'automatic_cache_deletion':False}
        savej(target/'reproducibility/WORKSPACE_PREPARATION.json',state)
    except Exception as exc:
        savej(target/'reproducibility/PREPARATION_FAILED.json',{'created_utc':started,'error':str(exc),'partial_workspace_preserved':True});raise

def execute(source,target,level,jobs,resume,contract):
    ready=readiness(source,level)
    if not ready['files_ready']:raise FileNotFoundError('Unpack missing companion inputs first: '+', '.join(ready['missing']))
    if resume:
        p=target/'reproducibility/WORKSPACE_PREPARATION.json'
        if not p.exists():raise ValueError('--resume only accepts a workspace prepared by this entry')
        state=loadj(p)
        if state['level']!=level or state['source_key_inputs']!=contract['key_input_sha256']:raise ValueError('Cannot resume a different level or changed key scientific inputs')
    else:prepare(source,target,level,contract)
    for name,want in contract['key_input_sha256'].items():
        if not(target/name).is_file()or sha(target/name)!=want:raise ValueError('Workspace frozen input changed: '+name)
    state=loadj(target/'reproducibility/WORKSPACE_PREPARATION.json')
    for name,want in state['copied_script_sha256'].items():
        if sha(target/name)!=want:raise ValueError('Prepared replay code changed; use a new workspace: '+name)
    import fcntl
    lock=(target/'reproducibility/replay_writer.lock').open('a+')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:raise RuntimeError('Another replay coordinator is active in this workspace')
    rt=runtime(target)
    if not rt['all_pins_match'] or not rt['fcntl_available']:
        savej(target/'reproducibility/RUNTIME_CHECK.json',rt)
        raise RuntimeError('Pinned runtime is incomplete/different; install recovered/work_v2_20261019/requirements.txt in the active Python environment. No packages were installed automatically.')
    recipe=plan(level,target,jobs);rp=target/'reproducibility/REPLAY_RUN_RECEIPT.json'
    previous=loadj(rp)if resume and rp.exists()else{'steps':[]}
    done={s['step']:s for s in previous['steps']if s.get('exit_code')==0}
    logdir=target/'reproducibility/logs';logdir.mkdir(exist_ok=True)
    rec={'status':'RUNNING','started_utc':now(),'level':level,'jobs':jobs,'resumed':resume,'runtime':rt,'steps':previous['steps'],
         'scientific_method_changes':False,'automatic_cache_deletion':False,'new_team_fusions_expected_only_for_initial_fresh':level=='fresh'and not resume}
    env=os.environ.copy();env['OPENBLAS_NUM_THREADS']='1';env['OMP_NUM_THREADS']='1'
    env['PERSONNEL_V2_REPOSITORY']=str(target/'recovered/repo_main_20261019')
    if (target/'deps').exists():env['PYTHONPATH']=str(target/'deps')+(os.pathsep+env['PYTHONPATH']if env.get('PYTHONPATH')else'')
    for step in recipe:
        script=Path(step['command'][1]);digest=sha(script)
        if step['step']in done:
            if done[step['step']]['script_sha256']!=digest:raise ValueError('A completed script changed; choose a new replay workspace: '+str(script))
            continue
        stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S')
        log=logdir/(step['step']+'_'+stamp+'.log');t=time.monotonic()
        row={**step,'started_utc':now(),'script_sha256':digest,'log':str(log.relative_to(target))}
        print('RUN',step['step'],'LOG',str(log),flush=True)
        with log.open('w',encoding='utf8')as handle:
            result=subprocess.run(step['command'],cwd=target,env=env,stdout=handle,stderr=subprocess.STDOUT)
        row.update(exit_code=result.returncode,seconds=time.monotonic()-t);rec['steps'].append(row)
        rec['status']='RUNNING'if result.returncode==0 else'FAILED_PRESERVED';savej(rp,rec)
        if result.returncode:raise RuntimeError('Replay stopped at '+step['step']+'; see '+str(log)+'. All inputs/caches retained.')
    rec['status']='COMPLETE';rec['completed_utc']=now();savej(rp,rec)
    print(json.dumps({'status':'COMPLETE','workspace':str(target),'receipt':str(rp)},ensure_ascii=False))

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source-root',type=Path,default=DEFAULT_SOURCE,help='unpacked work_personnel_typing_A_20261019 source; read only')
    ap.add_argument('--level',choices=['verify','aggregate','refit','fresh'],default='verify')
    ap.add_argument('--workspace',type=Path,help='NEW .../work_personnel_typing_A_20261019 for explicit execution')
    ap.add_argument('--execute',action='store_true',help='execute the selected level in the explicit isolated workspace')
    ap.add_argument('--resume',action='store_true',help='resume only a workspace created by this entry; no cache deletion')
    ap.add_argument('--jobs',type=int,default=1,help='native event/reverse fold processes; default 1 limits memory')
    ap.add_argument('--deep',action='store_true',help='stream complete named CSVs for CRC, row counts and keys; no fitting')
    ap.add_argument('--report',type=Path,help='optional path for verification/plan JSON; default prints only')
    args=ap.parse_args();source=args.source_root.resolve();contract=loadj(HERE/'EXCHANGE_FIELD_CONTRACT.json')
    if args.jobs<1:ap.error('--jobs must be >=1')
    if args.resume and not args.execute:ap.error('--resume requires --execute')
    if args.execute and args.level=='verify':ap.error('verify is read-only; omit --execute')
    if args.execute and args.workspace is None:ap.error('--execute requires a NEW explicit --workspace')
    check=verify(source,contract,args.deep)
    destination=args.workspace.resolve()if args.workspace else Path('/NEW_PARENT')/LEAF
    result={'verification':check,'selected_level':args.level,'will_execute':bool(args.execute),'planned_workspace':str(destination),'commands':plan(args.level,destination,args.jobs),
            'level_readiness':{level:readiness(source,level)for level in ['aggregate','refit','fresh']},
            'no_existing_cache_is_deleted':True,'default_action_is_read_only':True}
    if args.report:savej(args.report,result)
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
    if not check['passed']:raise SystemExit(2)
    if args.execute:execute(source,destination,args.level,args.jobs,args.resume,contract)
if __name__=='__main__':main()
