"""Bind one run to audited observations, reviews, timing and numerical code.

Raw exports stay local. Cloud reruns consume the verified, self-contained run root.
"""
from __future__ import annotations
import argparse, copy, gzip, hashlib, json, shutil, zipfile
from pathlib import Path
import numpy as np
import pandas as pd
from . import release, diagnostics, history_analysis, extra_checks, analysis_extensions, composition_sensitivity

REPO = Path(__file__).resolve().parents[4]
BASE = REPO/'analysis_results/clustering_release_local_20260920'
ARCHIVE = REPO/'analysis_results/clustering_release_received_20260920'
CORRECTIONS = {'8ffe08f072e2b12e': ('4738', 28, 'researcher_coordinate_correction'),
               '9b8f8bec4da82b48': ('4784', 20, 'researcher_confirmed_point_removed')}

def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def pointsha(points):
    return hashlib.sha256(json.dumps(points, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def rows_at(p):
    with gzip.open(p, 'rt', encoding='utf8') as f:
        return [json.loads(line) for line in f if line.strip()]

def write_rows(p, rows):
    # Stable gzip header makes identical batches byte reproducible.
    with Path(p).open('wb') as raw, gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0) as f:
        f.write(''.join(json.dumps(r, ensure_ascii=False, allow_nan=False)+'\n' for r in rows).encode())

def raw_points(annotation):
    pts=[]
    for r in annotation.get('result', []):
        if r.get('type') in ('keypointlabels', 'keypointregion'):
            v=r['value'];p=[float(v['x'])*1024/100, float(v['y'])*512/100]
            if not np.isfinite(p).all(): raise ValueError('Nonfinite raw point')
            pts.append(p)
    return pts

def corrected(rows, new_index, source_version):
    result=copy.deepcopy(rows);audit=[]
    for r in result:
        cid=r['canonical_annotation_id']
        if cid not in CORRECTIONS: continue
        annotation, count, action=CORRECTIONS[cid]
        _,project,task,worker,aid=r['raw_annotation_version_id'].split('|')
        if project!='28' or task!='3081' or aid!=annotation: raise ValueError('Correction identity mismatch')
        p=raw_points(new_index[task,worker,aid][1])
        if len(p)!=count or not np.isfinite(p).all() or not all(0<=x<=1024 and 0<=y<512 for x,y in p):
            raise ValueError('Correction count/range mismatch')
        old=r['effective_points_1024x512']
        if aid=='4738':
            differences=[(i,j) for i,(a,b) in enumerate(zip(old,p)) for j in range(2) if abs(a[j]-b[j])>1e-8]
            if len(differences)!=1 or differences[0][1]!=1: raise ValueError('Expected exactly one y correction')
            i,j=differences[0]
            if not np.isclose(old[i][j],p[i][j]*10): raise ValueError('Expected documented tenfold y correction')
        else:
            bad=[i for i,(x,y) in enumerate(old) if not (0<=x<=1024 and 0<=y<512)]
            if len(bad)!=1 or not np.allclose([v for i,v in enumerate(old) if i!=bad[0]],p,atol=1e-8,rtol=0):
                raise ValueError('Expected removal of the documented out-of-range point only')
        r.update(effective_points_1024x512=p,effective_point_count=count,calculation_included=True,
                 processing_status=action,correction_source_version=source_version,
                 confirmation_source='user_explicit_apply_Project28_20260920',researcher_corrected=True)
        audit.append(dict(id=cid,action=action,old_effective_count=len(old),new_effective_count=count,
                          old_point_version=pointsha(old),new_point_version=pointsha(p),independent_vote_added=False))
    if len(audit)!=2: raise ValueError('Both confirmed corrections must be present')
    return result,audit

def intake(rows, batches):
    """Convert explicit batch manifests; never infer worker, condition or independence."""
    result=copy.deepcopy(rows);byid={r['canonical_annotation_id']:r for r in result}
    seen={(r['image_id'],r['raw_condition'],r['worker_id']) for r in result}
    receipts=[]
    for manifest_path in batches:
        m=read(manifest_path)
        required={'batch_id','stage','project_id','export_path','worker_map','tasks','record_type','annotation_form_version'}
        if not required<=m.keys(): raise ValueError('Incomplete batch manifest')
        if m['record_type']!='independent_initial' or m['annotation_form_version']!='manual_scope_only_v1':
            raise ValueError('This intake accepts explicit independent manual_scope_only_v1 batches only')
        ep=(Path(manifest_path).parent/m['export_path']).resolve();export=read(ep)
        task_map={str(t['runtime_task_id']):t for t in m['tasks']}
        if len(task_map)!=len(m['tasks']): raise ValueError('Duplicate planned task mapping')
        n=0
        for t in export:
            for a in t.get('annotations',[]):
                if a.get('was_cancelled') or a.get('skipped'): raise ValueError('Cancelled response needs explicit disposition')
                if str(t['id']) not in task_map: raise ValueError('Submitted task has no approved mapping')
                meta=task_map[str(t['id'])];w=a['completed_by'];w=str(w['id'] if isinstance(w,dict) else w)
                worker=m['worker_map'].get(w)
                if not worker or not __import__('re').fullmatch(r'W\d{3,}',worker): raise ValueError('Unknown stable worker')
                from urllib.parse import unquote,urlparse
                if Path(unquote(urlparse(t['data']['image']).path)).stem!=meta['image_id']: raise ValueError('Mapped image differs from export')
                if meta['raw_condition']!='manual' or meta['assistance_exposure']!='none': raise ValueError('New form requires explicit unaided Manual')
                identity=f"{m['stage']}|{m['project_id']}|{t['id']}|{w}|{a['id']}"
                cid=hashlib.sha256(identity.encode()).hexdigest()[:20]
                p=raw_points(a);key=(meta['image_id'],'manual',worker)
                if cid in byid:
                    if byid[cid]['raw_points_1024x512']!=p: raise ValueError('Changed existing response is a revision, not a new vote')
                    continue
                if key in seen: raise ValueError('Repeated person/image/condition requires explicit revision review')
                scope=[z for z in a.get('result',[]) if z.get('from_name','').lower()=='scope']
                ok=bool(p) and all(0<=x<=1024 and 0<=y<512 for x,y in p)
                r=dict(canonical_annotation_id=cid,annotation_identity=identity,raw_annotation_version_id=identity,
                       raw_export_path=str(ep),raw_export_version=sha(ep),worker_id=worker,image_id=meta['image_id'],
                       building_id=meta['building_id'],image_code=meta.get('image_code',meta['image_id']),
                       project_id=str(m['project_id']),runtime_task_id=str(t['id']),raw_annotation_id=str(a['id']),
                       raw_condition='manual',assistance_exposure='none',stage=m['stage'],block_index=m.get('block_index',0),
                       record_type='independent_initial',batch_id=m['batch_id'],annotation_form_version='manual_scope_only_v1',
                       raw_points_1024x512=p,effective_points_1024x512=copy.deepcopy(p),raw_point_count=len(p),effective_point_count=len(p),
                       coordinate_width=1024,coordinate_height=512,calculation_included=ok,processing_status='unchanged' if ok else 'pending_point_review',
                       imputed_point=False,imputation_provenance=None,scope_original=scope,
                       difficulty_status='not_collected',model_issue_status='not_applicable',active_time_status='unfrozen',active_time_seconds=None)
                result.append(r);byid[cid]=r;seen.add(key);n+=1
        receipts.append(dict(batch_id=m['batch_id'],export_version=sha(ep),new_independent=n))
    return sorted(result,key=lambda r:r['canonical_annotation_id']),receipts

def prepare_run(root, project28, batches=()):
    from tools.thesis_main.analysis.audit_building_convergence_20260908 import source_annotation_index,require_same_points
    root=Path(root).resolve()
    if (root/'RUN_MANIFEST.json').exists(): raise ValueError('Run exists; use another directory or rerun its verified inputs')
    root.mkdir(parents=True,exist_ok=True)
    archive=REPO/'analysis_results/pro_next_round_20260920/pro_next_round_20260920.zip'
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            if Path(name).is_absolute() or '..' in Path(name).parts: raise ValueError('Unsafe evidence archive path')
        z.extractall(root/'input/source')
    inp=root/'inputs';inp.mkdir()
    original=root/'input/source/analysis_results/paired_split_research_received_20260920/inputs'
    for p in original.iterdir():
        if p.is_file(): shutil.copy2(p,inp/p.name)
    rows=rows_at(inp/'responses.jsonl.gz');exports={};lineage=[]
    for r in rows:
        path=r['raw_export_path']
        if path not in exports: exports[path]=source_annotation_index(read(REPO/path))
        stage,project,task,worker,annotation=r['raw_annotation_version_id'].split('|')
        t,a=exports[path][task,worker,annotation];require_same_points(raw_points(a),r['raw_points_1024x512'])
        from urllib.parse import unquote,urlparse
        if Path(unquote(urlparse(t['data']['image']).path)).stem!=r['image_id'] or int(worker)!=int(r['worker_id'][1:]):
            raise ValueError('Raw identity/image mismatch')
        lineage.append(dict(id=r['canonical_annotation_id'],source_export=path,source_version=sha(REPO/path),project=project,task=task,annotation=annotation,worker=r['worker_id'],raw_points_verified=True))
        r.update(project_id=project,runtime_task_id=task,raw_annotation_id=annotation,record_type='independent_initial',annotation_form_version='historical_frozen')
    if len(rows)!=2501 or len({r['canonical_annotation_id'] for r in rows})!=2501: raise ValueError('Historical baseline count mismatch')
    new=source_annotation_index(read(project28));old=exports[next(r['raw_export_path'] for r in rows if r['canonical_annotation_id']=='8ffe08f072e2b12e')]
    changed={k for k in old if old[k][1]['result']!=new[k][1]['result']}
    if set(old)!=set(new) or changed!={('3081','2','4738'),('3081','18','4784')}: raise ValueError('Unexpected Project28 changes')
    rows,correction_audit=corrected(rows,new,sha(project28))
    rows,receipts=intake(rows,batches);write_rows(inp/'responses.jsonl.gz',rows)
    release.writejson(inp/'corrections.json',correction_audit)
    pd.DataFrame(lineage).to_csv(inp/'source_lineage.csv',index=False,encoding='utf-8-sig')
    prior=pd.read_csv(inp/'prior_response_audit.csv')
    additions=[dict(id=r['canonical_annotation_id'],image_id=r['image_id'],code=r.get('image_code',r['image_id'])) for r in rows if r['canonical_annotation_id'] not in set(prior.id)]
    pd.concat([prior,pd.DataFrame(additions)],ignore_index=True).to_csv(inp/'prior_response_audit.csv',index=False,encoding='utf-8-sig')
    # Frozen values and eligibility are copied unchanged; researcher edits add no time.
    tp=REPO/'analysis_results/local_point_research_received_20260919/previous_pairing_time/results/time_record_audit.csv'
    shutil.copy2(tp,inp/'frozen_time_audit.csv');time=pd.read_csv(tp).set_index('id');timing=[]
    for r in rows:
        cid=r['canonical_annotation_id'];t=time.loc[cid] if cid in time.index else None
        if t is not None and (t.worker!=r['worker_id'] or t.image_id!=r['image_id'] or t.condition!=r['raw_condition']): raise ValueError('Frozen time identity mismatch')
        timing.append(dict(id=cid,status='historical_frozen' if t is not None else 'excluded_worker_no_time_analysis' if r['worker_id'] in ['W019','W026'] else 'unfrozen',
                           seconds=t.seconds if t is not None else None,strict_eligible=bool(t.strict_eligible) if t is not None else False,
                           timing_version=sha(tp) if t is not None else None,source_match=t.source_seconds_match if t is not None else None))
    pd.DataFrame(timing).to_csv(inp/'time_context.csv',index=False,encoding='utf-8-sig')
    supp=root/'input/supplement';shutil.copytree(ARCHIVE/'supplement',supp,dirs_exist_ok=True)
    latest=read(REPO/'analysis_results/spatial_dimensions_review_20260913_v2/空间描述与历轮人工记录.json')
    reg=read(REPO/'analysis_results/scene_image_exploration_20260910_v1/same_room_selection_registry_v2_20260912.json')
    reg['images']=latest['images']
    for r in reg['images']:
        r['spatial_classification']=dict(r['spatial_classification'],coarse_type=r['current_coarse_review']['value'])
    release.writejson(supp/'scene_registry_current.json',reg)
    (supp/'same_room_selection_registry_20260912.json').unlink()
    reviews=inp/'user_reviews';reviews.mkdir()
    for name in ['user12_review.json','user_six_review.json']:
        shutil.copy2(inp/name,reviews/name)
    for p in (root/'input/source/analysis_results/human_review_reconciliation_20260918').glob('*.json'):
        shutil.copy2(p,reviews/p.name)
    accounting=dict(historical_canonical=2501,current_canonical=len(rows),historical_source_exports=len(exports),
                    original_points_checked=2501,corrections=correction_audit,project28_changed_results=2,
                    historical_time_unchanged=sha(tp)==sha(inp/'frozen_time_audit.csv'),new_batches=receipts,
                    expected_collection_480_is_not_completion=True,new_batch_time_frozen=False)
    release.writejson(root/'DATA_AUDIT.json',accounting)
    bind(root)
    return accounting

def bind(root):
    files={str(p.relative_to(root)).replace('\\','/'):sha(p) for folder in ['inputs','input'] for p in sorted((root/folder).rglob('*')) if p.is_file() and '__pycache__' not in str(p)}
    code={str(p.relative_to(REPO)).replace('\\','/'):sha(p) for folder in [Path(__file__).parent,Path(__file__).parent.parent/'paired_split_research'] for p in sorted(folder.glob('*.py')) if p.name not in ['pro_package.py','release_review.py']}
    payload=dict(schema='clustering_release_run_v1',data_version='history2501_Project28_corrected_v1',method=release.CONFIG,input_files=files,code_files=code)
    version=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
    release.writejson(root/'RUN_MANIFEST.json',dict(payload,run_id=version[:16],version=version,publication_status='candidate_pending_human_visual_review'))

def verify(root):
    m=read(root/'RUN_MANIFEST.json')
    for name,expected in m['input_files'].items():
        if sha(root/name)!=expected: raise ValueError('Input version mismatch: '+name)
    for name,expected in m['code_files'].items():
        if sha(REPO/name)!=expected: raise ValueError('Code version mismatch: '+name)
    if m['method']!=release.CONFIG: raise ValueError('Method config mismatch')
    return m

def run(root,permutations=128):
    root=Path(root).resolve();m=verify(root);out=root/'results';out.mkdir(exist_ok=True)
    release.main(root,out);diagnostics.run(root,out)
    cache=history_analysis.run_history(root,out,permutations)
    history_analysis.run_composition(root,out,cache);history_analysis.run_rooms(root,out,cache)
    history_analysis.run_prediction(root,out,cache);extra_checks.run(root,out)
    analysis_extensions.run(root,out);composition_sensitivity.run(root,out)
    verify(root)
    members=pd.read_csv(out/'memberships.csv');elig=pd.read_csv(out/'eligibility.csv')
    primary=members[(members.metric=='split_cyclic')&(members.cut==9)]
    if primary.id.duplicated().any() or set(primary.id)!=set(elig.loc[elig.split_available,'id']): raise ValueError('Membership conservation failure')
    # Raw odd counts are provenance, not an exclusion rule: use confirmed effective points.
    rows=rows_at(root/'inputs/responses.jsonl.gz')
    repaired=[r for r in rows if r['raw_point_count']%2 and r['effective_point_count'] is not None
              and r['effective_point_count']!=r['raw_point_count']]
    byid=elig.set_index('id');repair_audit=[]
    for r in repaired:
        cid=r['canonical_annotation_id'];e=byid.loc[cid]
        if not e.excluded_worker and not e.split_available:
            raise ValueError('Confirmed odd-point repair unexpectedly unavailable: '+cid)
        repair_audit.append(dict(id=cid,worker=r['worker_id'],code=e.code,
            raw_count=r['raw_point_count'],effective_count=r['effective_point_count'],
            processing_status=r['processing_status'],imputed_point=r['imputed_point'],
            excluded_worker=bool(e.excluded_worker),primary_included=cid in set(primary.id)))
    release.writejson(out/'CONFIRMED_ODD_REPAIR_AUDIT.json',repair_audit)
    release.writejson(out/'PUBLICATION_CHECK.json',dict(run_id=m['run_id'],numerical_gate='passed',human_visual_gate='pending',
        canonical=len(elig),excluded=int(elig.excluded_worker.sum()),primary_eligible=len(primary),
        nonexcluded_unavailable=int((~elig.excluded_worker&~elig.split_available).sum()),
        new_time_gate='unfrozen_not_used',researcher_corrections_not_new_votes=True))
    release.writejson(out/'RESULT_MANIFEST.json',dict(run_id=m['run_id'],files={p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file() and p.name!='RESULT_MANIFEST.json'}))
    print(json.dumps(read(out/'PUBLICATION_CHECK.json'),ensure_ascii=False),flush=True)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run-root',type=Path,default=BASE/'current')
    ap.add_argument('--prepare',action='store_true');ap.add_argument('--project28',type=Path)
    ap.add_argument('--new-batch-manifest',action='append',type=Path,default=[]);ap.add_argument('--permutations',type=int,default=128)
    args=ap.parse_args()
    if args.prepare:
        if not args.project28: ap.error('--prepare requires --project28')
        prepare_run(args.run_root,args.project28,args.new_batch_manifest)
    elif args.new_batch_manifest: ap.error('Append input requires a new prepared run directory')
    run(args.run_root,args.permutations)

if __name__=='__main__': main()
