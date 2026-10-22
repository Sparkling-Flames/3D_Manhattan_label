"""Recreate small scalar-only pool files for summary reruns.

This consumes the delivered ENDPOINT_SCALARS.csv.gz, not raw annotations, and
does not perform fusion or restore missing outcomes. Geometry and full vote
state are intentionally absent; run the native engine for those analyses.
"""
from pathlib import Path
import argparse,gzip,json,os
import pandas as pd


def main(source,out):
    out=Path(out);(out/'pools').mkdir(parents=True,exist_ok=True)
    df=pd.read_csv(source,low_memory=False)
    for pid,group in df.groupby('pool_id',sort=False):
        rows=group.astype(object).where(pd.notna(group),None).to_dict('records')
        obj={'pool_id':pid,'scalar_only_delivery_adapter':True,'teams':rows}
        path=out/'pools'/(pid+'.json.gz');temp=path.with_suffix('.tmp')
        with gzip.open(temp,'wt',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,allow_nan=False,separators=(',',':'))
        os.replace(temp,path)
    print(json.dumps({'source':str(source),'rows':len(df),'pools':df.pool_id.nunique(),'geometry_included':False}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();main(a.source,a.out)
