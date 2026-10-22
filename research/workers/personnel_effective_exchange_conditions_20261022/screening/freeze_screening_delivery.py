"""Freeze small review bundle; large independent tables stay separately named."""
from common_screening import *
import zipfile

def main():
    required=['UNIFIED_COMPLETION.json','SCREEN_COMPLETION.json','INTERNAL_LOBO_COMPLETION.json',
              'FOCUS_SUMMARY_COMPLETION.json','CACHE_OPPORTUNITY_COMPLETION.json','FOCUS_TIME_VERIFICATION.json']
    for name in required:assert (HERE/name).exists(),name
    paths=[]
    for p in HERE.rglob('*'):
        if not p.is_file():continue
        rel=p.relative_to(HERE)
        if any(a in ['__pycache__','event_parts'] for a in rel.parts):continue
        if p.name.endswith(('.tmp','.partial','.jsonl','.txt','.zip')) or p.name in ['FINAL_MANIFEST.json','FINAL_DELIVERY.json']:continue
        paths.append(p)
    files=[dict(path=str(p.relative_to(HERE)),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(paths)]
    save_json('FINAL_MANIFEST.json',dict(status='complete',data_version='v2',prior_v3_is_round_id=True,
      registered_old_event_rows=85570,unique_analysis_events=85203,native_calls=0,
      independent_tables='EVENTS_UNIFIED.csv.gz; views/*/CORE_ALL_CANDIDATES.csv.gz and SELECTION_ALL_PURPOSES.csv.gz; lobo/*/ALL_TRAINING_FOLD_CANDIDATES.csv.gz',
      omitted_duplicates='event_parts are reproducible copies of unified rows; no old endpoint cache or images bundled',files=files))
    small=[]
    for p in paths:
        rel=str(p.relative_to(HERE))
        if rel=='EVENTS_UNIFIED.csv.gz' or 'DUPLICATE_ANALYSIS_EVENT_PROVENANCE' in rel:continue
        if rel.startswith('views/') and p.name not in ['SELECTED_CONDITIONS.csv','COMPLETION.json']:continue
        if rel.startswith('lobo/') and p.name not in ['CONDITION_HELDOUT_SUMMARY.csv.gz','HELDOUT_SUMMARY.csv','COMPLETION.json']:continue
        small.append(p)
    target=HERE/'SCREENING_SUMMARY.zip';tmp=target.with_suffix('.partial')
    with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=5) as z:
        for p in sorted(small+[HERE/'FINAL_MANIFEST.json']):z.write(p,arcname=str(p.relative_to(HERE)))
    with zipfile.ZipFile(tmp) as z:assert z.testzip() is None
    tmp.replace(target)
    save_json('FINAL_DELIVERY.json',dict(status='complete',files=len(files),summary_files=len(small)+1,
      summary_bundle=dict(path=target.name,bytes=target.stat().st_size,sha256=sha(target)),
      report=dict(path='REPORT_ZH.md',sha256=sha(HERE/'REPORT_ZH.md')),native_calls=0,
      note='This closes prior-event screening only; new native expansion is reported independently in expanded_blocks/analysis.'))
    print(json.dumps(json.loads((HERE/'FINAL_DELIVERY.json').read_text()),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
