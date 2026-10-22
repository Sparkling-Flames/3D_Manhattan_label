"""Produce an isolated optional evaluator patch; source remains unchanged."""
from pathlib import Path
import argparse,os
import difflib
HERE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',type=Path,default=Path(os.environ.get('QUALITY_AUDIT_SOURCE',HERE.parents[2]/'unpacked/full/quality_deep_20261007')),help='Path to extracted quality_deep_20261007 package')
ROOT=parser.parse_args().source.resolve()
original=(ROOT/'src/evaluator.py').read_text()
patched=original.replace("row={'reference_id':g.get('id'),'reference_version':g.get('version'),**region_metrics(p,pg)","row={'reference_id':g.get('id'),'reference_version':g.get('version'),'reference_status':'ok',**region_metrics(p,pg)")
old=" rank_ready=target=='confirmed_same_target' and context.get('reference_usable') is True and not conflicts\n"
new=""" # The supplied context is still global caller evidence, not a per-reference judgment.
 context_ready=target=='confirmed_same_target' and context.get('reference_usable') is True and not conflicts
 for row in results:
  range_computed=(row.get('reference_status')=='ok' and all(
   isinstance(row.get(key),(int,float)) and math.isfinite(row[key])
   for key in ('iou','centroid_distance_normalized')))
  row['spatial_reference_cost_comparable_with_same_context']=bool(context_ready and range_computed)
 # A global true flag means every supplied reference has a computable spatial comparison.
 # Angular/3-D availability and overall quality remain separate.
 rank_ready=bool(results) and all(row['spatial_reference_cost_comparable_with_same_context'] for row in results)
"""
assert old in patched
patched=patched.replace(old,new)
(HERE/'evaluator_proposed.py').write_text(patched)
(HERE/'evaluator_optional.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True),patched.splitlines(True),fromfile='a/src/evaluator.py',tofile='b/src/evaluator.py')))
print('Created isolated evaluator_proposed.py and evaluator_optional.patch')
