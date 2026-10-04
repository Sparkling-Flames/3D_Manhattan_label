"""Read-only verification against a user's full local frozen repository.
This verifier was not run against a full repository in the cloud environment.
"""
import argparse,json,hashlib,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'src'))
from cases import failure_records

def blob(data):return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('--repo',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.out.exists():raise ValueError('output_exists')
    plans=[('analysis_results/worker_profiles_20261003/input.json','5a174746730bb70e405680a3748663caf56dd51f',
            json.loads((ROOT/'inputs/real24_points.json').read_text())['records']+failure_records()),
           ('analysis_results/lee_expanded_20261003/input.json','faa118622c05b47c8edac1e04476282af08c97c5',
            json.loads((ROOT/'inputs/current_excerpt.json').read_text())['images'][0]['annotations'])]
    rows=[]
    for rel,sha,rs in plans:
        content=(a.repo/rel).read_bytes()
        if blob(content)!=sha:raise ValueError('source_blob_changed:'+rel)
        d=json.loads(content);by={r['id']:r for im in d['images'] for r in im['annotations']}
        for r in rs:
            src=by[r['id']]
            for key in ['points','source_pair_indices','source_point_indices','ring_confirmed','worker','independent','consensus_eligible','condition']:
                if key not in r:continue
                equal=np.array_equal(np.asarray(r[key]),np.asarray(src.get(key))) if key=='points' else r[key]==src.get(key)
                if not equal:raise ValueError('source_field_mismatch:'+r['id']+':'+key)
            rows.append(dict(id=r['id'],source=rel,source_blob_sha=sha,status='matched'))
    a.out.write_text(json.dumps(dict(status='passed',records=rows),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
