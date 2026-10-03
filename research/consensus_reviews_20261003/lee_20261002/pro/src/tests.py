"""Focused checks of the extracted kernels and new diagnostics, not the repository suite."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import Polygon,Point,box
from shapely.ops import unary_union
from core import tile_consensus,region_iou
ROOT=Path(__file__).resolve().parents[1]
def record(i,p):return dict(id=str(i),worker=str(i),footprint=list(p.exterior.coords)[:-1])
def test_published_summary_agrees():
 a=pd.read_csv(ROOT/'inputs/published_summary_extract.csv').sort_values(['method','k']);b=pd.read_csv(ROOT/'results/replayed_16_summary.csv').sort_values(['method','k'])
 for k in a.columns:
  if k=='method':assert a[k].tolist()==b[k].tolist()
  else:np.testing.assert_allclose(a[k],b[k],rtol=1e-9,atol=1e-10,equal_nan=True)
def test_exhaustive_refinement():
 c=json.loads((ROOT/'results/checks.json').read_text());assert c['refinement_max_symmetric_difference_h2']<1e-12
 assert c['subsets']==255 and c['method_subsets']==510
def test_decomposition_identity():
 s=json.loads((ROOT/'results/support_field.json').read_text());assert abs(s['identity_error'])<1e-12
def test_finite_population_formula():
 s=pd.read_csv(ROOT/'results/support_field_finite_population.csv');np.testing.assert_allclose(s.expected_soft_loss,s.analytic_soft_loss,atol=1e-12)
def test_tie_union_intersection():
 a,b=box(0,0,2,2),box(1,0,3,2);x=tile_consensus([record(1,a),record(2,b)])
 assert x['regions']['mv50'].equals(a.union(b));assert x['regions']['mv_strict'].equals(a.intersection(b))
def test_subdivision_and_reverse():
 a=Polygon([(0,0),(1,0),(2,0),(2,2),(0,2)]);b=box(1,0,3,2)
 records=[record(1,a),record(2,b),record(3,a)]
 first=tile_consensus(records)['regions']['mv50'];records[0]['footprint'].reverse()
 assert first.equals(tile_consensus(records[::-1])['regions']['mv50'])
def test_missing_and_duplicate_fail():
 r=record(1,box(0,0,1,1))
 with pytest.raises(ValueError):tile_consensus([r,r])
 with pytest.raises(ValueError):tile_consensus([r,dict(id='2',worker='2',footprint=None)])
def test_majority_of_simple_rooms_can_have_hole():
 outer=box(-1,-1,3,3);hole=box(1,1,2,2)
 cuts=[box(1.4,2,1.6,3.1),box(2,1.4,3.1,1.6),box(1.4,-1.1,1.6,1)]
 polygons=[outer.difference(unary_union([hole,c])) for c in cuts]
 assert all(p.is_valid and p.geom_type=='Polygon' and len(p.interiors)==0 and p.contains(Point(0,0)) for p in polygons)
 result=tile_consensus([record(i,p) for i,p in enumerate(polygons)])
 out=result['regions']['mv50'];assert out.equals(outer.difference(hole));assert len(out.interiors)==1
 (ROOT/'results/hole_counterexample.json').write_text(json.dumps(dict(inputs=[list(p.exterior.coords) for p in polygons],output_exterior=list(out.exterior.coords),output_holes=[list(r.coords) for r in out.interiors],all_inputs_simple_contains_camera=True),indent=2))
def test_hard_majority_not_recover_disagreement():
 s=json.loads((ROOT/'results/support_field.json').read_text());x=pd.read_csv(ROOT/'results/exact_vs_16.csv')
 assert (x[x.k==8].exact_member_distance==0).all();assert s['full_disagreement']>0
