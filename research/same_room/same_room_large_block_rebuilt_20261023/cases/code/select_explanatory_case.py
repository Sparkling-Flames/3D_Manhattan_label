#!/usr/bin/env python3
"""Select one exploratory mechanism example from completed new ABC outcomes.

No team generation; no target-based claim of held-out validation. Prefer an
actual equal nonzero turn step in the two views with opposite |dQ|>2 effects.
Choose the direction/condition cell with the widest pair support, not max Q.
"""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
import pandas as pd

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--effects',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    d=pd.read_csv(a.effects,low_memory=False);b=d[d.method.eq('V3_BEHAVIOR')&d.condition.eq('manual')&d.ordinary_comparable.astype(str).str.lower().eq('true')&d.layer_a.eq('ordinary_manual')&d.layer_b.eq('ordinary_manual')].copy();rows=[];counts=[]
    for comparison in ['CA','CB','BA']:
        qa=pd.to_numeric(b['B8L2_a_'+comparison],errors='coerce');qb=pd.to_numeric(b['B8L2_b_'+comparison],errors='coerce');ta=pd.to_numeric(b['fusion_turn_n_a_'+comparison],errors='coerce');tb=pd.to_numeric(b['fusion_turn_n_b_'+comparison],errors='coerce')
        valid=qa.notna()&qb.notna()&ta.notna()&tb.notna()&b.Q_common6.astype(str).str.lower().isin(['true','1','1.0']);big=(qa.abs()>2)&(qb.abs()>2)
        cases=[('equal_turn_step_opposite_Q',valid&big&(qa*qb<0)&(ta==tb)&(ta!=0)),('opposite_turn_step',valid&big&(ta*tb<0))]
        for category,mask in cases:
            z=b[mask].copy();z['case_category']=category;z['comparison']=comparison;z['Q_delta_a']=qa[mask];z['Q_delta_b']=qb[mask];z['turn_delta_a']=ta[mask];z['turn_delta_b']=tb[mask];rows.append(z);counts.append(dict(category=category,comparison=comparison,events=len(z),physical_pairs=z.pair_key.nunique(),buildings=z.building.nunique()))
    candidate=pd.concat(rows,ignore_index=True)
    if candidate.empty:
        # This is a recorded fallback, never a fabricated zero/failed endpoint.
        z=b[pd.to_numeric(b['incomplete_fraction'],errors='coerce')>0].copy();z['case_category']='observed_incomplete_or_connection_failure';z['comparison']='CA';candidate=z
        counts.append(dict(category='observed_incomplete_or_connection_failure',comparison='CA',events=len(z),physical_pairs=z.pair_key.nunique(),buildings=z.building.nunique()))
    assert len(candidate)>0,'No requested mechanism or actual failure candidate in completed support.'
    priorities={'equal_turn_step_opposite_Q':0,'opposite_turn_step':1,'observed_incomplete_or_connection_failure':2};candidate['category_priority']=candidate.case_category.map(priorities);candidate['comparison_priority']=candidate.comparison.map({'CA':0,'CB':1,'BA':2})
    best=candidate[candidate.category_priority.eq(candidate.category_priority.min())];best=best[best.comparison_priority.eq(best.comparison_priority.min())]
    # A mechanism subgroup is selected by distinct physical pair support. All
    # endpoints in the case remain exploratory illustrations of that subgroup.
    cols=['source_role_key','target_role_key','difficulty_pair','ratio_band']
    if 'turn_delta_a' in best and best.turn_delta_a.notna().any():cols.append('turn_delta_a')
    cells=best.groupby(cols,dropna=False).agg(events=('event_id','size'),physical_pairs=('pair_key','nunique'),buildings=('building','nunique')).reset_index();cells['cell_key']=cells[cols].astype(str).agg('|'.join,axis=1);cells=cells.sort_values(['physical_pairs','buildings','cell_key'],ascending=[False,False,True]);cell=cells.iloc[0]
    chosen=best.copy()
    for c in cols:chosen=chosen[chosen[c].isna() if pd.isna(cell[c]) else chosen[c].eq(cell[c])]
    chosen=chosen.sort_values('event_id').iloc[0];short=['event_id','case_category','comparison','pair_key','groups','building','image_a','image_b','method','source_role_key','target_role_key','n','m','D_n','m_over_n','difficulty_pair','ratio_band','Q_delta_a','Q_delta_b','turn_delta_a','turn_delta_b']
    keep=[c for c in short if c in candidate];candidate[keep].to_csv(a.out/'EXPLORATORY_CASE_CANDIDATES.csv.gz',index=False,compression={'method':'gzip','mtime':0});cells.to_csv(a.out/'EXPLORATORY_CANDIDATE_CELLS.csv',index=False);pd.DataFrame(counts).to_csv(a.out/'EXPLORATORY_SEARCH_COUNTS.csv',index=False)
    receipt=dict(event_id=chosen.event_id,comparison=chosen.comparison,case_category=chosen.case_category,selection='exploratory outcome-selected mechanism illustration; first prioritize equal nonzero actual turn step with opposite Q and both abs Q > 2; prefer CA then CB then BA; choose widest distinct-pair direction/condition cell, then smallest event_id; never max Q',selection_is_independent_validation=False,event_count_is_not_independent_person_repeat=True,new_fusion=0,new_labels=0,effect_source=str(a.effects),effect_source_sha256=hashlib.sha256(a.effects.read_bytes()).hexdigest(),searched_manual_structure_ordinary_events=len(b),candidate_counts=counts,selected_cell={c:cell[c].item() if hasattr(cell[c],'item') else cell[c] for c in cols+['physical_pairs','buildings','events']},selected_effects={c:chosen[c].item() if hasattr(chosen[c],'item') else chosen[c] for c in ['Q_delta_a','Q_delta_b','turn_delta_a','turn_delta_b'] if c in chosen})
    (a.out/'CASE_SELECTION.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');print(json.dumps(receipt,ensure_ascii=False))

if __name__=='__main__':main()
