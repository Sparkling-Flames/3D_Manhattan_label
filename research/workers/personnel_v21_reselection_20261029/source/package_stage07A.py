"""Create the compact final research core, excluding large event/geometry caches."""
from pathlib import Path
import csv,gzip,hashlib,io,json,zipfile

W=Path(__file__).resolve().parents[1]
D=W/'deliverables'
NAME='HOHONET_v21_阶段07A_主报告分类采用与复现代码_20261029.zip'

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()

paths=set()
def add(p):
    p=W/p
    if p.is_file() and not any(q in p.parts for q in ['__pycache__']) and not p.name.endswith(('.writing','.tmp','.log','.pyc')):paths.add(p)
def tree(rel):
    for p in (W/rel).rglob('*'):
        if p.is_file():add(p.relative_to(W))
for s in ['README.md','人员分类与构成不确定性_研究组织与比较清单_20261022.md','DELIVERY_INDEX.md','DOWNLOAD_INDEX.csv','REPRODUCE_AND_DATA_DICTIONARY_ZH.md']:
    add(s)
tree('stage07_adoption');tree('integration');tree('targets')
for p in (W/'stage01').glob('*'):
    if p.is_file() and p.suffix in ['.csv','.json','.md']:add(p.relative_to(W))
for s in ['DOMAIN_SUBSET_COVERAGE_26x2.csv','PHASE1_PHASE2_PHASE3_DOMAIN_COVERAGE_26x2.csv','DOMAIN_COVERAGE_RETRIEVAL.json']:
    add('stage01/old_sources/'+s)
for p in (W/'stage02').glob('*'):
    if p.is_file() and p.name!='FILE_MANIFEST.json':add(p.relative_to(W))
for s in ['MAIN45_LABELS_ALL_LOBO.csv.gz','MAIN45_FROZEN_RECEIPT.json','SEMI_BASE_LABELS_ALL_LOBO.csv.gz','CANDIDATE_CONFIG_BEFORE_TEAM_RESULTS.json',
          'CLASS_ROLES_COMPACT_ALL_LOBO.csv.gz','CLASS_ROLES_ALL.csv','CLASS_MEMBER_CENTER_EXTRACT_FOR_MAIN_REPORT.csv',
          'NEW_PERSONNEL_LABELS_AND_MISSING_ALL.csv','NEW_CLASS_DEFINITIONS_ALL.csv','NEW_PERSONNEL_HISTORY_ALL.csv',
          'OLD_V2_TO_CURRENT_V21_WORKER_LABEL_TRANSITIONS.csv.gz','OLD_V2_TO_CURRENT_V21_LABEL_CHANGE_SUMMARY.csv',
          'NEW_TO_OFFICIAL_BASELINE_WORKER_TRANSITIONS.csv.gz','NEW_TO_OFFICIAL_BASELINE_OVERLAP_SUMMARY.csv',
          'METHOD_CAPACITY_SCOPE_SUMMARY.csv','NEW_TARGET_AWARE_METHODS_ZH.md','NEW_CANDIDATE_REGISTRY.csv']:
    add('classification/'+s)
for s in ['RUNTIME_VERSIONS.json','TOP_DOCUMENT_RETRIEVAL.json','ENGINE_CHECKOUT_PATHS.json','ORIGINAL_PERSONNEL_MAIN_REPORT_AT_a476461d.md']:
    add('source/'+s)
for folder in ['source','experiment','analysis','classification/code','composition/code','raw_similarity/code']:
    for p in (W/folder).glob('*.py'):add(p.relative_to(W))
