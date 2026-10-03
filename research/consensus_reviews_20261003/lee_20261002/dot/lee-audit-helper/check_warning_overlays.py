"""Validate warned pairs against independent multiplicity-layer overlay, without grid snapping."""
import json,sys,warnings
from pathlib import Path
from collections import Counter
import numpy as np,shapely
from shapely import from_wkb
from shapely.geometry import Polygon,GeometryCollection
from shapely.ops import unary_union
ROOT=Path(__file__).resolve().parent.parent
source=json.loads((ROOT/'lee-audit-original/research/lee_tile_stage1_20261002/input.json').read_text())
inputs={i['code']:{r['id']:r for r in i['annotations']} for i in source['images']}
audit=json.loads((ROOT/'lee-audit-helper/warned_operands.json').read_text())
cache={};rows=[];layer_rows=[]
def independently_count_layers(image,tag):
 key=(image,tuple(tag['members']),tag['method'])
 if key in cache:return cache[key]
 layers={};covered=GeometryCollection()
 for rid in tag['members']:
  p=Polygon(inputs[image][rid]['footprint']);new={}
  for k,g in layers.items():
   remainder=g.difference(p);overlap=g.intersection(p)
   new[k]=unary_union([new.get(k,GeometryCollection()),remainder])
   new[k+1]=unary_union([new.get(k+1,GeometryCollection()),overlap])
  new[1]=unary_union([new.get(1,GeometryCollection()),p.difference(covered)])
  layers=new;covered=unary_union([covered,p])
 n=len(tag['members'])
 selected=[g for k,g in layers.items() if (2*k>=n if tag['method']=='mv50' else 2*k>n)]
 cache[key]=unary_union(selected)
 return cache[key]
with warnings.catch_warnings(record=True) as caught:
 warnings.simplefilter('always',RuntimeWarning)
 for idx,event in enumerate(audit['events']):
  a,b=from_wkb(bytes.fromhex(event['a_wkb'])),from_wkb(bytes.fromhex(event['b_wkb']))
  area_direct=a.intersection(b).area
  area_reverse=b.intersection(a).area
  area_difference_a=a.area-a.difference(b).area
  area_difference_b=b.area-b.difference(a).area
  alternative={}
  for label,g in [('a',a),('b',b)]:
   tag=event[label+'_tag']
   if tag:
    independent=independently_count_layers(event['image'],tag)
    delta=g.symmetric_difference(independent).area
    layer_rows.append(dict(event=idx,label=label,image=event['image'],members=tag['members'],method=tag['method'],symdiff_area=delta,relative_symdiff=delta/max(1.,g.area),area_difference=abs(g.area-independent.area),independent_valid=independent.is_valid))
    alternative[label]=independent
   else: alternative[label]=g
  ai,bi=alternative['a'],alternative['b'];ix=ai.intersection(bi).area
  alt_iou=ix/(ai.area+bi.area-ix) if ai.area+bi.area-ix else 1.
  rows.append(dict(event=idx,image=event['image'],stage=event['stage'],method=event['method'],k=event['k'],direct=area_direct,reverse=area_reverse,difference_a=area_difference_a,difference_b=area_difference_b,max_intersection_delta=max(abs(v-area_direct) for v in [area_reverse,area_difference_a,area_difference_b]),source_iou=event['iou'],independent_overlay_iou=alt_iou,iou_difference=abs(alt_iou-event['iou'])))
result=dict(environment=dict(python=sys.version,numpy=np.__version__,shapely=shapely.__version__,geos=shapely.geos_version_string),operand_pairs=len(rows),independently_rebuilt_regions=len(cache),max_intersection_delta=max(x['max_intersection_delta'] for x in rows),max_overlay_symdiff_area=max(x['symdiff_area'] for x in layer_rows),max_overlay_relative_symdiff=max(x['relative_symdiff'] for x in layer_rows),max_overlay_iou_difference=max(x['iou_difference'] for x in rows),warnings=[str(w.message) for w in caught],rows=rows,layer_checks=layer_rows)
(ROOT/'lee-audit-helper/warning_overlay_checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ['rows','layer_checks','warnings']},indent=2))
