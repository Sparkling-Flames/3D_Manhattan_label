"""Verbatim aggregation helpers from taxonomy_response/analyze_response.py; no weighting change."""
from pathlib import Path
import os,gzip
import pandas as pd

def write_csv(path, df):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    raw=df.to_csv(index=False).encode('utf-8-sig')
    if path.suffix=='.gz':raw=gzip.compress(raw,mtime=0)
    tmp=path.with_name(path.name+'.tmp');tmp.write_bytes(raw);os.replace(tmp,path)

def hierarchy(df,keys,value_cols):
    """Panel -> direct pair -> declared group -> building equally.

    A direct pair with multiple declarations appears in each adopted declaration;
    this is an explicit descriptive weighting, not independent-room inference.
    """
    if not len(df):return pd.DataFrame(),pd.DataFrame(),pd.DataFrame(),pd.DataFrame()
    keys=list(keys);keep=keys+['pair_key','building','groups']
    pair=df.groupby(keep,dropna=False)[value_cols].mean().reset_index()
    counts=df.groupby(keep,dropna=False).size().reset_index(name='n_panel_rows')
    pair=pair.merge(counts,on=keep,how='left')
    pair['group_id']=pair.groups.fillna('').str.split('|');e=pair.explode('group_id')
    group=e.groupby(keys+['building','group_id'],dropna=False)[value_cols].mean().reset_index()
    group=group.merge(e.groupby(keys+['building','group_id'],dropna=False).agg(n_direct_pairs=('pair_key','nunique')).reset_index(),on=keys+['building','group_id'])
    building=group.groupby(keys+['building'],dropna=False)[value_cols].mean().reset_index()
    building=building.merge(group.groupby(keys+['building'],dropna=False).agg(n_declared_groups=('group_id','nunique')).reset_index(),on=keys+['building'])
    summary=building.groupby(keys,dropna=False)[value_cols].mean().reset_index()
    support=e.groupby(keys,dropna=False).agg(direct_pairs=('pair_key','nunique'),buildings=('building','nunique'),declared_groups=('group_id','nunique')).reset_index()
    summary=summary.merge(support,on=keys,how='left')
    return pair,group,building,summary
