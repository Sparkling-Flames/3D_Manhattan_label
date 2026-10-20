"""Freeze the reviewable discovered direction portfolio before its assessment."""
from __future__ import annotations
import copy,datetime,hashlib
from pathlib import Path
from design_history_panel import read,write
ROOT=Path(__file__).resolve().parents[2];WORK=ROOT/'interchangeability_20261020'

FORWARD=[
 ('F20_highQ23_T_qK2','C02','C01','Primary efficiency direction; weak geometry separation retained explicitly'),
 ('F20_highQ18_T_qK2','C02','C01','Nested high-Q efficiency sensitivity; narrower independent personnel/Q-overlap support'),
 ('F20_highQnew_T_NewEdit_balanced_K2','C02','C01','High-Q new-source T/edit conditional efficiency with source and Q-overlap checks'),
 ('F20_all_QTG_balanced_medoids_K4','C04','C02','Clear discovery class-block separation with strong quality signal'),
 ('F20_all_QTG_balanced_medoids_K4','C02','C04','Prospective counterpart quality-improvement direction, not assumed symmetric stability'),
 ('F20_highQ23_Detail_qK2','C02','C01','User-priority high-Q structural refinement; quality and geometry distinct'),
 ('F20_hard_TDG_balanced_K3','C03','C02','Existing-hard-condition quality/efficiency candidate with limited building support'),
 ('F20_new_Scope_qK2','C02','C01','Scope tendency/efficiency comparator, not OOS correctness or established shape type'),
 ('F20_semiNew_NewEdit_qK2','C01','C02','Semi quality gain versus complete-failure tradeoff'),
 ('F20_new_NewNonedit_qK2','C01','C02','Negative ordinary-Manual interchangeability control'),
 ('F20_semiNew_NewNonedit_qK2','C01','C02','Negative control: more stable/complete can accompany worse quality')]

REVERSE=[
 ('R_directswap_geometry_partition_b0_K7__ordinary__mixed_history_v1','primary','C02','C01'),
 ('R_directswap_geometry_partition_b0_K7__ordinary_new__mixed_history_v1','same_source_team','C07','C06'),
 ('R_directswap_geometry_partition_b0_K7__ordinary_new__mixed_history_v1','same_source_team','C04','C01'),
 ('R_directswap_joint_partition_b0_K10__ordinary__mixed_history_v1','primary','C07','C01'),
 ('R_directswap_geometry_partition_b0_K7__hard_new__mixed_history_v1','same_source_team','C03','C06'),
 ('R_directswap_geometry_partition_b0_K7__hard_new__mixed_history_v1','same_source_team','C06','C03')]

