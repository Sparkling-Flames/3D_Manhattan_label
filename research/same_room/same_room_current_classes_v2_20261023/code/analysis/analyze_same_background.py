"""Match actual retained members and replacement size, inside paired panels.

For each actual D and m, compare all disjoint same-source-class blocks with
all source-to-target pure blocks. This preserves exact D, n and m. Large m
with no same-class comparator remains unavailable instead of being invented.
"""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
import pandas as pd
from analyze_exact_changes import read_pool,finite,analysis_subsets

METRICS=['B8L2','D10','S_bottom_deg','dir','Hmean','Hcenter','nodes','fusion_turn_n','fusion_short_turn_edges','iou_2d','omission','extension']


def main(design,native,out):
    out.mkdir(parents=True,exist_ok=True)
    panels=pd.read_csv(design/'PANELS.csv').fillna({'core':''});links=pd.read_csv(design/'PANEL_TEAM_LINKS.csv.gz')
    linked={k:g.sort_values('selected_mask').reset_index(drop=True) for k,g in links.groupby('panel_id')}
    rows=[];ready=0;panel_stats=[];n_background_rows=0
    output_rows=out/'ACTUAL_BACKGROUND_COMPARISONS.csv.gz'
    if output_rows.exists():output_rows.unlink()
    columns=['panel_id','shared_mask','m','direction','actual_core','same_class_contrasts','cross_class_contrasts']
    columns += [kind+'_complete_rate_'+str(side) for side in (0,1) for kind in ('same','cross')]
    for metric in METRICS:
        columns += [metric+'__same_four_finite_n',metric+'__cross_four_finite_n']
        columns += [metric+'__'+x+'_'+str(side) for side in (0,1) for x in ('same_abs','cross_abs','cross_minus_same_abs','cross_signed')]
        columns += [metric+'__'+x for x in ('cross_larger_both','same_larger_both','amplitude_relation_changes_view')]
    numeric=[c for c in columns if c not in ['panel_id','shared_mask','m','direction','actual_core']]
    for pair,pp in panels.groupby('pair_key',sort=False):
        pools=[read_pool(native,pp.iloc[0].pool_id_a),read_pool(native,pp.iloc[0].pool_id_b)]
        for p in pp.itertuples():
            g=linked[p.panel_id];keys=[g.team_key_a.tolist(),g.team_key_b.tolist()]
            if not all(all(k in pools[side] for k in keys[side]) for side in [0,1]):continue
            ready+=1;rec=[[pools[side][k] for k in keys[side]] for side in [0,1]]
            mask=g.selected_mask.to_numpy(int);h=g.hi_selected.to_numpy(int);ii,jj=np.triu_indices(len(g),1)
            rev=h[jj]<h[ii];i=np.where(rev,jj,ii);j=np.where(rev,ii,jj)
            removed=mask[i]&~mask[j];added=mask[j]&~mask[i];shared=mask[i]&mask[j]
            m=np.array([int(x).bit_count() for x in removed]);r=h[j]-h[i]
            hi_mask=sum(1<<p.candidates.split('|').index(w) for w in p.hi_candidates.split('|'))
            hr=np.array([int(x&hi_mask).bit_count() for x in removed]);ha=np.array([int(x&hi_mask).bit_count() for x in added])
            arrays={metric:[np.array([x.get(metric) if finite(x.get(metric)) else np.nan for x in rr]) for rr in rec] for metric in METRICS}
            delta={metric:[v[j]-v[i] for v in vv] for metric,vv in arrays.items()}
            complete=[np.array([bool(x.get('complete_evaluable')) for x in rr]) for rr in rec]
            for shared_mask,mm in sorted(set(zip(shared,m))):
                z=(shared==shared_mask)&(m==mm)
                pure=z&(r==mm)
                if not pure.any():continue
                for direction,within in [('lower_to_higher',z&(r==0)&(hr==0)&(ha==0)),('higher_to_lower',z&(r==0)&(hr==mm)&(ha==mm))]:
                    if not within.any():continue
                    actual_core=sorted(set(p.core.split('|') if p.core else [])|{w for b,w in enumerate(p.candidates.split('|')) if shared_mask&(1<<b)})
                    row={'panel_id':p.panel_id,'shared_mask':int(shared_mask),'m':int(mm),'direction':direction,
                         'actual_core':'|'.join(actual_core),'same_class_contrasts':int(within.sum()),'cross_class_contrasts':int(pure.sum())}
                    for side in (0,1):
                        cc=complete[side][i]&complete[side][j]
                        row[f'same_complete_rate_{side}']=float(cc[within].mean());row[f'cross_complete_rate_{side}']=float(cc[pure].mean())
                    for metric,dd in delta.items():
                        both=np.isfinite(dd[0])&np.isfinite(dd[1])
                        ss=within&both;cc=pure&both
                        row[metric+'__same_four_finite_n']=int(ss.sum());row[metric+'__cross_four_finite_n']=int(cc.sum())
                        if not ss.any() or not cc.any():continue
                        for side in (0,1):
                            a=np.abs(dd[side][ss]).mean();b=np.abs(dd[side][cc]).mean()
                            row[metric+f'__same_abs_{side}']=float(a);row[metric+f'__cross_abs_{side}']=float(b)
                            row[metric+f'__cross_minus_same_abs_{side}']=float(b-a)
                            row[metric+f'__cross_signed_{side}']=float(dd[side][cc].mean()*(1 if direction=='lower_to_higher' else -1))
                        x=row[metric+'__cross_minus_same_abs_0'];y=row[metric+'__cross_minus_same_abs_1']
                        row[metric+'__cross_larger_both']=float(x>0 and y>0)
                        row[metric+'__same_larger_both']=float(x<0 and y<0)
                        row[metric+'__amplitude_relation_changes_view']=float(x*y<0)
                    rows.append(row)
        if rows:
            df=pd.DataFrame(rows).reindex(columns=columns)
            df.to_csv(output_rows,index=False,mode='a',header=n_background_rows==0,compression='gzip')
            panel_stats.append(df.groupby(['panel_id','m','direction'])[numeric].mean().reset_index())
            n_background_rows+=len(df);rows=[]
        print('processed pair',pair,'panels',ready,'background rows',n_background_rows,flush=True)
    if not panel_stats:return
    # An actual D is a finite-design unit, not an independent observed image.
    ps=pd.concat(panel_stats,ignore_index=True)
    d=ps.merge(panels,on='panel_id');d['mid_n']=[max(3,k,min(N-k,N//2)) for k,N in zip(d.k_selected,d.known_common_n)]
    outsum=[];allgroups=[];allbuildings=[]
    for subset,zz in analysis_subsets(d):
        if not len(zz):continue
        keys=['m','direction'];pair=zz.groupby(keys+['building','pair_key','groups'])[numeric].mean().reset_index()
        group=pair.assign(group_id=pair.groups.str.split('|')).explode('group_id').groupby(keys+['building','group_id'])[numeric].mean().reset_index();group['subset']=subset;allgroups.append(group)
        bb=group.groupby(keys+['building'])[numeric].mean().reset_index();bb['subset']=subset;allbuildings.append(bb)
        for key,gg in bb.groupby(keys):
            s=zz[(zz.m==key[0])&(zz.direction==key[1])]
            row={'subset':subset,'m':key[0],'direction':key[1],'panels':s.panel_id.nunique(),'pairs':s.pair_key.nunique(),'images':len(set(s.image_a)|set(s.image_b)),'buildings':s.building.nunique(),'groups':len(set('|'.join(s.groups).split('|')))}
            row.update({c:gg[c].mean() for c in numeric});outsum.append(row)
    pd.DataFrame(outsum).to_csv(out/'SAME_BACKGROUND_SUMMARY.csv',index=False)
    pd.concat(allgroups).to_csv(out/'SAME_BACKGROUND_GROUPS.csv',index=False);pd.concat(allbuildings).to_csv(out/'SAME_BACKGROUND_BUILDINGS.csv',index=False)
    (out/'ANALYSIS_RECEIPT.json').write_text(json.dumps({'ready_panels':ready,'total_panels':len(panels),'background_strata':n_background_rows,
        'comparison':'same actual retained D, n and m; homogeneous within-source replacements vs homogeneous source-target blocks; both views four-endpoint finite for effect magnitude',
        'all_masks_enumerated':True,'new_fusion':0,'quality_threshold_not_used_to_select':True},ensure_ascii=False,indent=2))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--design',type=Path,required=True);ap.add_argument('--native',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();main(a.design,a.native,a.out)
