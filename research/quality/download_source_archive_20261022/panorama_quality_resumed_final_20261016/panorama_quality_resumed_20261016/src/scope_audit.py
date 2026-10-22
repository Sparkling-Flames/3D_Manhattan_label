from pathlib import Path
import json,sys
import numpy as np,pandas as pd
from shapely.geometry import Polygon,Point,LineString
from envelope_quality import normalized_pair,shell
import recompute_baseline as base
ROOT=Path(__file__).resolve().parents[1]

def main():
 base.initialize();pairs=json.loads((ROOT/'inputs/fixed_pairs.json').read_text());refs=pd.read_csv(ROOT/'inputs/reference_catalog.csv');rows=[];refsummary={}
 for p in pairs:
  if not p['introduced_scope_edges']:continue
  n=normalized_pair(p['answer'],p['reference'],detail=True);g=p['reference'];bp=np.array(g['bottom3d'])[:,[0,2]];edges=np.roll(bp,-1,axis=0)-bp
  sample=np.array(n['GA']['points']);w=np.array(n['GA']['sample_weights']);credit=np.array(n['GA']['credit']);position=np.array(n['GA']['position_credit'])
  diff=sample[:,None,:]-bp[None,:,:];u=np.clip((diff*edges).sum(-1)/(edges*edges).sum(-1),0,1);d2=((diff-u[:,:,None]*edges)**2).sum(-1);ties=d2<=d2.min(-1)[:,None]+1e-18
  flags=np.isin(np.arange(len(bp)),p['introduced_scope_edges']);cut=(ties&flags).any(1)&~(ties&~flags).any(1);inherited=(ties&~flags).any(1)&~(ties&flags).any(1);amb=~(cut|inherited)
  row={k:p[k] for k in ['object_id','record_id','image_id','image_code','reference_id','physical_wall_asserted']}
  row.update(EBC2_sum=n['score'],EBC2_L2=n['score_l2'],I=n['I'],boundary_coverage=n['boundary_coverage'],cut_length_h=float(w@cut),inherited_length_h=float(w@inherited),transition_tie_length_h=float(w@amb),cut_mismatch_length_h=float(w@(cut*(1-credit))),inherited_mismatch_length_h=float(w@(inherited*(1-credit))),cut_position_mismatch_h=float(w@(cut*(1-position))),reference_length_h=float(w.sum()))
  rows.append(row)
  if p['reference_id'] not in refsummary:
   s=shell(g);refsummary[p['reference_id']]=dict(reference_id=p['reference_id'],image_id=p['image_id'],image_code=p['image_code'],saved_vertices=len(bp),computational_vertices=len(s['p']),introduced_scope_edges_original=p['introduced_scope_edges'],vertex_sources=p['vertex_sources'],physical_wall_asserted=p['physical_wall_asserted'],edge_roles='introduced protocol closure vs inherited source boundary; inherited is not a new physical-wall assertion',self_score=normalized_pair(g,g)['score'])
 pd.DataFrame(rows).to_csv(ROOT/'results/crop_boundary_components.csv',index=False)
 (ROOT/'results/crop_reference_provenance.json').write_text(json.dumps(list(refsummary.values()),ensure_ascii=False,indent=2))
 # New targets remain non-evaluable: inspect their explicitly labelled previews
 # geometrically without converting the previews into scoring references.
 new=[];preview_geoms=[]
 for item in json.loads((ROOT/'inputs/v6_new_scope_references.json').read_text()):
  rec=item['reference'];sources=refs[(refs.image_id==rec['image_id'])&(refs.role=='selected_gt')];assert len(sources)==1
  old=sources.iloc[0];oldg=base.engine.geometry(json.loads(old.points_1024x512));preview=base.engine.geometry(item['display_points']);target=Polygon(np.array(preview['bottom3d'])[:,[0,2]]);source=Polygon(np.array(oldg['bottom3d'])[:,[0,2]])
  outside=target.difference(source);bl=target.exterior.length;bd=[target.exterior.interpolate(t) for t in np.linspace(0,bl,10001)]
  dmax=max(p.distance(source) for p in bd)
  cons=rec['evidence']['constructions'][0]['source_plane'];camera=cons['cameraHeight'];raw=cons['source_json_geometry']['layoutPoints']['points'];xyz=np.array([p['xyz'] for p in raw]);rawp=Polygon(xyz[:,[0,2]]/camera)
  buffered={str(eps):target.difference(source.buffer(eps)).area for eps in [0,1e-6,1e-5,1e-4,1e-3]}
  new.append(dict(image_id=rec['image_id'],image_code=rec['image_code'],target_id=rec['target_id'],full_reference_available=rec['full_reference_available'],display_status=item['display_status'],source_reference_id=old.target_id,outside_source_area_h2=float(outside.area),recorded_outside_source_area_h2=rec['outside_source_area_h2'],target_area_h2=target.area,outside_target_fraction=outside.area/target.area,max_sampled_outside_distance_h=dmax,source_camera_height_m=camera,max_sampled_outside_distance_mm_if_source_metric_scale_trusted=dmax*camera*1000,source_json_floor_outside_area_h2=target.difference(rawp).area,outside_after_buffer_h=buffered,source_json_ceiling_plane=cons['plane'],conclusion='precision-scale protrusion is compatible with boundary rounding/conversion; it is NOT approval to extrapolate a reference. Explicit target/source reconciliation and full-reference admission still required. No score emitted.'))
  preview_geoms.append(dict(image_id=rec['image_id'],image_code=rec['image_code'],old_source_reference=oldg,preview_geometry=preview,preview_role='unapproved source-ceiling-extrapolation display only; never a scoring reference'))
 (ROOT/'results/new_targets_precision_audit.json').write_text(json.dumps(new,ensure_ascii=False,indent=2));(ROOT/'inputs/new_target_preview_geometry_DIAGNOSTIC_ONLY.json').write_text(json.dumps(preview_geoms,ensure_ascii=False))
 summary=dict(scored_crop_answers=len(rows),crop_reference_count=len(refsummary),new_targets_not_scored=len(new),all_target_closure_edges_retained=True,physical_wall_score_not_claimed=True)
 (ROOT/'results/scope_audit_summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2));print(json.dumps(new,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
