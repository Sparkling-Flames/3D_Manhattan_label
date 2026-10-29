"""将已核主表与具名作者分项接入离线页面；不重新评分或融合。"""
from pathlib import Path
import json
import pandas as pd

ROOT=Path(__file__).resolve().parents[3]
ARCHIVE=ROOT/'research/workers/personnel_ac_v21_20261030'
REVIEW=ROOT/'research/workers/personnel_ac_review_20261030'
FINAL=ROOT/'research/data/releases/v2.1/final_classification_downstream'
WEB=ROOT/'research/statistics/research_explorer_v1_r2_20261017'
CONDITIONS={
    'TARGET_DSTRUCT_K3_20_7_2_to_3':('TARGET K3 · 20人换7人','TARGET_DSTRUCT_K3','A_fixed_n',20,7,'2->3'),
    'TARGET_whole_target_n20':('TARGET K3 · 固定20人，目标类全部换入','TARGET_DSTRUCT_K3','whole_equal_fixed_n_all_m',20,None,'2->3'),
    'OPPJOINT_K3_20_10_1_to_2':('OPPJOINT K3 · 20人换10人','OPPJOINT_K3','A_fixed_n',20,10,'1->2'),
    'V21_DSTRUCT_RAW3_K3_23_12_1_to_2':('RAW3 K3 · 23人换12人','V21_DSTRUCT_RAW3_K3','A_fixed_n',23,12,'1->2'),
}


def select_conditions(frame):
    rows=[]
    base=frame[frame.scope.eq('primary')&frame.condition.eq('manual')&frame.layer.eq('ordinary_manual')]
    for key,(_,method,view,n,m,direction) in CONDITIONS.items():
        mask=base.method.eq(method)&base.analysis_view.eq(view)&pd.to_numeric(base.n_condition,errors='coerce').eq(n)&base.role_direction.eq(direction)
        if m is not None:mask &= pd.to_numeric(base.m_condition,errors='coerce').eq(m)
        else:mask &= base.m_condition.eq('whole_class_actual_m')
        rows.append(base[mask].assign(contrast=key))
    return pd.concat(rows,ignore_index=True)


def records(frame):
    return json.loads(frame.to_json(orient='records',force_ascii=False))


def build():
    parts=[select_conditions(d) for d in pd.read_csv(ARCHIVE/'stage05_main/CONDITION_METRIC_SUMMARY.csv.gz',chunksize=100000,low_memory=False)]
    metrics=pd.concat(parts,ignore_index=True)
    assert not metrics.duplicated(['contrast','metric']).any()
    effects=pd.read_csv(REVIEW/'MAIN_EFFECTS_RECOMPUTED.csv')
    for r in effects.itertuples():
        for metric,expected in [('B8L2_CA',r.Q),('D10_CA',r.D10)]:
            got=metrics[(metrics.contrast==r.contrast)&(metrics.metric==metric)]
            assert len(got)==1 and abs(got.iloc[0].image_mean-expected)<1e-9
    labels=pd.read_csv(ARCHIVE/'stage00_intake/FINAL_LABELS_FOR_AC_ALL_LOBO.csv.gz',low_memory=False)
    labels=labels[['method','heldout_building','worker_id','known','class_id','missing_reason','label_stage']]
    same=pd.read_csv(FINAL/'SAME_ROOM_SUMMARY.csv')
    same=same[same.budget.eq('mid_n_rep0')&same.analysis_layer.eq('ordinary_comparable')&same.metric.isin(['B8L2','fusion_turn_n','log_recorded_time'])]
    data=dict(conditions={k:v[0] for k,v in CONDITIONS.items()},effects=records(effects),
        images=records(pd.read_csv(REVIEW/'MAIN_EFFECTS_BY_IMAGE.csv')),metrics=records(metrics),
        coalitions=records(pd.read_csv(REVIEW/'SEVEN_COALITIONS_VERIFIED.csv')),
        coverage=records(pd.read_csv(REVIEW/'COALITION_COVERAGE.csv')),
        labels=records(labels),same_room=records(same),
        strict=records(pd.read_csv(FINAL/'ADOPTED_CONDITIONS.csv')),
        review='Q/D10重点条件与七组合成员/端点沿用独立核对；其余分项为作者保存结果',
        browser='未完成：本轮浏览器安全策略拒绝本地文件访问')
    (WEB/'v21-population-study-data.js').write_text('window.V21_POPULATION_STUDY='+json.dumps(data,ensure_ascii=False,allow_nan=False,separators=(',',':'))+';\n',encoding='utf-8')
    checks=dict(selected_conditions=len(effects),metric_rows=len(metrics),seven_union_rows=len(data['coalitions']),
        q_d10_summary_parity=True,new_fusion=0,new_scores=0,browser=data['browser'])
    (ARCHIVE/'WORKBENCH_CHECKS.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(checks,ensure_ascii=False))


if __name__=='__main__':build()
