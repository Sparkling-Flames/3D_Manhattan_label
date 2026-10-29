"""Archive complete per-pool AC event metrics without duplicating the global CSV.

Each independent ZIP stays below the Library upload limit. Exact pool assignment,
rows, byte hashes, and full gzip/CSV readback receipts are retained.
"""
from __future__ import annotations
import argparse,json,subprocess,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--build',action='store_true');ap.add_argument('--part',type=int);a=ap.parse_args()
    metadata=ROOT/'stage04_metrics';r=json.loads((metadata/'MEASUREMENT_RECEIPT.json').read_text())
    if not r.get('complete'):raise RuntimeError('Only a complete, verified measurement can be packaged.')
    files=sorted((metadata/'metric_shards').glob('*.csv.gz'))
    contract=json.loads((ROOT/'stage01_registered/FROZEN_MERGED_DESIGN.json').read_text())
    # Registration count is checked independently by the measurement receipt;
    # do not infer a domain from lexicographic filenames or a fixed count.
    plans=[];items=[];size=0;limit=340*1024**2
    for p in files:
        n=p.stat().st_size
        if items and size+n>limit:
            plans.append({'part':len(plans)+1,'compressed_input_bytes':size,'files':items});items=[];size=0
        if n>limit:raise ValueError('Unexpected oversized individual pool: '+p.name)
        items.append(str(p.relative_to(ROOT)));size+=n
    if items:plans.append({'part':len(plans)+1,'compressed_input_bytes':size,'files':items})
    index=metadata/'METRIC_DELIVERY_PARTITIONS.json'
    payload={'pool_count':len(files),'parts':plans,'duplicate_merged_csv_excluded':True,'all_event_columns_preserved':True,'partition_is_only_for_storage':True}
    if index.exists():assert json.loads(index.read_text())==payload
    else:index.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'pools':len(files),'parts':[{'part':p['part'],'pools':len(p['files']),'bytes':p['compressed_input_bytes']} for p in plans]},ensure_ascii=False),flush=True)
    if a.build:
        for p in plans:
            if a.part and a.part!=p['part']:continue
            include=p['files']+[str(index.relative_to(ROOT))]
            if p['part']==1:
                include += [str(q.relative_to(ROOT)) for q in metadata.iterdir() if q.is_file() and q.suffix in {'.json','.md'} and q!=index]
            subprocess.run([sys.executable,str(ROOT/'code/package_stage.py'),'--root',str(ROOT),'--name',f"HOHONET_v21_AC_stage04_metrics_part{p['part']:02}",'--include',*include,'--out',str(ROOT/'delivery')],check=True)


if __name__=='__main__':main()
