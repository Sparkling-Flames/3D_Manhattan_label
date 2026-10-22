from pathlib import Path
import json,sys,hashlib,shutil
import numpy as np,pandas as pd
from shapely.geometry import Polygon
from geomscore import from_erp,shell,canonical
O=Path(__file__).resolve().parents[1];ROOT=O.parent;H=O/'frozen_repo'
sys.path.insert(0,str(O/'legacy'))
from structure_quality import direction_rms,old_score

def readj(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def writej(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def digest(d):return hashlib.sha256(json.dumps(d,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def full_equal(g,h):
 a=shell(g);b=shell(h)
 return a['p'].shape==b['p'].shape and np.allclose(a['p'],b['p'],rtol=0,atol=1e-7) and np.allclose(a['h'],b['h'],rtol=0,atol=1e-7)
def prism(a,r):
 p=Polygon(a['p']);q=Polygon(r['p']);ha=np.mean(a['h']);hr=np.mean(r['h']);v=p.intersection(q).area*min(ha,hr)
 return 100*v/(p.area*ha+q.area*hr-v)

def main():
 c=pd.read_csv(H/'research/descriptive_statistics_rescored_20261016/quality_records.csv').set_index('object_id',drop=False)
 refs={r['target_id']:r for r in readj(H/'research/scope_quality_rescore_20261016/reference_catalog.json')}
 fb=pd.read_csv(H/'research/quality_ab_feedback_handoff_20261015/FEEDBACK_30_JOINED.csv').set_index('object_id',drop=False)
 gg=readj(H/'research/quality_ab_feedback_handoff_20261015/geometries.json')
 ans={};sources={};conflicts=[]
 for context in readj(H/'research/same_room_quality_curves_20261015/current_common_worker_inputs.json'):
  for rec in context['records']:
   oid=rec['object_id'];g=from_erp(rec['points'])
   if oid in ans and digest(ans[oid])!=digest(g):conflicts.append(oid)
   ans[oid]=g;sources[oid]='current_common_worker_inputs.json:ERP'
   if oid in c.index:assert rec['worker']==c.loc[oid,'worker_id'] and context['image_id']==c.loc[oid,'image_id']
 for oid in fb.index:
  if oid in ans:assert full_equal(ans[oid],gg[oid]),oid
  else:ans[oid]=gg[oid];sources[oid]='geometries.json:explicit3d'
 assert not conflicts
 audit=[];meta=[];pairs=[]
 keys=['object_id','record_id','image_id','image_code','worker_id','condition','reference_id','current_target_id','use_panel','pool_source_workers','difficulty_class','doorway_status','WQ','A10','B8L2','IoU3D100','iou_2d','S_bottom_deg','dir','Hmean','Hcenter']
 for oid,ga in ans.items():
  row={'object_id':oid,'source':sources[oid]}
  if oid not in c.index:row['status']='not_current_eligible';audit.append(row);continue
  cr=c.loc[oid];rid=cr['reference_id'];ref=refs.get(rid)
  if ref is None or not ref.get('full_reference_available') or not ref.get('geometry'):row['status']='missing_reference';audit.append(row);continue
  assert cr['current_quality_eligible'] and cr['pool_analysis_eligible'] and not cr['gt_error_excluded']
  assert cr['pool_source_workers']>=3 and cr['worker_id'] not in ['W019','W026']
  assert not ref.get('image_analysis_blocked',False)
  gr=ref['geometry'];a=shell(ga);r=shell(gr);pa=Polygon(a['p']);pr=Polygon(r['p']);inter=pa.intersection(pr).area
  measure=dict(iou_2d=inter/(pa.area+pr.area-inter),Hmean=abs(a['mu']/r['mu']-1),dir=direction_rms(a['p']),IoU3D100=prism(a,r))
  errors={k:abs(v-float(cr[k])) for k,v in measure.items()};row.update({'error_'+k:v for k,v in errors.items()})
  if max(errors.values())>1e-5:row['status']='geometry_version_mismatch';audit.append(row);continue
  row['status']='current_fixed_reference_parity';audit.append(row)
  m={k:cr[k] for k in keys};m.update(source=sources[oid],case_id='',grade='',comment='',same_feedback_reference_id=False,same_feedback_reference_geometry=False)
  if oid in fb.index:
   f=fb.loc[oid];m.update(case_id=f.case_id,grade=f.grade,comment='' if pd.isna(f.comment) else f.comment,
                         same_feedback_reference_id=bool(f.reference_id==rid),same_feedback_reference_geometry=full_equal(gg[f.reference_id],gr))
  m.update(answer_sha256=digest(ga),reference_sha256=digest(gr),reference_version=ref['reference_version']);meta.append(m)
  pairs.append(dict(object_id=oid,reference_id=rid,current_target_id=cr.current_target_id,image_id=cr.image_id,condition=cr.condition,worker_id=cr.worker_id,
                    answer=ga,reference=gr,answer_sha256=m['answer_sha256'],reference_sha256=m['reference_sha256'],source=sources[oid],live_loader_verified=False))
 pd.DataFrame(audit).to_csv(O/'results/input_recovery_audit.csv',index=False);pd.DataFrame(meta).to_csv(O/'inputs/current_metadata.csv',index=False);writej(O/'inputs/current_pairs.json',pairs)
 selves=[dict(reference_id=rid,reference=refs[rid]['geometry']) for rid in sorted(set(c.reference_id)) if refs.get(rid,{}).get('geometry')]
 writej(O/'inputs/reference_self.json',selves)
 fb_a=[]
 for oid,f in fb.iterrows():
  present=oid in c.index;rr=c.loc[oid,'reference_id'] if present else None
  sameid=bool(present and rr==f.reference_id);samegeo=bool(present and rr in refs and refs[rr].get('geometry') and full_equal(gg[f.reference_id],refs[rr]['geometry']))
  fb_a.append(dict(case_id=f.case_id,object_id=oid,grade=f.grade,phase=f.phase,current_present=present,same_reference_id=sameid,same_reference_geometry=samegeo,
                   primary_grade_usable=bool(present and sameid and samegeo),old_reference_id=f.reference_id,current_reference_id=rr))
 pd.DataFrame(fb_a).to_csv(O/'results/feedback_binding_audit.csv',index=False)
 for src,dst in [('quality_ab_feedback_handoff_20261015/FEEDBACK_30_JOINED.csv','feedback30_joined.csv'),('quality_ab_feedback_handoff_20261015/quality_ab_human_review_20261015_v1.json','raw_feedback30.json')]:
  shutil.copy2(H/'research'/src,O/'inputs'/dst)
 # Formula parity on entire frozen ledgers is distinct from geometry remeasurement.
 hist=pd.read_csv(H/'research/quality_ab_feedback_handoff_20261015/prior_AB/results/SCORES_1145.csv');sc=[]
 for name,d in [('current891',c),('historical1145',hist)]:
  for ver,col in [('WQ','WQ'),('A10','A10' if 'A10' in d else 'Q_A10'),('B8L2','B8L2' if 'B8L2' in d else 'Q_B8L2')]:
   v=old_score(d.iou_2d,d.S_bottom_deg,d.dir,d.Hmean,d.Hcenter,ver);sc.append(dict(cohort=name,version=ver,n=len(d),max_error=float(np.max(abs(v-d[col])))))
 pd.DataFrame(sc).to_csv(O/'results/legacy_formula_parity.csv',index=False)
 md=pd.DataFrame(meta)
 inputs=['research/descriptive_statistics_rescored_20261016/quality_records.csv','research/scope_quality_rescore_20261016/reference_catalog.json','research/same_room_quality_curves_20261015/current_common_worker_inputs.json','research/quality_ab_feedback_handoff_20261015/geometries.json','research/quality_ab_feedback_handoff_20261015/FEEDBACK_30_JOINED.csv']
 sourcehash={p:dict(sha256=hashlib.sha256((H/p).read_bytes()).hexdigest(),bytes=(H/p).stat().st_size) for p in inputs}
 coh=dict(attachment_baseline='f16394da8ddaaded0ad5c6c26156e6194fb6b92f',live_main='d1b435ab4d7bfbb199805809be127c00e921c347',
          full_current_n=len(c),current_images=c.image_id.nunique(),recovered_n=len(pairs),recovered_images=md.image_id.nunique(),
          recovered_conditions=md.condition.value_counts().to_dict(),workers=md.worker_id.nunique(),min_pool_workers=int(md.pool_source_workers.min()),
          human_feedback_same_id_geometry=int(sum(x['primary_grade_usable'] for x in fb_a)),human_feedback_geometry_alias_inclusive=int(sum(x['same_reference_geometry'] for x in fb_a)),
          reference_self_count=len(selves),recovery_dispositions=pd.DataFrame(audit).status.value_counts().to_dict(),source_hashes=sourcehash,
          evidence_boundary='Current fixed geometry snapshots and ledger; original panoramas, LFS bytes and fresh canonical loader not acquired; no new visual GT judgement.')
 writej(O/'results/COHORT.json',coh);print(json.dumps(coh,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
