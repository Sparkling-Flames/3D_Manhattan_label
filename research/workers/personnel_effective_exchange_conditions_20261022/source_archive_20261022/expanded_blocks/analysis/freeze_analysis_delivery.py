"""Freeze compact final expansion analysis; full events/endpoints stay separate."""
from pathlib import Path
import csv,gzip,json,os,sys,zipfile
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from analyze_expanded_results import save_json,sha,NEW

def main():
    receipt=json.loads((HERE/'FINAL_ANALYSIS_COMPLETION.json').read_text())
    assert receipt['status']=='FINAL_COMPLETE' and receipt['pending_cells']==0
    assert (HERE/'FINAL_FINDINGS_ZH.md').exists() and (HERE/'FINAL_TABLES_FOR_REPORT_ZH.md').exists()
    files=[]
    for p in sorted(HERE.iterdir()):
        if not p.is_file():continue
        take=(p.suffix=='.py' or p.name in ['ANALYSIS_PROTOCOL_ZH.md','RESTORATION_ADAPTER_VERIFICATION.json','REPORT_TABLES_COMPLETION.json']
          or p.name.startswith('CANONICAL_') and not p.name.endswith('_PROGRESS.json')
          or p.name.startswith('FINAL_') and p.name not in ['FINAL_WAIT_STATUS.json']
          or p.name.endswith('_FINAL_COMPLETE.csv.gz'))
        if not take:continue
        if p.name.endswith(('.log','.tmp','.zip')):continue
        rec=dict(path=str(p.relative_to(NEW)),bytes=p.stat().st_size,sha256=sha(p))
        if p.name.endswith(('.csv','.csv.gz')):
            op=gzip.open if p.suffix=='.gz' else open
            with op(p,'rt',encoding='utf-8-sig',newline='') as f:
                rows=csv.reader(f);cols=next(rows);n=0
                for row in rows:assert len(row)==len(cols);n+=1
            rec.update(rows=n,columns=len(cols),EOF_verified=True)
        files.append(rec)
    dependency=NEW/'screening/common_screening.py'
    files.append(dict(path=str(dependency.relative_to(NEW)),bytes=dependency.stat().st_size,sha256=sha(dependency),role='shared_atomic_io_dependency'))
    manifest=dict(status='complete',underlying_data_version='v2',registered_cells=receipt['registered_cells'],
      complete_cells=receipt['complete_cells'],complete_events=receipt['complete_events'],complete_panels=receipt['complete_panels'],
      native_fusion_calls_in_analysis=0,files=files,
      excluded='original images, virtual environment, endpoint/runtime caches, duplicate cell events, temporary partial tables, restoration test copies',
      companion_inputs=['expanded_blocks/REGISTERED_EVENT_PARTS.csv','expanded_blocks/REGISTERED_MEMBER_PANELS.csv.gz',
        'expanded_blocks/CLASS_CONFIG_MEMBER_COVERAGE.csv.gz','expanded_blocks/ALL_TEAMS_REGISTERED.csv.gz',
        'expanded_blocks/design_parts/ (frozen requests)','expanded_blocks/results/*/PANEL_SUMMARY.csv.gz',
        'expanded_blocks/results/*/COMPLETION.json','delivery/expanded_events/ (25 full event shards and receipts)'],
      reproduction='restore_event_inputs_from_delivery.py if needed; analyze_expanded_results.py --require-complete; prepare_readable_results.py; make_report_tables.py',
      all_sources_unchanged='native results, eligibility, reference, labels, B8L2/D10, and fusion parameters are referenced unchanged')
    save_json('ANALYSIS_FINAL_MANIFEST.json',manifest)
    dest=HERE/'EXPANSION_ANALYSIS_SUMMARY.zip';tmp=dest.with_name(dest.name+'.tmp')
    with zipfile.ZipFile(tmp,'w',allowZip64=True) as z:
        for r in files:
            p=NEW/r['path'];z.write(p,r['path'],compress_type=zipfile.ZIP_STORED if p.suffix=='.gz' else zipfile.ZIP_DEFLATED)
        z.write(HERE/'ANALYSIS_FINAL_MANIFEST.json','expanded_blocks/analysis/ANALYSIS_FINAL_MANIFEST.json',compress_type=zipfile.ZIP_DEFLATED)
    with tmp.open('rb') as f:os.fsync(f.fileno())
    with zipfile.ZipFile(tmp) as z:assert z.testzip() is None
    tmp.replace(dest)
    output=dict(status='complete',path=str(dest.relative_to(NEW)),bytes=dest.stat().st_size,sha256=sha(dest),
      manifest_sha256=sha(HERE/'ANALYSIS_FINAL_MANIFEST.json'),files=len(files)+1,
      report_sha256=sha(HERE/'FINAL_FINDINGS_ZH.md'),tables_sha256=sha(HERE/'FINAL_TABLES_FOR_REPORT_ZH.md'),
      underlying_data_version='v2')
    save_json('ANALYSIS_FINAL_DELIVERY.json',output);print(json.dumps(output,ensure_ascii=False))

if __name__=='__main__':main()
