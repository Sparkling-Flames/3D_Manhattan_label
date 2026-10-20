"""Declared outcome-selected discovery illustrations, retaining counterexamples."""
from pathlib import Path
import hashlib,json,sys
import pandas as pd
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'interchangeability_20261020/code'))
from design_history_panel import read,write

CHOICES=[
 ('MC01','MC20_318ec4f80840bb1d1b36a7','整队重抽保持接近，快慢比例改变后范围偏移','highQ23 快慢类 n4 的 3:1→2:2；发现阶段此精确比较有 21 图/6 楼支持，此图为差异可见的例子。评估整体是否重现另报，不用本图代替规则验证。'),
 ('MC02','MC20_17ab7fbae4a9ff5d472651','同样15人、同样完整构成，近分仍可异形','反向连续风险三类整队 A/B 构成完全相同且无共同成员，Q 接近但平面明显不同；反驳只看均分或只看总节点数的互换判断。'),
 ('MC03','MC20_0985405d9b6b17212d4b61','同构成整队稳定但低分，调整比例后改善','反向连续风险三类整队15人 4:4:7→5:5:5；A/B 几何和得分均接近但约39分，C 改变2个类别槽和2个具体成员后约65分。局部机制图，不称通用最优比例。'),
 ('MC04','MC20_f59ea2d612bd309d2aea6a','多类混合整队可重抽，改三类槽后质量下降','反向几何风险七类整队9人，同构成 A/B 接近99分；C 同样替换 A 的9人，B→C 实换8人、净改变3个类别槽，降至约59分。局部多类结构反例，不能把单图归为条件类别泛化。')]

def main():
    request=ROOT/'interchangeability_20261020/mixed_challenge/discovery_requests.json.gz';data=read(request);events={e['event_id']:e for e in data['events']}
    f=pd.read_csv(HERE/'discovery_effects/EVENT_EVIDENCE.csv.gz').set_index('event_id');cases=[];details=[]
    positive=f[(f.context_id=='whole_team')&f.n.ge(4)&f.actual_source_match&f.within_joint_stable_main&f.within_geometry_shape_main&(~f.cross_geometry_noQ_main)&f.net_B8L2_change.abs().ge(10)]
    counter=f[(f.context_id=='whole_team')&f.n.ge(6)&f.actual_source_match&f.within_abs_B8L2_change.le(2)&(~f.within_geometry_noQ_main)&f.within_floor_jaccard_difference.ge(.15)]
    for cid,eid,title,reason in CHOICES:
        e=events[eid];r=f.loc[eid]
        item=dict(case_id=cid,title=title,reason=reason,native_dir=str(ROOT/'interchangeability_20261020/mixed_challenge/native_discovery'),requests_file=str(request),event_id=eid,view={},subtitle='结果驱动选择的发现阶段机制案例；固定参考、固定融合、固定B8L2及D10。完整人数组合见JSON。')
        cases.append(item)
        keys=['A_vector','C_vector','n','m','changed_category_slots','changed_class_labels_n','B_to_C_actual_turnover','A_B8L2','B_B8L2','C_B8L2','A_D10','B_D10','C_D10','A_nodes','B_nodes','C_nodes','within_joint_stable_main','within_geometry_noQ_main','within_geometry_shape_main','cross_joint_stable_main','cross_geometry_noQ_main','cross_geometry_shape_main','within_floor_jaccard_difference','cross_floor_jaccard_difference','within_bottom_y_absdiff_deg_p95','cross_bottom_y_absdiff_deg_p95','within_top_y_absdiff_deg_p95','cross_top_y_absdiff_deg_p95','net_B8L2_change']
        metrics={k:(None if pd.isna(r[k]) else r[k].item() if hasattr(r[k],'item') else r[k]) for k in keys}
        details.append(dict(case_id=cid,title=title,reason=reason,event=e,metrics=metrics))
    write(HERE/'MIXED_EXPORT_SELECTION.json',dict(cases=cases))
    write(HERE/'MIXED_CASE_DETAILS.json',dict(discovery_request_sha256=hashlib.sha256(request.read_bytes()).hexdigest(),selection_role='Discovery illustrations selected after outcomes; no external or held-out success claim. Primary suggested pair MC03 (composition changes improvement after stable low quality) and MC02 (same composition, similar Q but different shape); MC01/MC04 optional alternatives.',positive_frame='whole_team, n>=4, actual_source_match, within original main + new shape pass, cross noQ fail, |C-B Q|>=10',positive_eligible_events=len(positive),counter_frame='whole_team, n>=6, actual_source_match, |A-B Q|<=2, within noQ fail, floor difference>=.15',counter_eligible_events=len(counter),all_positive_eligible_event_ids=positive.index.tolist(),all_counter_eligible_event_ids=counter.index.tolist(),selected=details))
    print(json.dumps({'cases':len(cases),'positive_eligible':len(positive),'counter_eligible':len(counter),'images':[x['event']['image'] for x in details]},ensure_ascii=False))

if __name__=='__main__':main()
