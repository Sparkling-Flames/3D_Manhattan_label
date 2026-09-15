"""Audit whether numerical geometry clusters behave like well-separated modes.
Complete-linkage always enforces a diameter limit but does not prove multimodal
density or semantically distinct explanations. Contrast fixed-partition occupancy
with re-clustering as people arrive; then test leave-one-person recovery.
"""
import collections,itertools,json
import numpy as np,pandas as pd
from sklearn.metrics import silhouette_score
from tools.thesis_main.analysis.image_portrait.convergence_v2_common import *


def run():
 d=read_responses();d=d[d.main_worker_included&d.raw_condition.isin(['manual','semi'])&d.geometry_valid];dense=boundary_map();rows=[];rec=[];bias=[]
 for (im,arm),g in d.groupby(['image_id','raw_condition']):
  g=g.sort_values('worker_id').reset_index(drop=True);n=len(g)
  if n<4:continue
  dm,pcs=pairs_for(g,dense)
  for cut in CUTS:
   full=cluster(dm,pcs,cut);groups={l:np.flatnonzero(full==l)for l in np.unique(full)};supp={l:ix for l,ix in groups.items()if len(ix)>=2}
   for a,b in itertools.combinations(supp,2):
    ia,ib=supp[a],supp[b]
    if pcs[ia[0]]!=pcs[ib[0]]:continue
    cross=dm[np.ix_(ia,ib)].ravel();ii=np.r_[ia,ib];zz=dm[np.ix_(ii,ii)];labs=np.r_[np.zeros(len(ia)),np.ones(len(ib))];sil=silhouette_score(zz,labs,metric='precomputed')
    ma=ia[np.argmin(dm[np.ix_(ia,ia)].sum(1))];mb=ib[np.argmin(dm[np.ix_(ib,ib)].sum(1))];ba=dense[g.canonical_annotation_id.iloc[ma]];bb=dense[g.canonical_annotation_id.iloc[mb]];dt=(bb-ba).astype(float)
    rows.append(dict(image_id=im,building=im.split('_')[0],condition=arm,cut=cut,n=n,point_count=int(pcs[ia[0]]),mode_a=int(a),mode_b=int(b),people_a=len(ia),people_b=len(ib),min_cross_distance=cross.min(),median_cross_distance=np.median(cross),cross_pairs_compatible_at_cut=(cross<=cut+1e-12).mean(),two_mode_silhouette=sil,medoid_a=g.canonical_annotation_id.iloc[ma],medoid_b=g.canonical_annotation_id.iloc[mb],medoid_distance=dm[ma,mb],weak_numeric_separation=bool(np.mean(cross<=cut+1e-12)>.5),physical_meaning='not adjudicated'))
    bias.append(dict(image_id=im,condition=arm,cut=cut,mode_a=int(a),mode_b=int(b),medoid_a=g.canonical_annotation_id.iloc[ma],medoid_b=g.canonical_annotation_id.iloc[mb],mean_top_delta_pixels=dt[0].mean(),mean_bottom_delta_pixels=dt[1].mean(),mean_band_width_delta_pixels=(dt[1]-dt[0]).mean(),column_fraction_top_delta_over5=(abs(dt[0])>5).mean(),column_fraction_bottom_delta_over5=(abs(dt[1])>5).mean(),delta_top_by_16sectors=json.dumps([float(z.mean())for z in np.array_split(dt[0],16)]),delta_bottom_by_16sectors=json.dumps([float(z.mean())for z in np.array_split(dt[1],16)]),interpretation='Numerical location/band changes only; cannot label physical scope without panorama review'))
   if len(supp)<2:continue
   for removed in range(n):
    ix=np.delete(np.arange(n),removed);lab=cluster(dm[np.ix_(ix,ix)],pcs[ix],cut);pools=[set(ix[lab==l])for l in np.unique(lab)]
    for l,members in supp.items():
     reference=set(members)-{removed};available=len(reference)>=2
     if not available:continue
     j=max(len(reference&p)/len(reference|p)for p in pools)
     rec.append(dict(image_id=im,building=im.split('_')[0],condition=arm,cut=cut,mode=int(l),mode_people=len(members),removed_worker=g.worker_id.iloc[removed],full_reference_members=';'.join(g.worker_id.iloc[list(members)]),Jaccard_recovery=j,recovered_exactly=j==1.,same_topology_alternative=any(k!=l and pcs[v[0]]==pcs[members[0]]for k,v in supp.items())))
 a=csv('structure/same_point_mode_separation.csv',rows);csv('structure/mode_medoid_spatial_bias.csv',bias);z=csv('structure/leave_one_person_mode_recovery.csv.gz',rec)
 if len(z):csv('structure/mode_recovery_summary.csv',z.groupby(['image_id','building','condition','cut','mode','mode_people','same_topology_alternative']).agg(removals=('removed_worker','size'),mean_Jaccard=('Jaccard_recovery','mean'),minimum_Jaccard=('Jaccard_recovery','min'),exact_recovery_fraction=('recovered_exactly','mean')).reset_index())
 lat=pd.read_csv(OUT/'process/exact_mode_discovery_curves.csv.gz');fixed=lat.groupby(['image_id','condition','cut','n','k'])[['P_seen','P_supported']].sum().reset_index();actual=pd.read_csv(OUT/'process/image_growth_curves.csv.gz');fixed=fixed.merge(actual[['image_id','condition','cut','k','n_modes','n_supported_modes']],on=['image_id','condition','cut','k'],validate='one_to_one');fixed['seen_count_difference']=fixed.n_modes-fixed.P_seen;fixed['supported_count_difference']=fixed.n_supported_modes-fixed.P_supported
 csv('process/fixed_partition_vs_reclustered_growth.csv.gz',fixed);s=fixed.groupby(['image_id','condition','cut']).agg(n=('n','max'),mean_abs_seen_count_difference=('seen_count_difference',lambda x:abs(x).mean()),mean_abs_supported_count_difference=('supported_count_difference',lambda x:abs(x).mean()),max_abs_supported_count_difference=('supported_count_difference',lambda x:abs(x).max())).reset_index();csv('structure/occupancy_vs_partition_growth_gap.csv',s)
 js('structure/partition_audit_method.json',dict(clustering='same-point complete linkage; three unmodified thresholds',limitation='A diameter-bounded partition is not proof of true multimodal geometry density or semantic ambiguity.',cross_compatibility='fraction of across-mode pairs at distance<=cut; high values flag weak separation, not automatic mode merging',leave_one='remove each distinct actual worker once; recluster; compare each surviving>=2-person full mode with best matching new cluster. Conditional recovery, not a new independent data sample.',fixed_vs_online='Exact fixed full-mode discovery compared with prefix re-clustering; differences expose partition identifiability beyond rare-mode occupancy.',spatial_deltas='derived1024-column boundary differences only; no source image viewed'))
 print('PARTITION AUDIT DONE',len(a),'same-point mode pairs')

if __name__=='__main__':run()
