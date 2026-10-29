"""Audit the v2.1 reaudit delivery from its repository source archive."""
import os
os.environ['OMP_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1'
from pathlib import Path
import json
import pandas as pd,numpy as np
from scipy.optimize import linear_sum_assignment
from scipy.cluster.hierarchy import linkage,cut_tree
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_rand_score
O=Path('research/workers/personnel_v21_reselection_20261029/independent_review/reaudit_20261029');V=Path('research/data/releases/v2.1');ROOT=Path.cwd();A=O/'source_archive';M=pd.read_csv(A/'SOURCE_ARCHIVE_MAP.csv')
def source_file(stage,suffix):
 rows=M[(M.source_zip_name==f'HOHONET_v21_reaudit_{stage}.zip')&M.member_path.str.endswith(suffix)];assert len(rows)==1,(stage,suffix,len(rows))
 p=rows.iloc[0].repository_or_local_path
 if p.startswith('git:'):p=p.split(':',2)[2]
 p=ROOT/p;assert p.is_file(),p;return p
def read(stage,s):
 p=source_file(stage,s);return pd.read_csv(p,compression='gzip' if s.endswith('.gz') else None,low_memory=False)
raw=read('stage06_reproducible_sources','RAW_TARGET_RESPONSE_RECORDS.csv.gz');h=read('stage06_reproducible_sources','HISTORY_FEATURES_ALL_LOBO.csv.gz');labels=read('stage01_classification','NEW_LABELS_ALL_LOBO.csv.gz')
ST=['turn_n','short_turn_edges','near_straight_nodes_5deg','unmatched_ref_9'];ordinary=raw[raw.layer.eq('ordinary_manual')].copy();rs=[];hist=[];fits=[]
# Independent reconstruction of all feature history from eligible records, held-out building removed.
for fold,hh in h.groupby('heldout_building'):
 d=ordinary if fold=='ALL' else ordinary[ordinary.building.ne(fold)];hh=hh.set_index('worker_id');calc=pd.DataFrame(index=hh.index)
 for name,mask in [('all',pd.Series(True,index=d.index)),('hard',d.official_difficulty.eq('困难')),('easy',d.official_difficulty.eq('简单'))]:
  a=d[mask]
  for field in ST:
   s=a.dropna(subset=[field+'_peer']).groupby(['worker_id','building','image_id','reference_id'])[field+'_peer'].mean().groupby(['worker_id','building','image_id']).mean().groupby(['worker_id','building']).mean().groupby('worker_id').mean(); col='m_'+name+'_'+field;calc[col]=s
   saved=hh[col];vv=calc[col];hist.append(dict(fold=fold,column=col,missing_mismatch=int((vv.isna()!=saved.isna()).sum()),error=float((vv-saved).abs().max())))
  for col,field in [('images','image_id'),('buildings','building')]:
   s=a.groupby('worker_id')[field].nunique().reindex(hh.index).fillna(0);calc['m_'+name+'_'+col]=s;hist.append(dict(fold=fold,column='m_'+name+'_'+col,missing_mismatch=0,error=float((s-hh['m_'+name+'_'+col]).abs().max())))
 for field in ST:calc['m_hard_minus_easy_'+field]=calc['m_hard_'+field]-calc['m_easy_'+field]
 known=calc.m_all_images.ge(12)&calc.m_all_buildings.ge(3)&calc.m_easy_images.ge(5)&calc.m_easy_buildings.ge(2)&calc.m_hard_images.ge(4)&calc.m_hard_buildings.ge(2)
 for fam,fields,pca in [('REPRO_TARGET_DSTRUCT',ST,True),('V21_DSTRUCT_RAW3',ST[:3],True),('V21_DSTRUCT_FULL',ST,False)]:
  domains=[['m_all_'+x for x in fields],['m_'+st+'_'+x for st in ['hard','hard_minus_easy'] for x in fields]];cols=sum(domains,[]);good=known&calc[cols].notna().all(axis=1);g=calc[good];parts=[]
  for dom in domains:
   a=g[dom].to_numpy();scale=np.quantile(a,.85,axis=0)-np.quantile(a,.15,axis=0);sd=a.std(axis=0);scale=np.where(scale>1e-9,scale,np.where(sd>1e-9,sd,1));a=np.clip((a-np.median(a,axis=0))/scale,-3,3);a=PCA(n_components=2,svd_solver='full').fit_transform(a) if pca else a-a.mean(axis=0);parts.append(a/np.sqrt(np.mean(np.sum(a*a,axis=1)))/np.sqrt(2))
  tree=linkage(np.column_stack(parts),method='ward',optimal_ordering=True)
  for k in [2,3,4]:
   method=fam+'_K'+str(k);ll=labels[(labels.method==method)&(labels.heldout_building==fold)].set_index('worker_id');c=cut_tree(tree,n_clusters=k).ravel();fits.append(dict(method=method,fold=fold,known=len(g),eligibility_equal=good.equals(ll.known.reindex(good.index)),ARI=adjusted_rand_score(c,ll.loc[g.index,'class_id'])))
pd.DataFrame(hist).to_csv(O/'HISTORY_RECONSTRUCTION.csv',index=False);pd.DataFrame(fits).to_csv(O/'CLASSIFICATION_REFIT.csv',index=False)
print('history',len(hist),'maxerror',pd.DataFrame(hist).error.max(),'missingmismatch',pd.DataFrame(hist).missing_mismatch.sum());print('fit',len(fits),'minARI',pd.DataFrame(fits).ARI.min(),'eligibility',pd.DataFrame(fits).eligibility_equal.all())
assert pd.DataFrame(hist).error.max()<1e-9 and pd.DataFrame(hist).missing_mismatch.sum()==0
assert pd.DataFrame(fits).ARI.min()==1 and pd.DataFrame(fits).eligibility_equal.all()
# Peer features must be derived from the same target, not scored using the best target.
for field in ST:
 expected=raw[field]-raw.groupby(['image_id','reference_id','condition'],dropna=False)[field].transform('median');error=(expected-raw[field+'_peer']).abs().max();rs.append(dict(metric=field,peer_error=error));assert error<1e-9
pd.DataFrame(rs).to_csv(O/'PEER_FEATURE_CHECK.csv',index=False)
