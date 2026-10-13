#!/usr/bin/env python3
"""Recheck actual W019 raw input and current exclusion ledger; do not pair points."""
import json,hashlib
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def main():
    p=ROOT/'integration/inputs/w019_source.json';src=read(p);ledger=read(ROOT/'sources/main/research/quality_parallel_local_20261012/eligibility_ledger.json')['records'];by={r['object_id']:r for r in ledger};rows=[]
    for r in src['rows']:
        gate=by[r['object_id']];assert r['worker_id']=='W019' and not gate['conditional_personnel_eligible'];links=r.get('links_zero_based')
        assert not links,'New pairing evidence appeared: re-investigate before treating this result as unchanged'
        rows.append(dict(record_id=gate['record_id'],object_id=r['object_id'],image_code=r['image_code'],raw_point_count=len(r.get('before_preprocessing_points') or []),pairing_basis=r.get('pairing_basis'),supplied_pair_count=len(links or []),old_main_gate=r['main_quality_gate'],current_gate=gate,current_input_geometry_constructed=False,score=None,floor_score=None,severe_label=None,reason='no_certified_corner_pairing; exclusion is not a geometry severity label'))
    result=dict(schema='w019_current_source_reverification_v1',records=len(rows),pairing_basis_counts=dict(Counter(r['pairing_basis'] for r in rows)),certified_pairs=sum(r['supplied_pair_count'] for r in rows),new_scores_constructed=0,new_severe_labels=0,personnel_exclusion_retained=True,source_subset_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),parent_source_sha256=src['source_file_sha256'],rows=rows)
    out=ROOT/'integration/results/W019_unavailable_ledger.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='rows'},ensure_ascii=False))
if __name__=='__main__':main()
