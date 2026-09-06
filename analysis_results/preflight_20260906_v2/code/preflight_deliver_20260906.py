"""Readable summaries, bounded synthetic EM demonstration and audited case cards.
Visual notes are analyst observations, never human adjudications. No new human labels.
"""
from pathlib import Path
import sys,json,math,hashlib,shutil,urllib.request,zipfile,html
import numpy as np
import pandas as pd
from scipy.special import expit,logsumexp
ROOT=Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from tools.thesis_main.analysis.preflight_data_20260906 import load,save,OUT,SUB,sha,old
from tools.thesis_main.analysis.preflight_statistics_20260906 import moments,finite_var,modes

def summaries():
 s=pd.read_csv(OUT/'denominator_tolerance_sensitivity.csv');c=pd.read_csv(OUT/'precision_curves_k_and_fraction.csv');m=pd.read_csv(OUT/'minority_capture_curves.csv')
 mm=m[(m.distance_cutoff==.05)&m.second_mode_supported]
 first=mm[mm.second_mode_capture2>=.9].groupby('context').k.min().rename('minority_capture90_first_k')
 joint=s.merge(first,on='context',how='left');joint['minority_capture90_by20']=joint.minority_capture90_first_k<=20
 joint['medoid_hindsight_stable_by20']=joint.medoid_hindsight_first_stable_k.notna()
 joint['finite_to_empirical_iid_sd_ratio_at20']=joint.finite_sd20/joint.iid_sd20
 joint['same_number_not_same_loss']='epsilon for precision SD and medoid movement are distinct criteria; minority target is 90% capture of an empirical group'
 save('joint_three_signals.csv',joint)
 summary=joint.groupby('epsilon').agg(contexts=('N','size'),finite_pass20=('finite_pass20','sum'),iid_diagnostic_pass20=('iid_pass20','sum'),finite_only_pass20=('finite_only_pass20','sum'),late_fraction_gt80=('late_fraction_gt80','sum'),median_fraction=('finite_fraction','median'),minority_supported=('minority_capture90_first_k','count'),minority_capture90_by20=('minority_capture90_by20','sum'),medoid_hindsight_stable_by20=('medoid_hindsight_stable_by20','sum')).reset_index();save('sensitivity_one_table.csv',summary)
 st=pd.read_csv(OUT/'standardized_N20_draws.csv').groupby(['context','epsilon']).agg(standardized20_first_k_median=('first_k','median'),standardized20_q25=('first_k',lambda x:x.quantile(.25)),standardized20_q75=('first_k',lambda x:x.quantile(.75))).reset_index()
 save('standardized_N20_summary.csv',s.merge(st,on=['context','epsilon']))
 grid=[]
 for context,q in c.groupby('context'):
  for f in [.25,.5,.75,.9,1.]:
   k=max(2,math.ceil(f*q.N.iloc[0]));r=q[q.k==k].iloc[0].to_dict();r['requested_fraction']=f;grid.append(r)
 save('precision_fraction_grid.csv',grid)
 tail=c[(c.N>20)&c.k.isin([15,20])];rr=[]
 for (stage,condition),q in tail.groupby(['stage','condition']):
  for col in ['selected_medoid_to_remaining','selected_medoid_reference_distance']:
   wide=q.pivot(index=['context','building'],columns='k',values=col).dropna();delta=wide[20]-wide[15]
   b=delta.groupby(level='building').mean().values;rng=np.random.default_rng(20260906)
   draws=np.mean(rng.choice(b,(3000,len(b)),replace=True),axis=1) if len(b) else np.array([np.nan])
   rr.append(dict(stage=stage,condition=condition,metric=col,contexts=len(delta),buildings=len(b),k15_mean=wide[15].mean(),k20_mean=wide[20].mean(),difference=delta.mean(),building_equal_difference=np.mean(b),bootstrap_q025=np.quantile(draws,.025),bootstrap_q975=np.quantile(draws,.975),reference_warning='reference-relative only; public/adjudicated/unready provenance stays separate in record inventory'))
 save('rebuilt_gains_15_20.csv',rr)
 fits=[]
 for context,q in c[c.N>20].groupby('context'):
  train=q[q.k.isin([3,5,8,12])];test=q[q.k.isin([15,20])]
  for power in [.25,.5,1.,2.]:
   X=np.c_[np.ones(len(train)),train.k.to_numpy(dtype=float)**(-power)];y=train.selected_medoid_to_remaining.to_numpy();a,b=np.linalg.lstsq(X,y,rcond=None)[0]
   fits.append(dict(context=context,power=power,asymptote=a,amplitude=b,train_RMSE=np.sqrt(np.mean((X@np.array([a,b])-y)**2)),tail_RMSE=np.sqrt(np.mean((a+b*test.k.to_numpy(dtype=float)**(-power)-test.selected_medoid_to_remaining)**2)),role='unconstrained_shape_sensitivity_not_population_upper_bound'))
 save('rebuilt_asymptote_sensitivity.csv',fits)

