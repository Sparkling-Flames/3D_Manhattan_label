"""Held-out block tolerance CDFs from frozen labels; independent recategorization."""
from pathlib import Path
import hashlib,json,os,gzip
os.environ['MPLCONFIGDIR']='/tmp/block_cdf_mpl'
import pandas as pd,numpy as np
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parent.parent;O=R/'audit_statistics/block_fit/tolerance';O.mkdir(exist_ok=True)
f=pd.read_csv(R/'audit_corner/history_block_metrics/COMMON_ENDPOINT_PAIRS.csv.gz',low_memory=False);labels=pd.read_csv(R/'audit_learning/block_fit/fold_labels.csv');bl=pd.read_csv(R/'audit_learning/original_Rnew2_inner_fold_labels.csv');order=sorted(f.building.unique(),key=lambda b:hashlib.sha256(f'2026102003|inner|{b}'.encode()).hexdigest());fold={b:i//2 for i,b in enumerate(order)};f['fold']=f.building.map(fold)
fh=gzip.open(O/'EMPIRICAL_CDF.csv.gz','wt'); written=0
metrics=['bev_max_h','top_max_h','bev_max_local_radius_fraction','top_max_local_radius_fraction'];rows=[];qs=[];support=[]
for mid,lab in labels.groupby('method_id'):
 parts=[]
 for fi,g in f.groupby('fold'):
  d=g.copy();mp=lab[lab.fold.eq(fi)].set_index('worker_id').class_id.to_dict();bp=bl[bl.fold.eq(fi)].set_index('worker_id').class_id.to_dict()
  for meth,mapping in [('candidate',mp),('Rnew2',bp)]:
   def vec(x):return tuple(sorted(mapping[w] for w in x.split('|'))) if all(w in mapping for w in x.split('|')) else None
   a=d.left_workers.map(vec);b=d.right_workers.map(vec);d[meth]=np.where(a.notna()&b.notna(),np.where(a==b,'within','between'),'unknown')
  parts.append(d)
 d=pd.concat(parts);d=d[(d.candidate!='unknown')&(d.Rnew2!='unknown')]
 for gate in ['all_common','angle_le_9','angle_le_12']:
  v=d[d.status.eq('unique_cyclic_candidate')].copy()
  if gate!='all_common':v=v[v.angle_deg<=int(gate.split('_')[-1])]
  common=set(v.anchor_id)
  for meth in ['candidate','Rnew2']:
   for arm in ['within','between']:common &= set(v.loc[v[meth].eq(arm),'anchor_id'])
  z=v[v.anchor_id.isin(common)].copy()
  for meth in ['candidate','Rnew2']:
   for arm in ['within','between']:
    raw=d[d[meth].eq(arm)];support.append(dict(method=mid,gate=gate,arm=meth+'_'+arm,all_observed_attempts=len(raw),all_observed_anchors=raw.anchor_id.nunique(),complete=int(raw.complete.sum()),same_count=int(raw.same_count.sum()),available=int(raw.status.eq('unique_cyclic_candidate').sum()),four_cell_common_anchors=len(common),conditional_events=int(z[meth].eq(arm).sum())))
  fig,axes=plt.subplots(2,2,figsize=(10,7))
  for j,metric in enumerate(metrics):
   xx=np.unique(np.r_[0,z[metric].to_numpy()])
   for meth in ['candidate','Rnew2']:
    for arm in ['within','between']:
     t=z[z[meth].eq(arm)].copy();counts=t.groupby('anchor_id')[metric].transform('size');anchors=t[['building','pool_id','n','anchor_id']].drop_duplicates();na=anchors.groupby(['building','pool_id','n']).anchor_id.nunique();nn=anchors.groupby(['building','pool_id']).n.nunique();ni=anchors.groupby('building').pool_id.nunique();nb=anchors.building.nunique();w=np.array([1/(nb*ni[r.building]*nn[r.building,r.pool_id]*na[r.building,r.pool_id,r.n]) for r in t.itertuples()])/counts.to_numpy();assert abs(w.sum()-1)<1e-10
     vv=t[metric].to_numpy();ix=np.argsort(vv);vv=vv[ix];cw=np.cumsum(w[ix]);inds=np.searchsorted(vv,xx,side='right');yy=np.where(inds>0,cw[np.maximum(inds-1,0)],0)
     chunk=pd.DataFrame(dict(method=mid,gate=gate,metric=metric,arm=meth+'_'+arm,tolerance=xx,fraction_le=yy));chunk.to_csv(fh,index=False,header=(written==0));written+=len(chunk);qs.append(dict(method=mid,gate=gate,metric=metric,arm=meth+'_'+arm,median=vv[np.searchsorted(cw,.5)],p90=vv[min(np.searchsorted(cw,.9),len(vv)-1)],p95=vv[min(np.searchsorted(cw,.95),len(vv)-1)],max=vv[-1]))
     if gate=='all_common':axes.flat[j].step(xx,yy,where='post',label=meth+' '+arm);axes.flat[j].set(title=metric,xlim=(0,xx[-1]*1.02),ylim=(0,1.02));axes.flat[j].legend(fontsize=8)
  if gate=='all_common':fig.suptitle(mid+' held-out history; four-cell common anchors\nEqual building / image / n / anchor weights; full observed axis');fig.tight_layout();fig.savefig(O/(mid+'.png'),dpi=140)
  plt.close(fig)
fh.close();pd.DataFrame(qs).to_csv(O/'QUANTILES.csv',index=False);pd.DataFrame(support).to_csv(O/'COVERAGE.csv',index=False)
(O/'RECEIPT.json').write_text(json.dumps(dict(raw_pairs=len(f),methods=labels.method_id.unique().tolist(),rows=written,folds='Hash-recomputed held-out buildings; no full-fit labels used.',support='Four-cell conditional common anchors; all-observed arm coverage separately. Same endpoints, not same within pair populations. No optimized tolerance.'),indent=2));print(written)
