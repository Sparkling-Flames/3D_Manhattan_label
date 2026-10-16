"""当前261图元数据与共同双评分的难度/场景描述；不执行绑定或评分。"""
import json
from collections import Counter
from pathlib import Path

import pandas as pd
import numpy as np

from ..data_prep.consolidate_research_input import load_current_bundle
from .current_annotation_context_20261017 import load_current_context
from .descriptive_pool_gate_20261015 import load_image_review_decisions
from .b8l2_detail_summary_20261016 import distribution

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'research/difficulty/difficulty_current_20261017'
SHARED=ROOT/'research/quality/quality_b8l2_d10_20261017'


def summarize(frame, compatible=False):
    assert not frame.object_id.duplicated().any()
    usable=frame.quality_usable
    same=frame.rescore_target_id.eq(frame.difficulty_target_id)
    selected=frame[usable & same] if compatible else frame[usable]
    result=dict(inventory_n=len(frame),inventory_images=frame.image_id.nunique(),
        quality_n=len(selected),quality_images=selected.image_id.nunique(),
        quality_workers=selected.worker_id.nunique(),quality_other_target_n=int((usable & ~same).sum()),
        computed_not_quality_n=int((~usable & frame.calculation_status.eq('full_computed')).sum()),
        quality_missing_or_excluded_n=len(frame)-len(selected))
    for status in ['full_computed','pending_target','input_uncomputable','floor_only_computed']:
        result['status_'+status]=int(frame.calculation_status.eq(status).sum())
    assert selected.B8L2.notna().all() and selected.D10.notna().all()
    for metric in ['B8L2','D10']:
        result.update({metric+'_'+k:v for k,v in distribution(selected[metric]).items()})
        means=selected.groupby('image_id')[metric].mean()
        result[metric+'_image_equal_mean']=means.mean() if len(means) else None
    delta=selected.D10-selected.B8L2
    result.update({'paired_delta_'+k:v for k,v in distribution(delta).items()})
    return result


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    paths=[SHARED/'CROSS_MODULE_INPUTS.json',SHARED/'shared_records.csv',SHARED/'MODEL_PARAMETERS.json']
    before={str(p):p.read_bytes() for p in paths}
    handoff=json.loads(before[str(paths[0])])
    bundle=load_current_bundle(ROOT/handoff['input_manifest'])
    context=load_current_context(bundle)
    rows=context['difficulty_records']
    reviews=load_image_review_decisions()
    refs={r['target_id']:r for r in context['reference_catalog']}
    old=json.loads((ROOT/'research/difficulty/difficulty_scope_resolution_20261016/current_259.json').read_text(encoding='utf-8'))['records']
    lookup={r['image_id']:r for r in rows}
    assert len(lookup)==len(rows)==261
    assert all(lookup[r['image_id']]==r for r in old), 'old difficulty/geometry changed'
    added=bundle['batch_admission']['difficulty_records']
    assert len(added)==2 and all(r['current_class']=='中等' and r['qualifier']=='偏简单' for r in added)
    metadata=[]
    for r in rows:
        ref=refs[r['target_version']]
        assert ref['image_id']==r['image_id'] and ref['current_target']
        assert len(ref['floor_xz_h'])==len(r['selected']['floor'])
        assert np.allclose(ref['floor_xz_h'],r['selected']['floor'],rtol=0,atol=1e-8)
        review=reviews.get(r['image_id'])
        metadata.append(dict(image_id=r['image_id'],image=r['image'],current_class=r['current_class'],
            qualifier=r.get('qualifier',''),difficulty_target_id=r['target_version'],
            scene=r['scene'],doorway_status=r['doorway_status'],oos_subtype=r['oos_subtype'],
            difficulty_analysis_eligible=r['difficulty_analysis_eligible'],
            difficulty_analysis_exclusion=r['difficulty_analysis_exclusion'],
            current_review_status=review['status'] if review else '',current_review_decision=review,
            full_reference_available=ref['full_reference_available'],
            selected_vertex_count=len(r['selected']['floor']),N_turn=r.get('N_turn'),H=r.get('H'),
            source='batch_admission' if r in added else 'difficulty_v6'))
    frame=pd.read_csv(paths[1],keep_default_na=False)
    for key in ['quality_usable','is_oos','is_doorway']:
        assert set(frame[key].astype(str).str.lower()) <= {'true','false'}
        frame[key]=frame[key].astype(str).str.lower().eq('true')
    for key in ['B8L2','D10']:frame[key]=pd.to_numeric(frame[key].replace('',None),errors='raise')
    objects={r['object_id']:r for r in bundle['data']['objects'] if r['object_kind']=='annotation'}
    assert len(frame)==len(objects)==3222 and set(frame.object_id)==set(objects)
    for r in frame.to_dict('records'):
        assert all(r[k]==objects[r['object_id']][k] for k in ['image_id','worker_id','condition'])
        assert r['difficulty_class']==lookup[r['image_id']]['current_class']
    frame['difficulty_target_id']=frame.image_id.map({r['image_id']:r['target_version'] for r in rows})
    assert not (frame.quality_usable & frame.is_oos).any()
    assert frame.loc[~frame.quality_usable,['B8L2','D10']].isna().all().all()
    assert int(frame.quality_usable.sum())==handoff['counts']['quality_rows']
    b8=next(r for r in metadata if r['image']=='b8cTxDM8gDG-04')
    assert b8['current_review_status']=='pending'
    assert not frame.loc[frame.image_id.eq(b8['image_id']),'quality_usable'].any()
    def write(name,data):
        (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
    write('current_261.json',dict(version='difficulty_v6_plus_admission_20261017',records=rows,image_review_decisions=list(reviews.values())))
    pd.DataFrame(metadata).to_csv(OUT/'image_metadata.csv',index=False,encoding='utf-8-sig')
    tables={}
    for name,dimensions,compatible in [
        ('difficulty_by_condition',['condition','difficulty_class'],True),
        ('difficulty_by_quality_use',['condition','difficulty_class','quality_use'],True),
        ('scene_by_condition',['condition','is_doorway','is_oos'],False),
        ('difficulty_scene_by_condition',['condition','difficulty_class','is_doorway','is_oos'],True),
        ('image_by_condition',['image_id','condition'],True)]:
        result=[]
        for keys,g in frame.groupby(dimensions,dropna=False):
            result.append(dict(zip(dimensions,keys),**summarize(g,compatible)))
        table=pd.DataFrame(result);table.to_csv(OUT/(name+'.csv'),index=False,encoding='utf-8-sig');tables[name]=result
    # 原因保留共同包文本与缺失，不将诊断分填入正式质量列。
    fields=['object_id','image_id','image_code','condition','difficulty_class','difficulty_target_id',
        'rescore_target_id','quality_usable','calculation_status','quality_exclusion_reasons','input_geometry_reasons',
        'measurement_reasons','quality_use','is_doorway','is_oos','B8L2','D10','B8L2_version','D10_version','rescore_reference_version']
    frame[fields].to_csv(OUT/'record_audit.csv',index=False,encoding='utf-8-sig')
    checks=dict(images=len(rows),inventory=len(frame),classes=dict(Counter(r['current_class'] for r in rows)),
        quality_n=int(frame.quality_usable.sum()),quality_matching_difficulty_target=int((frame.quality_usable & frame.rescore_target_id.eq(frame.difficulty_target_id)).sum()),
        calculation_status=frame.calculation_status.value_counts().to_dict(),old_259_unchanged=True,
        added_images=[r['image'] for r in added],b8c04_pending=True,
        shared_version=handoff['version'],shared_input=handoff['input_manifest'],
        scoring_rerun=False,binding_rules_changed=False)
    assert all(p.read_bytes()==before[str(p)] for p in paths), 'shared package changed during build: rerun'
    write('CHECKS.json',checks)
    write('SOURCE_HANDOFF.json',handoff)
    write('MODEL_PARAMETERS.json',json.loads(before[str(paths[2])]))
    write('FIELD_CONTRACT.json',dict(version='difficulty_current_20261017_v1',
        ordinary_rule='difficulty tables require quality_usable and exact rescore_target_id=difficulty_target_id; scene tables use all quality_usable',
        missing='empty metric is missing, never zero; quality_missing_or_excluded includes other-target quality in difficulty tables',
        weight='mean is answer-equal; image_equal_mean is mean of image means within each condition',
        diagnostic='calculation status counts cover full inventory; computed_not_quality is distinct from input_uncomputable',
        scene='is_oos/is_doorway are shared operational flags, false is not proof of reviewed absence; original unknown statuses preserved in image_metadata',
        registration_pending=['research/difficulty/difficulty_current_20261017','tools/thesis_main/analysis/difficulty_current_20261017.py','tests/test_difficulty_current_20261017.py']))
    lines=['# 当前261图难度与双评分描述','',
        '保留v6全部259图原记录，叠加登记的两张中等（偏简单仅备注）；b8c04通过独立人工决定保持暂停。无改标签、改范围、重新绑定或评分。', '',
        f"共同包版本：{handoff['version']}；库存{len(frame)}，质量可用{checks['quality_n']}，其中与当前难度目标完全一致{checks['quality_matching_difficulty_target']}。",'',
        '以下难度质量表仅纳入质量可用且评分target_id与难度target_id一致的作答，按采集条件分别报告。不能把另一种合法空间的评分解释为当前空间的难度效果。场景表另保留全部质量可用作答；OOS只诊断。', '',
        '|条件|等级|库存份|同目标质量份/图|B8L2作答均值|D10作答均值|B8L2图片等权|D10图片等权|','|---|---|---:|---:|---:|---:|---:|---:|']
    def fmt(x):return '缺失' if x is None or pd.isna(x) else f'{x:.2f}'
    for r in tables['difficulty_by_condition']:
        lines.append(f"|{r['condition']}|{r['difficulty_class']}|{r['inventory_n']}|{r['quality_n']}/{r['quality_images']}|{fmt(r['B8L2_mean'])}|{fmt(r['D10_mean'])}|{fmt(r['B8L2_image_equal_mean'])}|{fmt(r['D10_image_equal_mean'])}|")
    lines+=['','上表按现有类别展示全部合格用途，并非全是普通难度主分析；`difficulty_by_quality_use.csv`进一步区分ordinary_primary、doorway_quality、special_conditional_only。例如e9z-16的简单等级与特殊用途保留，不混称普通图。', '',
        '|条件|门洞标志|OOS标志|库存|质量可用|完整算出但不用于质量|输入不可算|待目标|仅底面|B8L2均值|D10均值|',
        '|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in tables['scene_by_condition']:
        lines.append(f"|{r['condition']}|{r['is_doorway']}|{r['is_oos']}|{r['inventory_n']}|{r['quality_n']}|{r['computed_not_quality_n']}|{r['status_input_uncomputable']}|{r['status_pending_target']}|{r['status_floor_only_computed']}|{fmt(r['B8L2_mean'])}|{fmt(r['D10_mean'])}|")
    lines+=['','完整表同时提供中位数、标准差、四分位数、配对D10−B8L2分布、计算状态及缺失数。图片等权先在同一条件内算每图均值，再平均；不能和作答等权混用。D10仅方向尺度8→10，其余不变，绝非A10；升分不是准确性验证。', '',
        '文件：`current_261.json`完整元数据及独立暂停决定；`image_metadata.csv`逐图；`difficulty_by_condition.csv`难度；`scene_by_condition.csv`门洞/OOS交集；`difficulty_scene_by_condition.csv`交叉；`image_by_condition.csv`逐图条件；`record_audit.csv`逐作答资格/缺失原因；`SOURCE_HANDOFF.json`及`MODEL_PARAMETERS.json`冻结本次来源与参数。', '',
        '新增两图场景为not_recorded，不能称已确认普通场景。旧41图43空间的确认、29份顶界待核继续保留，参见[前轮逐图原因](../difficulty_b8l2_handoff_20261016/PENDING_SCOPE_AUDIT.md)。N/H未重算，也不据质量均值调整人工粗类。', '',
        '共享评分可能继续因多空间绑定规则更新；本报告仅代表SOURCE_HANDOFF所记录版本，重新运行本工具可接入最新包，旧共享快照由其所有者保留。未修改全局CURRENT以免破坏依赖259图基线的增量消费者。公共catalog/地图登记由统筹协调，待登记路径在FIELD_CONTRACT。', '',
        '复现：`python -m tools.thesis_main.analysis.difficulty_current_20261017`。本模块不执行归属规则或几何评分；数值可计算性与分析资格不混同。']
    (OUT/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(checks,ensure_ascii=False))


if __name__=='__main__':main()