def resources(groups):
 rr=[]
 strata=sorted({(g['stage'],g['condition']) for g in groups.values() if g['n']>=20})
 for stage,condition in strata:
  gg=[g for g in groups.values() if g['n']>=20 and (g['stage'],g['condition'])==(stage,condition)];M=len(gg)
  if M<2:continue
  between=np.var([g['D_mean'] for g in gg],ddof=1)
  for k in [3,5,10,15,20]:
   vv=np.mean([finite_var(moments(g['D']),k) for g in gg])
   for m in sorted(set([1,min(5,M),min(10,M),M])):
    a=(1/m-1/M)*between;b=vv/m
    rr.append(dict(stage=stage,condition=condition,available_scenes=M,sampled_scenes=m,workers_per_scene=k,budget=m*k,scene_variance=a,annotation_variance=b,total_RMSE=np.sqrt(a+b),target='finite_scene_average_pairwise_disagreement_independently_drawn_panels; not_per_image_layout_quality'))
 save('rebuilt_resource_grid.csv',rr)

def em_demo():
 rng=np.random.default_rng(20260906);result=[];traces=[]
 for fraction in [0.,.15]:
  for nworkers in [3,5,10,20,40]:
   for rep in range(40):
    truth=rng.integers(0,2,300);effective=truth.copy();flips=rng.choice(300,round(300*fraction),False);effective[flips]=1-effective[flips]
    actual=rng.uniform(.65,.9,nworkers);labels=np.where(rng.random((300,nworkers))<actual,effective[:,None],1-effective[:,None]);p=np.full(nworkers,.75)
    previous=None;converged=False
    for iteration in range(300):
     lp=np.log(p);lq=np.log1p(-p);L1=(labels*lp+(1-labels)*lq).sum(1);L0=((1-labels)*lp+labels*lq).sum(1)
     likelihood=np.sum(np.logaddexp(L1,L0)-np.log(2));post=expit(L1-L0)
     if previous is not None:
      assert likelihood>=previous-1e-7,'EM likelihood decreased'
      if abs(likelihood-previous)/300<1e-8:converged=True;break
     if rep==0 and nworkers==20:traces.append(dict(shared_flip_fraction=fraction,iteration=iteration,log_likelihood=likelihood,physical_truth_error=np.mean((post>=.5)!=truth)))
     previous=likelihood;p=np.clip((post[:,None]*labels+(1-post[:,None])*(1-labels)).mean(0),.5001,.9999)
    result.append(dict(shared_flip_fraction=fraction,workers=nworkers,replicate=rep,iterations=iteration+1,optimizer_converged=converged,EM_truth_error=np.mean((post>=.5)!=truth),majority_truth_error=np.mean((labels.mean(1)>=.5)!=truth),EM_effective_target_error=np.mean((post>=.5)!=effective),role='synthetic_assumption_demo_not_fitted_to_human_data_or_validated_worker_simulator'))
 save('synthetic_EM_demo.csv',result);save('synthetic_EM_objective_trace.csv',traces)
 save('synthetic_EM_summary.csv',pd.DataFrame(result).groupby(['shared_flip_fraction','workers']).agg(replicates=('replicate','size'),converged=('optimizer_converged','sum'),mean_iterations=('iterations','mean'),mean_EM_truth_error=('EM_truth_error','mean'),mean_majority_error=('majority_truth_error','mean'),mean_effective_target_error=('EM_effective_target_error','mean')).reset_index())

