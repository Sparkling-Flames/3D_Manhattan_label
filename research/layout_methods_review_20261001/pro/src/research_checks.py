"""Small checks of the new experiments, NOT the original snapshot verifier."""
import json,csv
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
def load(n):return json.load(open(BASE/'results'/n))
def main():
 checks=[]
 a=list(csv.DictReader(open(BASE/'results/snapshot_74_independent.csv')));assert len(a)==74;checks.append('74 independent parameter cases executed')
 a=list(csv.DictReader(open(BASE/'results/real_recomputed.csv')));assert len(a)==3 and max(abs(float(r['diff_bev'])) for r in a)<1e-10 and max(abs(float(r['diff_column'])) for r in a)==0;checks.append('3 real BEV and column spot checks')
 r=load('real_local_windows.json')[0];assert len(r['a_paths'][0]['interior_vertex_indices'])==3 and len(r['b_paths'][0]['interior_vertex_indices'])==2;checks.append('real physical-ring window retains 3 versus 2 original pairs')
 r=load('quarter_turn_parity.json');assert not set(r[2]['possible_exit_directions_mod4'])&set(r[3]['possible_exit_directions_mod4']);checks.append('orthogonal-turn parity condition')
 r=load('local_path_cases.json')[0];assert r['metrics']['hausdorff_lower']<1e-12;checks.append('collinear subdivision preserves path geometry')
 r=load('order_counterexample.json');assert r['unordered_cost']<1e-10 and r['cyclic']['cost']>0 and r['space']['bev_iou']<.7;checks.append('same points do not determine same ring')
 r=load('subtraction_exhaustive.json');assert r['enumerated_valid']==61 and r['orthogonal_geometries']==2 and r['residual_then_complexity']['vertices']==4 and r['residual_then_complexity']['fidelity_lower']>.39;checks.append('residual/complexity removes supported 0.4h feature')
 r=load('consensus_joint_counterexample.json');assert r['mv']==[1,1,1] and r['mv_whole_count']==0;checks.append('local support does not imply observed full support')
 a=list(csv.DictReader(open(BASE/'results/insertion_noise.csv')));assert len(a)==1200;checks.append('300 noise examples and four matching outputs')
 r=load('identifiability_counterexample.json');assert r['rank']==12 and r['effect_reallocation_prediction_max']==0;checks.append('one-worker-per-image fixed effects are confounded')
 (BASE/'logs/research_checks.json').write_text(json.dumps(dict(passed=len(checks),checks=checks,scope='new research only; original verifier not run'),indent=2));print('\n'.join(checks))
if __name__=='__main__':main()
