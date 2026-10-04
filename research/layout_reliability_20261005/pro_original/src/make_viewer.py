"""Build an offline evidence viewer. Does not construct or choose candidates."""
from pathlib import Path
import json,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
from arc_consensus import Ring,Unsupported,TAU,W,footprint,paired_wall_proxy

def plain(x):
 if hasattr(x,'tolist'):return x.tolist()
 raise TypeError(type(x).__name__)

def main():
 references={i['image']:i['references'][0] for i in json.loads((ROOT/'evaluation/references.json').read_text())['images']}
 data=[];xs=(np.arange(2048)+.5)/2048*W
 def display_record(r):
  d=dict(r);f,A=footprint(r);d['display_footprint']=f.tolist()
  try:d['display_curves']=Ring(r).evaluate(xs/W*TAU).tolist()
  except Unsupported:d['display_curves']=None
  try:t,b=paired_wall_proxy(r);d['display_top_xyz']=t.tolist();d['display_bottom_xyz']=b.tolist()
  except Exception:d['display_top_xyz']=None;d['display_bottom_xyz']=None
  return d
 import pandas as pd
 for p in sorted((ROOT/'inputs').glob('*.json')):
  inp=json.loads(p.read_text());im=inp['image'];f=json.loads((ROOT/'results/construction'/f'{im}_exact.json').read_text())
  d=dict(image=im,records=[display_record(v) for v in inp['records']],reference=display_record(references[im]),full=f,
   domain=json.loads((ROOT/'results/construction'/f'{im}_domain.json').read_text()),
   locations=json.loads((ROOT/'results/domain_locations'/f'{im}.json').read_text()),
   lee=json.loads((ROOT/'results/construction'/f'{im}_lee.json').read_text()),variants=[])
  if f['status']=='ok_conditional_representation':
   exact=f['methods'][f['bev_mv50_complete_method']];d['variants'].append(dict(key='exact',label='精确全员（Lee ≥50%底面兼容）',record=display_record(exact),loss=None,witness=json.loads((ROOT/'results/compression'/f'{im}_exact_witnesses.json').read_text())))
   loss=pd.read_csv(ROOT/'results/compression'/f'{im}_losses.csv')
   for policy,label in [('pixel_only','原像素压缩'),('bottom_locked_mandatory_anchor','锁底＋必要起点'),('bottom_locked','锁底＋原固定起点对照')]:
    for eps in [.25,.5,1,2]:
     stem=f'{im}_{policy}_{eps:g}px';r=json.loads((ROOT/'results/compression'/(stem+'.json')).read_text())
     v=loss[(loss.policy==policy)&(loss.epsilon_px==eps)].iloc[0].to_dict();v={k:(None if isinstance(x,float) and not np.isfinite(x) else x) for k,x in v.items()}
     d['variants'].append(dict(key=stem,label=label+' '+str(eps)+'px',record=display_record(r),loss=v,witness=json.loads((ROOT/'results/compression'/(stem+'_witnesses.json')).read_text())))
  data.append(d)
 template=(ROOT/'source/viewer_template.html').read_text()
 payload=json.dumps(dict(images=data,x=xs.tolist()),ensure_ascii=False,separators=(',',':'),default=plain).replace('</','<\\/')
 (ROOT/'EVIDENCE_VIEWER_ZH.html').write_text(template.replace('__PAYLOAD__',payload),encoding='utf-8')
 print('viewer bytes',(ROOT/'EVIDENCE_VIEWER_ZH.html').stat().st_size)
if __name__=='__main__':main()
