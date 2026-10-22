"""Rebuild the compact ordinary-primary actual-D table from saved endpoints.

The finite comparison and hierarchy are the same as analyze_same_background.py.
This does not read the corrupted large row export and never invokes fusion.
The package scalar table is sufficient; native geometries are not needed.
"""
from __future__ import annotations
import os
for _k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:
    os.environ[_k]='1'
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import time
import numpy as np
import pandas as pd

METRICS=['B8L2','D10','fusion_turn_n']
META=['pair_key','building','groups','n','replicate','image_a','image_b','pool_id_a','pool_id_b',
      'reference_id_a','reference_id_b','class_lo','class_hi','method','selected_family']


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def write_csv(path,frame):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    blob=frame.to_csv(index=False).encode('utf-8-sig')
    if path.suffix=='.gz':blob=gzip.compress(blob,compresslevel=5,mtime=0)
    temp=path.with_name(path.name+'.tmp');temp.write_bytes(blob);os.replace(temp,path)


def background_panel(p,g,endpoints):
    g=g.sort_values('selected_mask').reset_index(drop=True)
    keys=[g.team_key_a.tolist(),g.team_key_b.tolist()]
    missing=[k for side in keys for k in side if k not in endpoints]
    if missing:raise ValueError(f'Missing saved endpoints in {p.panel_id}: {missing[:3]}')
    rec=[[endpoints[k] for k in side] for side in keys]
    mask=g.selected_mask.to_numpy(int);h=g.hi_selected.to_numpy(int)
    ii,jj=np.triu_indices(len(g),1);rev=h[jj]<h[ii]
    i=np.where(rev,jj,ii);j=np.where(rev,ii,jj)
    removed=mask[i]&~mask[j];added=mask[j]&~mask[i];shared=mask[i]&mask[j]
    m=np.array([int(x).bit_count() for x in removed]);r=h[j]-h[i]
    candidates=p.candidates.split('|')
    hi_mask=sum(1<<candidates.index(w) for w in p.hi_candidates.split('|'))
    hr=np.array([int(x&hi_mask).bit_count() for x in removed])
    ha=np.array([int(x&hi_mask).bit_count() for x in added])
    arrays={metric:[np.array([x[metric] for x in rr],dtype=float) for rr in rec] for metric in METRICS}
    delta={metric:[v[j]-v[i] for v in vv] for metric,vv in arrays.items()}
    complete=[np.array([x['complete_evaluable'] is True or x['complete_evaluable']==1 for x in rr],bool) for rr in rec]
    rows=[]
    for shared_mask,mm in sorted(set(zip(shared,m))):
        use=(shared==shared_mask)&(m==mm);pure=use&(r==mm)
        if not pure.any():continue
        for direction,within in [
          ('lower_to_higher',use&(r==0)&(hr==0)&(ha==0)),
          ('higher_to_lower',use&(r==0)&(hr==mm)&(ha==mm))]:
            if not within.any():continue
            actual_core=sorted(set(p.core.split('|') if p.core else [])|{w for b,w in enumerate(candidates) if shared_mask&(1<<b)})
            assert len(actual_core)==int(p.n)-int(mm)
            raw_key=f'{p.panel_id}|{shared_mask}|{mm}|{direction}'
            same_pairs=[[int(mask[a]),int(mask[b])] for a,b in zip(i[within],j[within])]
            cross_pairs=[[int(mask[a]),int(mask[b])] for a,b in zip(i[pure],j[pure])]
            if direction=='higher_to_lower':cross_pairs=[pair[::-1] for pair in cross_pairs]
            row={k:getattr(p,k) for k in META}
            row.update(background_key='SRCC23D_'+hashlib.sha256(raw_key.encode()).hexdigest()[:20],
                panel_id=p.panel_id,shared_mask=int(shared_mask),m=int(mm),direction=direction,
                actual_core='|'.join(actual_core),same_mask_pairs_json=json.dumps(same_pairs,separators=(',',':')),
                cross_mask_pairs_json=json.dumps(cross_pairs,separators=(',',':')),
                same_class_contrasts=int(within.sum()),cross_class_contrasts=int(pure.sum()))
            for side in (0,1):
                cc=complete[side][i]&complete[side][j]
                row[f'same_complete_rate_{side}']=float(cc[within].mean())
                row[f'cross_complete_rate_{side}']=float(cc[pure].mean())
            for metric,dd in delta.items():
                both=np.isfinite(dd[0])&np.isfinite(dd[1]);ss=within&both;cc=pure&both
                row[metric+'__same_four_finite_n']=int(ss.sum())
                row[metric+'__cross_four_finite_n']=int(cc.sum())
                if not ss.any() or not cc.any():continue
                for side in (0,1):
                    sa=np.abs(dd[side][ss]).mean();ca=np.abs(dd[side][cc]).mean()
                    row[metric+f'__same_abs_{side}']=float(sa)
                    row[metric+f'__cross_abs_{side}']=float(ca)
                    row[metric+f'__cross_minus_same_abs_{side}']=float(ca-sa)
                    row[metric+f'__cross_signed_{side}']=float(dd[side][cc].mean()*(1 if direction=='lower_to_higher' else -1))
                x=row[metric+'__cross_minus_same_abs_0'];y=row[metric+'__cross_minus_same_abs_1']
                row[metric+'__cross_larger_both']=float(x>0 and y>0)
                row[metric+'__same_larger_both']=float(x<0 and y<0)
                row[metric+'__amplitude_relation_changes_view']=float(x*y<0)
            rows.append(row)
    return rows


