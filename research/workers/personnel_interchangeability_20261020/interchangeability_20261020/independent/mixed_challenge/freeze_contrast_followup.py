"""Freeze discovery-only exact mixed-vector contrast checks before assessment."""
from pathlib import Path
import datetime,hashlib,json,sys
import pandas as pd
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'interchangeability_20261020/code'))
from design_history_panel import write

def main():
    target=OUT/'CONTRAST_REPLICATION_FREEZE.json'
    if target.exists():raise RuntimeError('Frozen contrast checks already exist; do not rewrite')
    source=OUT/'discovery_effects/EXACT_COMPOSITION_CONTRAST.csv.gz';d=pd.read_csv(source)
    eligible=d[(d.images>=3)&(d.buildings>=2)].copy()
    keys=['method_id','domain','context_id','n','m','A_vector','C_vector']
    # All supported discovery contrasts remain visible. A display priority has
    # stronger support and is selected on the already observed discovery only.
    stronger=eligible[(eligible.images>=8)&(eligible.buildings>=3)]
    ranked=[]
    for _,g in stronger.groupby(['method_id','domain','context_id']):
        ranked.append(g.sort_values(['gap_joint_stable_main_building_mean','images','A_vector','C_vector'],ascending=[False,False,True,True]).head(3))
    priority=pd.concat(ranked,ignore_index=True) if ranked else stronger
    result=dict(schema='mixed_exact_contrast_internal_replication_v1',registered_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),discovery_contrast_table_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),assessment_scientific_outcomes_read_before_freeze=False,candidate_count=len(eligible),all_eligible_contrasts=eligible[keys].to_dict('records'),display_priority_contrasts=priority[keys].to_dict('records'),eligibility='Exact method/domain/context/n/m/A full vector/C full vector observed on >=3 discovery images and >=2 buildings; keep all candidates. No image results alter the frozen seven classification routes or assessment requests.',display_priority_rule='Among discovery contrasts with >=8 images and >=3 buildings, top three per route/context ranked by within-minus-cross original main stability gap, then image support, then lexicographic vectors. This is discovery selection; report matching assessment capacity and all outcomes, including reversals/missingness.',limitations='Randomly sampled mixed-vector interventions; changed category slots and B/C actual member turnover differ. A/B and A/C each replace exactly m from the same core. Assessment reuses v2 and is not external blind testing.')
    write(target,result)
    vf=OUT/'VECTOR_REPLICATION_FREEZE.json'
    write(OUT/'VECTOR_AND_CONTRAST_FREEZE_RECEIPT.json',dict(registered_utc=result['registered_utc'],assessment_results_read=False,files={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [target,vf]},candidates=len(eligible),priority_contrasts=len(priority)))
    print(json.dumps({'candidate_contrasts':len(eligible),'priority_contrasts':len(priority),'priority_rows':priority[keys+['images','buildings','gap_joint_stable_main_building_mean','net_B8L2_change_building_mean']].to_dict('records')},ensure_ascii=False))

if __name__=='__main__':main()
