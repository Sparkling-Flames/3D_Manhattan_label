"""Verify frozen input bytes and compare current-result reruns; no semantic assertions."""
from pathlib import Path
import gzip,hashlib,json,zipfile
import numpy as np,pandas as pd
from pandas.testing import assert_frame_equal
from release import writejson

def run(root):
    a=root/'results/final_run';b=root/'results/recheck';results=[]
    if not b.exists():raise FileNotFoundError('First run code/run_all.py --out results/recheck; no missing rerun is treated as a pass')
    for p in sorted(a.iterdir()):
        if p.name.endswith('.csv') or p.name.endswith('.csv.gz'):
            q=b/p.name
            if not q.exists():continue
            try:
                x=pd.read_csv(p);y=pd.read_csv(q);assert_frame_equal(x,y,check_exact=False,atol=1e-9,rtol=1e-9)
                results.append(dict(file=p.name,rows=len(x),columns=len(x.columns),passed=True))
            except pd.errors.EmptyDataError:
                assert p.read_bytes()==q.read_bytes();results.append(dict(file=p.name,rows=0,columns=0,passed=True))
    archive=root/'input/download/pro_next_round_20260920.zip';files=[]
    if not results:raise ValueError('No result tables compared')
    archive_sha=None
    if archive.exists():
        with zipfile.ZipFile(archive) as z:
            assert z.testzip() is None
            for info in z.infolist():
                if info.is_dir():continue
                path=Path(info.filename)
                assert not path.is_absolute() and '..' not in path.parts
                f=root/'input/source'/path;expected=z.read(info.filename);assert f.read_bytes()==expected
                files.append(dict(path=str(path),bytes=len(expected),sha256=hashlib.sha256(expected).hexdigest()))
        archive_sha=hashlib.sha256(archive.read_bytes()).hexdigest()
    else:
        original=json.loads((root/'INPUT_INTEGRITY.json').read_text());archive_sha=original['original_zip_sha256']
        for row in original['files']:
            f=root/'input/source'/row['path'];assert hashlib.sha256(f.read_bytes()).hexdigest()==row['sha256'];files.append(row)
    writejson(root/'INPUT_INTEGRITY.json',dict(source_commit='f4a6f4a3b85c08d8873c8a56066219844dc7c88b',original_zip_sha256=archive_sha,final_source_files_match_original_zip=True,files=files))
    writejson(root/'REPRODUCIBILITY.json',dict(table_comparison_tolerance=1e-9,tables_compared=len(results),all_compared_tables_match=all(r['passed'] for r in results),comparisons=results,rerun='separate local process same environment; not independent semantic validation',source_files_verified=len(files),final_source_matches_original=True,source_recheck_metadata_handling=json.loads((root/"results/SOURCE_RECHECK_OUTPUT_HANDLING.json").read_text()),new_human_data_used=False,new_visual_review=False,software_intake_checks=json.loads((a/'INTAKE_AND_REVIEW_TESTS.json').read_text()),numerical_checks=json.loads((a/'TESTS.json').read_text())))
    return len(results),len(files)
if __name__=='__main__':print(run(Path(__file__).resolve().parents[1]))
