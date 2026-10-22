from round_d import *
import pandas as pd
panel=json.loads(INPUT.read_text())['images'];ims={im['code']:im for im in panel};df=pd.read_csv(OUT/'D_full_panel_metrics.csv');d=json.loads((OUT/'D_summary.json').read_text())
status={}
for im in panel:
 for r in im['annotations']+im['references']:
  try:Ring(r);status[(im['code'],r['id'])]='ok'
  except (ValueError,TypeError,KeyError) as ex:status[(im['code'],r['id'])]=str(ex)
source_status=[];ref_status=[]
for _,row in df.iterrows():
 source_status.append(status[(row.image,row.id)]);ref_status.append(status[(row.image,row.reference_id)])
df['source_ring_status']=source_status;df['reference_ring_status']=ref_status
df['angular_provenance']=['both_ok' if s=='ok' and r=='ok' else 'source_only_unavailable' if r=='ok' else 'reference_only_unavailable' if s=='ok' else 'both_unavailable' for s,r in zip(source_status,ref_status)]
df.to_csv(OUT/'D_full_panel_metrics.csv',index=False,encoding='utf-8-sig')
counts=df.groupby(['gate','reference_version','angular_provenance']).size().reset_index(name='rows');counts.to_csv(OUT/'D_coverage_by_gate_reference.csv',index=False,encoding='utf-8-sig')
# No replacement policy: keep paired original / manual-revision references and show their effect.
paired=df[df.reference_version=='original'].merge(df[df.reference_version=='manual_revision'],on=['image','building','id','gate'],suffixes=('_original','_revision'))
pr=[]
for _,r in paired.iterrows():
 row={k:r[k] for k in ['image','building','id','gate']}
 for metric in ['iou','centroid_distance_normalized','top_mae_deg','top3d_symmetric_mean_h']:
  row['original_'+metric]=r[metric+'_original'];row['revision_'+metric]=r[metric+'_revision'];row['delta_'+metric]=r[metric+'_revision']-r[metric+'_original']
 pr.append(row)
csvout('D_reference_version_deltas.csv',pr)
choices=[]
for (im,gate),group in paired.groupby(['image','gate']):
 for metric in ['iou','centroid_distance_normalized','top_mae_deg','top3d_symmetric_mean_h']:
  q=group.dropna(subset=[metric+'_original',metric+'_revision'])
  if len(q)<2:continue
  asc=metric!='iou';a=q.sort_values([metric+'_original','id'],ascending=[asc,True]).iloc[0];b=q.sort_values([metric+'_revision','id'],ascending=[asc,True]).iloc[0]
  choices.append({'image':im,'gate':gate,'metric':metric,'common_pool_n':len(q),'original_selected':a.id,'revision_selected':b.id,'changed':a.id!=b.id})
csvout('D_reference_choice_sensitivity.csv',choices)
s=pd.read_csv(OUT/'D_actual_same_floor_pairs.csv');w=pd.read_csv(OUT/'D_actual_matched_pairs.csv')
d['same_floor_3d_distinct_pairs_gt_1e_5']=int(((s.D3_a-s.D3_b).abs()>1e-5).sum());d['same_floor_3d_distinct_images']=int(s[(s.D3_a-s.D3_b).abs()>1e-5].image.nunique());d['same_floor_angular_distinct_pairs_gt_1e_5']=int(((s.U_a-s.U_b).abs()>1e-5).sum());d['same_floor_pairs_not_claimed_independent_replicates']=True
d['matched_iou_different_C_images']=int(w[w.witness_type=='matched_iou_different_centroid'].image.nunique());d['angular_provenance']=df.angular_provenance.value_counts().to_dict();d['paired_reference_rows']=len(paired);d['paired_reference_images']=int(paired.image.nunique())
d['reference_choice_change_by_metric']={metric:{'changed':int(sum(c['changed'] for c in choices if c['metric']==metric)),'eligible_image_gate_pools':sum(c['metric']==metric for c in choices)} for metric in ['iou','centroid_distance_normalized','top_mae_deg','top3d_symmetric_mean_h']}
dump('D_summary.json',d)
print(json.dumps(d,ensure_ascii=False,indent=2));print(counts.to_string(index=False))
