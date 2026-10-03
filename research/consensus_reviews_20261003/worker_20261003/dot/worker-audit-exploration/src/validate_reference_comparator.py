from pathlib import Path
import argparse,json
import numpy as np
import pandas as pd


def main():
    p=argparse.ArgumentParser();p.add_argument('--source-dir',type=Path,required=True);p.add_argument('--results',type=Path,required=True);p.add_argument('--comparator',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    r=json.loads((a.source_dir/'rosters.json').read_text());actual=pd.read_csv(a.results/'pair_effects_by_image.csv',float_precision='round_trip');checks=[]
    for g in r['groups']:
        for method in ('mv50','mv_strict'):
            for version in ('original','manual_revision'):
                src=a.comparator/f"{g['key']}_{method}_{version}.csv"
                if not src.exists():continue
                q=pd.read_csv(src,float_precision='round_trip');policy='original' if version=='original' else 'revised_where_available'
                v=actual[(actual.image==g['image'])&(actual.method==method)&(actual.evaluation_policy==policy)]
                v=v.set_index(['worker_a','worker_b']).loc[pd.MultiIndex.from_frame(q[['worker_a','worker_b']])]
                maximum=max(np.max(abs(v[c].to_numpy()-q[c].to_numpy())) for c in ['mean_a_minus_b','sd_a_minus_b','p10','p90','a_better_fraction','b_better_fraction'])
                maximum=max(maximum,np.max(abs(v.tie_fraction.to_numpy()-q.ties_fraction.to_numpy())))
                assert maximum<1e-12
                checks.append(dict(key=src.stem,pairs=len(q),max_absolute_difference=float(maximum)))
    assert len(checks)==28
    a.out.write_text(json.dumps(dict(arrays_checked=len(checks),pairs_checked=sum(c['pairs'] for c in checks),max_absolute_difference=max(c['max_absolute_difference'] for c in checks),checks=checks),indent=2)+'\n')
if __name__=='__main__':main()
