"""Density counterexample, NA provenance and public API guards."""
import audit
from audit import *
evaluate=None

def direct_project(points):
 out=[]
 for x,y,z in points:
  out.append([((math.atan2(x,-z)/(2*math.pi)+.5)*1024)%1024,(.5-math.atan2(y,math.hypot(x,z))/math.pi)*512])
 return out

def density():
 im=next(i for i in read(ROOT/'inputs/panel.json')['images'] if i['code']=='2t7WUuJeko7-09');a=next(a for a in im['annotations'] if a['id']=='R00016');t,f=reconstruct(a);edge=max(range(len(f)),key=lambda j:np.linalg.norm(f[(j+1)%len(f)]-f[j]));fit_a=target.project_existing(a);out=[]
 for count in [2,8]:
  T=[];F=[]
  for j in range(len(f)):
   T.append(t[j]);F.append(f[j])
   if j==edge:
    for k in range(1,count+1):
     alpha=k/(count+1);T.append((1-alpha)*t[j]+alpha*t[(j+1)%len(f)]);F.append((1-alpha)*f[j]+alpha*f[(j+1)%len(f)])
  dense={'id':'independent_dense_'+str(count),'points':[p for pair in zip(direct_project(T),direct_project(F)) for p in pair]}
  metric=target.compare(dense,a);fit=target.project_existing(dense);proj=target.compare(fit['record'],fit_a['record']);at,af=reconstruct(fit_a['record']);bt,bf=reconstruct(fit['record'])
  out.append({'source_id':a['id'],'edge_index':edge,'source_pairs':len(f),'dense_pairs':len(F),'original_iou':metric['iou'],'original_top3d':independent_curve(np.array(T),t),'original_floor3d':independent_curve(np.array(F),f),'original_flat_rms_deg':target.intrinsic(a)['flat_top_angular_rms_deg'],'dense_flat_rms_deg':target.intrinsic(dense)['flat_top_angular_rms_deg'],'fit_status':[fit_a['status'],fit['status']],'fitted_iou':proj['iou'],'fitted_top_mae_deg':proj['top_mae_deg'],'fitted_bottom_mae_deg':proj['bottom_mae_deg'],'fitted_top3d_oracle_h':independent_curve(at,bt),'fitted_floor3d_oracle_h':independent_curve(af,bf)})
 save('density_counterexample.json',out);return out

def na_provenance():
 ims={i['code']:i for i in read(ROOT/'inputs/panel.json')['images']};objects={(i['image'],i['id']):i['record'] for i in read(ROOT/'results/objects.json')};m=pd.read_csv(ROOT/'results/metrics.csv');out=[]
 for _,r in m.iterrows():
  a=objects[(r.image,r.id)];g=next(x for x in ims[r.image]['references'] if x['id']==r.reference_id);d={'image':r.image,'id':r.id,'reference_id':r.reference_id,'panel':r.panel,'kind':r.kind,'saved_longitude_status':str(r.longitude_status)}
  for name,record in [('source',a),('reference',g)]:
   try:target.Ring(record);d[name+'_ring']='ok'
   except Exception as e:d[name+'_ring']=str(e)
  out.append(d)
 df=pd.DataFrame(out);df.to_csv(HERE/'na_provenance.csv',index=False)
 s=pd.read_csv(ROOT/'results/correction_metrics.csv');q=s[(s.panel=='broad')&(s.alpha==1)&(s.version=='original')&(s.status=='ok')];q=q.merge(df.rename(columns={'id':'source_id'}),on=['image','source_id','reference_id'],suffixes=('','_provenance'));q.to_csv(HERE/'broad_projection_na_provenance.csv',index=False)
 groups=lambda d:d.groupby(['source_ring','reference_ring']).size().reset_index(name='n').to_dict('records')
 result={'all_comparison_ring_reasons':groups(df),'broad_101_success_ring_reasons':groups(q),'broad_101_source_eligibility':q.source_eligible.value_counts().to_dict(),'broad_101_quality_gate':q.source_quality_gate.value_counts().to_dict(),'broad_failed_records':s[(s.panel=='broad')&(s.status!='ok')][['image','source_id','reason']].to_dict('records')}
 save('na_provenance_summary.json',result);return result

def api_guard():
 ims=read(ROOT/'inputs/panel.json')['images'];im=next(i for i in ims if i['code']=='2t7WUuJeko7-09');a=next(a for a in im['annotations'] if a['id']=='R00016');g=im['references'];context={'target_compatibility':'confirmed_same_target','reference_usable':True}
 import copy
 bad=copy.deepcopy(a);bad['points'][1][1]=256
 z=evaluate(bad,g,context,.5);empty=evaluate(a,[],context,.5)
 result={'invalid_floor_example':{'intrinsic':z['intrinsic_conditional_geometry'],'reference_agreement':z['reference_agreement'],'reference_cost_comparable_with_same_context':z['reference_cost_comparable_with_same_context'],'overall_state':z['overall_state']},'empty_reference_example':{'reference_agreement':empty['reference_agreement'],'reference_cost_comparable_with_same_context':empty['reference_cost_comparable_with_same_context'],'overall_state':empty['overall_state']}}
 save('api_guard_counterexamples.json',result);return result
if __name__=='__main__':
 checks={'density':density,'na':na_provenance,'api':api_guard}
 args=parse_config(__doc__,list(checks));audit.configure(args)
 ROOT,SOURCE,OFFICIAL,target=audit.ROOT,audit.SOURCE,audit.OFFICIAL,audit.target
 from evaluator import evaluate
 for name,f in checks.items():
  if 'all' in args.checks or name in args.checks:print(f.__name__,json.dumps(f(),ensure_ascii=False,indent=2),flush=True)