def main():
 out=WORK/'assessment';out.mkdir(exist_ok=True)
 fs=read(WORK/'discovery/FORWARD_SPEC.json')['methods'];rs=read(WORK/'discovery/REVERSE_SPEC.json')['methods']
 chosen=[]
 for mid,c1,c2,why in FORWARD:
  source=next(x for x in fs if x['method_id']==mid)
  x=copy.deepcopy(source);x['directions']=[[c1,c2]];x['selection_basis']=why;chosen.append(x)
 for mid,context,c1,c2 in REVERSE:
  source=next(x for x in rs if x['method_id']==mid and x['context_id']==context)
  x=copy.deepcopy(source);x['directions']=[[c1,c2]];x['selection_basis']='Frozen reverse direction portfolio, detailed discovery evidence in RECOMMENDED_DIRECTIONS.json; includes negative and opportunity-limited directions.';chosen.append(x)
 methods=[]
 for item in chosen:
  original_context=item.get('context_id','primary')
  fixed=copy.deepcopy(item);fixed['discovery_context']=original_context
  semi=fixed['pool_filter']['layer']=='ordinary_semi';n=7 if semi else 13
  fixed.update(context_id='fixed_n'+str(n)+'_m2',n_values=[n],m_values=[2],min_n=3,
    background_policies=['random','out_rich','in_rich'],events_per_pool=100000,replicates=2)
  methods.append(fixed)
  stress=copy.deepcopy(item);stress.update(context_id='stress_integer_n_m',discovery_context=original_context,
    min_n=3,max_n=25,m_values=[2,3,4,5,6],events_per_pool=8,replicates=2)
  methods.append(stress)
 spec=dict(schema='frozen_direction_portfolio_v1',phase='assessment',seed=2026102021,methods=methods,
  events_per_pool=8,selection='Discovery-only direction selection; historical labels unchanged. All named failure controls retained.',
  primary='Each named class direction: fixed n13/m2 (Semi n7/m2), each feasible exact background/source-policy cell, two independent seeded member/core draws.',
  stress='All capacity-feasible integer n3..25,m2..6 count frame, 8 source/direction-stratified cells per pool, two draws; not an exhaustive concrete-team census.',
  caution='The new-only reverse K2 is additionally registered in NESTED_NEW2_SPEC; n13/m2 is a dilution control and m5 is a large-block primary contrast, not a failed proxy for large-block evidence.')
 write(out/'DIRECTION_SPEC.json',spec)
 new2=copy.deepcopy(next(x for x in rs if x['method_id']=='R_directswap_geometry_partition_b2_K2__ordinary_new__mixed_history_v1' and x['context_id']=='same_source_team'))
 new2.update(directions=[['C01','C02'],['C02','C01']],m_values=[2,5],replicates=2,
  context_id='nested_same_source_team',matching_policies=['source_matched'])
 nested=dict(schema='frozen_new2_nested_blocks_v1',phase='assessment',seed=2026102023,methods=[new2],
  primary='n13,m5 large-block contrast and n13,m2 dilution control; all feasible n>=3 with identical entrant blocks and nested random core, two registered block/core draws.',
  evidence='Discovery K2 broad-m separation was clear but weakened at m2/n11..17. This interaction motivated distinct scales before assessment; no assessment outcomes read.')
 write(out/'NESTED_NEW2_SPEC.json',nested)
 files=['forward/worker_labels.csv.gz','reverse/legacy_fit/worker_labels.csv.gz','reverse/mixed_fit/worker_labels.csv.gz',
  'discovery/FORWARD_SPEC.json','discovery/REVERSE_SPEC.json','independent/METRIC_CONTRACT.json',
  'assessment/DIRECTION_SPEC.json','assessment/NESTED_NEW2_SPEC.json']
 receipt=dict(schema='assessment_rule_freeze_v1',frozen_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
  source_main_commit='445686f8f3cf6039c4ce1f60016cad1d26829044',science_commit='82c6164b0d4630de5316199c92aa405930973168',
  assessment_buildings=read(ROOT/'analysis/composition/SPLIT.json')['validation_buildings'],
  knowledge='These v2 assessment buildings have been studied previously. No external blind-test claim. Common-panel assessment native outputs were computed under its earlier fixed registration, but not opened or summarized by current F/R selectors. Known G/R baselines have their independent pre-batch registration. Current direction choices use discovery outputs only.',
  inherited='Frozen input coordinates/rings/qualifications, references, fusion, B8L2 primary/D10 sensitivity; N1 absent.',
  forward_directions=len(FORWARD),reverse_fixed_directions=len(REVERSE),reverse_nested_directions=2,
  file_sha256={p:hashlib.sha256((WORK/p).read_bytes()).hexdigest() for p in files},
  residual_branches='Same-crew condition transfer and the seven mixed-composition methods were registered before their discovery fusion. They will be replayed with exact assessment crews. Newly selected ratio hypotheses receive a separate freeze before their own assessment is read; these cannot change the present direction portfolio.')
 write(out/'ASSESSMENT_FREEZE.json',receipt)
 print(dict(fixed_direction_count=len(chosen),settings=len(methods),reverse_nested_directions=2))

if __name__=='__main__':main()
