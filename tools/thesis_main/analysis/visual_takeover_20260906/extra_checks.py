"""Additional support, representation and fixed-membership checks; not new clustering."""
import json
from itertools import combinations
import numpy as np
import pandas as pd
import measure as m
import footprint as f

def run():
 O=m.O;P=m.P
 a,images,parts,members,versions,models,refs,raw,norm=m.load()
 bc=pd.read_csv(O/'analysis/context_metrics.csv');fc=pd.read_csv(O/'analysis/footprint_contexts.csv')
 ext=parts[parts.version=='extended73'][['context_key','cluster_count','partition_status']]
 joined=bc[['context_key','raw_count','projected_count','bi_gap','d_projected','d_linear','d_solid','initialization_source_kind']].merge(fc,on=['context_key','raw_count'],validate='one_to_one').merge(ext,on='context_key',validate='one_to_one')
 joined['band_coverage']=joined.projected_count/joined.raw_count;joined['floor_coverage']=joined.floor_count/joined.raw_count
 rows=[]
 for no_synthetic in [False,True]:
  base=joined[joined.initialization_source_kind!='trap_synthetic_disjoint_source'] if no_synthetic else joined
  for min_n in [2,5,10]:
   for min_fraction in [0,.5,.8]:
    z=base[(base.projected_count>=min_n)&(base.floor_count>=min_n)&(base.band_coverage>=min_fraction)&(base.floor_coverage>=min_fraction)].dropna(subset=['bi_gap','bi_floor_gap','d_projected','d_human_floor'])
    rows.append(dict(without_synthetic=no_synthetic,min_responses=min_n,min_coverage=min_fraction,contexts=len(z),buildings=z.building_id.nunique(),band_rho=m.rho(z.bi_gap,z.d_projected),floor_rho=m.rho(z.bi_floor_gap,z.d_human_floor),scope='same_contexts_but_metric_specific_response_support'))
 m.save('analysis/metric_support_sensitivity.csv',rows)
 m.save('analysis/coverage_association.csv',[dict(metric='projected_band',contexts=len(joined),rho_model_gap_usable_fraction=m.rho(joined.bi_gap,joined.band_coverage)),dict(metric='floor',contexts=len(joined),rho_model_gap_usable_fraction=m.rho(joined.bi_floor_gap,joined.floor_coverage))])
 bp=pd.read_csv(O/'analysis/pair_distances.csv.gz');fp=pd.read_csv(O/'analysis/footprint_pairs.csv.gz');same=bp.merge(fp,on=['context_key','left','right'],validate='one_to_one');q=same.groupby('context_key').agg(n_same_pairs=('left','size'),projected_same=('d_projected','mean'),linear_same=('d_linear','mean'),solid_same=('d_solid','mean'),floor_same=('d_floor','mean')).reset_index().merge(joined[['context_key','bi_gap','bi_floor_gap','building_id','stage','condition','initialization_source_kind']],on='context_key')
 m.save('analysis/exact_same_pairs_metric_comparison.csv',q)
 m.save('analysis/exact_same_pairs_summary.csv',[dict(scope=scope,contexts=len(g),buildings=g.building_id.nunique(),pairs=g.n_same_pairs.sum(),band_rho=m.rho(g.bi_gap,g.projected_same),floor_rho=m.rho(g.bi_floor_gap,g.floor_same),rho_linear_projected=m.rho(g.linear_same,g.projected_same)) for scope,g in [('all',q),('without_synthetic',q[q.initialization_source_kind!='trap_synthetic_disjoint_source'])]])
 census=pd.read_csv(O/'census/images_380_enriched.csv',keep_default_na=False);eq=m.read(P/'models/dual_equality_checks.csv')[['image_id','comparison_status','raw_sequence_equal','ordered_cycle_equal']]
 census=census.merge(eq,on='image_id',validate='one_to_one');census['head_equality_status']=np.where(census.comparison_status=='comparable',np.where(census.raw_sequence_equal.map(m.yes),'same_original_coordinates','different_original_coordinates'),'not_evaluable_source_geometry');m.save('census/images_380_final.csv',census)
 by={i:{} for i in images.image_id};poly={}
 for r in models:
  if r['source_role']=='offline_dual_prediction':by[r['image_id']][r['head']]=r
  try:poly[r['layout_id']]=f.footprint(r['points_1024x512'])
  except (ValueError,IndexError,TypeError):pass
 nesting=[]
 for i,heads in by.items():
  er=heads.get('enclosed',{});xr=heads.get('extended',{});e=poly.get(er.get('layout_id'));x=poly.get(xr.get('layout_id'))
  if e is None or x is None:nesting.append(dict(image_id=i,status='not_comparable_original_cycle'));continue
  outside=e.difference(x).area;nesting.append(dict(image_id=i,status='comparable',enclosed_area=e.area,extended_area=x.area,enclosed_fraction_outside_extended=outside/e.area,extended_fraction_outside_enclosed=x.difference(e).area/x.area,extended_area_smaller=x.area<e.area-1e-8,geometric_subset=outside/e.area<1e-6,semantic_scope_adjudicated=False))
 m.save('analysis/head_nesting_diagnostic.csv',nesting)
 for k,v in norm.items():
  try:poly[k]=f.footprint(v)
  except (ValueError,IndexError,TypeError):pass
 composition=[]
 for p in parts[parts.version=='extended73'].to_dict('records'):
  mm=members[members.partition_id==p['partition_id']];memmap={r.canonical_annotation_id:r.cluster_id for r in mm.itertuples() if r.canonical_annotation_id in poly};within=[];between=[]
  for i,j in combinations(sorted(memmap),2):
   d=f.d(poly[i],poly[j]);(within if memmap[i]==memmap[j] else between).append(d)
  composition.append(dict(context_key=p['context_key'],image_id=p['image_id'],members=len(memmap),clusters=len(set(memmap.values())),within_pairs=len(within),between_pairs=len(between),within_distance=np.mean(within) if within else np.nan,between_distance=np.mean(between) if between else np.nan,scope='archived_clusters_geometric_separation_is_not_independent_validation'))
 m.save('analysis/fixed_cluster_within_between.csv',composition)
 cl=pd.read_csv(O/'analysis/footprint_cluster_proximity.csv');cover=[]
 for min_support in [1,2,3]:
  z=cl[(cl.original_support>=min_support)&(cl.floor_support>0)].dropna(subset=['medoid_floor_E','medoid_floor_X'])
  for radius in [.025,.05,.1,.2]:
   e=z.medoid_floor_E<=radius;x=z.medoid_floor_X<=radius;cover.append(dict(min_original_support=min_support,radius=radius,clusters=len(z),both_close=int((e&x).sum()),neither_close=int((~e&~x).sum()),E_only=int((e&~x).sum()),X_only=int((~e&x).sum()),semantic_labels_assigned=False))
 m.save('analysis/floor_template_radius_sensitivity.csv',cover)
 status=members.mapping_status.value_counts().to_dict();rawonly=members[members.mapping_status=='raw_version_only'];rv={r['raw_annotation_version_id']:r for r in versions}
 checks=[dict(raw_annotation_version_id=r.raw_annotation_version_id,present=r.raw_annotation_version_id in rv,canonical_geometry_substituted=False) for r in rawonly.itertuples()]
 m.dump('EXTRA_QA.json',dict(census_images=len(census),room_instance_known=int((census.room_instance_id!='').sum()),mapping_status=status,raw_only_checks=checks,duplicate_context_worker=int(a.duplicated(['context_key','worker_id']).sum()),exact_same_pairs=len(same),decisions_changed=False))
 print('additional support checks complete',len(same))
if __name__=='__main__':run()
