"""Recreate expanded prefix rows from exact links and deduplicated scalars."""
import argparse
import pandas as pd
from run_prefix_endpoints import csv,save

def main():
    p=argparse.ArgumentParser();p.add_argument('--links',required=True);p.add_argument('--scalars',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    links=pd.read_csv(a.links,low_memory=False);scalars=pd.read_csv(a.scalars,low_memory=False)
    assert not scalars.team_key.duplicated().any()
    assert set(links.team_key)<=set(scalars.team_key)
    values=[c for c in scalars if c not in links or c=='team_key']
    result=links.merge(scalars[values],on='team_key',how='left',validate='many_to_one')
    assert len(result)==len(links)
    csv(a.out,result)
    print('linked',len(result),'prefix rows to',result.team_key.nunique(),'unique endpoints')

if __name__=='__main__':main()
