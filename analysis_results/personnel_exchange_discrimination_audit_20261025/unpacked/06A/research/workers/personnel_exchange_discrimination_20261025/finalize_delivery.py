"""Assemble final comparison exports and compact delivery; never runs fusion."""
from pathlib import Path
import argparse, csv, hashlib, json, os, zipfile
import pandas as pd

ROOT = Path(__file__).resolve().parent
PREFIX = Path('research/workers/personnel_exchange_discrimination_20261025')
STAGES = ['screen', 'confirm', 'reverse_screen', 'reverse_confirm']
EXPORTS = {
    'ALL_METHOD_N_M_COMPARISON.csv.gz': 'METHOD_N_M_COMPARISON.csv',
    'ALL_METHOD_N_M_OUTCOMES.csv.gz': 'ALL_OUTCOMES_BY_METHOD_N_M.csv.gz',
    'ALL_DIFFICULTY_COMPARISON.csv.gz': 'DIFFICULTY_COMPARISON.csv',
    'ALL_DIFFICULTY_OUTCOMES.csv.gz': 'ALL_OUTCOMES_BY_DIFFICULTY.csv.gz',
    'ALL_SEMANTIC_ROLE_COMPARISON.csv.gz': 'SEMANTIC_ROLE_COMPARISON.csv',
    'ALL_SEMANTIC_ROLE_OUTCOMES.csv.gz': 'ALL_OUTCOMES_BY_SEMANTIC_ROLE.csv.gz',
    'ALL_POOL_METHOD_N_M_SUMMARIES.csv.gz': 'POOL_METHOD_N_M_SUMMARY.csv.gz',
    'ALL_BUILDING_METHOD_N_M_SUMMARIES.csv.gz': 'BUILDING_METHOD_N_M_SUMMARY.csv.gz',
    'ALL_RISK_TIME_SUMMARIES.csv.gz': 'RISK_TIME_SUMMARY.csv',
}

def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(2**20), b''): h.update(b)
    return h.hexdigest()

def comparisons():
    records = []
    for dest, src in EXPORTS.items():
        frames = []
        for stage in STAGES:
            p = ROOT / 'analysis' / stage / src
            frame = pd.read_csv(p, low_memory=False)
            frame.insert(0, 'delivery_source_stage', stage)
            frames.append(frame)
            records.append({'output': f'final/{dest}', 'source': str(p.relative_to(ROOT)),
                            'source_rows': len(frame), 'source_sha256': sha(p)})
        frame = pd.concat(frames, ignore_index=True, sort=False)
        frame.to_csv(ROOT / 'final' / dest, index=False, compression='gzip')
        print(dest, len(frame), flush=True)
    pd.DataFrame(records).to_csv(ROOT / 'final/COMPARISON_EXPORT_SOURCES.csv', index=False)

def allowed(p):
    return (p.is_file() and not any(s.startswith('.') or s == '__pycache__' for s in p.relative_to(ROOT).parts)
            and not p.name.endswith(('.pyc', '.writing', '.log'))
            and not p.name.endswith('_LOG.txt'))

def make_zip(name, paths, prefix=True, additional=None):
    dest = ROOT / 'deliverables' / name
    entries = {}
    for p in paths:
        if allowed(p): entries[str(PREFIX / p.relative_to(ROOT)) if prefix else str(p.relative_to(ROOT))] = p
    if additional: entries.update(additional)
    manifest = [{'archive_path': k, 'bytes': p.stat().st_size, 'sha256': sha(p)} for k,p in sorted(entries.items())]
    tmp = dest.with_suffix('.zip.writing')
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for k,p in sorted(entries.items()): z.write(p,k)
        z.writestr('PACKAGE_FILE_MANIFEST.json', json.dumps(manifest, ensure_ascii=False, indent=2))
    with zipfile.ZipFile(tmp) as z:
        err = z.testzip()
        if err: raise ValueError(f'Corrupt archive entry: {err}')
    os.replace(tmp,dest)
    receipt = {'file': str(dest), 'bytes': dest.stat().st_size, 'sha256': sha(dest), 'files':len(entries),
               'crc_verified': True, 'new_fusion_for_packaging': False,
               'archive_layout': 'repository_root' if prefix else 'research_directory'}
    print(json.dumps(receipt, ensure_ascii=False), flush=True)
    return receipt, manifest

