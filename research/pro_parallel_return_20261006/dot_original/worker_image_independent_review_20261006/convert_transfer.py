#!/usr/bin/env python3
"""Convert the lossless decimal-string message export; not a CSV-byte re-download."""
import argparse,json,csv
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('input_json');p.add_argument('output_csv');a=p.parse_args()
s=json.loads(Path(a.input_json).read_text());rows=[]
for pol in s['policies']:
 for i,img in enumerate(s['image_order']):
  for j,worker in enumerate(s['worker_order']):
   rows.append(dict(policy=pol['policy'],image=img,worker=worker,building=s['buildings'][i],gt_area_h2=pol['gt_area_h2'][i],reference_version=pol['versions'][i],**{m:pol[m][i][j] for m in ('O','E','D')}))
with open(a.output_csv,'w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print(f'Wrote {len(rows)} balanced cells')
