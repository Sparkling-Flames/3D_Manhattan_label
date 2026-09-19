"""Package and verify the delivered study. Does not download or modify source data."""
from pathlib import Path
import hashlib,json,shutil,zipfile
R=Path(__file__).resolve().parents[1];OUT=R.parent
included=[]
for folder in ['code','inputs','results','sensitivity_min_horizontal_results','report','visual']:
    for p in sorted((R/folder).rglob('*')):
        if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ['.pyc','.pyo']:
            included.append(p)
included += [R/f for f in ['00_START_HERE.html','REPORT_ZH.md','REPORT_ZH.html','ATLAS.html']]
manifest={'study':'paired_split_study_20260920','source_task_zip':'Pro续研_20260920(1).zip','raw_source_zip_sha256':hashlib.sha256((OUT/'Pro续研_20260920(1).zip').read_bytes()).hexdigest(),'files':[]}
for p in included:
    manifest['files'].append({'path':str(p.relative_to(R)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
mp=R/'PACKAGE_MANIFEST.json';mp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
zp=OUT/'paired_split_research_20260920.zip'
with zipfile.ZipFile(zp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in included+[mp]:z.write(p,arcname='paired_split_study_20260920/'+str(p.relative_to(R)))
with zipfile.ZipFile(zp) as z:
    assert z.testzip() is None
    target=OUT/'paired_split_export_check_20260920';target.mkdir(exist_ok=True);z.extractall(target)
    r=target/'paired_split_study_20260920'
    for v in manifest['files']:
        assert hashlib.sha256((r/v['path']).read_bytes()).hexdigest()==v['sha256'],v['path']
for a,b in [('REPORT_ZH.html','paired_split_report_20260920.html'),('ATLAS.html','paired_split_atlas_20260920.html'),('REPORT_ZH.md','paired_split_report_20260920.md')]:shutil.copy2(R/a,OUT/b)
with zipfile.ZipFile(OUT/'paired_split_report_only_20260920.zip','w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    z.write(R/'REPORT_ZH.html','REPORT_ZH.html');z.write(R/'REPORT_ZH.md','REPORT_ZH.md')
sha=hashlib.sha256(zp.read_bytes()).hexdigest();(OUT/'paired_split_research_20260920_SHA256.txt').write_text(sha+'  '+zp.name+'\n')
result={'zip_path':str(zp),'bytes':zp.stat().st_size,'crc_ok':True,'extracted_file_hashes_verified':len(manifest['files']),'sha256':sha,'numerical_recheck':json.loads((R/'results/REPRODUCTION_CHECK.json').read_text())['all_equal'],'local_navigation_not_tested':True}
(OUT/'paired_split_research_20260920_export_check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False,indent=2))
