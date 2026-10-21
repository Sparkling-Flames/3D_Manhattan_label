"""Package only reproducible study outputs, with exact input references.

The source repository, environments, full native geometry checkpoints and
repeated historical caches are not copied. Large convenience summaries that
can be recreated from delivered scalars are listed explicitly as omitted.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
import os
import shutil
import zipfile
from pathlib import Path
import pandas as pd

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
COMMIT='51b519f943b2dd3a4fb2f0198133ac5dd17209ab'
TOP='personnel_global_composition_20261021'

OMIT={
 'composition/HISTORICAL_TEAM_KEYS.txt.gz':'Historical duplicate index; recover_historical_keys.py recreates from the original generators and audit hashes.',
 'composition/STAGE1_REQUESTS.json.gz':'Subset of final ENDPOINT_REQUESTS; retain final request only.',
 'composition/STAGE2_REQUESTS.json.gz':'Subset of final ENDPOINT_REQUESTS; exact layer table and receipts retained.',
 'composition/CLASS_VECTOR_UNIVERSE.csv':'Initial coverage convenience table superseded by UNIVERSE_FINAL_COVERAGE.csv.gz; global_study.py inventory recreates it.',
 'analysis/NEAR_CENSUS_ADDITION_EDGES.csv.gz':'Convenience edge table duplicated by delivered team scalars and complete last-two suffix paths; analyze_global.py --part near recreates it.',
 'analysis/CONFIGURATION_CELL_RESULTS.csv.gz':'Wide cell mean/std convenience table; CONFIG_MEMBERSHIP and all endpoint scalars are delivered; analyze_global.py --part grid recreates it.',
 'analysis/ABC_BUILDING_VALUES.csv.gz':'Wide per-n/m metric summary duplicated by exact event data and summary; analyze_global.py --part abc recreates it.',
 'analysis/team_response/TEAM_RESPONSE_POOL_RESULTS.csv.gz':'Large per-pool model convenience table. Full building/model/increment/eligibility tables and code retained; team_continuous_check.py recreates it.',
 'integration/LABELS_BEFORE_FINAL_COVERAGE.json':'Temporary before/after metadata; FINAL_INTEGRATION_CHECK already records the unchanged hashes.',
 'composition/ABC_GEOMETRY_PARTIAL_RECEIPT.json':'Superseded by final complete geometry receipt.',
 'report/REPORT_DRAFT_ZH.md':'Unfilled draft template; final report supplied; finalize_report_data.py is retained as provenance, not a needed report-reading step.'
}

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()

def candidates():
    chosen=[];excluded=[]
    for p in sorted(HERE.rglob('*')):
        if not p.is_file():continue
        rel=p.relative_to(HERE).as_posix()
        # Continuation experiments are saved as independent, incremental batches.
        # Never silently fold an actively written continuation into the frozen v1 package.
        if rel.startswith('continuation_20261021/'):continue
        if any(x in p.relative_to(HERE).parts for x in ['runtime','__pycache__','benchmark_endpoints','delivery']):continue
        if p.suffix in ('.pyc','.tmp') or rel.startswith('analysis/team_response_stage1/'):continue
        if rel in ['DELIVERY_MANIFEST.csv','DELIVERY_RECEIPT.json','DERIVED_FILES_OMITTED.csv']:continue
        if rel in OMIT:excluded.append(dict(path=rel,bytes=p.stat().st_size,sha256=sha(p),reason=OMIT[rel]));continue
        if 'record_prediction_' in rel or 'RECORD_PREDICTION' in rel or p.name=='evaluate_lobo_records.py':continue
        if p.name.endswith('_REQUESTS.json.gz') and p.name!='ENDPOINT_REQUESTS.json.gz':
            excluded.append(dict(path=rel,bytes=p.stat().st_size,sha256=sha(p),reason='Stage or priority request subset; final precise request contains all actual endpoints.'));continue
        chosen.append(p)
    return chosen,excluded

def input_references():
    prefix='research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/fusion/'
    refs={prefix+n for n in ['INPUT_SNAPSHOT.json.gz','POOL_MEMBERS.csv','POOL_ELIGIBILITY.csv','fusion_engine.py','pool_io.py']}
    refs.update([
      'research/statistics/v2_evidence_audit_20261019/records.json.gz',
      'research/statistics/b8l2_shared_v6_20261016/inputs/measurement_engine.zip',
      'research/statistics/b8l2_shared_v6_20261016/inputs/working_models.py',
      'research/workers/personnel_interchangeability_20261020/analysis/composition/fusion_runner.py',
      'research/workers/personnel_interchangeability_20261020/analysis/composition/summarize_grid.py',
      'research/workers/personnel_interchangeability_followup_20261020/audit_corner/corner_distance.py',
      'research/workers/personnel_marking_patterns_20261020/record_expression.csv',
      'research/workers/personnel_profiles_composition_20261020/source/tables/profiles/record_index.csv.gz',
      'tools/thesis_main/analysis/wall_consensus_quality_20261015.py',
      'docs/thesis_main/人员标法分类与换类研究_总体进度_20261020.md',
      'docs/thesis_main/研究模型_人员图片与融合不确定性_20261006.md',
      'docs/thesis_main/人员多变量反向分型_双线任务与验收_20261019.md'])
    # Receipt keys are exact referenced repository paths, not guessed files.
    def visit(x):
        if isinstance(x,dict):
            for k,v in x.items():
                if isinstance(k,str) and k.startswith(('research/','tools/','docs/')) and (ROOT/k).is_file():refs.add(k)
                visit(v)
        elif isinstance(x,list):
            for v in x:visit(v)
        elif isinstance(x,str) and x.startswith(('research/','tools/','docs/')) and (ROOT/x).is_file():refs.add(x)
    for folder in ['coverage','multivariate','integration','composition','evidence']:
        for p in (HERE/folder).glob('*.json'):
            try:visit(json.loads(p.read_text()))
            except (json.JSONDecodeError,UnicodeDecodeError):pass
    rows=[]
    for rel in sorted(refs):
        if rel.startswith('research/workers/'+TOP+'/'):continue
        p=ROOT/rel
        rows.append(dict(repository_path=rel,source_commit=COMMIT,materialized=p.is_file(),
          bytes=p.stat().st_size if p.is_file() else None,sha256=sha(p) if p.is_file() else '',
          retrieval=f'https://github.com/Sparkling-Flames/3D_Manhattan_label/blob/{COMMIT}/{rel}'))
    pd.DataFrame(rows).to_csv(HERE/'INPUT_REFERENCES.csv',index=False,encoding='utf-8-sig')
    return rows

def validate_event_export():
    """A valid CSV/ZIP hash alone cannot detect an accidentally published prefix."""
    columns=['event_id','team_A','team_B','team_C','composition_A','composition_B','composition_C']
    source=pd.read_csv(HERE/'analysis/ABC_ALL_COMPONENT_EVENTS.csv.gz',usecols=columns,keep_default_na=False)
    exported=pd.read_csv(HERE/'report/ABC_EVENT_RESULTS_KEY.csv',keep_default_na=False)
    if source.event_id.duplicated().any() or exported.event_id.duplicated().any():
        raise ValueError('Duplicate event IDs; refusing publication')
    if len(source)!=len(exported) or source.event_id.tolist()!=exported.event_id.tolist():
        raise ValueError('Incomplete or reordered event export; refusing publication')
    pd.testing.assert_frame_equal(source[columns],exported[columns],check_dtype=False)
    return {'event_rows':len(exported),'event_columns':len(exported.columns),'event_ids':source.event_id.tolist()}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);ap.add_argument('--inventory-only',action='store_true');a=ap.parse_args()
    event_check=validate_event_export()
    refs=input_references();chosen,excluded=candidates()
    pd.DataFrame(excluded).to_csv(HERE/'DERIVED_FILES_OMITTED.csv',index=False,encoding='utf-8-sig')
    chosen.append(HERE/'DERIVED_FILES_OMITTED.csv')
    rows=[dict(path=p.relative_to(HERE).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in chosen]
    pd.DataFrame(rows).to_csv(HERE/'DELIVERY_MANIFEST.csv',index=False,encoding='utf-8-sig')
    chosen.append(HERE/'DELIVERY_MANIFEST.csv')
    total=sum(p.stat().st_size for p in chosen)
    if a.inventory_only:
        print(json.dumps({'files':len(chosen),'input_refs':len(refs),'uncompressed_bytes':total,'excluded_derived_files':len(excluded)},ensure_ascii=False));return
    a.out.mkdir(parents=True,exist_ok=True)
    zpath=a.out/'HOHONET_人员分类与整体构成_研究包_20261021.zip'
    temporary=zpath.with_name(zpath.name+'.tmp')
    with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in chosen:
            # Already compressed endpoint data needs no second deflation.
            z.write(p,arcname=TOP+'/'+p.relative_to(HERE).as_posix(),compress_type=zipfile.ZIP_STORED if p.suffix in ['.gz','.png','.pdf'] else zipfile.ZIP_DEFLATED)
    with zipfile.ZipFile(temporary) as z:
        with z.open(TOP+'/report/ABC_EVENT_RESULTS_KEY.csv') as stream:
            ids=[row['event_id'] for row in csv.DictReader(io.TextIOWrapper(stream,encoding='utf-8-sig',newline=''))]
        if ids!=event_check['event_ids']:
            raise ValueError('Packaged event IDs do not match complete source; final ZIP was not replaced')
    os.replace(temporary,zpath)
    exports={
      'report/HOHONET_personnel_global_composition_20261021.pdf':'HOHONET_人员分类与整体构成_报告_20261021.pdf',
      'report/HOHONET_personnel_global_composition_20261021.html':'HOHONET_人员分类与整体构成_离线报告_20261021.html',
      'report/REPORT_ZH.md':'HOHONET_人员分类与整体构成_报告_20261021.md',
      'integration/MANUAL_LABELS_LONG.csv':'Manual_逐人分类_20261021.csv',
      'integration/SEMI_LABELS_LONG.csv':'Semi_逐人分类_20261021.csv',
      'integration/CLASS_MEMBERS.csv':'人员类别_成员名单_20261021.csv',
      'integration/DOMAIN_SUBSET_COVERAGE_26x2.csv':'人员分类_26域组合覆盖账_20261021.csv',
      'report/PRIMARY_RESULTS.csv':'人员构成_主要结果_20261021.csv',
      'report/ABC_EVENT_RESULTS_KEY.csv':'人员构成_12953逐事件结果_20261021.csv',
      'report/figures/large_replacement_quality_and_shape.png':'大团队_质量与形状结果_20261021.png',
      'evidence/figures/G03_M_structure_pa4_n15_m8/comparison.png':'结构类别_局部补充实例_20261021.png',
      'evidence/figures/C02_rPc17_semi_same_class/raw_position_and_votes.png':'Semi同类_关键补票反例_20261021.png',
    }
    for src,name in exports.items():shutil.copy2(HERE/src,a.out/name)
    result={'source_commit':COMMIT,'files_in_zip':len(chosen),'uncompressed_bytes':total,'zip_bytes':zpath.stat().st_size,
       'zip_sha256':sha(zpath),'zip':str(zpath),'standalone_files':[str(a.out/n) for n in exports.values()],
       'omitted_derived_files':len(excluded),'native_geometry_caches_and_old_duplicate_inputs_excluded':True,
       'validated_event_rows':event_check['event_rows'],'validated_event_columns':event_check['event_columns'],
       'continuation_batches_saved_separately':True}
    (HERE/'DELIVERY_RECEIPT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