for s in ['experiment/ALL_EXCHANGE_EXECUTION_LEDGER.json','experiment/COMPLETED_ENDPOINT_STAGES.csv','experiment/COMPLETED_EVENT_STAGES.csv',
          'experiment/focused_selection/SELECTED_CONDITIONS.csv','experiment/focused_selection/SELECTION_BEFORE_EXTENSION_RESULTS.json',
          'experiment/focused_capacity/POOL_CONDITION_ENTRY_AND_EXIT.csv.gz','experiment/benchmark/BENCHMARK_AND_PARITY.json',
          'analysis/joint_baseline_comparison/SAME_SUPPORT_COMPARISON.csv','analysis/joint_baseline_comparison/EXACT_PARENT_DIRECTIONS_BY_POOL.csv',
          'analysis/scale_background_summary/README.md','analysis/scale_background_summary/MAIN_POLICY_Q.csv',
          'analysis/scale_background_summary/MAIN_POLICY_STRUCTURE_TIME_RISK.csv','analysis/scale_background_summary/READING_EXAMPLES_FIXED_M.csv',
          'analysis/scale_background_summary/TARGET_BACKGROUND_CORE_SUMMARY.csv',
          'analysis/fine_increment/README.md','analysis/fine_increment/STAGE07D_INDEX.md',
          'composition/OPPJOINT_K4_complete_configuration_cases/README.md','composition/OPPJOINT_K4_complete_configuration_cases/CASE_TABLES.md',
          'composition/OPPJOINT_K4_complete_configuration_cases/ALL_CONFIGURATIONS_Q_READABLE.csv',
          'composition/OPPJOINT_K4_complete_configuration_cases/ALL_CONFIGURATION_Q_DISTRIBUTIONS.png',
          'composition/exact_small_pool_policies_OPPJOINT_K4/README.md','composition/primary_mixture_results/README.md','composition/semi_mixture_results/README.md',
          'stage06_cases/CASE_MECHANISMS_ZH.md','stage06_cases/CASE_MECHANISM_SUMMARY.csv','stage06_cases/local/STRUCTURE_AND_THRESHOLD_RGB_DETAIL.png',
          'raw_similarity/RAW_ANSWER_SIMILARITY_ZH.md','cases/source/NotoSansCJKsc-Regular.otf']:
    add(s)
manifest=[]
for p in sorted(paths):
    manifest.append(dict(path=p.relative_to(W).as_posix(),bytes=p.stat().st_size,sha256=sha(p)))
mp=D/'STAGE07A_SOURCE_FILE_INDEX.csv'
with mp.open('w',newline='',encoding='utf-8-sig') as f:
    wr=csv.DictWriter(f,fieldnames=['path','bytes','sha256']);wr.writeheader();wr.writerows(manifest)
archive=D/NAME;tmp=archive.with_suffix('.writing')
with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED,compresslevel=5,allowZip64=True) as z:
    for p in sorted(paths):z.write(p,p.relative_to(W).as_posix())
    z.write(mp,'stage_delivery/stage07A/SOURCE_FILE_INDEX.csv')
tmp.replace(archive)
with zipfile.ZipFile(archive) as z:
    assert len(z.namelist())==len(set(z.namelist()))
    assert z.testzip() is None
    checks=[]
    for row in manifest:
        b=z.read(row['path']);assert hashlib.sha256(b).hexdigest()==row['sha256']
        if row['path'].endswith('.gz'):gzip.decompress(b)
        checks.append(row['path'])
    # Parse the key research outputs from the final archive, not loose caches.
    import pandas as pd
    def csvrows(name):return len(pd.read_csv(io.BytesIO(z.read(name)),compression='gzip' if name.endswith('.gz') else None))
    labels=csvrows('classification/MAIN45_LABELS_ALL_LOBO.csv.gz');conditions=csvrows('stage07_adoption/EFFECTIVE_EXCHANGE_CONDITIONS.csv')
    methods=csvrows('stage07_adoption/ALL45_METHOD_ADOPTION_DECISIONS.csv');members=csvrows('stage07_adoption/PERSONNEL_ALL_MEMBERS.csv')
    assert (labels,conditions,methods,members)==(64170,32,45,62)
receipt=dict(file=archive.name,bytes=archive.stat().st_size,sha256=sha(archive),files=len(manifest)+1,zip_crc_passed=True,all_source_sha_passed=True,
    labels=labels,conditions=conditions,methods=methods,personnel_rows=members,
    source_commit='a476461d7ede8db95da43de4139e612c05e618bc',data_release='v2.1',
    note='Core includes updated report, adoption and code; complete event/endpoint data are in 07B/07C/07D and earlier thematic packages. Embedded download index is a snapshot and does not hash its own containing ZIP.')
(D/'STAGE07A_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
print(json.dumps(receipt,ensure_ascii=False))
