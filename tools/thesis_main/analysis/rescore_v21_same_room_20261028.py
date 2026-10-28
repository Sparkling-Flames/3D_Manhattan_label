"""Rescore saved same-room endpoints only; retain direct-pair identity and gaps."""
import argparse,csv,gzip,importlib.util,json
from collections import Counter,defaultdict
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
from types import SimpleNamespace
from .rebuild_v21_20261028 import ROOT,OUT,read
from .rescore_v21_exchange_endpoints_20261028 import score_one,object_ids
from .scope_quality_scoring_20261016 import scoring_engine

TARGET=OUT/'same_room_endpoint_rescore'
LARGE=ROOT/'research/same_room/same_room_large_block_rebuilt_20261023/native_endpoints'
CURRENT=ROOT/'research/same_room/same_room_current_classes_v2_20261023'
POP=ROOT/'research/workers/personnel_population_curves_v2_20261023'
PREC=POP/'sampling_precision_20261025/new_endpoints/table_shards'
EXT=POP/'sampling_extension_20261026'
FROZEN=ROOT/'research/same_room/same_room_large_block_rebuilt_20261023/engine/frozen_repo'
FR=FROZEN/'research/workers/personnel_interchangeability_20261020/analysis/composition/fusion_runner.py'
GD=FR.with_name('geometry_diagnostics.py')
STUDY=FROZEN/'tools/thesis_main/analysis/paired_split_research/study.py'
FIELDS=['B8L2','D10','WQ','iou_2d','IoU3D100','S_bottom_deg','dir','Hmean','Hcenter','omission','extension','nodes','ref_node_recall_5','ref_node_recall_9','ref_edge_recall_5','ref_edge_recall_9','diag_corner_recall_05','diag_wall_coverage_03','diag_wall_coverage_05']

def records(p):
    with gzip.open(p,'rt',encoding='utf-8-sig',newline='') as f:yield from csv.DictReader(f)

def unpack(s):return list(json.loads(s)) if s.startswith('[') else s.split('|') if s else []

