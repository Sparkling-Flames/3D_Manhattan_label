"""Render selected exact replacement evidence from frozen replay JSON.

Case selection is explanatory exploration; these pictures do not estimate the
population effect. The ledgers and experiment-wide analysis provide support.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from local_study_paths import WORK,CODE_ROOT,NATIVE,TAXONOMY,MECHANISMS,BUDGET,BUDGET_CASES,BUDGET_FINAL,FIGURES,ENGINE,REPO

from pathlib import Path
import json,gzip,sys
import pandas as pd
import numpy as np
from render_case import draw,plt,v

P=MECHANISMS
BEFORE='#ec6805';AFTER='#00b5cf'
def read(name):
 p=P/(name+'_EVIDENCE.json.gz')
 if not p.exists():p=P/(name+'_REPLAY.json.gz')
 return json.load(gzip.open(p,'rt'))
def compact(t):return {k:t[k] for k in ['B8L2','D10','nodes']}|dict(points=t['geometry']['points'],footprint=t['geometry']['footprint'])

def build(prefix,removed,added,title,notes,zooms):
 data=read(prefix);views=[];rawviews=[]
 end=pd.read_csv(P/(prefix+'_ENDPOINTS.csv')).set_index(['side','phase'])
 raws=pd.read_csv(P/(prefix+'_RAW_PEOPLE.csv'))
 for side in ['a','b']:
  rows={r['phase']:r for r in data if r['side']==side};b,a=[rows[x] for x in ['before','after']]
  t0,t1=b['team'],a['team'];tb,ta=end.loc[(side,'before')],end.loc[(side,'after')]
  base=dict(image=t0['image'],image_id=t0['image_id'],photo=str(P/'photos'/(t0['image_id']+'.png')),
     reference=b['reference'],zoom=zooms[side],zoom_title='同图局部：橙替换前 / 青替换后')
  f=lambda t:f"Q {t['B8L2']:.2f} / D10 {t['D10']:.2f} / 点 {t['nodes']} / 转折 {t['fusion_turn_n']}"
  teams=[compact(t0)|dict(color=BEFORE,label='橙 · '+f(t0)),compact(t1)|dict(color=AFTER,label='青 · '+f(t1))]
  text=f"底点误差 {t0['S_bottom_deg']:.3f}→{t1['S_bottom_deg']:.3f}°\n正交方向残差 dir {t0['dir']:.3f}→{t1['dir']:.3f}°\nIoU {t0['iou_2d']:.3f}→{t1['iou_2d']:.3f}"
  views.append(base|dict(subtitle=f"{tb['class_vector']} → {ta['class_vector']}",teams=teams,component_text=text+f"\n固定参考 {t0['reference_nodes']} 节点"))
  records=[]
  for row,who,col,phase in [(b,removed,BEFORE,'before'),(a,added,AFTER,'after')]:
   r=next(z for z in row['records'] if z['worker_id']==who);cl=raws[(raws.side==side)&(raws.phase==phase)&(raws.worker_id==who)].iloc[0]['class']
   records.append(dict(worker_id=who,object_id=r['object_id'],points=r['points'],color=col,linewidth=1.7,alpha=.95,
      label=f"{'橙 · 移出' if phase=='before' else '青 · 加入'} {who}（{cl}）：原答 Q {r['B8L2']:.2f} / D10 {r['D10']:.2f}"))
  rawviews.append(base|dict(subtitle='同一实际替换块的原答',records=records,component_text='其他成员原答保持固定；\n全员 ID 与坐标见 EVIDENCE / REPLAY。'))
 case=dict(case_id=prefix+'_fusion',title=title,note=notes,views=views)
 rawcase=dict(case_id=prefix+'_raw',title=title+'｜实际替换人员原答',note='原答为正式合格作答；原始环序与参考保留。当前标签采用该建筑楼外版本。',views=rawviews)
 for c in [case,rawcase]:
  (P/(c['case_id']+'.json')).write_text(json.dumps(c,ensure_ascii=False,indent=2));print(draw(c,P/'figures'))

def g078_medians():
 prefix='G078_current_m1';d=pd.read_csv(P/(prefix+'_COORDINATE_MEDIANS.csv'));d=d[d.coordinate.eq('bottom_y')]
 end=pd.read_csv(P/(prefix+'_ENDPOINTS.csv')).set_index(['side','phase'])
 fig=plt.figure(figsize=(15,8));gs=fig.add_gridspec(2,2,width_ratios=[1.6,1],hspace=.38,wspace=.22)
 for row,side in enumerate(['a','b']):
  ax=fig.add_subplot(gs[row,0]);b=d[(d.side==side)&d.phase.eq('before')].sort_values('feature_id').reset_index(drop=True);a=d[(d.side==side)&d.phase.eq('after')].sort_values('feature_id').reset_index(drop=True)
  for i in range(4):
   delta=a.iloc[i]['median']-b.iloc[i]['median'];ax.plot([0,delta],[i,i],color=AFTER,lw=3);ax.scatter([0],[i],color=BEFORE,s=55,zorder=5);ax.scatter([delta],[i],color=AFTER,s=55,zorder=5)
   old=b.iloc[i];new=a.iloc[i];label=f"{old.lower_worker}+{old.upper_worker} → {new.lower_worker}+{new.upper_worker}\n{old['median']:.3f} → {new['median']:.3f} px"
   ax.text(.08,i,label,ha='left',va='center',fontsize=9)
  ax.axvline(0,color='#999',lw=.8);ax.set_xlim(-1.55,1.7);ax.set_ylim(3.55,-.55)
  ax.set_yticks(range(4),[f"角 {i+1}" for i in range(4)]);ax.set_xlabel('相对于替换前的底点 y 位移（px）；负值向地平线')
  ax.set_title(end.loc[(side,'before'),'image']+'：四角始终14票，门槛7',loc='left',fontsize=12)
  ax.spines[['top','right']].set_visible(False)
  bx=fig.add_subplot(gs[row,1]);bx.axis('off');bb,aa=[end.loc[(side,p)] for p in ['before','after']]
  table=[['B8L2',f'{bb.B8L2:.2f}',f'{aa.B8L2:.2f}',f'{aa.B8L2-bb.B8L2:+.2f}'],
    ['面积 / h²',f'{bb.geometry_area_h2:.2f}',f'{aa.geometry_area_h2:.2f}',f'{aa.geometry_area_h2-bb.geometry_area_h2:+.2f}'],
    ['遗漏比例',f'{bb.omission:.3f}',f'{aa.omission:.3f}',f'{aa.omission-bb.omission:+.3f}'],
    ['扩张比例',f'{bb.extension:.3f}',f'{aa.extension:.3f}',f'{aa.extension-bb.extension:+.3f}']]
  tbl=bx.table(cellText=table,colLabels=['量','替换前','替换后','变化'],cellLoc='center',loc='upper center',bbox=[0,.20,1,.66]);tbl.auto_set_font_size(False);tbl.set_fontsize(10)
  msg='02 原先内缩：同向扩张补足遗漏，Q 上升' if side=='a' else '08 原先已外扩：继续扩张增加范围误差，Q 下降'
  bx.set_title(msg,fontsize=11,loc='left');bx.text(0,.02,'相同调整方向 ≠ 相同参照质量作用',fontsize=10,color='#334155')
 fig.suptitle('G078｜坐标中位次序改变，解释同一替换块为何在两视角作用相反',fontsize=16,y=.98)
 fig.text(.5,.025,'W105（M2）→ W015（M3），n=14，固定其余13人。图中角编号仅视角内有效，不声明跨相机对应。',ha='center',fontsize=10)
 fig.subplots_adjust(top=.89,bottom=.12);path=P/'figures/G078_coordinate_medians_and_bias.png';fig.savefig(path,dpi=155);plt.close(fig);print(path)

if __name__=='__main__':
 build('G078_current_m1','W105','W015','G078｜同一人替换：两视角都扩张，质量作用相反',
   'n=14，W105（M2）→ W015（M3）；固定其他13人。四角各14票，变化来自坐标中位数，不来自结构票门槛。',
   {'a':[45,82,285,311],'b':[822,859,276,304]})
 build('G057_n18_m1','W125','W130','G057｜同一人替换：有效转折都 +2，质量分项出现不同权衡',
   'n=18，W125（M1）→ W130（M2）；门槛9。01为新增1点及既有点脱离近共线，04为新增2点。',
   {'a':[195,253,284,343],'b':[677,717,290,345]})
 g078_medians()
 if (P/'G015_current_same_class_EVIDENCE.json.gz').exists():
  build('G015_current_same_class','W104','W120','G015｜两套类别均相同，换具体成员仍出现跨视角反转',
   'n=7，W104→W120，均为结构M2、联合J3。11参考4点、19参考8点；壁炉与简化GT解释按既有裁定保留。',
   {'a':[927,965,320,352],'b':[319,364,326,366]})
