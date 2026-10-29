"""Exact-identity AC endpoint reuse and the unchanged v2.1 native engine.

This adapter does not define classes, choose teams, change a reference, or alter
fusion/scoring. ``prepare`` reads only already frozen requests. ``run`` evaluates
missing physical teams and separately records geometry replays of old teams.
"""
from __future__ import annotations
import os
for _name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[_name]='1'
os.environ.setdefault('MPLCONFIGDIR','/tmp/hohonet_mpl')
import argparse,collections,csv,gzip,hashlib,importlib.metadata,json,math,multiprocessing,platform,sys,time
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
import pandas as pd

SCORE_PARITY_FIELDS=['B8L2','D10','IoU3D100','iou_2d','S_bottom_deg','dir','Hmean','Hcenter',
                    'omission','extension','nodes','fusion_turn_n','fusion_short_turn_edges',
                    'fusion_redundancy_n','geometry_area_h2','centroid_x_h','centroid_z_h',
                    'height_mean_h','boundary_loss','direction_loss','height_loss']
FULL_SCORE_FIELDS=['B8L2','D10','IoU3D100','boundary_loss','direction_loss','height_loss']

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1<<20),b''):h.update(block)
    return h.hexdigest()
def digest(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def workers(value):
    if isinstance(value,list):return sorted(map(str,value))
    return sorted(str(value).split('|')) if value not in ('',None) else []
def team_key(pid,ws):return pid+'__'+digest(sorted(ws))[:20]
def finite(value):
    try:return value is not None and math.isfinite(float(value))
    except (TypeError,ValueError):return False
def clean(obj):
    if isinstance(obj,dict):return {str(k):clean(v) for k,v in obj.items()}
    if isinstance(obj,(list,tuple)):return [clean(v) for v in obj]
    if isinstance(obj,float) and not math.isfinite(obj):return None
    return obj
def read_json(path):
    with (gzip.open(path,'rt',encoding='utf-8-sig') if str(path).endswith('.gz') else open(path,encoding='utf-8-sig')) as f:return json.load(f)
def read_csv(path):
    with (gzip.open(path,'rt',encoding='utf-8-sig',newline='') if str(path).endswith('.gz') else open(path,encoding='utf-8-sig',newline='')) as f:
        return list(csv.DictReader(f))
def write_json(path,obj):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.writing')
    tmp.write_text(json.dumps(clean(obj),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8');tmp.replace(p)
def write_csv(path,rows):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.writing')
    frame=rows if isinstance(rows,pd.DataFrame) else pd.DataFrame(rows)
    if str(p).endswith('.gz'):
        with gzip.open(tmp,'wt',encoding='utf-8-sig',newline='',compresslevel=4) as f:
            frame.to_csv(f,index=False);f.flush()
    else:
        with tmp.open('w',encoding='utf-8-sig',newline='') as f:
            frame.to_csv(f,index=False);f.flush();os.fsync(f.fileno())
    tmp.replace(p)
def iter_jsonl(path):
    with gzip.open(path,'rt',encoding='utf-8-sig') as f:
        for line in f:
            if line.strip():yield json.loads(line)
def write_jsonl(path,rows):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.writing')
    with gzip.open(tmp,'wt',encoding='utf-8',compresslevel=5) as f:
        for row in rows:f.write(json.dumps(clean(row),ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')
    tmp.replace(p)

def merge_csv_shards(paths,target,key_field,expected_keys=None):
    """Union columns, then stream gzip CSV rows; never materialize the corpus."""
    paths=list(map(Path,paths));fields=[]
    for path in paths:
        with gzip.open(path,'rt',encoding='utf-8-sig',newline='') as f:
            for field in csv.DictReader(f).fieldnames:
                if field not in fields:fields.append(field)
    target=Path(target);target.parent.mkdir(parents=True,exist_ok=True);temp=target.with_name(target.name+'.writing')
    seen=set();count=0;acquisition=collections.Counter()
    with gzip.open(temp,'wt',encoding='utf-8-sig',newline='',compresslevel=4) as out:
        writer=csv.DictWriter(out,fieldnames=fields);writer.writeheader()
        for path in paths:
            with gzip.open(path,'rt',encoding='utf-8-sig',newline='') as src:
                for row in csv.DictReader(src):
                    key=row[key_field];assert key not in seen,(key_field,key,'duplicate_shard_identity')
                    seen.add(key);count+=1;writer.writerow(row)
                    if 'endpoint_acquisition' in row:acquisition[row['endpoint_acquisition']]+=1
    if expected_keys is not None:assert seen==set(expected_keys),(count,len(expected_keys))
    temp.replace(target)
    return {'rows':count,'columns':len(fields),'acquisition_counts':dict(acquisition)}

def verify_csv_shard(path,key_field,expected_keys):
    seen=set()
    with gzip.open(path,'rt',encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        for row in reader:
            assert None not in row and all(v is not None for v in row.values()),(str(path),'incomplete_csv_record')
            assert row[key_field] not in seen,(str(path),'duplicate_identity')
            seen.add(row[key_field])
    assert seen==set(expected_keys),(str(path),'incomplete_identity_set',len(seen),len(expected_keys))
    return {'rows':len(seen),'gzip_read_to_eof':True,'csv_width_and_identity_set_verified':True}

def source_contract(repo,pool_paths,commit,previous_import_audit):
    """Hash the already audited import closure; no engine initialization needed."""
    repo=Path(repo).resolve();paths=set()
    if previous_import_audit:
        audit=read_json(previous_import_audit)
        oldroot=Path(audit['original_workspace']['repository'])
        for p in audit['original_workspace']['loaded_repository_files']:
            paths.add(repo/Path(p).relative_to(oldroot))
    paths.update(repo/p for p in [
        'research/statistics/b8l2_shared_v6_20261016/inputs/measurement_engine.zip',
        'research/statistics/b8l2_shared_v6_20261016/inputs/working_models.py',
        'research/workers/personnel_profiles_composition_20261020/source/tables/profiles/record_index.csv.gz',
        'research/workers/personnel_v21_reselection_20261029/analysis/legacy_geometry_diagnostics.py'])
    manifest=[{'path':str(p.relative_to(repo)),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(paths)]
    pools={p['pool_id']:p for fn in pool_paths for p in read_json(fn)['images']}
    runtime={'python':platform.python_version(),'packages':{}}
    for package in ['numpy','scipy','pandas','shapely','Pillow']:
        runtime['packages'][package]=importlib.metadata.version(package)
    import shapely
    runtime['geos']=getattr(shapely,'geos_version_string',None)
    contract={'data_release':'v2.1','current_repository_commit':commit,'engine_root':str(repo),
              'engine_files':manifest,'runtime':runtime,'engine_digest':digest({'files':manifest,'runtime':runtime}),
              'pool_sources':[{'path':str(Path(p).resolve()),'sha256':sha(p)} for p in pool_paths],
              'pool_hashes':{pid:digest(p) for pid,p in sorted(pools.items())},
              'reference_hashes':{pid:digest(p['reference']) for pid,p in sorted(pools.items())},
              'scientific_algorithm_unchanged':True,'labels_not_used_by_engine':True}
    return contract,pools

def semantic_identity(pool,ws,engine_digest,pool_hash=None,reference_hash=None):
    by={r['worker_id']:r for r in pool['records']}
    return digest({'pool_id':pool['pool_id'],'condition':pool['meta']['condition'],
                   'pool_hash':pool_hash or digest(pool),'reference_hash':reference_hash or digest(pool['reference']),
                   'reference_id':pool['meta']['reference_id'],'reference_version':pool['meta']['reference_version'],
                   'engine_digest':engine_digest,'members':sorted(ws),
                   'objects':[by[w]['object_id'] for w in sorted(ws)]})

def identity_issue(row,pool,request,container=None,allow_panel_binding=False,pool_hash=None):
    if row.get('pool_id')!=pool['pool_id']:return 'pool_id'
    ws=workers(row.get('member_workers'));wanted=workers(request['member_workers'])
    if ws!=wanted or len(ws)!=len(set(ws)):return 'members'
    if row.get('team_key')!=team_key(pool['pool_id'],ws):return 'team_key'
    by={r['worker_id']:r for r in pool['records']}
    if not set(ws)<=set(by):return 'unqualified_member'
    if row.get('condition') and row['condition']!=pool['meta']['condition']:return 'condition'
    for field in ['reference_id','reference_version']:
        if row.get(field)!=pool['meta'][field]:return field
    ids=workers(row.get('member_object_ids'))
    if not ids and not allow_panel_binding:return 'object_ids_missing'
    if ids and ids!=sorted(str(by[w]['object_id']) for w in ws):return 'object_ids'
    for obj in [row,container or {}]:
        h=obj.get('input_pool_sha256') or obj.get('pool_input_sha256')
        if h and h!=(pool_hash or digest(pool)):return 'pool_hash'
    version=row.get('data_release') or row.get('quality_data_release') or row.get('underlying_data_version')
    if version!='v2.1':return 'not_v21'
    if row.get('k') not in ('',None) and int(float(row['k']))!=len(ws):return 'team_size'
    return None

def cache_full(row):
    if 'geometry' not in row:return False
    if finite(row.get('B8L2')) and any(k not in row for k in FULL_SCORE_FIELDS):return False
    return 'record_time_by_kind_json' in row

def default_sources(work,repo):
    work=Path(work);repo=Path(repo);base=repo/'research/workers/personnel_v21_reselection_20261029'
    sources=[]
    previous=work/'HOHONET_v21_reaudit_20261029/stage03_completed_abc/ENDPOINT_GEOMETRY.jsonl.gz'
    if previous.exists():sources.append((previous,'jsonl'))
    # The separate strict m9/m10 study is already committed in the latest source.
    # Its endpoints can be reused; its study design is never rerun here.
    strict=work/'HOHONET_v21_AC_population_20261029/stage02_engine/current_strict_cache'
    if strict.exists():
        assert (strict/'EXTRACTION_RECEIPT.json').exists(),'Strict-cache extraction must finish before preparing a reuse plan.'
        sources += [(p,'jsonl') for p in sorted((strict/'endpoints/pools').glob('*/part_*.jsonl.gz'))]
    # Existing full geometry for the admitted targets; other old exports retain scalars.
    sources += [(p,'jsonl') for p in sorted((base/'additional_delivery/packages/03A/composition/other_targets_endpoints').rglob('*.jsonl.gz'))]
    for p in sorted(base.rglob('ENDPOINT_SCALARS.csv.gz')):
        sources.append((p,'panel_csv' if (p.parent/'TEAM_MEMBERS.csv.gz').exists() else 'scalar_csv'))
    natural=repo/'research/data/releases/v2.1/same_room_frozen_design/current_classes/native/pools'
    sources += [(p,'pool_json') for p in sorted(natural.glob('*.json.gz'))]
    return sources

def prepare(args):
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    if (out/'CACHE_PLAN.json').exists():raise FileExistsError('Use a new plan directory or reuse the existing frozen cache plan.')
    contract,pools=source_contract(args.repo,args.pools,args.commit,args.previous_import_audit)
    requests=read_csv(args.requests);wanted={r['team_key']:r for r in requests}
    assert len(wanted)==len(requests)
    for key,request in wanted.items():
        ws=workers(request['member_workers']);pid=request['pool_id']
        assert key==team_key(pid,ws) and len(ws)==int(request.get('n',request.get('k')))
        assert len(ws)>=3,'n<3 requires its separate frozen pipeline and an explicit design.'
        assert len(ws)==len(set(ws)) and set(ws)<={r['worker_id'] for r in pools[pid]['records']}
    full={};scalar={};sources=[];reject=collections.Counter();seen_files=set();duplicate_identity=collections.Counter()
    input_sources=default_sources(args.work,args.repo)+[(Path(p),'jsonl') for p in args.extra_jsonl]
    def accept(row,path,kind,container=None,panel_bound=False):
        key=row.get('team_key')
        if key not in wanted:return False
        pool=pools[wanted[key]['pool_id']]
        issue=identity_issue(row,pool,wanted[key],container,panel_bound,contract['pool_hashes'][pool['pool_id']])
        if issue:reject[issue]+=1;return False
        own=dict(row,cache_source=str(path.resolve()),cache_kind=kind,
                 cache_identity_binding='explicit_members_objects_reference_v21' if not panel_bound else 'frozen_panel_members_current_reference_binding')
        if cache_full(own):
            if key in full:duplicate_identity['full']+=1
            else:full[key]=own
        else:
            if key in scalar:duplicate_identity['scalar']+=1
            # Prefer the richest explicit scalar record for replay verification.
            if key not in scalar or len(own)>len(scalar[key]):scalar[key]=own
        return True
    start=time.monotonic()
    for path,kind in input_sources:
        checksum=sha(path)
        if checksum in seen_files:continue
        seen_files.add(checksum);hits=0;rows=0
        if kind=='jsonl':
            for row in iter_jsonl(path):rows+=1;hits+=accept(row,path,kind)
        elif kind=='pool_json':
            container=read_json(path)
            for row in container.get('teams',[]):rows+=1;hits+=accept(row,path,kind,container)
        else:
            members_map={};ref_map={}
            if kind=='panel_csv':
                for row in read_csv(path.parent/'TEAM_MEMBERS.csv.gz'):
                    if row['team_key'] in wanted:members_map[row['team_key']]=row
                for row in read_csv(path.parent/'PANELS_USED.csv'):ref_map[row['pool_id']]=row
            for chunk in pd.read_csv(path,chunksize=20000,low_memory=False):
                rows+=len(chunk)
                for row in chunk[chunk.team_key.isin(wanted)].to_dict('records'):
                    row=clean(row)
                    if kind=='panel_csv':
                        if row['team_key'] not in members_map:reject['panel_members_missing']+=1;continue
                        row.update({k:v for k,v in members_map[row['team_key']].items() if k not in row or row[k] in (None,'')})
                        ref=ref_map[row['pool_id']]
                        row.update(reference_id=ref['reference_id'],reference_version=ref['reference_version'],data_release='v2.1')
                    hits+=accept(row,path,kind,panel_bound=kind=='panel_csv')
        sources.append({'path':str(path.resolve()),'kind':kind,'sha256':checksum,'rows_scanned':rows,'requested_identity_hits':hits})
    identities=[];by_pool=collections.defaultdict(list)
    for request in requests:
        key=request['team_key'];pid=request['pool_id'];ws=workers(request['member_workers'])
        state='reused_full' if key in full else 'geometry_replay_existing_team' if key in scalar else 'new_physical_team'
        prior=full.get(key,scalar.get(key,{}))
        identities.append(dict(request,endpoint_acquisition=state,semantic_identity=semantic_identity(pools[pid],ws,contract['engine_digest'],contract['pool_hashes'][pid],contract['reference_hashes'][pid]),
                               prior_source=prior.get('cache_source',''),engine_digest=contract['engine_digest'],input_pool_sha256=contract['pool_hashes'][pid],reference_sha256=contract['reference_hashes'][pid]))
        if key in full:by_pool[pid].append(full[key])
    for pid,rows in by_pool.items():write_jsonl(out/'reused_full'/f'{pid}.jsonl.gz',rows)
    replay=[scalar[k] for k in wanted if k not in full and k in scalar]
    write_jsonl(out/'EXISTING_SCALAR_REPLAY_BASELINE.jsonl.gz',replay)
    write_csv(out/'REQUEST_IDENTITY_AND_REUSE.csv.gz',identities);write_csv(out/'CACHE_SOURCE_MANIFEST.csv',sources)
    write_json(out/'ENGINE_AND_INPUT_CONTRACT.json',contract)
    counts=dict(collections.Counter(r['endpoint_acquisition'] for r in identities))
    receipt={'requests_file':str(Path(args.requests).resolve()),'requests_sha256':sha(args.requests),'unique_requests':len(requests),
             'pools':len({r['pool_id'] for r in requests}),'acquisition_counts':counts,'rejected_candidate_rows':dict(reject),
             'duplicate_cached_identity_counts':dict(duplicate_identity),'cache_files':len(sources),'seconds':time.monotonic()-start,
             'new_fusions':0,'new_scores':0,'labels_recomputed':0,'semantic_identity_definition':'pool/target/condition + qualified records and objects + current reference + frozen engine and time input digest + exact members'}
    write_json(out/'CACHE_PLAN.json',receipt);print(json.dumps(receipt,ensure_ascii=False),flush=True)

def load_engine(repo):
    sys.path.insert(0,str(Path(repo)/'research/workers/personnel_v21_reselection_20261029/experiment'))
    from benchmark_engine import load_engine as load
    return load(Path(repo))

def replay_difference(before,after):
    differences={}
    for field in SCORE_PARITY_FIELDS:
        a,b=before.get(field),after.get(field)
        if finite(a):
            assert finite(b),(after['team_key'],field,'old_value_missing_after_replay')
            diff=abs(float(a)-float(b));assert diff<1e-7,(after['team_key'],field,a,b)
            differences[field]=diff
    if before.get('score_status') not in (None,''):assert before['score_status']==after.get('score_status'),(after['team_key'],'score_status')
    # Q availability is part of the endpoint identity outcome, not only its value.
    if 'B8L2' in before:assert finite(before.get('B8L2'))==finite(after.get('B8L2'))
    return {'team_key':after['team_key'],'fields_compared':len(differences),'maximum_difference':max(differences.values(),default=0),'differences':differences}

def evaluate_pool(payload):
    repo,pool,requests,contract,plan_dir,output,part_size,replay=payload
    native=load_engine(repo);pid=pool['pool_id'];folder=Path(output)/'pools'/pid;folder.mkdir(parents=True,exist_ok=True)
    wanted={r['team_key']:r for r in requests};done={};part=0;buffer=[];checks=[];counts=collections.Counter();start=time.monotonic()
    if (folder/'REPLAY_PARITY.json').exists():checks=read_json(folder/'REPLAY_PARITY.json').get('checks',[])
    ph,rh=contract['pool_hashes'][pid],contract['reference_hashes'][pid]
    context={'pool_id':pid,'pool_input_sha256':ph,'reference_sha256':rh,'engine_digest':contract['engine_digest']}
    context_path=folder/'POOL_INPUT.json'
    if context_path.exists():assert read_json(context_path)==context
    else:write_json(context_path,context)
    for path in sorted(folder.glob('part_*.jsonl.gz')):
        part=max(part,int(path.stem.split('.')[0].split('_')[-1]))
        for row in iter_jsonl(path):
            key=row['team_key'];assert key in wanted and key not in done
            assert row['semantic_identity']==wanted[key]['semantic_identity']
            done[key]=row
    previous=len(done)
    def flush():
        nonlocal part
        if not buffer:return
        part+=1;write_jsonl(folder/f'part_{part:05d}.jsonl.gz',buffer);buffer.clear()
        write_json(folder/'PROGRESS.json',{'pool_id':pid,'requested':len(wanted),'done':len(done),'resumed':previous,'acquired':dict(counts),'seconds':time.monotonic()-start})
    full_path=Path(plan_dir)/'reused_full'/f'{pid}.jsonl.gz'
    if full_path.exists():
        for row in iter_jsonl(full_path):
            key=row['team_key']
            if key in done:continue
            row=dict(row,semantic_identity=wanted[key]['semantic_identity'],endpoint_acquisition='reused_full',
                     current_repository_commit=contract['current_repository_commit'],engine_digest=contract['engine_digest'],input_pool_sha256=ph,reference_sha256=rh)
            done[key]=row;buffer.append(row);counts['reused_full']+=1
            if len(buffer)>=part_size:flush()
    flush()
    remaining=[r for k,r in wanted.items() if k not in done]
    if remaining:
        with native.Engine(full_state=False) as engine:
            for request in remaining:
                ws=workers(request['member_workers']);row=engine.evaluate(pool,ws);geo=row.get('geometry')
                if geo is not None:
                    extra=engine.scorecache.get(engine.fr.digest([row['k']==2,row.get('nodes'),geo]))
                    if extra:row.update(extra)
                assert row['team_key']==request['team_key'] and row['k']==int(request['n'])
                key=row['team_key'];state=request['endpoint_acquisition']
                if state=='geometry_replay_existing_team':checks.append(replay_difference(replay[key],row))
                row.update(data_release='v2.1',underlying_data_version='v2.1',repository_commit=contract['current_repository_commit'],
                           current_repository_commit=contract['current_repository_commit'],engine_digest=contract['engine_digest'],input_pool_sha256=ph,reference_sha256=rh,
                           semantic_identity=request['semantic_identity'],endpoint_acquisition=state,endpoint_origin='v21_direct_ac_population_20261029',fusion_quality_contract_unchanged=True)
                row=native.gs.clean(row);done[key]=row;buffer.append(row);counts[state]+=1
                if len(buffer)>=part_size:
                    flush()
                    write_json(folder/'REPLAY_PARITY.json',{'old_entity_replays':len(checks),'checks':checks,'all_passed':True})
            flush()
    scalars=[]
    for row in done.values():
        row=dict(row)
        for field in ['member_workers','member_object_ids']:row[field]=workers(row[field])
        scalars.append(native.native.scalar_row(row))
    scalar_path=Path(output)/'scalar_shards'/f'{pid}.csv.gz'
    write_csv(scalar_path,scalars)
    scalar_verification=verify_csv_shard(scalar_path,'team_key',wanted)
    write_json(folder/'REPLAY_PARITY.json',{'old_entity_replays':len(checks),'checks':checks,'all_passed':True})
    result={'pool_id':pid,'requested':len(wanted),'resumed':previous,'acquisition_counts':dict(counts),'total':len(done),
            'Q_available':sum(finite(r.get('B8L2')) for r in done.values()),'seconds':time.monotonic()-start,'complete':set(done)==set(wanted),
            'scalar_verification':scalar_verification}
    write_json(folder/'CHECKS.json',result);return result

def run(args):
    plan=Path(args.plan);out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    contract=read_json(plan/'ENGINE_AND_INPUT_CONTRACT.json')
    assert sha(read_json(plan/'CACHE_PLAN.json')['requests_file'])==read_json(plan/'CACHE_PLAN.json')['requests_sha256']
    repo=Path(args.repo).resolve()
    for entry in contract['engine_files']:assert sha(repo/entry['path'])==entry['sha256'],entry['path']
    assert platform.python_version()==contract['runtime']['python']
    for package,version in contract['runtime']['packages'].items():assert importlib.metadata.version(package)==version,(package,version)
    pools={p['pool_id']:p for src in contract['pool_sources'] for p in read_json(src['path'])['images']}
    for pid,pool in pools.items():assert digest(pool)==contract['pool_hashes'][pid]
    requests=read_csv(plan/'REQUEST_IDENTITY_AND_REUSE.csv.gz');groups=collections.defaultdict(list)
    for row in requests:groups[row['pool_id']].append(row)
    # Optional timed first wave consists only of already registered pools in
    # deterministic pool-id order. A later full run resumes these same files.
    selected_groups=sorted(groups.items())[:args.pilot_pools] if args.pilot_pools else sorted(groups.items())
    replay={r['team_key']:r for r in iter_jsonl(plan/'EXISTING_SCALAR_REPLAY_BASELINE.jsonl.gz')}
    start=time.monotonic();results=[]
    # Spawn avoids copying the large all-study request/index object graph into
    # every native worker under the 8 GiB memory budget.
    with ProcessPoolExecutor(max_workers=args.jobs,mp_context=multiprocessing.get_context('spawn')) as executor:
        pending=[executor.submit(evaluate_pool,(str(repo),pools[pid],rows,contract,str(plan),str(out),args.part_size,{r['team_key']:replay[r['team_key']] for r in rows if r['team_key'] in replay})) for pid,rows in selected_groups]
        for future in as_completed(pending):
            result=future.result();results.append(result);print(json.dumps(result),flush=True)
            write_json(out/'PROGRESS.json',{'pools_done':len(results),'total_pools':len(groups),'selected_pools_this_pass':len(selected_groups),'seconds':time.monotonic()-start,'pools':results})
    if args.pilot_pools:
        receipt={'pilot_pools':len(selected_groups),'registered_total_pools':len(groups),'registered_unique_teams':len(requests),
                 'pilot_teams':sum(x['total'] for x in results),'native_evaluations':sum(sum(v for k,v in x['acquisition_counts'].items() if k!='reused_full') for x in results),
                 'seconds':time.monotonic()-start,'by_pool':results,'selection':'First registered pool ids in deterministic lexical order, no outcome selection',
                 'next_step':'Run the same plan/output without --pilot-pools; exact saved endpoints resume.'}
        write_json(out/'TIMED_FIRST_WAVE.json',receipt);print(json.dumps(receipt,ensure_ascii=False),flush=True);return
    scalar=merge_csv_shards(sorted((out/'scalar_shards').glob('*.csv.gz')),out/'ENDPOINT_SCALARS.csv.gz','team_key',{r['team_key'] for r in requests})
    files=sorted((out/'pools').glob('*/part_*.jsonl.gz'))
    write_jsonl(out/'ENDPOINT_GEOMETRY.jsonl.gz',(row for p in files for row in iter_jsonl(p)))
    counts=scalar['acquisition_counts']
    receipt={'requested_unique_teams':len(requests),'endpoint_rows':scalar['rows'],'pools':len(groups),'acquisition_counts':counts,
             'truly_new_physical_teams':counts.get('new_physical_team',0),'old_entity_geometry_replays':counts.get('geometry_replay_existing_team',0),
             'full_endpoint_reused':counts.get('reused_full',0),'native_evaluations_this_run':sum(sum(v for k,v in x['acquisition_counts'].items() if k!='reused_full') for x in results),
             'resumed_endpoints':sum(r['resumed'] for r in results),'all_complete':all(r['complete'] for r in results),'seconds':time.monotonic()-start,
             'engine_digest':contract['engine_digest'],'current_repository_commit':contract['current_repository_commit'],
             'no_label_or_reference_changes':True,'Q_missing_never_imputed':True,'full_geometry_and_failure_states_preserved':True}
    write_json(out/'RUN_RECEIPT.json',receipt);print(json.dumps(receipt,ensure_ascii=False),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);sub=ap.add_subparsers(dest='command',required=True)
    p=sub.add_parser('prepare');p.add_argument('--repo',required=True);p.add_argument('--work',required=True);p.add_argument('--pools',nargs='+',required=True)
    p.add_argument('--requests',required=True);p.add_argument('--output',required=True);p.add_argument('--commit',required=True)
    p.add_argument('--previous-import-audit');p.add_argument('--extra-jsonl',nargs='*',default=[])
    p=sub.add_parser('run');p.add_argument('--repo',required=True);p.add_argument('--plan',required=True);p.add_argument('--output',required=True)
    p.add_argument('--jobs',type=int,default=6);p.add_argument('--part-size',type=int,default=100);p.add_argument('--pilot-pools',type=int,default=0)
    a=ap.parse_args();prepare(a) if a.command=='prepare' else run(a)
