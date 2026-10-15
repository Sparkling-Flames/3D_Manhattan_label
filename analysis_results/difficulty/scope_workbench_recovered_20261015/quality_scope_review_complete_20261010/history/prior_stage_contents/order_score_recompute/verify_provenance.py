#!/usr/bin/env python3
"""Verify local snapshot inputs against committed blobs/LFS content hashes."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
from recompute import read,save,sha,ROOT

def git(repo,*a):return subprocess.check_output(['git',*a],cwd=repo)
def verify_file(repo,commit,rel):
    committed=git(repo,'show',commit+':'+rel);actual=(repo/rel).read_bytes()
    if committed.startswith(b'version https://git-lfs.github.com/spec/v1\n'):
        expected=re.search(rb'oid sha256:([a-f0-9]{64})',committed).group(1).decode();size=int(re.search(rb'size ([0-9]+)',committed).group(1))
        assert hashlib.sha256(actual).hexdigest()==expected and len(actual)==size
        kind='lfs_content_sha256_and_size'
    else:
        assert committed==actual,rel
        kind='exact_blob_bytes'
    return {'file':rel,'sha256':hashlib.sha256(actual).hexdigest(),'bytes':len(actual),'verification':kind}
def main():
    p=argparse.ArgumentParser();p.add_argument('--old-repo',type=Path,required=True);p.add_argument('--new-repo',type=Path,required=True);a=p.parse_args()
    oldbase=git(a.old_repo,'rev-parse','fae48e69').decode().strip();newbase='24360ad8544d76d8aba18a8e641f784a76ca0d42'
    delta=git(a.old_repo,'diff','--name-only',oldbase,'HEAD','--','tools','docs','analysis_results','research/quality_scope_comparison_20261010').decode()
    assert not delta,delta
    records={}
    files=['analysis_results/research_input_20260929/'+s for s in ['preprocessed_source.json','comments.json','research_tables.json','manifest.json','quality_update_20261010.json','final_review/summary.json','final_review/received_orders.json']]
    files += ['tools/thesis_main/data_prep/'+s for s in ['consolidate_research_input.py','materialize_current_research_input.py','apply_quality_review_20261010.py','project_public_research_20260929.py']]
    for name,repo,commit in [('old',a.old_repo,oldbase),('new',a.new_repo,newbase)]:
        records[name]={'authoritative_source_commit':commit,'local_checkout_commit':git(repo,'rev-parse','HEAD').decode().strip(),'files':[verify_file(repo,commit,rel) for rel in files]}
        snapshot=read(ROOT/'inputs'/f'{name}_formal.json');snapshot['local_checkout_commit']=snapshot['source_commit'];snapshot['source_commit']=commit;snapshot['baseline_provenance']='source bytes verified against authoritative commit; local checkout may include unrelated unpublished additive artifacts';save(ROOT/'inputs'/f'{name}_formal.json',snapshot)
    engine=[]
    for p in sorted((ROOT/'frozen_engine').rglob('*')):
        if not p.is_file() or '__pycache__' in p.parts:continue
        rel='research/quality_scope_comparison_20261010/'+p.relative_to(ROOT).as_posix()
        meta=verify_file(a.new_repo,newbase,rel);assert p.read_bytes()==(a.new_repo/rel).read_bytes();assert git(a.old_repo,'show',oldbase+':'+rel)==p.read_bytes();engine.append(meta)
    records['frozen_engine_unchanged_files']=engine
    records['old_local_tree_relevant_paths_equal_authoritative_base']=True
    records['current_commit']=newbase;records['passed']=True
    save(ROOT/'results/source_provenance.json',records)
    print('Provenance passed:',len(engine),'frozen engine files;',len(files),'source files per snapshot')
if __name__=='__main__':main()
