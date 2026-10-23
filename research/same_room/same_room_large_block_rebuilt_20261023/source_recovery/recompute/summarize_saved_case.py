#!/usr/bin/env python3
"""New reading helper: regroup saved four historical paths, not a new experiment."""
from pathlib import Path
import argparse
import pandas as pd

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);args=p.parse_args()
    root=Path(__file__).resolve().parent
    d=pd.read_csv(root/'population_existing_originals/cases/UwV83HsGsw3-12/PATH_SCALARS.csv')
    assert len(d)==112 and d.path_id.nunique()==4
    out=d.groupby('k').agg(attempts=('team_key','size'),paths=('path_id','nunique'),Q_n=('B8L2','count'),Q_mean=('B8L2','mean'),Q_P10=('B8L2',lambda x:x.quantile(.1,interpolation='linear')),Q_SD_ddof1=('B8L2','std'))
    out['Q_missing']=out.attempts-out.Q_n
    out['policy_deferred_attempts']=out.attempts.where(out.index==2,0)
    out['source_stage']='existing_4_historical_natural_paths_not_full24'
    out['operation']='this_turn_reading_helper_no_new_fusion_or_scoring'
    args.out.parent.mkdir(parents=True,exist_ok=True);out.to_csv(args.out,encoding='utf-8-sig')
    print(f'Saved {len(out)} existing per-k rows; no new experiment')

if __name__=='__main__':main()