def inventory():
    TARGET.mkdir(parents=True,exist_ok=True)
    ids={r['pool_id'] for r in read(OUT/'pools/DEPENDENCIES.json') if r['action']=='reuse_geometry_rescore'}
    pools={r['pool_id']:r for r in read(OUT/'pools/INPUT_SNAPSHOT.json')['images']};assert ids<=set(pools)
    scalars={};current_all={};counts={}
    for label,paths in [('large_block',[LARGE/'ENDPOINT_SCALARS.csv.gz']),('current_classes',sorted((CURRENT/'results/native/parts').glob('*.csv.gz')))]:
        n=0
        for path in paths:
            for r in records(path):
                if label=='current_classes':current_all[r['team_key']]=r['member_workers']
                if r['pool_id'] not in ids:continue
                assert r['team_key'] not in scalars,(label,r['team_key'])
                workers=unpack(r['member_workers']);oids=unpack(r['member_object_ids']);assert len(set(workers))==len(set(oids))==int(r['k'])
                scalars[r['team_key']]=dict(team_key=r['team_key'],pool_id=r['pool_id'],k=int(r['k']),member_workers=workers,member_set_key='|'.join(sorted(workers)),member_object_ids=r['member_object_ids'],reference_id=pools[r['pool_id']]['meta']['reference_id'],original_reference_id=r['reference_id'],original_reference_version=r['reference_version'],original_score_status=r['score_status'],original_complete_evaluable=r['complete_evaluable']=='True',original_metrics={k:r.get(k) for k in FIELDS},source_scalar=[path.relative_to(ROOT).as_posix()],source_geometry=[],study=label,geometry=None);n+=1
        counts[label]=n
    located={}
    for r in records(LARGE/'ENDPOINT_ARCHIVE_LOCATOR.csv.gz'):
        if r['team_key'] in scalars:
            assert r['team_key'] not in located;located[r['team_key']]=r
    shards=defaultdict(dict)
    for key,loc in located.items():shards[loc['geometry_shard']][int(loc['geometry_line_1based'])]=key
    missing_paths=[]
    for rel,lines in shards.items():
        path=LARGE/rel
        if not path.is_file():missing_paths.append(rel);continue
        with gzip.open(path,'rt',encoding='utf8') as f:
            for n,line in enumerate(f,1):
                if n not in lines:continue
                z=json.loads(line);r=scalars[lines[n]];assert z['team_key']==r['team_key'] and z['pool_id']==r['pool_id']
                assert set(z['member_workers'])==set(r['member_workers']) and set(z['member_object_ids'])==object_ids(r['member_object_ids'])
                assert z['reference_id']==r['original_reference_id'] and z['score_status']==r['original_score_status']
                r['geometry']=z.get('geometry');r['source_geometry'].append(path.relative_to(ROOT).as_posix()+'#L'+str(n))
    # Other exact-team geometry can recover a small subset of the compact current-classes delivery.
    wanted={k for k,r in scalars.items() if r['study']=='current_classes'};candidates=defaultdict(list)
    oldpath=POP/'results/ENDPOINT_GEOMETRY.json.gz'
    with gzip.open(oldpath,'rt',encoding='utf8') as f:
        for n,z in enumerate(json.load(f)):
            if z['team_key'] in wanted:candidates[z['team_key']].append((oldpath.relative_to(ROOT).as_posix()+'#index='+str(n),z))
    for path in sorted((PREC/'NEW_ENDPOINT_GEOMETRY_COMPACT').glob('*.jsonl.gz')):
        with gzip.open(path,'rt',encoding='utf8') as f:
            for n,line in enumerate(f,1):
                z=json.loads(line)
                if z['team_key'] in wanted:candidates[z['team_key']].append((path.relative_to(ROOT).as_posix()+'#L'+str(n),z))
    extensions=[];missing_extension=[]
    for r in records(EXT/'new_endpoints26/COMPLETE_NEW_ENDPOINT_SHARD_INDEX.csv.gz'):
        if r['pool_id'] in ids:extensions.append(r)
    for spec in extensions:
        path=EXT/spec['geometry_file']
        if not path.is_file():missing_extension.append(spec['geometry_file']);continue
        with gzip.open(path,'rt',encoding='utf8') as f:
            for n,line in enumerate(f,1):
                z=json.loads(line)
                if z['team_key'] in wanted:candidates[z['team_key']].append((path.relative_to(ROOT).as_posix()+'#L'+str(n),z))
    # Match each candidate against its own frozen scalar member/object identity.
    matchkeys=set(candidates);candidate_scalars=defaultdict(list)
    scalarpaths=[POP/'results/ENDPOINT_SCALARS.csv.gz']+sorted((PREC/'NEW_ENDPOINT_SCALARS').glob('*.csv.gz'))
    scalarpaths += [EXT/x['scalar_file'] for x in extensions]
    for path in scalarpaths:
        if not path.is_file():continue
        for row in records(path):
            if row['team_key'] in matchkeys:candidate_scalars[row['team_key']].append(row)
    conflicts=[];recovered=0
    for key,entries in candidates.items():
        r=scalars[key];valid=[]
        for path,z in entries:
            same=[a for a in candidate_scalars[key] if a['pool_id']==r['pool_id'] and int(a['k'])==r['k'] and set(unpack(a['member_workers']))==set(r['member_workers']) and object_ids(a.get('member_object_ids',''))==object_ids(r['member_object_ids']) and a['reference_id']==r['original_reference_id'] and a['score_status']==r['original_score_status']]
            if same and z.get('pool_id')==r['pool_id'] and z.get('geometry') is not None:valid.append((path,z['geometry']))
        if not valid:conflicts.append(dict(team_key=key,reason='candidate scalar identity or state not matched'));continue
        if any(g!=valid[0][1] for _,g in valid[1:]):conflicts.append(dict(team_key=key,reason='conflicting same-key geometry'));continue
        r['source_geometry']=[v[0] for v in valid];r['geometry']=valid[0][1];recovered+=1
    matched_links=0
    with gzip.open(TARGET/'CURRENT_CLASS_PANEL_LINKS.csv.gz','wt',encoding='utf8',newline='') as out:
        writer=None
        for row in records(CURRENT/'design/PANEL_TEAM_LINKS.csv.gz'):
            if row['team_key_a'] not in wanted and row['team_key_b'] not in wanted:continue
            members=set(unpack(row['member_set_key']))
            for key in ['team_key_a','team_key_b']:
                assert row[key] in current_all and set(unpack(current_all[row[key]]))==members,(row['panel_id'],row[key])
            if writer is None:writer=csv.DictWriter(out,fieldnames=list(row));writer.writeheader()
            writer.writerow(row);matched_links+=1
    available=[r for r in scalars.values() if r['geometry'] is not None];missing=[r for r in scalars.values() if r['geometry'] is None]
    for name,rows0 in [('INPUT_TEAMS.jsonl.gz',available),('MISSING_GEOMETRY.jsonl.gz',missing)]:
        with gzip.open(TARGET/name,'wt',encoding='utf8') as f:
            for row in sorted(rows0,key=lambda x:x['team_key']):f.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n')
    c=dict(affected_pools=len(ids),scalar_counts=counts,locator_keys=len(located),locator_shards=len(shards),locator_missing_files=missing_paths,precision_extension_files=len(extensions),precision_extension_missing_files=missing_extension,current_candidate_keys=len(candidates),current_recovered=recovered,current_conflicts=conflicts,geometries_available=len(available),geometries_missing=len(missing),missing_status_counts=dict(Counter(r['original_score_status'] for r in missing)),matching_panel_links=matched_links,original_cross_view_members_verified=True,no_fusion=True)
    (TARGET/'COVERAGE.json').write_text(json.dumps(c,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(c,ensure_ascii=False),flush=True)

def load_module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def diagnostic_modules():
    angular=load_module(STUDY,'same_room_frozen_study').angular
    fr=load_module(FR,'same_room_frozen_runner');fr.FE=SimpleNamespace(angular=angular)
    return fr,load_module(GD,'same_room_geometry_diagnostics')

def score(r,ref,engine,models,fr,gd):
    out=score_one(r,ref,engine,models);out['member_set_key']=r['member_set_key'];out['study']=r['study']
    g=r['geometry'] or {};points=g.get('points');floor=g.get('footprint');out['reference_dependent_diagnostics']=fr.reference_structure(points,ref['points_1024x512'])
    d=gd.diagnose(floor,ref['floor_xz_h']);out['reference_dependent_diagnostics'].update({k:d.get(k) for k in ['diag_status','diag_corner_recall_05','diag_wall_coverage_03','diag_wall_coverage_05']})
    n=r['original_metrics'].get('nodes');out['reference_dependent_diagnostics']['reference_nodes']=len(ref['points_1024x512'])//2
    out['reference_dependent_diagnostics']['reference_node_shortfall']=max(0,len(ref['points_1024x512'])//2-int(float(n))) if n else None
    out['reference_dependent_diagnostics_status']='complete' if points is not None else 'not_applicable_no_candidate'
    return out

def large_event_links():
    wanted=set()
    for name in ['INPUT_TEAMS.jsonl.gz','MISSING_GEOMETRY.jsonl.gz']:
        with gzip.open(TARGET/name,'rt',encoding='utf8') as f:
            for line in f:
                r=json.loads(line)
                if r['study']=='large_block':wanted.add(r['team_key'])
    members={}
    for r in records(LARGE/'ENDPOINT_SCALARS.csv.gz'):members[r['team_key']]=set(unpack(r['member_workers']))
    src=LARGE.parent/'design/STRICT_ABC_EVENTS.csv.gz';fields=['event_id','pair_key','A_members','B_members','C_members']+[f'team_key_{v}_{side}' for v in 'ABC' for side in 'ab']
    count=0
    with gzip.open(TARGET/'LARGE_BLOCK_EVENT_LINKS.csv.gz','wt',encoding='utf8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for row in records(src):
            if not any(row[k] in wanted for k in fields[5:]):continue
            for letter in 'ABC':
                expected=set(unpack(row[letter+'_members']))
                for side in 'ab':
                    key=row[f'team_key_{letter}_{side}'];assert key in members and members[key]==expected,(row['event_id'],key)
            w.writerow({k:row[k] for k in fields});count+=1
    c=read(TARGET/'COVERAGE.json');c['large_block_affected_event_links']=count;c['large_block_cross_view_members_verified']=True;(TARGET/'COVERAGE.json').write_text(json.dumps(c,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('large block cross-view event membership checked',count,flush=True)

def normalize_same_room_status():
    counts=Counter();total=0
    for path in sorted((TARGET/'shards').glob('*.jsonl.gz')):
        with gzip.open(path,'rt',encoding='utf8') as f:rows=[json.loads(x) for x in f]
        for row in rows:
            if row['reference_dependent_diagnostics_status']=='no_candidate_points':row['reference_dependent_diagnostics_status']='not_applicable_no_candidate'
            elif row['reference_dependent_diagnostics_status']=='computed':row['reference_dependent_diagnostics_status']='complete'
            counts[row['reference_dependent_diagnostics_status']]+=1;total+=1
        temp=path.with_suffix('.normalize')
        with gzip.open(temp,'wt',encoding='utf8') as f:
            for row in rows:f.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n')
        temp.replace(path)
    c=read(TARGET/'CHECKS.json');assert total==c['rows'];c['diagnostics']=dict(counts);(TARGET/'CHECKS.json').write_text(json.dumps(c,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('same room status normalized',total,dict(counts),flush=True)

def exchange_diag_shard(payload):
    path,items=payload;refs={r['target_id']:r for r in read(OUT/'reference_catalog.json')};fr,gd=diagnostic_modules()
    with gzip.open(path,'rt',encoding='utf8') as f:rows=[json.loads(line) for line in f]
    assert len(rows)==len(items)
    for row,item in zip(rows,items):
        assert row['team_key']==item['team_key'] and row['reference_id']==item['reference_id']
        g=item['geometry'] or {};points=g.get('points');ref=refs[row['reference_id']]
        diag=fr.reference_structure(points,ref['points_1024x512']);details=gd.diagnose(g.get('footprint'),ref['floor_xz_h'])
        diag.update({k:details.get(k) for k in ['diag_status','diag_corner_recall_05','diag_wall_coverage_03','diag_wall_coverage_05']})
        n=item['original_metrics'].get('nodes');diag['reference_nodes']=len(ref['points_1024x512'])//2
        diag['reference_node_shortfall']=max(0,diag['reference_nodes']-int(float(n))) if n else None
        row['reference_dependent_diagnostics']=diag
        row['reference_dependent_diagnostics_status']='complete' if points is not None else 'not_applicable_no_candidate'
    temp=path.with_suffix('.diagnostics')
    with gzip.open(temp,'wt',encoding='utf8') as f:
        for row in rows:f.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n')
    temp.replace(path)
    return len(rows),dict(Counter(row['reference_dependent_diagnostics_status'] for row in rows))

def exchange_diagnostics(jobs):
    dest=OUT/'exchange_endpoint_rescore';items={}
    with gzip.open(dest/'INPUT_TEAMS.jsonl.gz','rt',encoding='utf8') as f:
        for line in f:
            r=json.loads(line);items[r['team_key']]=r
    payload=[]
    for path in sorted((dest/'shards').glob('*.jsonl.gz')):
        with gzip.open(path,'rt',encoding='utf8') as f:keys=[json.loads(x)['team_key'] for x in f]
        payload.append((path,[items[k] for k in keys]))
    assert sum(len(x) for _,x in payload)==len(items)
    total=0;states=Counter()
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        futures=[ex.submit(exchange_diag_shard,x) for x in payload]
        for i,f in enumerate(as_completed(futures),1):
            n,c=f.result();total+=n;states.update(c)
            if i%10==0:print('exchange diagnostics',i,'/',len(payload),flush=True)
    (dest/'DIAGNOSTICS_CHECKS.json').write_text(json.dumps(dict(rows=total,status=dict(states),scores_unchanged=True,new_fusion=False),ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    c=read(dest/'CHECKS.json');c['reference_dependent_diagnostics']='completed_or_not_applicable';c['diagnostic_status']=dict(states);(dest/'CHECKS.json').write_text(json.dumps(c,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('exchange diagnostics complete',total,dict(states),flush=True)

def shard(payload):
    n,items=payload;path=TARGET/'shards'/f'{n:05d}.jsonl.gz'
    if path.exists():raise FileExistsError(path)
    refs={r['target_id']:r for r in read(OUT/'reference_catalog.json')};fr,gd=diagnostic_modules()
    with scoring_engine() as (engine,models):result=[score(r,refs[r['reference_id']],engine,models,fr,gd) for r in items]
    temp=path.with_suffix('.writing')
    with gzip.open(temp,'wt',encoding='utf8') as f:
        for row in result:f.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n')
    temp.replace(path);return len(result)

def run(jobs):
    (TARGET/'shards').mkdir(parents=True,exist_ok=True)
    with gzip.open(TARGET/'INPUT_TEAMS.jsonl.gz','rt',encoding='utf8') as f:items=[json.loads(x) for x in f]
    blocks=[(i//200,items[i:i+200]) for i in range(0,len(items),200)];total=0
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        futures=[ex.submit(shard,b) for b in blocks]
        for i,f in enumerate(as_completed(futures),1):
            total+=f.result()
            if i%10==0:print('same room shards',i,'/',len(blocks),flush=True)
    states=Counter();diagnostics=Counter()
    for n,_ in blocks:
        with gzip.open(TARGET/'shards'/f'{n:05d}.jsonl.gz','rt',encoding='utf8') as f:
            for line in f:
                r=json.loads(line);states[r['rescore_state']]+=1;diagnostics[r['reference_dependent_diagnostics_status']]+=1
    assert total==len(items)
    (TARGET/'CHECKS.json').write_text(json.dumps(dict(rows=total,shards=len(blocks),states=states,diagnostics=diagnostics,new_fusion=False),ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('done',total,dict(states),dict(diagnostics),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--part',required=True,choices=['inventory','score','normalize','verify_links','exchange_diagnostics']);ap.add_argument('--jobs',type=int,default=4);a=ap.parse_args()
    if a.part=='inventory':inventory()
    elif a.part=='score':run(a.jobs)
    elif a.part=='normalize':normalize_same_room_status()
    elif a.part=='verify_links':large_event_links()
    else:exchange_diagnostics(a.jobs)
