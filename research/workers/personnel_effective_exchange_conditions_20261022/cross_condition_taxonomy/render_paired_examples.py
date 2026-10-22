#!/usr/bin/env python3
"""Actual paired raw ERP/BEV/3D views. No scores, fusion, or edit inference."""
import os
for v in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[v]='1'
import gzip,importlib.util,json,sys
from pathlib import Path
import numpy as np
import pandas as pd
from PIL import Image
from discover_cross_condition import HERE,PREVIOUS,REPO,save,js,atomic,clean,sha
sys.path.insert(0,'/tmp/hohonet_deps')

def read(path):
 with gzip.open(path,'rt') if str(path).endswith('.gz') else open(path) as f:return json.load(f)

SPECS=[
 dict(case_id='CROSS_7y13_same_Joint_class_different_scale',code='7y3sRwLe3Va-13',method='XCOND_GEOM_QT',
  workers=['W105','W119','W104'],titles=['W105：两条件4转折，范围与高度改变','W119：同一联合类，面积接近而高度摘要改变','W104：另一联合类，变化较小'],
  image='7y3sRwLe3Va_92fb09a83f8949619b9dc5bda2855456',photo_folder='originals_7y13',
  reference_case='fusion_7y13/cases/V3_7y13_positive_n12_m4.json.gz',
  title='同一人的Manual与Semi终稿：联合类中的方向与成员差异',
  note='事后解释案例；使用7y楼外联合标签。两种条件均为真实终稿，不能据此推断编辑过程。'),
 dict(case_id='CROSS_wc2_56_paired_class_counterexample',code='wc2JMjhGNzB-56',method='XCOND_PAIRED',
  workers=['W113','W130','W133'],titles=['W113：配对类X1，4→8个非共线转折','W130：同配对类X1，4→4个转折','W133：配对类X2，6对点中有1近共线点'],
  image='wc2JMjhGNzB_cae8fb3d40314ecea16654062030571b',photo_folder='originals',
  reference_case='cases/V3_RAW_wc2_56_SEMI.json.gz',
  title='成员稳定的配对类不等于每图条件响应相同：实际正反原答',
  note='事后解释案例；使用wc2楼外配对标签。可见开口涉及范围选择，新增转折不自动判错；新批缺精确初始化。')]

