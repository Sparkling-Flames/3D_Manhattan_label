import csv,gzip,io,json,zipfile
from pathlib import Path
import argparse

ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--repo',type=Path,required=True)
parser.add_argument('--design-zip',type=Path,required=True)
args=parser.parse_args()
REPO=args.repo
with gzip.open(REPO/'research/workers/personnel_population_curves_v2_20261023/inputs/INPUT_SNAPSHOT.json.gz','rt',encoding='utf-8-sig') as f:
    snap=json.load(f)
pools={p['pool_id']:p for p in snap['images'] if p['meta']['layer'] in ['ordinary_manual','doorway_manual']}
assert len(pools)==194
prefix='research/workers/personnel_population_curves_v2_20261023/sampling_extension_20261026/design26/'
checked=0
with zipfile.ZipFile(args.design_zip) as z:
    for pid,p in pools.items():
        own={r['worker_id']:r['object_id'] for r in p['records']}
        name=prefix+'dependencies_by_pool/'+pid+'.csv.gz'
        with z.open(name) as raw,gzip.GzipFile(fileobj=raw) as gz,io.TextIOWrapper(gz,encoding='utf-8-sig',newline='') as f:
            for row in csv.DictReader(f):
                ws=row['member_workers'].split('|')
                assert set(ws)<=set(own)
                assert [own[w] for w in ws]==row['member_object_ids'].split('|')
                for field in ['image_id','reference_id','reference_version','condition','layer']:
                    assert row[field]==p['meta'][field],(pid,field)
                assert int(row['pool_n'])==len(own)
                checked+=1
result={'frozen_snapshot':'research/workers/personnel_population_curves_v2_20261023/inputs/INPUT_SNAPSHOT.json.gz','pools':194,'dependency_teams':checked,'worker_object_and_reference_identity':'all match frozen local snapshot'}
assert checked==1396509
(ROOT/'FROZEN_POOL_IDENTITY_CHECK.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
