#!/usr/bin/env python3
"""Create the four non-overlapping research archives and verify their actual bytes."""
from pathlib import Path
import argparse,hashlib,json,zipfile
from package_verify import inspect_archive

PREFIX='research/statistics/room_type_similarity_20261027/'
COMMIT='b2b0898b90bd631df37f1f2e75e8380800a43cf8'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,required=True);ap.add_argument('--only',choices=['all','01','02','03','04'],default='all');a=ap.parse_args();b=a.base.resolve();de=b/'delivery';de.mkdir(exist_ok=True)
    exclude_parts={'__pycache__','history_invalid_concurrent_outputs'}
    def files(folder):
        return [p for p in (b/folder).rglob('*') if p.is_file() and not (set(p.parts)&exclude_parts) and p.suffix not in {'.log','.pyc'}]
    s01=[p for p in b.iterdir() if p.is_file() and p.suffix in {'.md','.html','.csv','.txt','.json'}]
    s01+=files('code')+files('key_tables')+files('figures')+files('assets')+files('integration')
    s01 += [p for p in files('inputs') if p.name!='annotation_geometry.jsonl.gz']
    for name in ['MAIN_UPDATE_SOURCE_CHECK.json','NEW_MAIN_SCOPING_COMPARISON.json','upstream_scoping_README.md','upstream_scoping_SCOPE_CHECK.json','USER_SCOPE_CONTEXT_NOTE.md']:
        p=b/'source'/name
        if p.exists():s01.append(p)
    # A small case preview makes 01 independently readable. Complete cases live only in 02.
    s01 += [b/'cases_history/C01_COMPLETE_ANSWERS.png',b/'cases_history/CASE_FINDINGS_ZH.md',b/'cases_history/CASE_IMAGE_SUMMARY.csv',b/'cases_history/CASE_PAIR_SUMMARY.csv',b/'cases_history/HISTORY_CONNECTIONS_ZH.csv']
    case_manifest=json.loads((b/'cases_history/CASE_PACKAGE_CONTENTS.json').read_text())
    s02=[b/'cases_history'/r['path'] for r in case_manifest['required_files']]+[b/'cases_history/CASE_PACKAGE_CONTENTS.json']
    exact={'CROSS_BUILDING_IMAGE_PAIRS.csv.gz','MATCHED_THREE_IMAGE_EVENTS.csv.gz'}
    s03=[p for p in files('results') if p.name not in exact]+[b/'inputs/annotation_geometry.jsonl.gz']
    s04=[b/'results/image'/n for n in sorted(exact)]
    # Small shared contract/index avoids making a large-data package opaque by itself.
    shared=[b/'FIELD_CONTRACT.md',b/'SOURCE_DEPENDENCIES.json',b/'CURRENT_VALID_FILES.md']
    groups={'01':('01_report_code_inputs',s01),'02':('02_cases',s02+shared),'03':('03_full_results_geometry',s03+shared),'04':('04_exact_matching_events',s04+shared+[b/'results/image/MATCHING_COVERAGE.csv',b/'results/image/IMAGE_ANALYSIS_FILE_INDEX.csv'])}
    all_receipts=[]
    for k,(name,paths) in groups.items():
        if a.only!='all' and a.only!=k:continue
        paths=sorted(set(paths));assert all(p.is_file() for p in paths),[str(p) for p in paths if not p.is_file()]
        archive=de/f'HOHONET_room_type_20261027_{name}.zip'
        manifest={'package':name,'source_commit':COMMIT,'repository_relative_root':PREFIX,'new_fusion':0,'files':[]}
        with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
            for p in paths:
                data=p.read_bytes();arc=PREFIX+p.relative_to(b).as_posix();z.writestr(arc,data)
                manifest['files'].append({'archive_path':arc,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
            z.writestr(PREFIX+'delivery/'+name+'/PACKAGE_MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
        r=inspect_archive(archive);(de/f'PACKAGE_{k}_PREUPLOAD_VERIFIED.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
        all_receipts.append({q:r[q] for q in ['archive','bytes','sha256','files','csv_rows','jsonl_records','associations']})
        print(json.dumps(all_receipts[-1],ensure_ascii=False),flush=True)
    if a.only=='all':(de/'PACKAGE_BUILD_INDEX.json').write_text(json.dumps(all_receipts,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