def main():
 spec=importlib.util.spec_from_file_location('frozen_viewer_for_cross',REPO/'research/workers/personnel_interchangeability_20261020/analysis/composition/case_visuals.py')
 v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
 font=HERE/'evidence/assets/NotoSansCJKsc-PairedSubset.ttf'
 if not font.exists():
  from fontTools.ttLib import TTFont
  from fontTools import subset
  from fontTools.varLib.instancer import instantiateVariableFont
  source=Path('/tmp/HOHONET_NotoSansCJKsc-VF.ttf')
  ff=TTFont(source);ss=subset.Subsetter()
  chars=Path(__file__).read_text()+Path(v.__file__).read_text()+''.join(chr(i) for i in range(32,128))
  ss.populate(text=chars);ss.subset(ff)
  if 'fvar' in ff:ff=instantiateVariableFont(ff,{'wght':400},inplace=True)
  font.parent.mkdir(parents=True,exist_ok=True);ff.save(font)
  license=Path('/tmp/HOHONET_NotoSansCJK_LICENSE.txt')
  if license.exists():atomic(font.parent/'FONT_LICENSE.txt',license.read_bytes())
 v._configure_font(font)
 records=read(REPO/'research/statistics/v2_evidence_audit_20261019/records.json.gz')['records']
 records={r['object_id']:r for r in records}
 paired=pd.read_csv(HERE/'PAIRED_INPUT_RECORDS.csv.gz');labels=pd.read_csv(HERE/'CROSS_LABELS_LOBO.csv.gz')
 table=[];receipts=[]
 for spec in SPECS:
  p=paired[paired.image_code_m.eq(spec['code'])&paired.worker_id.isin(spec['workers'])].set_index('worker_id')
  assert set(p.index)==set(spec['workers'])
  building=p.building_id.iloc[0];ll=labels[labels.method.eq(spec['method'])&labels.condition.eq('manual')&labels.heldout_building.eq(building)].set_index('worker_id')
  ref=read(PREVIOUS.parent/'evidence'/spec['reference_case'])['reference'];refid=ref.get('reference_id',ref.get('target_id'))
  assert p.reference_id.nunique()==1
  if refid:assert p.reference_id.iloc[0]==refid,(p.reference_id.iloc[0],refid)
  photo_path=PREVIOUS.parent/'evidence'/spec['photo_folder']/(spec['image']+'.png')
  photo=np.asarray(Image.open(photo_path).convert('RGB'));ref_geom=v.viewer_geometry(ref['points_1024x512'],ref.get('floor_xz_h'))
  data=[];geoms={}
  for w in spec['workers']:
   row=p.loc[w]
   for cond,suffix in [('manual','m'),('semi','s')]:
    oid=row['object_id_'+suffix];r=records[oid];points=r['points_1024x512'];geom=v.viewer_geometry(points);geoms[w,cond]=geom
    rec=dict(worker_id=w,condition=cond,object_id=oid,points=points,coarse_label=ll.loc[w,'coarse_label'],fine_label=ll.loc[w,'fine_label'],
     turn_n=row['turn_n_'+suffix],redundant_nodes=row['near_straight_nodes_5deg_'+suffix],pair_n=len(points)//2,
     log_area=row['log_area_'+suffix],log_height=row['log_height_'+suffix],B8L2=row['B8L2_'+suffix],D10=row['D10_'+suffix],
     source_active_time_seconds=row['source_active_time_seconds_'+suffix],time_source_kind=row['time_source_kind_'+suffix])
    data.append(rec);table.append(dict(case_id=spec['case_id'],method=spec['method'],heldout_building=building,**{k:val for k,val in rec.items() if k!='points'}))
  bounds=v._bounds([ref_geom]+list(geoms.values()));heights=v._heights([ref_geom]+list(geoms.values()))
  fig=v.plt.figure(figsize=(17.4,11.2));grid=fig.add_gridspec(3,3,height_ratios=[1.05,1.2,1.45],left=.045,right=.985,top=.88,bottom=.09,hspace=.23,wspace=.19)
  colors={'manual':'#1f77b4','semi':'#d55e00'}
  for i,w in enumerate(spec['workers']):
   ax=fig.add_subplot(grid[0,i]);v._erp_background(ax,photo)
   for cond in ['manual','semi']:
    rec=next(r for r in data if r['worker_id']==w and r['condition']==cond);v._erp_edges(ax,rec['points'],colors[cond],linewidth=1.3,alpha=.95,markers=True)
   v._erp_edges(ax,ref['points_1024x512'],v.REF_ERP_COLOR,reference=True,linewidth=1.0)
   ax.set_title(spec['titles'][i]+'\n楼外类 '+ll.loc[w,'fine_label'],fontsize=11)
   ax=fig.add_subplot(grid[1,i])
   for cond in ['manual','semi']:v._bev_ring(ax,geoms[w,cond].get('floor'),colors[cond],alpha=.9)
   v._bev_ring(ax,ref_geom.get('floor'),v.REF_COLOR,reference=True);v._style_bev(ax,bounds);ax.set_title('同一坐标尺度的底面',fontsize=10)
   ax=fig.add_subplot(grid[2,i],projection='3d')
   for cond in ['manual','semi']:v._wire3d(ax,geoms[w,cond],colors[cond])
   v._wire3d(ax,ref_geom,v.REF_COLOR,reference=True);v._style3d(ax,bounds,heights,{'elev':26,'azim':-54});ax.set_title('原答3D代理；相机高度=1',fontsize=10)
  fig.suptitle(spec['title'],fontsize=17,y=.975,x=.045,ha='left')
  fig.text(.045,.927,spec['code']+'  |  蓝色Manual、橙色Semi；黄色ERP／黑虚线为原冻结参考',fontsize=11)
  fig.text(.045,.04,spec['note']+'\n只绘制原坐标、原参考及真实Release原图；未重评分、未重融合、未改变范围资格。',fontsize=10,color='#475569')
  out=HERE/'evidence'/spec['case_id'];out.mkdir(parents=True,exist_ok=True);fp=out/'paired_raw_three_views.png';fig.savefig(fp,dpi=155,facecolor='white');v.plt.close(fig)
  payload=dict(spec,heldout_building=building,label_stage='LOBO',selection='post_result_explanatory_not_frequency_estimator',reference=ref,records=data,
   photo_source_path=str(photo_path.relative_to(REPO)),photo_sha256=sha(photo_path),shared_bev_bounds=bounds,shared_height_bounds=heights)
  atomic(out/'RAW_CASE.json.gz',gzip.compress(json.dumps(clean(payload),ensure_ascii=False,allow_nan=False).encode(),mtime=0))
  receipts.append(dict(case_id=spec['case_id'],figure=str(fp.relative_to(HERE)),figure_sha256=sha(fp),raw_case_sha256=sha(out/'RAW_CASE.json.gz'),source_image_sha256=sha(photo_path),no_point_changes=True,no_scores=True,no_fusion=True))
  print('rendered',spec['case_id'],flush=True)
 save(pd.DataFrame(table),'evidence/PAIRED_CASE_RECORDS.csv');save(pd.DataFrame(receipts),'evidence/RENDER_RECEIPTS.csv');js('evidence/VIEW_SPEC.json',SPECS)
if __name__=='__main__':main()
