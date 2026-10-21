"""Attach new outside-building labels to earlier fixed semantic opportunities.

This is reuse of the exact old window observations, not new ground-truth
annotation, a new blind test, or rescoring of GT-hold pictures.
"""
from pathlib import Path
import argparse,hashlib,json
import pandas as pd

HERE=Path(__file__).resolve().parent;V3=HERE.parent
SOURCE=HERE.parents[3]/'research/workers/personnel_taxonomy_20261021/evidence/local_opportunities.csv'

def main():
    s=pd.read_csv(SOURCE,keep_default_na=False)
    assert not s.duplicated(['object_id','feature_id']).any()
    labels_path=V3/'taxonomy/ALL_METHOD_LABELS_LOBO.csv.gz'
    labels=pd.read_csv(labels_path,keep_default_na=False)
    rows=[]
    for method in ['V3_BEHAVIOR','V3_JOINT_QT']:
        lab=labels[labels.method.eq(method)].copy()
        joined=s.merge(lab,left_on=['worker_id','condition','building_id'],right_on=['worker_id','condition','heldout_building'],how='left',validate='many_to_one')
        assert len(joined)==len(s)
        assert joined.method.notna().all()
        joined['observation_phase']='reused_personnel_taxonomy_20261021_fixed_window'
        joined['label_phase']='v3_outer_building_excluded'
        joined['new_semantic_adjudication']=False
        rows.append(joined)
    d=pd.concat(rows,ignore_index=True)
    out=HERE/'reused_semantic';out.mkdir(exist_ok=True)
    d.to_csv(out/'EXACT_OBSERVATIONS_WITH_NEW_LABELS.csv',index=False,encoding='utf-8-sig')
    summary=[]
    for tier in ['coarse_label','fine_label']:
        for key,g in d.groupby(['method','condition','building_id','image_code','feature_id',tier],dropna=False):
            known=g.known.eq(True).all()
            summary.append(dict(zip(['method','condition','building','image','feature_id','class_id'],key),tier=tier,
              known=bool(known),members='|'.join(sorted(g.worker_id.unique())),observations=len(g),people=g.worker_id.nunique(),
              expression_hits=int(g.localized_expression_proxy.eq(True).sum()),expression_rate=float(g.localized_expression_proxy.eq(True).mean()),
              semantic_status='|'.join(sorted(g.semantic_status.unique())),quality_usable=g.quality_usable.eq(True).all(),
              selected_family='|'.join(sorted(g.selected_family.unique())),coarse_k='|'.join(map(str,sorted(g.coarse_k.unique()))),fine_k='|'.join(map(str,sorted(g.fine_k.unique()))),
              mean_outside_building_turn=pd.to_numeric(g.turn_history,errors='coerce').mean(),
              mean_outside_building_short=pd.to_numeric(g.short_history,errors='coerce').mean(),
              training_scope='target building excluded',new_ground_truth=False))
    z=pd.DataFrame(summary);z.to_csv(out/'CLASS_LOCAL_EXPRESSION.csv',index=False,encoding='utf-8-sig')
    (out/'PROVENANCE.json').write_text(json.dumps(dict(status='complete_reuse',observation_rows=len(s),labelled_method_observation_rows=len(d),
      images=s.image_code.nunique(),buildings=s.building_id.nunique(),source=str(SOURCE),source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
      labels_sha256=hashlib.sha256(labels_path.read_bytes()).hexdigest(),new_scores=0,new_fusion_teams=0,
      note='Old fixed windows and semantic qualifications retained; new labels are independently trained outside each target building. Window hit is an expression proxy, not a new per-corner correctness adjudication.'),ensure_ascii=False,indent=2))
    print(z[(z.image=='pRbA3pwrgk9-12')&z.tier.eq('fine_label')][['method','class_id','people','expression_hits','expression_rate','selected_family']].to_string(index=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,default=SOURCE,
        help='Exact fixed-window table from pinned main; saved provenance records its SHA256.')
    SOURCE=parser.parse_args().source
    provenance=HERE/'reused_semantic/PROVENANCE.json'
    if provenance.exists():
        expected=json.loads(provenance.read_text())['source_sha256']
        if hashlib.sha256(SOURCE.read_bytes()).hexdigest()!=expected:
            raise ValueError('Use the exact pinned-main semantic table named by PROVENANCE.json; this script does not change the earlier observations.')
    main()
