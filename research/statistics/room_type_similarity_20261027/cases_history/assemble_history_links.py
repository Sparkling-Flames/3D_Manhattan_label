#!/usr/bin/env python3
"""Extract inherited room-stratified results; never reclassify or refit."""
from pathlib import Path
import argparse,json,hashlib
import pandas as pd

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=Path(__file__).resolve().parent);a=p.parse_args();out=a.out
    rel='research/workers/personnel_composition_study_20261019/analysis/composition/scene_analysis/'
    src=out/'source'/rel/'room_type_frozen_rule_strata.csv.gz';d=pd.read_csv(src)
    f=d[d.rule_id.eq('H1_Q_quantile') & d.phase.eq('validation') & d.k.eq(9) & d.difficulty_stratum.eq('all')].copy()
    f['reuse_status']='inherited_frozen_20261019_fusion_plus_post_freeze_scene_stratification'
    f['direction']='historical_Q_low_C01_to_high_C03'
    f.to_csv(out/'HISTORICAL_Q9_ROOM_STRATA.csv',index=False,encoding='utf-8-sig')
    links=[
        dict(topic='旧按用途描述统计',source='research/statistics/descriptive_statistics_20261015/',identity='历史v1统计快照',scope='3152库存、27人、259图；worker/target等面板另有资格',reuse='用途字段拆分和人员×用途描述框架',not_reused='不把旧WQ/A10/B8L2数值并入当前5719份普通Manual，不用历史阈值恢复资格'),
        dict(topic='已有构成按用途分层',source=rel,identity='既有v2融合实验的事后用途/难度分层',scope='1317对比索引行；974分层结果行；不是974独立图片',reuse='保留发现/验证阶段与精确contrast_id；示例H1纯类9人高历史Q对低Q分用途',not_reused='不称同用途个人表现跨楼重复验证；不据用途分层重新挑选分类'),
        dict(topic='几何条件与同人表达',source='research/difficulty/difficulty_mechanisms_v2_20261020/',identity='冻结结构特征与既有b8-07/jtc-13原答案例',scope='旧共同33人、两图两楼；本轮分别保留两图全部35正式答案',reuse='H/短边/有效转折定义；重新画完整原答和参考',not_reused='H不是照片遮挡；少于参考转折不是独立人工漏角裁定'),
        dict(topic='同物理房间预测',source='research/same_room/same_room_v2_prediction_20261019/',identity='同房不同视角的既有研究',scope='普通123直接关系、64图、12楼',reuse='共同人员/本人排除同行均值/楼外历史及留楼评价的分解思路',not_reused='不把同用途当同房事实；不把同物理房间的视角当新房间验证'),
        dict(topic='自然人数曲线追加',source='research/workers/personnel_population_curves_v2_20261023/sampling_extension_20261026/',identity='上轮已完成的256自然顺序；本轮接续到最新main b2b0898时已归档',scope='Manual194池、普通177图；策略32配对路径另立',reuse='需要连接时引用已保存端点与固定人数支持',not_reused='本轮原答用途研究没有新增融合；不能以自然曲线替代类别/ABC或新DSTRUCT/RFUSE验证')
    ]
    pd.DataFrame(links).to_csv(out/'HISTORY_CONNECTIONS_ZH.csv',index=False,encoding='utf-8-sig')
    (out/'HISTORY_COMPUTE_RECEIPT.json').write_text(json.dumps({'source_commit':'b9bcec809fbaec8ab055931a1abb7baa5db44dac','input':str(src),'sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'input_rows':len(d),'selected_rows':len(f),'new_fusion':0,'new_classification':0,'history_links':len(links)},ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