def summarize(rows,panels):
    metrics=['same_class_contrasts','cross_class_contrasts']
    metrics += [f'{kind}_complete_rate_{side}' for side in (0,1) for kind in ('same','cross')]
    metrics += [c for c in rows.columns if any(c.startswith(m+'__') for m in METRICS)]
    ps=rows.groupby(['panel_id','m','direction'])[metrics].mean().reset_index()
    d=ps.merge(panels,on='panel_id',validate='many_to_one')
    keys=['m','direction']
    pair=d.groupby(keys+['building','pair_key','groups'])[metrics].mean().reset_index()
    group=pair.assign(group_id=pair.groups.str.split('|')).explode('group_id').groupby(keys+['building','group_id'])[metrics].mean().reset_index()
    building=group.groupby(keys+['building'])[metrics].mean().reset_index()
    summary=[]
    for key,g in building.groupby(keys):
        ss=d[(d.m==key[0])&(d.direction==key[1])]
        z=dict(subset='ordinary_mid',m=int(key[0]),direction=key[1],panels=int(ss.panel_id.nunique()),
            pairs=int(ss.pair_key.nunique()),images=len(set(ss.image_a)|set(ss.image_b)),
            buildings=int(ss.building.nunique()),groups=len(set('|'.join(ss.groups).split('|'))))
        z.update({c:float(g[c].mean()) for c in metrics});summary.append(z)
    return pd.DataFrame(summary),ps


