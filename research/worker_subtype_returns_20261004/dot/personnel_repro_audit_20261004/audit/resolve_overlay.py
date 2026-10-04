"""Diagnose an auditor comparator failure without changing any source geometry."""
import sys,json,itertools,warnings,platform,os,argparse
from pathlib import Path
from decimal import Decimal,localcontext
import numpy as np
import shapely
from shapely.geometry import Polygon,Point,mapping
from shapely.ops import unary_union
parser=argparse.ArgumentParser();parser.add_argument('--bundle',type=Path,default=Path(__file__).resolve().parents[1]/'author_bundle');parser.add_argument('--out',type=Path,default=Path(__file__).resolve().parent);args=parser.parse_args()
p=args.bundle;out=args.out;out.mkdir(parents=True,exist_ok=True);sys.path.insert(0,str(p/'src'))
from finite_pool import make_basis
D=json.loads((p/'inputs/rpc_geometry.json').read_text());rr=sorted(D['records'],key=lambda r:r['worker']);SS=list(range(6));pp=[Polygon(r['footprint']) for r in rr];g=Polygon(D['reference']['footprint']);b=make_basis(rr,D['reference']);tile=unary_union([t for t,m in zip(b.tiles,b.subset(SS,'mv50')) if m]);P=Point(.35790104492516644,.48718312274104003)
R=dict(environment=dict(python=platform.python_version(),numpy=np.__version__,shapely=shapely.__version__,geos=shapely.geos_version_string),image=D['image'],indices=SS,workers=[rr[i]['worker'] for i in SS],record_ids=[rr[i]['id'] for i in SS],reference_id=D['reference']['id'],threshold=3,source_inputs_unchanged=True)
R['validity']=[dict(worker=rr[i]['worker'],valid=pp[i].is_valid,reason=shapely.is_valid_reason(pp[i]),covers=pp[i].covers(P),contains=pp[i].contains(P),distance_to_boundary=pp[i].boundary.distance(P)) for i in SS]
# Ray crossing with 70 decimal digits from actual binary float inputs. Confirms no boundary ambiguity.
def inside_decimal(points,pt):
 with localcontext() as ctx:
  ctx.prec=70;x,y=map(Decimal.from_float,pt);v=[tuple(Decimal.from_float(c) for c in q) for q in points];inside=False
  for (x1,y1),(x2,y2) in zip(v,v[1:]+v[:1]):
   if (y1>y)!=(y2>y) and x<(x2-x1)*(y-y1)/(y2-y1)+x1:inside=not inside
  return inside
R['decimal70_point_votes']=[dict(worker=rr[i]['worker'],inside=inside_decimal(rr[i]['footprint'],(P.x,P.y))) for i in SS]
R['triple_orders']=[]
triple=[1,2,4]
with warnings.catch_warnings(record=True) as ww:
 warnings.simplefilter('always')
 for ids in itertools.permutations(triple):
  first=pp[ids[0]].intersection(pp[ids[1]]);xx=first.intersection(pp[ids[2]])
  R['triple_orders'].append(dict(workers=[rr[i]['worker'] for i in ids],first_area=first.area,first_contains_probe=first.contains(P),triple_area=xx.area,triple_contains_probe=xx.contains(P),valid=xx.is_valid))
 R['consensus_orders']=[];R['union_orders']=[]
 outputs={}
 for mode in ['forward','reverse','rotate1','rotate2']:
  pieces=[]
  for ids in itertools.combinations(SS,3):
   ids=list(ids)
   if mode=='reverse':ids.reverse()
   if mode=='rotate1':ids=ids[1:]+ids[:1]
   if mode=='rotate2':ids=ids[2:]+ids[:2]
   pieces.append(pp[ids[0]].intersection(pp[ids[1]]).intersection(pp[ids[2]]))
  x=unary_union(pieces);outputs[mode]=x
  if mode=='forward':
   for ordering in ['forward','reverse']:
    ps=pieces if ordering=='forward' else pieces[::-1];seq=ps[0]
    for piece in ps[1:]:seq=seq.union(piece)
    R['union_orders'].append(dict(order=ordering,operation='sequential binary union',iou=seq.intersection(g).area/seq.union(g).area,versus_full_tile_symdiff=seq.symmetric_difference(tile).area))
   R['union_preservation']=dict(any_input_contains_probe=any(piece.contains(P) for piece in pieces),unary_union_contains_probe=x.contains(P))
  R['consensus_orders'].append(dict(order=mode,iou=x.intersection(g).area/x.union(g).area,area=x.area,versus_full_tile_symdiff=x.symmetric_difference(tile).area,valid=x.is_valid))
 R['precision_grid_diagnostics']=[]
 for grid in [1e-12,1e-10,1e-9,1e-8]:
  pieces=[]
  for ids in itertools.combinations(SS,3):pieces.append(shapely.intersection(shapely.intersection(pp[ids[0]],pp[ids[1]],grid_size=grid),pp[ids[2]],grid_size=grid))
  x=shapely.union_all(pieces,grid_size=grid)
  R['precision_grid_diagnostics'].append(dict(grid_size=grid,diagnostic_only=True,iou=x.intersection(g).area/x.union(g).area,versus_unmodified_tile_symdiff=x.symmetric_difference(tile).area))
 R['warnings']=[str(w.message) for w in ww]
R['full_tile']=dict(iou=b.iou(b.subset(SS,'mv50')),area=tile.area,valid=tile.is_valid)
bb=make_basis([rr[i] for i in SS],D['reference']);sub=unary_union([t for t,m in zip(bb.tiles,bb.subset(range(6),'mv50')) if m]);R['six_only_tile']=dict(iou=bb.iou(bb.subset(range(6),'mv50')),area=sub.area,versus_full_tile_symdiff=sub.symmetric_difference(tile).area)
# Drop in erroneous comparator is contained by exactly the required 3 voters except tiny boundaries.
diff=tile.symmetric_difference(outputs['forward']);R['lost_region']=dict(area=diff.area,probe=[P.x,P.y],forward_covers_probe=outputs['forward'].covers(P),tile_covers_probe=tile.covers(P),all_three_overlap_area=pp[1].intersection(pp[4]).intersection(pp[2]).intersection(diff).area,missing_from_tile_but_in_forward=outputs['forward'].difference(tile).area)
R['resolution']='Auditor direct-comparator forward-intersection-order unary_union loses a positive-area region. Full-pool author tile, fresh six-person tile, three alternative direct operation orders and 70-digit probe votes agree. No source repair or production precision change applied. Not an observed author numerical error.'
(out/'overlay_resolution.json').write_text(json.dumps(R,ensure_ascii=False,indent=2)+'\n')
features=[dict(type='Feature',properties=dict(kind='annotation',id=rr[i]['id'],worker=rr[i]['worker']),geometry=mapping(pp[i])) for i in SS]
features += [dict(type='Feature',properties=dict(kind=kind),geometry=mapping(geom)) for kind,geom in [('reference',g),('author_full_pool_tile',tile),('six_person_tile',sub),('direct_forward',outputs['forward']),('direct_reverse',outputs['reverse']),('difference',diff)]]
(out/'overlay_failure_fixture.geojson').write_text(json.dumps(dict(type='FeatureCollection',features=features),ensure_ascii=False)+'\n')
(out/'overlay_failure_fixture.json').write_text(json.dumps(dict(image=D['image'],records=[rr[i] for i in SS],reference=D['reference'],threshold=3,probe=[P.x,P.y]),ensure_ascii=False,indent=2)+'\n')
print(json.dumps(R,ensure_ascii=False,indent=2))
