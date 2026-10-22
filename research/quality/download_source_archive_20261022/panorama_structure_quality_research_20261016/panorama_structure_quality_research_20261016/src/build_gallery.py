from pathlib import Path
import json,html
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1]
def esc(s):return html.escape(str(s))
def svg(a,b,title):
 a=np.asarray(a)[:,[0,2]] if np.asarray(a).shape[1]==3 else np.asarray(a)
 b=np.asarray(b)[:,[0,2]] if np.asarray(b).shape[1]==3 else np.asarray(b)
 pts=np.vstack((a,b,[0,0]));lo=pts.min(axis=0);hi=pts.max(axis=0);span=np.maximum(hi-lo,.5);scale=min(470/span[0],320/span[1]);center=(lo+hi)/2
 def xy(p):return (p-center)*[scale,-scale]+[260,185]
 def path(p):
  return 'M '+' L '.join(f'{x:.3f},{y:.3f}' for x,y in xy(p))+' Z'
 body=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 520 380" role="img" aria-label="{esc(title)}"><title>{esc(title)}</title>',f'<path d="{path(b)}" fill="none" stroke="currentColor" stroke-width="2" stroke-dasharray="7 5"/>',f'<path d="{path(a)}" fill="none" stroke="currentColor" stroke-width="1.6"/>']
 for typ,p in [('A',a),('R',b)]:
  for j,(x,y) in enumerate(xy(p)):
   shape=f'<circle cx="{x:.3f}" cy="{y:.3f}" r="2.8" fill="currentColor"/>' if typ=='A' else f'<rect x="{x-3:.3f}" y="{y-3:.3f}" width="6" height="6" fill="none" stroke="currentColor"/>'
   body.append(f'<g><title>{typ}{j}: x={p[j,0]:.6f}, z={p[j,1]:.6f}</title>{shape}</g>')
 x,y=xy(np.array([0,0]));body.append(f'<path d="M {x-5},{y} h 10 M {x},{y-5} v 10" stroke="currentColor"/><text x="{x+7}" y="{y-7}" font-size="10">camera</text>')
 body.append('<text x="18" y="369" font-size="11">Solid / circles: answer. Dashed / squares: fixed reference. Units: camera height.</text></svg>')
 return ''.join(body)
g=json.loads((ROOT/'inputs/geometries30.json').read_text());r=pd.read_csv(ROOT/'results/review30_working.csv').fillna('');cards=[]
for _,q in r.iterrows():
 a,b=g[q.object_id.strip()],g[q.reference_id];plot=svg(a['bottom3d'],b['bottom3d'],q.case_id)
 if q.case_id=='N24':(ROOT/'figures/N24_geometry.svg').write_text(plot)
 text=f"原始反馈：{esc(q.grade_label)}；{esc(q.comment)}。B8L2={q.B8L2:.2f}；RCS={q.Q_RCS02:.2f}；C={q.C:.3f}；I={q.iou_2d:.3f}；D={q.dir:.3f}°。当前同参考兼容：{q.current_full_reference_geometry_same}。"
 cards.append(f'<details {"open" if q.case_id in ["N05","N10","N17","N24"] else ""}><summary>{q.case_id} · {esc(q.image_code)} · {esc(q.grade_label)}</summary><p>{text}</p>{plot}<p class="id">object_id={esc(q.object_id)}<br>reference_id={esc(q.reference_id)}</p></details>')
 current=pd.read_csv(ROOT/'results/current227_working.csv');pairs={p['object_id']:p for p in json.loads((ROOT/'inputs/current_matched_pairs.json').read_text())}
order=current.assign(delta=current.Q_RCS02-current.B8L2).sort_values('delta');chosen=pd.concat([order.head(3),order.tail(3)])
for _,q in chosen.iterrows():
 p=pairs[q.object_id];plot=svg(p['answer']['bottom3d'],p['reference']['bottom3d'],q.record_id)
 cards.append(f'<details><summary>补充 {esc(q.record_id)} · {esc(q.image_code)} · {esc(q.worker_id)}</summary><p>未新增视觉质量标签。B8L2={q.B8L2:.2f}；RCS={q.Q_RCS02:.2f}；变化={q.delta:+.2f}；C={q.C:.3f}；I={q.iou_2d:.3f}；D={q.dir:.3f}°。</p>{plot}<p class="id">{esc(q.object_id)}</p></details>')
syn=pd.read_csv(ROOT/'results/synthetic_controls.csv').set_index('case');geos=json.loads((ROOT/'inputs/synthetic_geometry_controls.json').read_text())
for p in geos:
 if p['case'] not in ['omit_bump_depth_0.01','omit_bump_depth_0.08','omit_bump_depth_0.3','wrong_bump_position','bevel_0.1','scale_1.2','rotate_10','sheared_reference_self_0.1']:continue
 q=syn.loc[p['case']];plot=svg(p['answer'],p['reference'],p['case'])
 cards.append(f'<details><summary>合成 {esc(p["case"])}</summary><p>I={q.I:.5f}；D={q.D:.5f}°；C={q.C:.5f}；边长DSC={q.length_dsc:.5f}；B={q.B8L2_arc_analogue:.2f}；RCS={q.Q_RCS02_arc_analogue:.2f}。这里的 Sb 为单独实现的球面弧长积分类比，不声称与项目采样器完全相同。</p>{plot}</details>')
page='''<!DOCTYPE html><html lang="zh-CN"><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>RCS 结构评分实验：几何证据查看</title><style>body{font:16px/1.6 system-ui,sans-serif;max-width:1000px;margin:32px auto;padding:0 20px}h1{font-size:28px}summary{font-weight:650;cursor:pointer}details{border-top:1px solid;padding:18px 0}svg{width:min(100%,650px);height:auto;display:block}p.id{font-size:12px;overflow-wrap:anywhere}aside{border:1px solid;padding:14px}a{color:inherit}</style><h1>参考相对结构评分：几何证据</h1><aside>这是原始坐标生成的俯视几何图，不是全景原图视觉审查。原图 0 张被读取；“较好／一般”等来自既有人工回执，不是本轮视觉裁决。实线为作答，虚线为事先固定参考；所有图保持两者共同坐标系，没有旋转、平移或缩放配准。显示缩放仅用于视口。悬停角点可见原坐标。</aside><p>当前工作原型 RCS-0.2-20261016。N/D 编号仅对本次 AB30 回执有效，不能与上一批同名编号混用。综合评分仍携带冻结 Sb、Hcenter；不能当作全部几何独立重测。</p>'''+''.join(cards)+'</html>'
(ROOT/'geometry_gallery.html').write_text(page,encoding='utf8')
print('Gallery cards',len(cards))