def main():
    p=argparse.ArgumentParser();p.add_argument('--design',type=Path,required=True)
    p.add_argument('--scalars',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--reference-summary',type=Path,required=True)
    p.add_argument('--corrupted-export',type=Path)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True);start=time.monotonic()
    panels=pd.read_csv(a.design/'PANELS.csv').fillna({'core':''})
    mid=pd.Series([max(3,int(k),min(int(N)-int(k),int(N)//2)) for k,N in zip(panels.k_selected,panels.known_common_n)],index=panels.index)
    panels=panels[panels.ordinary_comparable.eq(True)&panels.replicate.eq(0)&panels.n.eq(mid)].copy()
    links=pd.read_csv(a.design/'PANEL_TEAM_LINKS.csv.gz')
    links=links[links.panel_id.isin(panels.panel_id)]
    usecols=['team_key','complete_evaluable']+METRICS
    df=pd.read_csv(a.scalars,usecols=usecols)
    wanted=set(links.team_key_a)|set(links.team_key_b)
    df=df[df.team_key.isin(wanted)]
    if df.team_key.duplicated().any():raise ValueError('Saved scalar team keys are not unique.')
    endpoints={r['team_key']:r for r in df.to_dict('records')}
    linked={pid:g for pid,g in links.groupby('panel_id',sort=False)}
    rows=[]
    for k,panel in enumerate(panels.itertuples(),1):
        rows.extend(background_panel(panel,linked[panel.panel_id],endpoints))
        if k%50==0:print(json.dumps({'panels':k,'background_rows':len(rows)}),flush=True)
    rows=pd.DataFrame(rows)
    if rows.background_key.duplicated().any():raise ValueError('Actual background key collision.')
    output=a.out/'PRIMARY_ACTUAL_BACKGROUND_COMPARISONS.csv.gz'
    write_csv(output,rows)
    summary,ps=summarize(rows,panels)
    write_csv(a.out/'PRIMARY_SAME_BACKGROUND_SUMMARY.csv',summary)
    original=pd.read_csv(a.reference_summary)
    original=original[original.subset.eq('ordinary_mid')&original.m.isin([1,2])]
    check=summary.merge(original,on=['subset','m','direction'],suffixes=('_rebuilt','_saved'),validate='one_to_one')
    compare=[c for c in summary.select_dtypes(include='number').columns if c!='m' and c in original]
    diffs=[]
    for c in compare:
        x=check[c+'_rebuilt'].to_numpy(float);y=check[c+'_saved'].to_numpy(float)
        if not np.array_equal(np.isnan(x),np.isnan(y)):raise AssertionError('Missing-state mismatch: '+c)
        good=np.isfinite(x)&np.isfinite(y)
        error=float(np.max(np.abs(x[good]-y[good]))) if good.any() else 0.
        diffs.append(dict(field=c,maximum_absolute_difference=error))
        if error>1e-10:raise AssertionError(f'Summary mismatch: {c} {error}')
    if len(check)!=len(original):raise AssertionError('Primary summary row support mismatch.')
    write_csv(a.out/'PRIMARY_SUMMARY_RECONSTRUCTION_CHECK.csv',pd.DataFrame(diffs))
    # Re-open the single atomic gzip stream to ensure the supplied artifact is readable.
    reread=pd.read_csv(output,usecols=['background_key','panel_id','m'])
    assert len(reread)==len(rows) and reread.background_key.nunique()==len(rows)
    receipt={'reconstruction_role':'corrupted-large-export omitted / reconstructed compact primary',
      'source_repository_commit':'72a44e80c344975962e1071bd54d894dd86bb4b4',
      'selection':'ordinary_comparable; replicate=0; n=max(3,k,min(N-k,floor(N/2)))',
      'requested_primary_panels':len(panels),'evaluated_primary_panels':len(panels),
      'panels_with_actual_D_comparator':int(rows.panel_id.nunique()),'background_strata':len(rows),
      'actual_m_values':sorted(map(int,rows.m.unique())),'metrics':METRICS,'endpoint_rows_used':len(endpoints),
      'new_fusions':0,'new_scores':0,'missing_states_preserved':True,
      'native_scalar_source':str(a.scalars),'native_scalar_source_sha256':sha(a.scalars),
      'design_panels_sha256':sha(a.design/'PANELS.csv'),'design_links_sha256':sha(a.design/'PANEL_TEAM_LINKS.csv.gz'),
      'reference_summary_sha256':sha(a.reference_summary),'reference_rows_matched':len(check),
      'summary_fields_checked':len(diffs),'summary_maximum_absolute_difference':max(x['maximum_absolute_difference'] for x in diffs),
      'tolerance':1e-10,'output_name':output.name,'output_sha256':sha(output),
      'output_gzip_readback_rows':len(reread),'write_mode':'one atomic gzip stream; no append',
      'mask_contract':'panel_id + selected_mask joins design/PANEL_TEAM_LINKS; same_mask_pairs are canonical within-class unordered orientations; cross_mask_pairs follow row direction; actual_core includes fixed core and shared candidate members',
      'wall_seconds':time.monotonic()-start}
    if a.corrupted_export:
        receipt['omitted_corrupted_large_export']={'name':a.corrupted_export.name,'byte_size':a.corrupted_export.stat().st_size,'sha256':sha(a.corrupted_export),'status':'previous read failed with gzip invalid code lengths; never parsed in this reconstruction'}
    (a.out/'PRIMARY_RECONSTRUCTION_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
    print(json.dumps(receipt,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
