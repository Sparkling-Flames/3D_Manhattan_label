"""Input-only opportunity support; does not read fusion/class outputs."""
from pathlib import Path
import pandas as pd
HERE=Path(__file__).resolve().parent

def main():
    x=pd.read_csv(HERE/'event_design.csv.gz',usecols=['event_id','panel_id','worker_a','worker_b','image_id','building','k','pool_id','member_workers_a','member_workers_b'],low_memory=False)
    x.groupby(['panel_id','k']).agg(events=('event_id','size'),images=('image_id','nunique'),buildings=('building','nunique')).reset_index().to_csv(
        HERE/'design_coverage_by_k.csv',index=False,encoding='utf-8-sig')
    rows=[]
    for panel,g in x.groupby('panel_id'):
        z=pd.concat([g.rename(columns={'worker_a':'worker_id'}).drop(columns='worker_b'),g.rename(columns={'worker_b':'worker_id'}).drop(columns='worker_a')])
        for w,a in z.groupby('worker_id'):
            rows.append(dict(panel_id=panel,worker_id=w,events=len(a),images=a.image_id.nunique(),buildings=a.building.nunique(),supported_k='|'.join(map(str,sorted(a.k.unique())))))
    pd.DataFrame(rows).to_csv(HERE/'entrant_opportunity_coverage.csv',index=False,encoding='utf-8-sig')
    collisions=[]
    keys=['pool_id','member_workers_a','member_workers_b']
    for (panel,k),g in x.groupby(['panel_id','k']):
        c=g.groupby(keys).size()
        collisions.append(dict(panel_id=panel,k=k,registered_events=len(g),unique_actual_endpoint_pairs=len(c),
                               repeated_event_occurrences=int((c-1).sum()),actual_pairs_repeated=int((c>1).sum())))
    pd.DataFrame(collisions).to_csv(HERE/'design_duplicate_actual_pairs.csv',index=False,encoding='utf-8-sig')
    print(pd.DataFrame(rows).groupby('panel_id').agg(workers=('worker_id','nunique'),min_images=('images','min')).to_string())

if __name__=='__main__':main()