CASE_NOTES=[
 ('C01','B6ByNegPMKs_75327de9719945aa8b893a6404667884','P1','semi','高分歧、稳定代表与前5人低估','走道两侧及中部为玻璃隔断，磨砂部分遮住另一侧的下部结构；远处走道与近处墙体转折同时可见。','需区分真实玻璃围护、门洞和透过玻璃看到的相邻空间；不得因透明就继续扩展。','本题是corner_drift合成trap初始化，不是自然模型随机出错；本例抽取的前5份在线性墙面带度量下与初始化相同，但不据此推断注意力或盲从。','实际初始化、early5和剩余几何的差别；统计模式不自动是合理多解。'),
 ('C02','yqstnuAEVhm_26b2e92ccd314a2da1a4fc8dfc6e6f56','C1','manual','独立Manual的早期低估反例','近景可见打开的玻璃门和门框，一侧是狭长木地板走道，另一侧可见带栏杆的楼梯口及相邻门洞。','相机接近连接位置；不能只凭材质变化判断空间结束，需核实相机所在单元与门框闭合。','图中确有楼梯口，不等于当前目标一定含楼梯井。所示10角点候选有多段穿过可见墙面或门扇中部，首先需核查几何及范围错误，不能直接命名合理替代解。','near-door闭合与跨入相邻区域的差异属于范围违规、可识别性不足还是参考选择，需要人工裁定。'),
 ('C03','B6ByNegPMKs_e26e2cb761894264a4a34b1046701f6b','C1','manual','W1角点倾向的跨建筑对照A','可见不止一处墙体折返、走道延续和中央突出墙体；红色楼梯门关闭，顶部可见管线与灯具。','关闭门不授权进入门后楼梯空间；墙体折返应与设备、管线分别判断。','与C04同一工人均偏多角点，但本图参考相对距离优于同图平均；不能把多角点统称错误。','检查新增点对应真实围护折返还是点操作冗余，不能由参考距离单独判真实性。'),
 ('C04','yqstnuAEVhm_9de98503fd994452b627cdcc7a7d47b2','C1','manual','W1角点倾向的跨建筑对照B','近景有打开的玻璃门、门框和大窗；两侧连通到摆放沙发等家具的区域，窗帘和柜体局部遮挡墙角。','应依据门框和围护关系确认当前结构单元，不能依据地板或家具功能区自动切分。','与C03同人同方向的角点偏多，在此图却有更大的参考相对距离；这只是反对将复杂度直接等同质量。','需核对W1具体边界延伸位置、遮挡推断和参考版本，不作人格或能力裁决。'),
 ('C05','wc2JMjhGNzB_ec04ef10a0664e94878aa2d0f1720c2f','C1','manual','Bi差异大而这5名人工相对一致','相机位于浴室门、衣橱入口、窄窗以及两侧较大房间之间；浴室有清楚木门框和不同地面，衣橱中可见搁架。','门洞后浴室与衣橱、左右连通空间不应未经当前目标规则判断就合并。','Bi两头差异来自归档机器距离，本轮未取得双头原始几何，因此不凭该数定位Bi具体多画哪条边。','人工只有5名，不能升级为高密度总体一致；需核验当前闭合位置及Bi原始输出。'),
 ('C06','q9vSo1VnCiC_dc320b1236f741a98303db9f89bc68a2','C1','manual','人和HoHo相近但与参考不同','左侧清晰门框通向带搁架的狭长衣橱；中部桌椅遮住部分下墙，右侧可见另一门及相邻有木梁的空间。','需要分别识别近门框、衣橱内部和相邻空间的围护；家具、镜面不当作主墙。','人机接近并不能推翻参考，也不能证明共享错误；保留当前public reference来源，未自动改GT。','叠图中参考在右侧门洞附近向相邻空间更深处延展，人工代表和HoHo更靠近近端门框；这由人工最终判断为参考问题、范围偏差或几何错误。'),
 ('C07','UwV83HsGsw3_bc29294428a647038f70e0ea31ea8972','C1','manual','反例：有玻璃镜面，但人机仍较一致','浴室有透明淋浴隔断、台盆上方镜子、马桶和打开的门，门后可见办公空间。','淋浴玻璃和镜子并不自动形成新的主围护边界，开放门框可作为核实当前闭合的位置。','本图23份几何整体分歧较低且模型差异小；反对把玻璃或镜面本身当作高不确定性充分条件。','保持人工最终判断为空；低平均距离仍不证明全部细节正确。')]

