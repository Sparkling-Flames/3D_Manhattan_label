"""Observed within-composition dispersion on identical finite team supports."""
from pathlib import Path
import argparse,json
import numpy as np
import pandas as pd

def main(data,panels,out):
    out=Path(out);d=pd.read_csv(data);p=pd.read_csv(panels).set_index('panel_id')
    methods=[c[:-12] for c in d if c.endswith('_composition')]
    metrics=['B8L2','fusion_turn_n','record_time_single_source'];cells=[];prs=[]
    for method in methods:
        col=method+'_composition'
        for metric in metrics:
            dd=d[d[metric].notna()].copy()
            groups=dd.groupby(['panel_id',col])[metric]
            c=groups.agg(valid_teams='size',mean='mean',sd='std',minimum='min',maximum='max').reset_index().rename(columns={col:'composition'})
            q=groups.quantile([.1,.25,.5,.75,.9]).unstack().reset_index().rename(columns={col:'composition',.1:'p10',.25:'p25',.5:'p50',.75:'p75',.9:'p90'})
            c=c.merge(q,on=['panel_id','composition'],validate='one_to_one')
            c['method']=method;c['metric']=metric;c['range']=c.maximum-c.minimum;c['iqr']=c.p75-c.p25
            # A singleton is a missing estimate of within-cell dispersion.
            c.loc[c.valid_teams.lt(2),['sd','range','iqr']]=np.nan
            c['within_ss']=c.sd.pow(2)*(c.valid_teams-1)
            c.loc[c.valid_teams.eq(1),'within_ss']=0.
            c=c.merge(p[['pool_id','image','building','n','source_domain','official_difficulty']],left_on='panel_id',right_index=True,validate='many_to_one')
            cells.append(c)
            for pid,g in c.groupby('panel_id'):
                vals=dd[dd.panel_id.eq(pid)][metric]
                total=vals.var(ddof=0);within=g.within_ss.sum()/len(vals)
                z=g[g.valid_teams.ge(2)]
                prs.append(dict(method=method,metric=metric,panel_id=pid,pool_id=p.loc[pid,'pool_id'],image=p.loc[pid,'image'],building=p.loc[pid,'building'],
                                valid_team_links=len(vals),cells=len(g),non_singleton_cells=len(z),singleton_teams=int(g[g.valid_teams.eq(1)].valid_teams.sum()),
                                total_variance=total,within_variance=within,between_variance=total-within,
                                median_cell_sd=z.sd.median(),p90_cell_sd=z.sd.quantile(.9),median_cell_p90_p10=(z.p90-z.p10).median(),
                                mean_cell_sd=z.sd.mean(),max_cell_range=z['range'].max()))
        print(method,flush=True)
    c=pd.concat(cells,ignore_index=True);c.to_csv(out/'SAME_COMPOSITION_CELL_DISTRIBUTIONS.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    r=pd.DataFrame(prs);r.to_csv(out/'SAME_COMPOSITION_PANEL_RESIDUALS.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    val=['total_variance','within_variance','between_variance','median_cell_sd','p90_cell_sd','median_cell_p90_p10','mean_cell_sd']
    pp=r.groupby(['method','metric','pool_id','image','building'])[val].mean().reset_index();im=pp.groupby(['method','metric','image','building'])[val].mean().reset_index();bl=im.groupby(['method','metric','building'])[val].mean().reset_index()
    rows=[]
    for weight,t in [('image_equal',im),('building_equal',bl)]:
        for keys,g in t.groupby(['method','metric']):
            z=g[val].mean();src=r[r.method.eq(keys[0])&r.metric.eq(keys[1])]
            rows.append(dict(method=keys[0],metric=keys[1],weighting=weight,panels=src.panel_id.nunique(),images=src.image.nunique(),buildings=src.building.nunique(),
                             valid_team_links=int(src.valid_team_links.sum()),**z.to_dict(),within_share=z.within_variance/z.total_variance if z.total_variance>1e-15 else np.nan,
                             between_share=z.between_variance/z.total_variance if z.total_variance>1e-15 else np.nan,
                             within_rms_sd=np.sqrt(z.within_variance)))
    pd.DataFrame(rows).to_csv(out/'SAME_COMPOSITION_RESIDUAL_SUMMARY.csv',index=False)
    im.to_csv(out/'SAME_COMPOSITION_IMAGE_RESIDUALS.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    (out/'SAME_COMPOSITION_COMPLETION.json').write_text(json.dumps(dict(methods=methods,metrics=metrics,cells=len(c),panels=r.panel_id.nunique(),zero_fusion=True,singleton_dispersion_missing=True),indent=2))

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--data',required=True);a.add_argument('--panels',required=True);a.add_argument('--out',required=True);z=a.parse_args();main(z.data,z.panels,z.out)
