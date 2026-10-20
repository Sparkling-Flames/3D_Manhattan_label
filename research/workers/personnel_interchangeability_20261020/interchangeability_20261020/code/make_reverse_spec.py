"""Native block competition for frozen direct-swap-risk candidate partitions."""
from __future__ import annotations
import argparse,datetime
from pathlib import Path
from design_history_panel import read,write

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--reverse',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();methods=[]
    for file,version in [('LEGACY_SCREEN_SHORTLIST.json','legacy_actual_swap'),('MIXED_SCREEN_SHORTLIST.json','expanded_actual_swap')]:
        items=read(a.reverse/file)['methods']
        for item in items:
            mid,dom=item['method_id'],item['domain'];k=len(item['class_sizes'])
            method=dict(method_id=mid,domain=dom,family=version,context_id='primary',
                        pool_filter={'layer':'ordinary_manual'},events_per_pool=24 if k<=3 else 48 if k<=6 else 60,
                        selection_basis=item.get('selection_reason','Legacy direct-risk CV and coarse/fine capacity coverage, fixed before target block outcomes'))
            if dom.startswith('hard'):method['pool_filter']['difficulty']='困难'
            if dom=='small_n':method['max_n']=12
            if dom=='large_n':method['min_n']=16
            if dom.endswith('_new'):
                method['matching_policies']=['source_matched']
                method['context_id']='new_blocks_mixed_background'
                methods.append(dict(method,allowed_origins=['new'],context_id='same_source_team'))
            methods.append(method)
    spec=dict(schema='direct_swap_risk_block_competition_v1',phase='discovery',seed=2026102012,
              frozen_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),methods=methods,
              selection='Only history actual-replacement inner CV, trait/condition diversity and real class capacities; no discovery/assessment outcome selection.',
              frame='Every capacity-feasible integer n,m and ordered pure class-block direction in declared domain; random/out-rich/in-rich cores; finite frame counted then 24/48/60 direction/source-stratified contexts per pool sampled.',
              source='New-only entrants evaluated both with same-source whole teams and source-external fixed background; these settings never pooled silently.')
    write(a.out,spec);print('method-settings',len(methods),'unique methods',len({m['method_id'] for m in methods}))

if __name__=='__main__':main()
