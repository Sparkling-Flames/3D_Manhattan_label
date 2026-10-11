"""Independent numerical check, preserving geometry and fixed reference.

Pre-screen only: the final thirty-case manifest may select other records.
Does not calibrate human quality or change canonical input.
"""
import argparse,csv,json,sys,hashlib
from pathlib import Path

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--bundle',type=Path,required=True);ap.add_argument('--records',nargs='*');args=ap.parse_args();root=args.bundle
 sys.path.insert(0,str(root/'frozen/scope_engine/core'))
 from quality_v11 import score_geometry
 rows=json.loads((root/'results/current_components.json').read_text());alignment={r['record_id']:r for r in json.loads((root/'results/target_alignment_ledger.json').read_text())}
 held={r['record_id'] for r in csv.DictReader(open(root/'results/room_holdout_manifest.csv',encoding='utf-8-sig')) if r['held_out_of_sample_and_future_calibration']=='True'}
 pool=[r for r in rows if alignment[r['record_id']]['target_unconfounded_conservative'] and r['record_id'] not in held]
 selected={}
 if args.records:
  wanted=set(args.records)
  for r in rows:
   if r['record_id'] in wanted:selected[r['record_id']]=r
  assert set(selected)==wanted
 else:
  for q in [50,60,75,85,90,95]:
   for side in ['lower','upper']:
    candidates=[r for r in pool if (r['Q']<q if side=='lower' else r['Q']>=q)]
    if candidates:
     r=min(candidates,key=lambda r:abs(r['Q']-q));selected[r['record_id']]=r
 geos=json.loads((root/'inputs/current_geometry_compact.json').read_text())['geometries']
 def variant(g,shift=0,reverse=False):
  out={'id':g.get('id')}
  for key in ['top3d','bottom3d']:
   ring=g[key][::-1] if reverse else g[key][:]; k=shift%len(ring);out[key]=ring[k:]+ring[:k]
  return out
 results=[]
 for r in selected.values():
  a,g=geos[r['object_id']],geos[r['reference_object_id']];scores=[]
  variants=[('original',a,g),('annotation_shift1',variant(a,1),g),('reference_shift1',a,variant(g,1)),('annotation_reverse',variant(a,reverse=True),g),('reference_reverse',a,variant(g,reverse=True)),('both_shift_reverse',variant(a,1,True),variant(g,1,True))]
  for name,aa,gg in variants:
   out=score_geometry(aa,gg,spherical_samples=2048,height_samples=4096);assert out['status']=='available',(r['record_id'],name,out['reason_codes']);scores.append({'variant':name,'Q':out['quality_score']})
  base=scores[0]['Q'];assert abs(base-r['Q'])<1e-9
  low,high=min(s['Q'] for s in scores),max(s['Q'] for s in scores)
  results.append({'record_id':r['record_id'],'object_id':r['object_id'],'image_code':r['image_code'],'reference_object_id':r['reference_object_id'],'scores':scores,'Q_range':high-low,'max_abs_delta':max(abs(s['Q']-base) for s in scores),'crossed_test_boundaries':[q for q in [50,60,75,85,90,95] if low<q<=high],'geometry_changed':False})
 summary={'purpose':'boundary representation sensitivity; not human validation','spherical_samples':2048,'height_samples':4096,'records':len(results),'variants_per_record':6,'max_Q_range':max(r['Q_range'] for r in results),'crossing_record_count':sum(bool(r['crossed_test_boundaries']) for r in results),'results':results}
 dest=Path(__file__).with_name('boundary_representation_selected.json' if args.records else 'boundary_representation_prescreen.json');dest.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in summary.items() if k!='results'},ensure_ascii=False))
if __name__=='__main__':main()
