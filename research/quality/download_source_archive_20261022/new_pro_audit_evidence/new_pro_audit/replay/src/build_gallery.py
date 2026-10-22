"""Render supplied explicit geometry only. No original panorama or image adjudication."""
from pathlib import Path
import json,html
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from geomscore import shell
O=Path(__file__).resolve().parents[1]

def plot_pair(ga,gr,title,out,mode='bev'):
 fig=plt.figure(figsize=(8,6),layout='constrained')
 if mode=='bev':
  ax=fig.add_subplot(111)
  for g,label,ls in [(gr,'Fixed reference','-'),(ga,'Answer','--')]:
   s=shell(g);p=s['p'];q=np.vstack([p,p[0]]);ax.plot(q[:,0],q[:,1],ls,marker='o',markersize=4,label=label,linewidth=1.8)
  ax.plot([0],[0],marker='+',markersize=11,linestyle='none',label='Camera projection');ax.set_aspect('equal',adjustable='box');ax.set_xlabel('X / camera height');ax.set_ylabel('Z / camera height');ax.grid(alpha=.2)
 else:
  ax=fig.add_subplot(111,projection='3d')
  for g,label,ls in [(gr,'Fixed reference','-'),(ga,'Answer','--')]:
   b=np.array(g['bottom3d']);t=np.array(g['top3d']);b=np.vstack([b,b[0]]);t=np.vstack([t,t[0]])
   line=ax.plot(b[:,0],b[:,2],b[:,1],ls,label=label,linewidth=1.7)[0]
   ax.plot(t[:,0],t[:,2],t[:,1],ls,linewidth=1.7,color=line.get_color())
   for p,q in zip(b[:-1],t[:-1]):ax.plot([p[0],q[0]],[p[2],q[2]],[p[1],q[1]],ls,linewidth=.8,color=line.get_color())
  ax.set_xlabel('X/h');ax.set_ylabel('Z/h');ax.set_zlabel('Y/h');ax.view_init(22,-58)
  points=np.concatenate([np.array(g[k]) for g in [ga,gr] for k in ['bottom3d','top3d']]);rng=np.ptp(points,axis=0);ax.set_box_aspect([rng[0],rng[2],rng[1]])
 ax.legend(loc='best' if mode=='bev' else 'upper left');ax.set_title(title+'\nExplicit geometry reconstruction; NOT original panorama',fontsize=11)
 fig.savefig(out,dpi=150);plt.close(fig)

def main():
 pairs={p['object_id']:p for p in json.load(open(O/'inputs/current_pairs.json'))};d=pd.read_csv(O/'results/current244_scores.csv');cards=[]
 for case in ['N02','N06','N10','N12','N16','N17','N24']:
  row=d[d.case_id==case].iloc[0];p=pairs[row.object_id];scores=f'B8L2 {row.B8L2:.2f} | A {row.QA:.2f} | B {row.QB:.2f} | C {row.QC:.2f}'
  for mode in ['bev','wireframe']:plot_pair(p['answer'],p['reference'],f'{case} / {row.image_code}\n{scores}',O/f'figures/{case}_{mode}.png',mode)
  cards.append(f'<section><h2>{case}: {html.escape(row.image_code)}</h2><p>{scores}</p><p>旧人工反馈：{html.escape(str(row.grade))}；{html.escape(str(row.comment))}</p><p>夹角残差RMS {row.angle_RMS_deg:.2f}°；结构计数差异 {row.detail_loss:.3f}；粗位置辅助损失 {row.placement_loss:.3f}。</p><p>此处沿用当前固定参考，未用原图重新判定墙的必要性。</p><img src="figures/{case}_bev.png"><img src="figures/{case}_wireframe.png"><details><summary>身份与版本</summary><pre>{html.escape(json.dumps({k:p[k] for k in ["object_id","reference_id","current_target_id","answer_sha256","reference_sha256"]},ensure_ascii=False,indent=2))}</pre></details></section>')
 actual=json.load(open(O/'results/actual_same_wall_GT.json'));plot_pair(actual['equivalent_without_redundant_pair'],actual['original'],'Current reference wc2JMjhGNzB-61 / exact same-wall redundancy',O/'figures/same_wall_actual_bev.png')
 cards.append('<section><h2>真实当前参考：同墙冗余点</h2><p>wc2JMjhGNzB-61的5对点与删除同墙冗余点后的4对点，底面及墙顶轮廓相同；三方案均100。这是表示冗余，不是新作出的GT错误裁决。</p><img src="figures/same_wall_actual_bev.png"></section>')
 syn={c['name']:c for c in json.load(open(O/'inputs/synthetic_geometry.json'))}
 for name in ['micro_four_0.001','omit_bump_0.3','yaw_10','erase_deep_notch','bump_wrong_wall']:
  p=syn[name];plot_pair(p['answer'],p['reference'],f'Synthetic mechanism: {name}',O/f'figures/{name}.png');cards.append(f'<section><h2>合成控制：{name}</h2><img src="figures/{name}.png"></section>')
 body='''<!doctype html><html lang="zh"><meta charset="utf-8"><title>GQS三路线几何审计</title><style>body{font:16px/1.6 system-ui,sans-serif;max-width:1200px;margin:32px auto;padding:0 20px}section{border-top:1px solid #ccc;padding:20px 0}img{width:100%;max-width:580px;vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere}h1{line-height:1.3}</style><h1>全景布局质量：三路线几何审计</h1><p><strong>这不是原图查看器。</strong>图由明确的原始作答／固定参考3D坐标生成，未补造隐藏几何，未吸附正交，未配准。原始全景照片未取得；现有评论也不是新的盲审标签。上下环与竖线为显式墙带，不填充未知屋顶曲面。</p>'''
 text=body+''.join(cards)+'</html>'
 import re,base64
 text=re.sub(r'src="(figures/[^"]+)"',lambda m:'src="data:image/png;base64,'+base64.b64encode((O/m.group(1)).read_bytes()).decode()+'"',text)
 (O/'geometry_gallery.html').write_text(text)
if __name__=='__main__':main()
