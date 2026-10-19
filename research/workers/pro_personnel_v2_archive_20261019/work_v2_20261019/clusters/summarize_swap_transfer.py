"""Score saved LOBO swap predictions with explicit image-before-building weights."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
from analyze_fusion_clusters import bs
HERE=Path(__file__).resolve().parent

def main():
    out=HERE/'swap_transfer';image=pd.read_csv(out/'image_k_scores.csv');models=sorted(image.model.unique());sums=[];comps=[]
    required=image.groupby('pool_id').k.nunique();common=set(required[required.eq(4)].index)
    panels={'all_available':image,'common_all_k':image[image.pool_id.isin(common)]}
    for name,value in [('easy','简单'),('medium','中等'),('hard','困难')]:panels['difficulty_'+name]=image[image.difficulty.eq(value)]
    for panel,data in panels.items():
        for outcome,g in data.groupby('outcome'):
            for k in ['all',8,12,16,24]:
                h=g if k=='all' else g[g.k.eq(k)]
                if not len(h):continue
                perimage=h.groupby(['building_id','pool_id','model'])[['squared_error','absolute_error']].mean().reset_index()
                bld=perimage.groupby(['building_id','model'])[['squared_error','absolute_error']].mean().reset_index()
                for model,b in bld.groupby('model'):
                    z=bs(b.squared_error)
                    sums.append(dict(panel=panel,outcome=outcome,k=k,model=model,images=h[h.model.eq(model)].pool_id.nunique(),buildings=z['n'],
                        MSE=z['mean'],RMSE=np.sqrt(z['mean']),MAE=b.absolute_error.mean(),low=z['low'],high=z['high']))
                wide=bld.pivot(index='building_id',columns='model',values='squared_error')
                contrasts=[(m,'known_task') for m in models if m!='known_task']+[('QT','Q'),('QTD','QT'),('QTD_actual_cluster_9','QTD'),('QTD_actual_cluster_9','actual_cluster_9')]
                for model,base in contrasts:
                    delta=(wide[model]-wide[base]).dropna();z=bs(delta)
                    comps.append(dict(panel=panel,outcome=outcome,k=k,model=model,baseline=base,buildings=z['n'],delta_MSE=z['mean'],low=z['low'],high=z['high'],
                        improved_buildings=int(delta.lt(0).sum()),worse_buildings=int(delta.gt(0).sum())))
    summary=pd.DataFrame(sums);comparison=pd.DataFrame(comps)
    summary.to_csv(out/'summary_weighted_panels.csv',index=False);comparison.to_csv(out/'paired_comparisons_weighted_panels.csv',index=False)
    # These replace the initial all-k aggregation, whose image/k rows had equal
    # weight. No fitted coefficients or predictions are changed.
    summary[summary.panel.eq('all_available')].drop(columns='panel').to_csv(out/'summary.csv',index=False)
    comparison[comparison.panel.eq('all_available')].drop(columns='panel').to_csv(out/'paired_comparisons.csv',index=False)
    r=json.loads((out/'RECEIPT.json').read_text());r['summary_weighting']='pairs -> background -> image/k -> image -> building; equal available k within image'
    r['summary_fix']='Original saved predictions unchanged; all-k summaries explicitly average k inside image before buildings.'
    r['summary_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();r['common_all_k_images']=len(common)
    (out/'RECEIPT.json').write_text(json.dumps(r,indent=2)+'\n');print(summary[(summary.panel=='all_available')&(summary.k=='all')].to_string(index=False))

if __name__=='__main__':main()
