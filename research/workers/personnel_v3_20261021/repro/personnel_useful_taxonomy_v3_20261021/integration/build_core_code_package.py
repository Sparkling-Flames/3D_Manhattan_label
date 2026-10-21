#!/usr/bin/env python3
"""Publish the runnable research additions and exact small historical inputs.

Native main inputs and already delivered endpoint tables are referenced, not
copied. This is a packaging operation and makes no inference or fusion calls.
"""
from pathlib import Path
import csv, hashlib, importlib.metadata, json, os, platform, sys, zipfile

HERE=Path(__file__).resolve().parent
V3=HERE.parent
REPO=V3.parents[2]
OLD=REPO/'research/workers/personnel_global_composition_20261021'
RECEIPTS=Path('/tmp/hohonet_v3_library_20261021')

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def successful():
    latest={}
    for p in sorted(RECEIPTS.glob('receipt_*.json')):
        try: rows=json.loads(p.read_text())['results']
        except (ValueError,KeyError):continue
        for r in rows:
            if r.get('status')=='succeeded':latest[r['local_path']]=r
    return latest

def restore_map():
    rows=[]
    vrel=str(V3.relative_to(REPO))
    for local,r in successful().items():
        p=Path(local)
        if p.suffix!='.zip' or not p.is_file():continue
        with zipfile.ZipFile(p) as z:names=z.namelist()
        tops=sorted({n.split('/')[0] for n in names})
        if tops==['batches']:dest=vrel+'/composition'
        elif 'research' in tops:dest='.'
        elif 'semi' in tops and 'analyze_responses.py' in tops:dest=vrel+'/response'
        elif 'F01_PANEL_MEMBERSHIP.csv.gz' in tops:dest=vrel+'/composition'
        elif 'recover_geometry.py' in tops:dest=vrel+'/integration/phase1_geometry_recovery'
        else:dest=vrel
        snapshot_only=('冻结阶段' in p.name or '实际选队规则与冻结选择' in p.name or '规模覆盖与语义复用_阶段' in p.name)
        rows.append(dict(package=p.name,sha256=sha(p),bytes=p.stat().st_size,
            extract_under_repository=dest,archive_top_levels='|'.join(tops),
            role='earlier_checkpoint_preserve_identity' if snapshot_only else 'completed_result_or_frozen_native_batch',
            download_url='https://chatgpt.com/api/library/files/'+r['library_file_id']+'/download',
            temporary_entries=sum('.partial' in n or '.tmp' in n for n in names)))
    p=HERE/'PACKAGE_RESTORE_DESTINATIONS.csv'
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    return p

def main():
    restore=restore_map()
    sys.path.insert(0,'/tmp/hohonet_deps')
    versions={}
    for x in ['numpy','pandas','scipy','scikit-learn','shapely','Pillow','matplotlib']:
        try:versions[x]=importlib.metadata.version(x)
        except importlib.metadata.PackageNotFoundError:versions[x]=None
    env=HERE/'REPRODUCTION_ENVIRONMENT.json'
    env.write_text(json.dumps(dict(python=platform.python_version(),platform=platform.platform(),
        packages=versions,read_only_packaging=True,native_calls=0,
        authoritative_native_contract='NATIVE_CONTRACT_MAIN_IDENTITY.json'),indent=2))
    files=set()
    for root in [V3,OLD]:
        for p in root.rglob('*.py'):
            if not any(x.startswith('.') or x in ('__pycache__','runtime','recovered_training_input') for x in p.relative_to(root).parts):files.add(p)
    # The old generated project is absent as a directory in main; these exact
    # compact inputs are needed by the current frozen label/feature adapters.
    oldinputs=['composition/FROZEN_LABELS.csv','composition/legacy_composition_labels.csv',
        'multivariate/continuous_features_lobo.csv.gz','multivariate/labels_lobo.csv.gz',
        'multivariate/same_source_candidate_labels.csv','multivariate/FIELD_SCHEMA.json',
        'multivariate/DOMAIN_SUBSET_SCALING.json','multivariate/domain_subset_26_coverage.csv',
        'requirements_research.txt','REPRODUCE_ZH.md','INPUT_REFERENCES.csv']
    for rel in oldinputs:
        p=OLD/rel;assert p.is_file(),p;files.add(p)
    for rel in ['REPRODUCE_AND_RECOVER_ZH.md','RESEARCH_DESK_FIELD_GUIDE_ZH.md',
        'MAIN_INPUT_REFERENCES.json','NATIVE_CONTRACT_MAIN_IDENTITY.json',
        'ENDPOINT_CSV_RESTORE_SCHEMA.json','RESTORE_SMOKE_CHECK.json',
        'PHASE1_PHASE2_PHASE3_DOMAIN_COVERAGE_26x2.csv','PHASE3_METHOD_EXPERIMENT_COVERAGE.csv',
        'EXACT_SCALE_RECEIPT.json','COVERAGE_CHECKPOINT.json']:
        files.add(HERE/rel)
    files.update([restore,env,V3/'report/人员分类与整体构成_整合报告_20261021.md'])
    # Design parameters/receipts are small, while complete member requests remain
    # in their already delivered design/native packages.
    for sub in ['taxonomy','composition','utility','response']:
        for p in (V3/sub).glob('*'):
            if p.is_file() and p.suffix in ('.json','.md','.txt') and p.stat().st_size<250000 and any(t in p.name.upper() for t in ['DESIGN','FREEZE','AMENDMENT','SCHEMA','FIELD','REPRODUCE','PARAMETER','ENVIRONMENT','EXECUTION_EQUIVALENCE']):files.add(p)
    for p in (HERE/'taxonomy_adoption_synthesis/fast_validation').rglob('*EQUIVALENCE_RECEIPT.json'):files.add(p)
    assert all(p.is_file() for p in files)
    rows=[dict(path=str(p.relative_to(REPO)),bytes=p.stat().st_size,sha256=sha(p),
         kind='code' if p.suffix=='.py' else 'small_frozen_input' if p.is_relative_to(OLD) else 'contract_or_recovery') for p in sorted(files)]
    manifest=HERE/'CORE_CODE_PACKAGE_MANIFEST.csv'
    with manifest.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    pack=HERE/'HOHONET_v3_复现代码与必要小输入_20261021.zip'
    tmp=pack.with_suffix('.zip.partial')
    with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(files|{manifest}):z.write(p,str(p.relative_to(REPO)))
    with zipfile.ZipFile(tmp) as z:
        assert z.testzip() is None
        assert not any('.partial' in n or '__pycache__' in n for n in z.namelist())
    with tmp.open('rb') as f:os.fsync(f.fileno())
    os.replace(tmp,pack)
    receipt=dict(status='complete',package=str(pack),sha256=sha(pack),bytes=pack.stat().st_size,
        files=len(files)+1,code_files=sum(r['kind']=='code' for r in rows),
        repository_main='324dba44d0a82d9d64a62965f2e549ee05165417',
        extract_under_repository='.',native_calls=0,
        omitted='native main input copies, raw-image corpus, environments, full runtime caches, duplicate endpoint tables')
    (HERE/'CORE_CODE_PACKAGE_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
    print(json.dumps(receipt,ensure_ascii=False))

if __name__=='__main__':main()
