"""Package fixed lexical pool partitions once all exact endpoints are complete.

Partitioning never inspects scores and does not select study conditions. The four
archives together restore every native per-pool endpoint file needed by analysis.
"""
from __future__ import annotations
import argparse,csv,gzip,json,math,subprocess,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--part',type=int);ap.add_argument('--build',action='store_true');a=ap.parse_args()
    out=ROOT/'stage03_checkpoints';out.mkdir(exist_ok=True)
    by={}
    with gzip.open(ROOT/'stage01_registered/TEAM_REQUESTS.csv.gz','rt',encoding='utf-8-sig',newline='') as f:
        for row in csv.DictReader(f):by.setdefault(row['pool_id'],set()).add(row['team_key'])
    pools=sorted(by);size=math.ceil(len(pools)/4);parts=[pools[i:i+size] for i in range(0,len(pools),size)]
    manifest={'partition_rule':'pool_id lexical order, four consecutive groups; no outcome selection',
              'pools':len(pools),'teams':sum(map(len,by.values())),
              'parts':[{'part':i+1,'pools':xs,'teams':sum(len(by[p]) for p in xs)} for i,xs in enumerate(parts)]}
    p=out/'NATIVE_PARTITIONS.json'
    if p.exists():assert json.loads(p.read_text())==manifest
    else:p.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    status=[]
    for i,xs in enumerate(parts,1):
        done=[pid for pid in xs if (ROOT/'stage03_endpoints/pools'/pid/'CHECKS.json').exists()]
        status.append({'part':i,'complete_pools':len(done),'total_pools':len(xs),'teams':sum(len(by[p]) for p in xs)})
    print(json.dumps(status),flush=True)
    if not a.build:return
    assert a.part and 1<=a.part<=len(parts)
    xs=parts[a.part-1];rows=[];includes=['stage03_checkpoints/NATIVE_PARTITIONS.json','code/checkpoint_native_partition.py']
    for pid in xs:
        folder=ROOT/'stage03_endpoints/pools'/pid
        check=json.loads((folder/'CHECKS.json').read_text());assert check['complete'] and check['total']==len(by[pid])
        seen=set()
        for path in sorted(folder.glob('part_*.jsonl.gz')):
            with gzip.open(path,'rt',encoding='utf-8-sig') as f:
                for line in f:
                    row=json.loads(line);assert row['team_key'] in by[pid] and row['team_key'] not in seen
                    assert 'geometry' in row and row['pool_id']==pid
                    seen.add(row['team_key'])
        assert seen==by[pid]
        rows.append({'pool_id':pid,'teams':len(seen),'complete':True})
        includes.append(str(folder.relative_to(ROOT)))
    index=out/f'PART_{a.part:02d}_IDENTITY_READABILITY.json'
    index.write_text(json.dumps({'part':a.part,'passed':True,'pool_checks':rows,'teams':sum(r['teams'] for r in rows)},indent=2)+'\n')
    includes.append(str(index.relative_to(ROOT)))
    subprocess.run([sys.executable,str(ROOT/'code/package_stage.py'),'--root',str(ROOT),
        '--name',f'HOHONET_v21_AC_stage03_native_part{a.part:02d}',
        '--include',*includes,'--out',str(ROOT/'delivery')],check=True)


if __name__=='__main__':main()
