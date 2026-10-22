"""Executed narrow regression and counterexample tests for the optional patch."""
from pathlib import Path
import argparse,os
import sys,json,copy,hashlib,importlib.util,unittest
HERE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',type=Path,default=Path(os.environ.get('QUALITY_AUDIT_SOURCE',HERE.parents[2]/'unpacked/full/quality_deep_20261007')),help='Path to extracted quality_deep_20261007 package')
ROOT=parser.parse_args().source.resolve()
sys.path.insert(0,str(ROOT/'src'))
import evaluator as original
spec=importlib.util.spec_from_file_location('evaluator_proposed',HERE/'evaluator_proposed.py');proposed=importlib.util.module_from_spec(spec);spec.loader.exec_module(proposed)
panel=json.loads((ROOT/'inputs/panel.json').read_text())['images'];im=next(i for i in panel if i['code']=='2t7WUuJeko7-09');a=next(a for a in im['annotations'] if a['id']=='R00016');refs=im['references']
ctx={'target_compatibility':'confirmed_same_target','reference_usable':True};bad=copy.deepcopy(a);bad['points'][1][1]=256
baseline_hash=hashlib.sha256((ROOT/'src/evaluator.py').read_bytes()).hexdigest();observations=[]

def run_case(name,layout,references,context):
 before=original.evaluate(layout,references,context,.5);after=proposed.evaluate(layout,references,context,.5)
 observations.append({'test':name,'original_global_comparable':before['reference_cost_comparable_with_same_context'],'proposed_global_comparable':after['reference_cost_comparable_with_same_context'],'per_reference':[{'id':r.get('reference_id'),'reference_status':r.get('reference_status'),'spatial_comparable':r['spatial_reference_cost_comparable_with_same_context']} for r in after['reference_agreement']]})
 return before,after

class Tests(unittest.TestCase):
 def test_valid_layout_preserves_comparability_and_numerics(self):
  before,after=run_case('valid',a,refs,ctx);self.assertTrue(after['reference_cost_comparable_with_same_context'])
  clean=copy.deepcopy(after)
  for r in clean['reference_agreement']:r.pop('spatial_reference_cost_comparable_with_same_context')
  self.assertEqual(before,clean)
 def test_invalid_floor_is_not_comparable(self):
  before,after=run_case('horizon_floor',bad,refs,ctx)
  self.assertTrue(before['reference_cost_comparable_with_same_context']);self.assertFalse(after['reference_cost_comparable_with_same_context']);self.assertEqual(after['reference_agreement'][0]['reference_status'],'unavailable')
 def test_empty_references_not_comparable(self):
  before,after=run_case('empty_reference_list',a,[],ctx)
  self.assertTrue(before['reference_cost_comparable_with_same_context']);self.assertFalse(after['reference_cost_comparable_with_same_context'])
 def test_invalid_reference_not_comparable(self):
  bg=copy.deepcopy(refs[0]);bg['points'][1][1]=256
  before,after=run_case('invalid_reference',a,[bg],ctx);self.assertFalse(after['reference_cost_comparable_with_same_context'])
 def test_mixed_references_keep_individual_status(self):
  bg=copy.deepcopy(refs[0]);bg['id']='invalid_reference_counterexample';bg['points'][1][1]=256
  before,after=run_case('mixed_reference_status',a,[refs[0],bg],ctx)
  self.assertFalse(after['reference_cost_comparable_with_same_context']);self.assertEqual([r['spatial_reference_cost_comparable_with_same_context'] for r in after['reference_agreement']],[True,False])
 def test_unknown_context_stays_unknown(self):
  before,after=run_case('unknown_context',a,refs,{})
  self.assertFalse(after['reference_cost_comparable_with_same_context']);self.assertEqual(before['overall_state'],after['overall_state'])
 def test_accepted_other_target_preserved(self):
  before,after=run_case('accepted_alternative_target',a,refs,dict(ctx,target_compatibility='accepted_alternative_target'))
  self.assertFalse(after['reference_cost_comparable_with_same_context']);self.assertEqual(after['overall_state'],'accepted_target_difference_not_automatic_error')
 def test_required_conflict_preserved(self):
  context=dict(ctx,requirements=[{'id':'test_detail','necessity':'required','status':'violated','source':'synthetic_test_only'}])
  before,after=run_case('required_conflict',a,refs,context)
  self.assertFalse(after['reference_cost_comparable_with_same_context']);self.assertEqual(after['overall_state'],'known_requirement_conflict')
 def test_footprint_only_valid_spatial_comparison(self):
  from components import footprint
  from shapely.geometry import mapping
  _,p=footprint(a);layout={'id':'footprint_control','geometry':mapping(p)}
  before,after=run_case('footprint_only',layout,refs,ctx)
  self.assertTrue(after['reference_cost_comparable_with_same_context']);self.assertEqual(after['reference_agreement'][0]['conditional_3d_status'],'not_applicable_no_upper_output')
  clean=copy.deepcopy(after)
  for r in clean['reference_agreement']:r.pop('spatial_reference_cost_comparable_with_same_context');r.pop('reference_status')
  self.assertEqual(before,clean)
 def test_all_shared_numeric_values_unchanged(self):
  for imid,aid in [('uNb9QFRL6hY-18','R02846'),('uNb9QFRL6hY-18','R02843'),('X7HyMhZNoso-19','R01646'),('X7HyMhZNoso-19','R00916')]:
   im=next(i for i in panel if i['code']==imid);layout=next(x for x in im['annotations'] if x['id']==aid)
   before,after=run_case('numeric_regression_'+aid,layout,im['references'],ctx)
   for r in after['reference_agreement']:r.pop('spatial_reference_cost_comparable_with_same_context')
   self.assertEqual(before,after)
 def test_source_bytes_unchanged(self):
  self.assertEqual(baseline_hash,hashlib.sha256((ROOT/'src/evaluator.py').read_bytes()).hexdigest())

if __name__=='__main__':
 suite=unittest.defaultTestLoader.loadTestsFromTestCase(Tests);result=unittest.TextTestRunner(verbosity=2).run(suite)
 (HERE/'test_results.json').write_text(json.dumps({'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'source_sha256':baseline_hash,'source_unmodified':baseline_hash==hashlib.sha256((ROOT/'src/evaluator.py').read_bytes()).hexdigest(),'cases':observations},ensure_ascii=False,indent=2))
 sys.exit(not result.wasSuccessful())
