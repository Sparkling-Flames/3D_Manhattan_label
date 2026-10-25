#!/usr/bin/env python3
"""Write a factual Chinese mechanism note; image semantics need researcher review."""
from pathlib import Path
import argparse,gzip,json
import numpy as np
import pandas as pd

def f(v):return '不可评' if pd.isna(v) else f'{float(v):.3f}'
def main():
 a=argparse.ArgumentParser();a.add_argument('folder',type=Path);args=a.parse_args();p=args.folder
 d=json.load(gzip.open(p/'CASE_GEOMETRY.json.gz','rt'));e=d['event'];q=pd.read_csv(p/'ABC_SCALARS.csv').set_index('role');v=pd.read_csv(p/'LOCAL_VOTE_CHANGES.csv');parts=pd.read_csv(p/'COMMON_OBSERVATION_REGROUPING.csv')
 s=[f'# {e["image"]}：{e["method"]} 严格同图大块替换',f'事件 `{e["event_id"]}`；楼外分类折为 `{e["building"]}`。此例是在完整比较之后选取的机制展示，不是独立估计总体效果。',f'总人数 n={e["n"]}，实际换人数 m={e["m"]}，比例 {e["m"]/e["n"]:.1%}；共同背景 D 为 {e["n"]-e["m"]} 人，含目标类 {e["background_target_n"]} 人。X/Y 同属源类 {e["source_class"]}，Z 属目标类 {e["target_class"]}，四块彼此不重叠。', '## 端点与比较','|指标|A 原队|B 同类替换|C 跨类替换|','|---|---:|---:|---:|']
 for k,txt in [('B8L2','Q'),('D10','D10'),('iou_2d','底面 IoU（0–1）'),('IoU3D100','三维代理（0–100）'),('S_bottom_deg','底界角误差（度）'),('dir','方向残差（度）'),('Hmean','整体高度项'),('Hcenter','局部高度项'),('omission','遗漏比例'),('extension','外扩比例'),('nodes','输出节点'),('source_time_total_seconds','来源记录总秒数')]:
  s.append('|'+txt+'|'+'|'.join(f(q.loc[r,k]) for r in ['A','B','C'])+'|')
 av,bv,cv=[q.loc[r,'B8L2']for r in ['A','B','C']]
 if all(pd.notna(v) for v in [av,bv,cv]):
  same=abs(bv-av);cross=(abs(cv-av)+abs(cv-bv))/2
  s.extend(['',f'B−A = {bv-av:+.3f}；C−A = {cv-av:+.3f}；C−B = {cv-bv:+.3f}。同类绝对变化 {same:.3f}，对称跨类绝对变化 {cross:.3f}。此单事件幅度不能替代逐图、逐楼支持率。'])
 else:s.extend(['',f'存在不可评分端点：'+ '、'.join(r+'（'+str(q.loc[r,'score_status'])+'）'for r in ['A','B','C']if pd.isna(q.loc[r,'B8L2']))+'。不以零分填入；底面等仍可用的指标单独保留。'])
 s.extend(['','## 局部票数与表达变化','下列 R 编号是冻结参考的角点序号。每队对应组均在融合完成后做角度一一分配；有票数不自动表示语义正确，匹配偏差大时必须结合原图。','|参考角点|A票/选留|B票/选留|C票/选留|A/B/C最大点对误差（度）|','|---|---|---|---|---|'])
 for r in v.to_dict('records'):
  fields=[]
  for role in ['A','B','C']:
   n=r[role+'_support'];sel=r[role+'_selected'];fields.append(('无对应组'if pd.isna(n)else str(int(n))+'/'+('选'if sel==True else'未选')))
  s.append('|R'+str(int(r['reference_corner']))+'|'+'|'.join(fields)+'|'+'/'.join(f(r[role+'_reference_pair_error_deg'])for role in ['A','B','C'])+'|')
 s.extend(['',f'三队门槛均为 {int(np.ceil(e["n"]/2))} 票。`RAW_BLOCK_SUPPORT.csv` 分别给 D/X/Y/Z 原答在参考角点的 5°/9°后验支持，`VOTES.csv` 给真实融合组的票数，两者不可混为同一票账。',''])
 for r in parts.to_dict('records'):s.append(f'- {r["from"]}→{r["to"]}：共有 {r["shared_observations"]} 个原观察；共同观察对分组发生 {r["same_observation_pairs_split"]} 次拆分、{r["same_observation_pairs_merged"]} 次合并。统计单位为观察对，不能称为换掉的人员数。')
 s.extend(['','## 图像解释记录','本段应在读取原图与叠图后补充；目前先保存可核对的几何与票数事实。不得仅因新增参考外角点就称为错误结构，也不得将参考匹配直接写成必要结构已经人工确认。','','![原图、原答、融合与票数](ABC_ERP_BEV_VOTES.png)','','![声明三维墙带](ABC_3D.png)','','## 可定位证据','精确成员见 `BLOCK_MEMBERS.csv`；完整事件和冻结点坐标见 `CASE_GEOMETRY.json.gz`；三队重放与已存端点核对见 `REPLAY_RECEIPT.json`。来源记录时间不是新测的生产耗时。'])
 render=[]
 for line in s:
  if render and line and render[-1] and not (line.startswith('|') and render[-1].startswith('|')):render.append('')
  render.append(line)
 (p/'CASE_NOTE_ZH.md').write_text('\n'.join(render)+'\n',encoding='utf-8')
if __name__=='__main__':main()
