"""Verify the frozen source excerpt and compare cleanly replayed artifacts."""
from pathlib import Path
import argparse, hashlib, json
ROOT=Path(__file__).resolve().parent
PIN='faa118622c05b47c8edac1e04476282af08c97c5'
SOURCE=ROOT/'source/extracted/full_layout_consensus_20261004'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);a=p.parse_args()
    inp=a.repo/'analysis_results/lee_expanded_20261003/input.json';raw=inp.read_bytes()
    blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    assert blob==PIN,(blob,PIN)
    full=json.loads(raw);by={im['code']:im for im in full['images']}
    ex=json.loads((SOURCE/'inputs/current_excerpt.json').read_bytes())
    ref=json.loads((SOURCE/'inputs/reference_excerpt.json').read_bytes())
    result={'expected_git_blob':PIN,'actual_git_blob':blob,'source_sha256':sha(inp),'source_bytes':len(raw),'image_metadata':[],'annotations':[],'references':[]}
    for im in ex['images']:
        src=by[im['code']];meta={k:src.get(k)==v for k,v in im.items() if k!='annotations'}
        assert all(meta.values());result['image_metadata'].append({'code':im['code'],'fields_equal':meta})
        byrec={r['id']:r for r in src['annotations']}
        for r in im['annotations']:
            c={k:byrec[r['id']].get(k)==v for k,v in r.items()};assert all(c.values())
            result['annotations'].append({'id':r['id'],'fields_equal':c})
    for r in ref['references']:
        src=next(t for t in by[r['code']]['references'] if t['id']==r['id'])
        c={k:src.get(k)==v for k,v in r.items() if k!='code'};assert all(c.values())
        result['references'].append({'id':r['id'],'fields_equal':c})
    prior=json.loads((ROOT/'source_field_comparison.json').read_text())
    result['source_input_unchanged_during_replay']=prior['sha256']==sha(inp)
    assert result['source_input_unchanged_during_replay']
    manifests=[]
    for line in (SOURCE/'MANIFEST.sha256').read_text().splitlines():
        expected,name=line.split('  ',1);actual=sha(SOURCE/name)
        assert actual==expected;manifests.append({'file':name,'sha256':actual})
    result['manifest_files_verified']=len(manifests)
    results=[]
    for f in sorted((SOURCE/'results').rglob('*')):
        if not f.is_file():continue
        rel=f.relative_to(SOURCE/'results');replay=ROOT/'replay/results'/rel
        results.append({'file':str(rel),'status':('equal' if sha(f)==sha(replay) else 'changed') if replay.exists() else 'not_regenerated',
                        'source_sha256':sha(f),'replay_sha256':sha(replay) if replay.exists() else None})
    result['output_comparison']=results
    result['comparison_counts']={s:sum(r['status']==s for r in results) for s in ('equal','changed','not_regenerated')}
    unexpected=[r for r in results if r['status']=='changed' and r['file']!='environment.json'];assert not unexpected,unexpected
    (ROOT/'final_verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'manifest':len(manifests),'blob':blob,'source_unchanged':result['source_input_unchanged_during_replay'],
                     'comparison_counts':result['comparison_counts'], 'not_regenerated':[r['file'] for r in results if r['status']=='not_regenerated']},indent=2))
if __name__=='__main__':main()
