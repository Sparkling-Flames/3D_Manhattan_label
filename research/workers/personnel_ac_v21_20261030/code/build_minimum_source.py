"""Export the exact frozen native import closure and inputs for reproduction.

No experiment is repeated. Actual file bytes are checked against the current
repository commit, rather than silently relabeling an older worktree.
"""
from __future__ import annotations
import csv, hashlib, json, shutil, subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT.parent
REPO=WORK/'repo'
COMMIT='ec0973ad46fcfa64d3cdbedfeeef1fee180c4cff'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    out=ROOT/'stage07_reproduction';out.mkdir(exist_ok=True)
    contract=json.loads((ROOT/'stage02_engine/cache_plan/ENGINE_AND_INPUT_CONTRACT.json').read_text())
    files={x['path']:x['sha256'] for x in contract['engine_files']}
    for x in contract['pool_sources']:
        files[str(Path(x['path']).relative_to(REPO))]=x['sha256']
    extras=[
      'research/workers/personnel_v21_reselection_20261029/analysis/measure_registered_events.py',
      'research/workers/personnel_v21_reselection_20261029/analysis/legacy_geometry_diagnostics.py',
      'research/workers/personnel_v21_reselection_20261029/experiment/benchmark_engine.py',
      'research/workers/personnel_v21_reselection_20261029/targets/POOL_TARGET_CONDITIONS.csv',
      'research/workers/personnel_v21_reselection_20261029/classification/CLASS_ROLES_COMPACT_ALL_LOBO.csv.gz',
      'research/workers/personnel_v21_reselection_20261029/classification/CANDIDATE_CONFIG_BEFORE_TEAM_RESULTS.json',
      'research/workers/personnel_v21_reselection_20261029/classification/SEMI_BASE_LABELS_ALL_LOBO.csv.gz']
    for rel in extras:files[rel]=sha(REPO/rel)
    tree=subprocess.run(['git','ls-tree','-r',COMMIT,'--',*files],cwd=REPO,capture_output=True,text=True,check=True).stdout
    blobs={line.split('\t',1)[1]:line.split('\t',1)[0].split()[2] for line in tree.splitlines()}
    rows=[]
    for rel, expected in sorted(files.items()):
        src=REPO/rel;data=src.read_bytes();assert hashlib.sha256(data).hexdigest()==expected
        actual_blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        assert rel in blobs and actual_blob==blobs[rel],('current commit source mismatch',rel)
        dst=out/'minimum_source/repo'/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
        rows.append({'path':rel,'bytes':len(data),'sha256':expected,'git_blob_at_current_commit':actual_blob,'matches_current_commit':True})
    with (out/'MINIMUM_SOURCE_MANIFEST.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    shutil.copy2(ROOT/'stage02_engine/cache_plan/ENGINE_AND_INPUT_CONTRACT.json',out/'ENGINE_AND_INPUT_CONTRACT.json')
    receipt={'commit':COMMIT,'files':len(rows),'bytes':sum(r['bytes'] for r in rows),
      'every_exported_file_matches_current_commit_git_blob':True,
      'original_worktree_unchanged':True,'new_fusions':0,'new_scoring':0,'new_classification_fits':0,
      'frozen_labels_and_registration':'Delivered in stage01 capacity and stage02 design packages; no refit is required to reproduce this study.',
      'runtime':contract['runtime']}
    (out/'SOURCE_EXPORT_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(receipt,ensure_ascii=False))


if __name__=='__main__':main()
