#!/usr/bin/env python3
"""Small presentation extracts, with explicit filters; no new fusion or score."""
from pathlib import Path
import argparse,json
import pandas as pd
from analyze_natural_curves import save

def main(a):
    p=Path(a.out)
    layers=['ordinary_manual','ordinary_semi','doorway_manual']
    c=pd.read_csv(p/'NATURAL_DIFFICULTY_CURVES.csv')
    c=c[c.panel.eq('fixed_pool_N_ge_20')&c.axis.eq('difficulty')&c.layer.isin(layers)&c.k.isin([1,3,6,10,20])]
    save(c,p/'SECTION6_KEY_CURVES.csv')
    s=pd.read_csv(p/'NATURAL_FIXED_N20_INTERVAL_SUMMARY.csv')
    s=s[s.axis.eq('difficulty')&s.layer.isin(layers)&s.interval.isin(['1_to_3','3_to_6','10_to_20','3_to_20'])]
    save(s,p/'SECTION6_KEY_INTERVALS.csv')
    m=pd.read_csv(p/'NATURAL_COMPONENT_CURVES.csv.gz')
    m=m[m.panel.eq('fixed_pool_N_ge_20')&m.axis.eq('difficulty')&m.layer.isin(layers)&m.k.isin([3,20])]
    save(m,p/'SECTION6_COMPONENTS_3_TO20.csv')
    images=['UwV83HsGsw3-12','pa4otMbVnkk-09','B6ByNegPMKs-33','UwV83HsGsw3-09','uNb9QFRL6hY-60']
    r=pd.read_csv(p/'NATURAL_IMAGE_CURVES.csv.gz')
    r=r[r.image.isin(images)&r.condition.eq('manual')&(r.k.isin([1,3,6,10,20])|r.full_pool_endpoint)]
    save(r,p/'CASE_NATURAL_PROCESS_SUMMARIES.csv')
    cols=['pool_id','path_id','interval','B8L2_delta','two_scored','quality_improved','quality_loss_gt5','quality_loss_gt10']
    d=pd.read_csv(p/'NATURAL_PAIRED_PATH_INTERVALS.csv.gz',usecols=cols)
    d=d[d.pool_id.str.split('__').str[0].isin(images)&d.pool_id.str.contains('__manual__')&d.interval.isin(['3_to_6','10_to_20'])]
    z=d.groupby(['pool_id','interval']).agg(paths=('path_id','size'),paired_scored=('two_scored','sum'),paired_Q_mean_delta=('B8L2_delta','mean'),improved_paths=('quality_improved','sum'),loss_gt5_paths=('quality_loss_gt5','sum'),loss_gt10_paths=('quality_loss_gt10','sum')).reset_index()
    save(z,p/'CASE_INTERVAL_PATH_SUPPORT.csv')
    (p/'SECTION6_EXTRACT_RECEIPT.json').write_text(json.dumps(dict(panel='fixed_pool_N_ge_20',layers=layers,axis='difficulty',curve_k=[1,3,6,10,20],intervals=['1_to_3','3_to_6','10_to_20','3_to_20'],case_images=images,curve_rows=len(c),interval_rows=len(s),component_rows=len(m),case_rows=len(r),case_support_rows=len(z),new_fusions=0,new_scores=0),ensure_ascii=False,indent=2)+'\n')
    print('Saved section 6 extracts:',len(c),len(s),len(m),len(r),len(z))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);main(p.parse_args())