def packages():
    core = set()
    for folder in ['classifications', 'features', 'features_scope', 'reverse', 'runtime', 'report_integration',
                   'analysis/condition_support', 'analysis/method_adoption', 'analysis/figures']:
        core.update((ROOT / folder).rglob('*'))
    core.update(ROOT.glob('*.py'))
    for filename in ['README.md','DATA_DICTIONARY.md','REPRODUCTION.md','DOWNLOAD_INDEX.md','DOWNLOAD_INDEX.csv',
                     'SCREEN_FINDINGS_ZH.md','STAGE01_README.md','STAGE03_README.md','STAGE04_README.md','STAGE05_README.md']:
        core.add(ROOT / filename)
    core.update((ROOT / 'analysis').glob('*.*'))
    core.update((ROOT / 'figures').glob('*.*'))
    # Include the small subset font needed by figure scripts, never a complete font cache.
    for p in (ROOT/'figures').rglob('*'):
        if p.is_file() and (p.suffix in ['.ttf','.otf'] and p.stat().st_size < 1_000_000 or p.name.startswith('OFL')): core.add(p)
    for stage in STAGES:
        for p in (ROOT/'analysis'/stage).glob('*'):
            if p.name.startswith(('GEOMQ_K3','REVERSE_BRANCH','REVERSE_CLASS_SIZE','FAIR_ROLE_COMPARISON',
                                  'FAIR_ROLE_RISK_TIME','FAIR_ROLE_COMMON_POOL','COMMON_POOL_BASELINE',
                                  'FOLD_CLASS_ROLE_MAP')) or p.name.endswith(('.md','.json')):
                core.add(p)
    # Stage05 already contains the full fixed-block paths. Retain its small entry tables here too.
    for folder in ['analysis/target_omissions','analysis/size_paths','analysis/large_team_ac_tail']:
        for p in (ROOT/folder).glob('*'):
            if p.suffix in ['.md','.py','.png','.svg','.json'] or p.name.startswith(('KEY_', 'SCALE_CONDITION', 'AC_TAIL_CONDITION')):
                core.add(p)
    for p in (ROOT/'stage00').glob('*'):
        if p.is_file() and p.stat().st_size < 1_000_000: core.add(p)
    for name in ['README.md','INTEGRATION_COMPLETE.json','MAIN_REPORT_INSERTIONS_COMPLETED_ZH.md',
                 'SOURCE_SNAPSHOT_MANIFEST.csv','NEW_LINK_FILE_CHECK.csv']:
        core.add(ROOT/'report_integration'/name)
    source_main = ROOT/'report_integration/sources/docs/thesis_main/人员分类与构成不确定性_研究组织与比较清单_20261022.md'
    core.add(source_main)
    core.add(ROOT/'repo_integration/personnel_main_update.patch')
    core.add(ROOT/'repo_integration/docs/thesis_main/人员分类与构成不确定性_研究组织与比较清单_20261022.md')
    for rel in pd.read_csv(ROOT/'report_integration/NEW_LINK_FILE_CHECK.csv')['work_relative_path']:
        core.add(ROOT/rel)
    for p in (ROOT/'final').iterdir():
        if p.name not in ['ALL_EVENTS_EXACT.csv.gz','EVENT_ENDPOINT_LINKS.csv.gz','UNIQUE_ENDPOINT_INVENTORY.csv.gz','ENDPOINT_REUSE_COUNTS.csv.gz']:
            core.add(p)
    core = {p for p in core if allowed(p) and not (p.suffix in ['.otf','.ttc'] and p.stat().st_size > 1_000_000)}
    main = ROOT/'repo_integration/docs/thesis_main/人员分类与构成不确定性_研究组织与比较清单_20261022.md'
    core_receipt, manifest = make_zip('HOHONET_换类区分度_阶段06A_主报告标签全比较与复现_20261025.zip',core,
        additional={'docs/thesis_main/人员分类与构成不确定性_研究组织与比较清单_20261022.md': main})
    ledger = [ROOT/'final'/n for n in ['ALL_EVENTS_EXACT.csv.gz','EVENT_ENDPOINT_LINKS.csv.gz',
        'UNIQUE_ENDPOINT_INVENTORY.csv.gz','ENDPOINT_REUSE_COUNTS.csv.gz','FINAL_LEDGER_RECEIPT.json','STAGE_PHASE_COVERAGE.csv']]
    ledger_receipt_path = ROOT/'deliverables/STAGE06C_PACKAGE_RECEIPT.json'
    if ledger_receipt_path.exists():
        ledger_receipt = json.loads(ledger_receipt_path.read_text())
        assert sha(Path(ledger_receipt['file'])) == ledger_receipt['sha256']
    else:
        ledger_receipt,_ = make_zip('HOHONET_换类区分度_阶段06C_97552事件与283211端点总账_20261025.zip', ledger)
    (ROOT/'deliverables/STAGE06_FINAL_PACKAGE_RECEIPTS.json').write_text(json.dumps([core_receipt,ledger_receipt],ensure_ascii=False,indent=2))
    pd.DataFrame(manifest).to_csv(ROOT/'deliverables/FINAL_CORE_FILE_MANIFEST.csv',index=False)
    paths=[core_receipt['file'],ledger_receipt['file']]
    standalone=[('final/人员分类与构成不确定性_主报告_更新至20261025.md','report'),
        ('final/20261025_新增分类与有效换类章节.md','report'),('final/有效换类条件_20261025.csv','sheet'),
        ('analysis/FINAL_CONDITIONS_COMPACT.csv','sheet'),('analysis/METHOD_ADOPTION_DECISIONS.csv','sheet'),
        ('final/LABELS_ALL.csv','sheet'),('final/LABELS_LOBO.csv.gz','other'),
        ('final/ALL_EVENTS_EXACT.csv.gz','other'),('final/UNIQUE_ENDPOINT_INVENTORY.csv.gz','other'),
        ('analysis/figures/CONFIRM_Q_SEPARATION.png','image'),('cases_size_threshold/SIZE_THRESHOLD_MECHANISM_ZH.png','image')]
    req={'uploads':[{'local_path':p,'purpose':'create_library_file','library_artifact_type':'other'} for p in paths]
         +[{'local_path':str(ROOT/p),'purpose':'create_library_file','library_artifact_type':t} for p,t in standalone]}
    (ROOT/'deliverables/UPLOAD_STAGE06_FINAL.json').write_text(json.dumps(req,ensure_ascii=False,indent=2))

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--step',choices=['comparisons','packages'],required=True);args=a.parse_args()
    comparisons() if args.step=='comparisons' else packages()
