"""Instrument unchanged official replay to retain warned geometry operands."""
import sys,json,hashlib,warnings,inspect
from pathlib import Path
import numpy as np,shapely
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'lee-audit-original'))
from tools.thesis_main.analysis import lee_tile_stage1_20261002 as lee
orig_iou,orig_tile,orig_replay=lee.region_iou,lee.tile_consensus,lee.replay_group
tags={};events=[];context={}
def tile(records):
 result=orig_tile(records)
 for method,g in result['regions'].items(): tags[g.wkb_hex]=dict(members=[r['id'] for r in records],method=method)
 return result
def replay(group,**kw):
 context.clear();context.update(image=group['code'],condition=group['condition'],gate=group['gate'])
 tags.clear()
 return orig_replay(group,**kw)
def iou(a,b):
 with warnings.catch_warnings(record=True) as caught:
  warnings.simplefilter('always',RuntimeWarning)
  value=orig_iou(a,b)
 if caught:
  caller=inspect.currentframe().f_back
  local=caller.f_locals
  if caller.f_code.co_name=='<listcomp>': stage='member_distance'; parent=caller.f_back.f_locals
  elif caller.f_lineno>=140: stage='member_distance';parent=local
  else: stage='evaluation';parent=local
  events.append(dict(**context,stage=stage,k=parent.get('k'),draw=parent.get('draw') if stage=='evaluation' else None,method=parent.get('method'),messages=[str(w.message) for w in caught],iou=value,a_area=a.area,b_area=b.area,a_valid=a.is_valid,b_valid=b.is_valid,a_type=a.geom_type,b_type=b.geom_type,a_tag=tags.get(a.wkb_hex),b_tag=tags.get(b.wkb_hex),a_wkb=a.wkb_hex,b_wkb=b.wkb_hex))
 for note in caught: warnings.warn(str(note.message),note.category,stacklevel=2)
 return value
lee.tile_consensus,lee.replay_group,lee.region_iou=tile,replay,iou
lee.plot_curves=lambda *a:None
lee.report=lambda *a:None
lee.run(ROOT/'lee-audit-original/research/lee_tile_stage1_20261002/input.json',ROOT/'lee-audit-warning-instrumented')
official=json.loads((ROOT/'lee-audit-warning-instrumented/warnings.json').read_text())
position=0
for event in events:
 bound=official[position:position+len(event['messages'])]
 assert [x['message'] for x in bound]==event['messages']
 assert all(x['image']==event['image'] for x in bound)
 event['stage']=bound[0]['stage'];event['k']=bound[0]['k'];event['method']=bound[0]['method'];event['draw']=bound[0].get('draw')
 event['warning_indices']=list(range(position,position+len(event['messages'])))
 position+=len(event['messages'])
assert position==len(official)
out=dict(environment=dict(python=sys.version,numpy=np.__version__,shapely=shapely.__version__,geos=shapely.geos_version_string),warning_records=sum(len(e['messages']) for e in events),operand_pairs=len(events),events=events)
(ROOT/'lee-audit-helper/warned_operands.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
print(json.dumps({k:v for k,v in out.items() if k!='events'},indent=2))