def cases(rows,groups,refs):
 from PIL import Image,ImageDraw
 from lib.misc.panostretch import pano_connect_points
 review=ROOT/'analysis_results/annotation_uncertainty_prescreen_20260903_v1/human_review_export_20260905.json'
 human30={r['image_id'] for r in json.loads(review.read_text())['items']}
 images=pd.read_csv(SUB/'image_registry.csv').set_index('image_id')
 proposals=pd.read_csv(SUB/'proposal_fact.csv',keep_default_na=False)
 curves=pd.read_csv(OUT/'precision_curves_k_and_fraction.csv');fail=pd.read_csv(OUT/'early_prediction_false_reassurance.csv');profiles=pd.read_csv(OUT/'crossfit_current20_profiles.csv')
 out=OUT/'cases';out.mkdir(exist_ok=True);cards=[]
 for cid,image,stage,condition,title,visible,closure,warning,pending in CASE_NOTES:
  assert image not in human30,'do not re-review the prior human30'
  g=next(g for g in groups.values() if g['image']==image and g['stage']==stage and g['condition']==condition)
  local=ROOT/'images'/(image+'.jpg');url=images.loc[image,'image_reference']
  if not local.is_file():
   local.parent.mkdir(exist_ok=True)
   with urllib.request.urlopen(url,timeout=30) as handle:local.write_bytes(handle.read())
  original=Image.open(local).convert('RGB');original.save(out/(cid+'_original.jpg'),quality=94)
  D=g['D'];labs,order=modes(D,g['corners'],.05);med=int(D.sum(1).argmin());selected=[('Full-pool medoid',g['rows'][med]['dense'],g['rows'][med],g['rows'][med]['pairs'])]
  if len(order)>1:
   idx=np.flatnonzero(labs==order[1]);j=int(idx[D[np.ix_(idx,idx)].sum(1).argmin()]);selected.append(('Second empirical group medoid',g['rows'][j]['dense'],g['rows'][j],g['rows'][j]['pairs']))
  example=fail[(fail.image==image)&(fail.k==5)];example=example.iloc[0].to_dict() if len(example) else None
  if example:
   idx=np.array([int(x) for x in example['early_indices'].split(';')]);j=int(idx[D[np.ix_(idx,idx)].sum(1).argmin()]);selected.append(('Early-five medoid: historical subset',g['rows'][j]['dense'],g['rows'][j],g['rows'][j]['pairs']))
  late_count_record=None
  if example:
   rest=np.array([int(x) for x in example['remaining_indices'].split(';')]);rl,ro=modes(D[np.ix_(rest,rest)],g['corners'][rest],.05)
   early_counts=set(g['corners'][idx])
   for label in ro:
    ss=rest[rl==label]
    if len(ss)>=2 and g['corners'][ss[0]] not in early_counts:
     j=int(ss[D[np.ix_(ss,ss)].sum(1).argmin()]);selected.append(('Later count-different supported group',g['rows'][j]['dense'],g['rows'][j],g['rows'][j]['pairs']))
     late_count_record=dict(support=len(ss),corner_pairs=float(g['corners'][j]),workers=g['workers'][ss].tolist());break
  if cid in ('C03','C04'):
   j=list(g['workers']).index(1);selected.append(('Worker 1 cross-building comparison',g['rows'][j]['dense'],g['rows'][j],g['rows'][j]['pairs']))
  ref=refs.get(image)
  if ref:selected.append(('Reference: not assumed physical truth',old._dense_boundaries(ref['pairs']),None,ref['pairs']))
  pp=proposals[(proposals.base_task_id==image)&(proposals.stage==stage)];proposal_meta=None
  if condition=='semi' and len(pp):
   pp=pp.iloc[0];norm=old.normalize_geometry(json.loads(pp.initial_points_json))
   if norm['valid']:selected.append(('Actual historical initialization',old._dense_boundaries(norm['pairs']),None,norm['pairs']))
   proposal_meta={c:str(pp[c]) for c in ['initialization_source_kind','trap_family_set_json','source_path','source_sha256']}
   if example and norm['valid']:
    ids=np.array([int(v) for v in example['early_indices'].split(';')]);initial_dense=old._dense_boundaries(norm['pairs'])
    proposal_meta['early5_initialization_distances']=[old._d_mask(g['rows'][j]['dense'],initial_dense) for j in ids]
  hoho=None
  for folder in old.HOHO_ROOTS.values():
   hp=folder/(image+'.layout.txt')
   if hp.exists():
    points=np.loadtxt(hp);norm=old.normalize_geometry(points)
    if norm['valid']:
     hoho=old._dense_boundaries(norm['pairs']);selected.append(('Offline HoHoNet, not historical initialization',hoho,None,norm['pairs']))
    break
  panels=[];records=[]
  for title0,(top,bottom),record,pairs in selected:
   canvas=Image.new('RGB',(1024,550),'white');canvas.paste(original.resize((1024,512)),(0,38));draw=ImageDraw.Draw(canvas);draw.text((10,10),title0,fill='black')
   for field,z in [('y_ceiling',-50),('y_floor',50)]:
    points=[(float(p['x']),float(p[field])) for p in pairs]
    for j in range(len(points)):
     xy=pano_connect_points(points[j],points[(j+1)%len(points)],z=z)
     breaks=np.flatnonzero(np.abs(np.diff(xy[:,0]))>512)+1
     for part in np.split(xy,breaks):
      line=[(int(x),int(y)+38) for x,y in part if np.isfinite(x) and np.isfinite(y)]
      if len(line)>1:draw.line(line,fill='black',width=5);draw.line(line,fill='white',width=2)
    for x,y in points:draw.ellipse((x-3,y+35,x+3,y+41),fill='white',outline='black')
   panels.append(canvas)
   if record:records.append({k:record[k] for k in ['canonical_annotation_id','worker_id','raw_annotation_id','raw_export_path','raw_export_sha256','corners','reference_distance']})
  contact=Image.new('RGB',(1024,550*len(panels)),'white')
  for j,p in enumerate(panels):contact.paste(p,(0,550*j))
  contact.save(out/(cid+'_overlays.jpg'),quality=92)
  tail=curves[(curves.context==g['context'])&curves.k.between(15,20)]
  card=dict(case_id=cid,image=image,stage=stage,condition=condition,title=title,visible_evidence=visible,closure_question=closure,interpretation_warning=warning,human_adjudication='pending',human_questions=pending,image_url=url,image_sha256=sha(local),prior_human30_overlap=False,N=g['n'],pairwise_D=g['D_mean'],late_medoid_step_mean=tail.medoid_step_distance.mean() if len(tail) else None,bilayout_head_gap=g['models'][0],reference_metadata=ref,reference_file_sha256=sha(ROOT/ref['source']) if ref else None,actual_initialization=proposal_meta,selected_raw_records=records,early_failure_example=example,metric='periodic_linear_wall_band_1_minus_IoU_1024x512; display curves use repository panostretch projection, while numerical distances retain the linear proxy')
  if hoho is not None:card['human_hoho_distance_mean']=float(np.mean([old._d_mask(r['dense'],hoho) for r in g['rows']]))
  if ref and hoho is not None:card['hoho_reference_distance']=old._d_mask(hoho,old._dense_boundaries(ref['pairs']))
  if cid in ('C03','C04'):
   j=list(g['workers']).index(1);r=g['rows'][j];p=profiles[(profiles.feature=='corners')&(profiles.worker==1)&(profiles.heldout_building==g['building'])].iloc[0]
   card['worker1_pair_evidence']=dict(crossfit_corner_effect=float(p.effect),actual_corner_deviation=float(g['corners'][j]-g['corners'].mean()),reference_distance=float(g['reference'][j]),reference_distance_deviation=float(g['reference'][j]-np.nanmean(g['reference'])))
  card['later_count_different_group']=late_count_record
  cards.append(card)
 (out/'case_cards.json').write_text(json.dumps(cards,ensure_ascii=False,indent=2,default=lambda x:x.item() if isinstance(x,np.generic) else x))
 intro='前3/5份均为固定种子无放回抽取的模拟前缀，不是历史真实提交顺序；最严重案例为事后压力测试。统计选例，不是随机发生率估计；可见描述为AI初查，最终裁定全部待人工。双头Bi仅有归档距离，未伪造其叠图。白/黑线由真实角点按仓库panostretch投影连接；数值仍使用线性墙面带代理，图形与统计度量不应混为同一曲线。'
 text=['# 统计现象与图像证据案例卡',intro]
 for a in cards:
  text += [f"\n## {a['case_id']} {a['title']}",f"`{a['image']}`，{a['stage']} {a['condition']}，N={a['N']}，D={a['pairwise_D']:.6f}。",a['visible_evidence'],a['closure_question'],a['interpretation_warning'],f"人工待判：{a['human_questions']}",f"![原图]({a['case_id']}_original.jpg)",f"![真实几何叠图]({a['case_id']}_overlays.jpg)"]
 (out/'CASE_CARDS.md').write_text('\n\n'.join(text))
 h=['<!doctype html><meta charset="utf-8"><title>案例卡</title><style>body{max-width:1100px;margin:30px auto;font-family:Arial,sans-serif;line-height:1.6}img{max-width:100%}article{border-top:2px solid #999;padding:20px 0}pre{white-space:pre-wrap}</style>',f'<h1>统计现象—图像证据</h1><p>{intro}</p>']
 for a in cards:
  h.append('<article><h2>'+html.escape(a['case_id']+' '+a['title'])+'</h2><p>'+html.escape(a['image'])+'</p>')
  h.append(f"<p>{a['stage']} / {a['condition']} · N={a['N']} · D={a['pairwise_D']:.6f}</p>")
  for name in ['visible_evidence','closure_question','interpretation_warning','human_questions']:h.append('<p>'+html.escape(a[name])+'</p>')
  h.append(f'<img src="{a["case_id"]}_original.jpg"><details><summary>查看实际标注、参考及候选叠图</summary><img src="{a["case_id"]}_overlays.jpg"></details><details><summary>版本、身份和数值证据</summary><pre>'+html.escape(json.dumps({k:v for k,v in a.items() if k!='reference_metadata'},ensure_ascii=False,indent=2))+'</pre></details></article>')
 (out/'index.html').write_text('\n'.join(h))
 (out/'CASE_QA.json').write_text(json.dumps(dict(case_count=len(cards),all_originals_opened_and_visually_reviewed=True,prior_human30_overlap=0,human_adjudications_made=0,Bi_original_overlays_available=False),indent=2))

if __name__=='__main__':
 rows,groups,refs=load();summaries();resources(groups);em_demo();cases(rows,groups,refs);print('DONE deliverable computations')
