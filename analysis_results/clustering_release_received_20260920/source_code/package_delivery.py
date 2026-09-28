"""Assemble only frozen sources and current outputs, then actually extract and hash-check."""
from pathlib import Path
import hashlib,json,shutil,zipfile,tempfile

ROOT=Path(__file__).resolve().parents[1]
DEST=Path('/mnt/data/clustering_release_RC1_20260920')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run():
    if DEST.exists():shutil.rmtree(DEST)
    DEST.mkdir()
    for name in ['README.md','NEW_DATA.md','PAPER_PLAN.md','config.json','requirements.txt','00_START_HERE.html','REPRODUCIBILITY.json','INPUT_INTEGRITY.json','ENVIRONMENT.json','GITHUB_DELIVERY.json','clustering_release_report_20260920.html']:
        shutil.copy2(ROOT/name,DEST/name)
    shutil.copytree(ROOT/'code',DEST/'code',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copytree(ROOT/'report',DEST/'report')
    shutil.copytree(ROOT/'input/supplement',DEST/'input/supplement')
    inp=json.loads((ROOT/'INPUT_INTEGRITY.json').read_text())
    for entry in inp['files']:
        src=ROOT/'input/source'/entry['path'];target=DEST/'input/source'/entry['path'];assert sha(src)==entry['sha256'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,target)
    shutil.copytree(ROOT/'results/final_run',DEST/'results/final_run')
    shutil.copytree(ROOT/'results/source_recheck_generated',DEST/'results/source_recheck_generated')
    for name in ['BROWSER_CHECK.json','SOURCE_RECHECK_OUTPUT_HANDLING.json','source_verify.log','full_source_recheck.log','final_run.log','independent_process_recheck.log']:
        p=ROOT/'results'/name
        if p.exists():shutil.copy2(p,DEST/'results'/name)
    files=[]
    for p in sorted(DEST.rglob('*')):
        if not p.is_file():continue
        assert p.suffix.lower() not in ['.ttf','.otf','.woff','.woff2'],p
        files.append(dict(path=str(p.relative_to(DEST)),bytes=p.stat().st_size,sha256=sha(p)))
    (DEST/'FILE_MANIFEST.json').write_text(json.dumps(dict(files=files,manifest_excludes_itself=True,source_commit='f4a6f4a3b85c08d8873c8a56066219844dc7c88b'),ensure_ascii=False,indent=2),encoding='utf-8')
    archive=Path('/mnt/data/clustering_release_RC1_20260920.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(DEST.rglob('*')):
            if p.is_file():z.write(p,str(Path(DEST.name)/p.relative_to(DEST)))
    with tempfile.TemporaryDirectory(prefix='rc1_zip_verification_') as td:
        with zipfile.ZipFile(archive) as z:
            assert z.testzip() is None
            for n in z.namelist():assert not Path(n).is_absolute() and '..' not in Path(n).parts
            z.extractall(td)
        recovered=Path(td)/DEST.name
        for entry in files:assert sha(recovered/entry['path'])==entry['sha256']
    # Small independent reading copies contain no hidden external-image dependence.
    report=Path('/mnt/data/clustering_release_report_20260920.html');shutil.copy2(ROOT/'clustering_release_report_20260920.html',report)
    browser=Path('/mnt/data/clustering_release_browser_20260920.html');shutil.copy2(ROOT/'report/RESULTS_BROWSER.html',browser)
    with zipfile.ZipFile('/mnt/data/clustering_release_report_only_20260920.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in [report,ROOT/'report/REPORT_ZH.md',ROOT/'NEW_DATA.md',ROOT/'PAPER_PLAN.md',ROOT/'config.json',ROOT/'REPRODUCIBILITY.json']:z.write(p,p.name)
    check=dict(zip=str(archive),bytes=archive.stat().st_size,sha256=sha(archive),crc_passed=True,extraction_sha256_files=len(files),all_passed=True,compared_result_tables=json.loads((ROOT/'REPRODUCIBILITY.json').read_text())['tables_compared'])
    Path('/mnt/data/clustering_release_RC1_20260920_export_check.json').write_text(json.dumps(check,indent=2))
    Path('/mnt/data/clustering_release_RC1_20260920_SHA256.txt').write_text(check['sha256']+'  '+archive.name+'\n')
    print(json.dumps(check,indent=2))
if __name__=='__main__':run()
