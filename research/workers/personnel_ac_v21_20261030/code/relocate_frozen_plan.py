"""Copy the saved execution plan and change only paths for a new directory.

All source hashes, members, references, runtime versions, reuse states and the
engine digest remain unchanged. The original plan is preserved.
"""
from __future__ import annotations
import argparse,hashlib,json,shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',default=str(ROOT/'stage07_reproduction/relocated_plan'));a=ap.parse_args()
    source=ROOT/'stage02_engine/cache_plan';out=Path(a.out).resolve();assert not out.exists()
    repo=(ROOT/'stage07_reproduction/minimum_source/repo').resolve()
    requests=(ROOT/'stage01_registered/TEAM_REQUESTS.csv.gz').resolve()
    plan=json.loads((source/'CACHE_PLAN.json').read_text())
    contract=json.loads((source/'ENGINE_AND_INPUT_CONTRACT.json').read_text())
    assert sha(requests)==plan['requests_sha256']
    for row in contract['engine_files']:assert sha(repo/row['path'])==row['sha256'],row['path']
    old_repo=Path(contract['engine_root'])
    changes=[{'field':'CACHE_PLAN.requests_file','old':plan['requests_file'],'new':str(requests)},
             {'field':'ENGINE_AND_INPUT_CONTRACT.engine_root','old':str(old_repo),'new':str(repo)}]
    plan['requests_file']=str(requests);contract['engine_root']=str(repo)
    for i,row in enumerate(contract['pool_sources']):
        old=Path(row['path']);new=repo/old.relative_to(old_repo);assert sha(new)==row['sha256']
        changes.append({'field':f'ENGINE_AND_INPUT_CONTRACT.pool_sources[{i}].path','old':str(old),'new':str(new)})
        row['path']=str(new)
    shutil.copytree(source,out)
    (out/'CACHE_PLAN.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
    (out/'ENGINE_AND_INPUT_CONTRACT.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2)+'\n')
    receipt={'original_plan_preserved':True,'path_changes_only':changes,'engine_digest_unchanged':contract['engine_digest'],
      'all_engine_and_pool_bytes_verified':True,'requests_sha256_unchanged':plan['requests_sha256'],
      'new_fusions':0,'new_scores':0,'new_labels':0}
    (out/'RELOCATION_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'relocated_plan':str(out),'repo':str(repo),'path_fields_changed':len(changes)},ensure_ascii=False))


if __name__=='__main__':main()
