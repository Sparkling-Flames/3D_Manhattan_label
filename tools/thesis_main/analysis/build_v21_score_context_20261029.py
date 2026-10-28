"""登记v2.1显式评分入口；原始bundle保持原字节，不推进CURRENT。"""
import json
import shutil
import pandas as pd
from .rebuild_v21_20261028 import ROOT,OUT,read
from .current_annotation_context_20261017 import load_scored_context
from ..data_prep.consolidate_research_input import load_current_bundle


def main():
    inventory=pd.DataFrame(read(OUT/'quality_inventory.json'))
    binding=pd.DataFrame(read(OUT/'reference_bindings.json'))
    for name,frame in [('quality_inventory',inventory),('reference_bindings',binding),('quality_records',inventory[inventory.quality_usable])]:
        frame=frame.copy()
        for col in frame:
            if frame[col].dtype=='object':frame[col]=frame[col].map(lambda v:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v)
        frame.to_csv(OUT/(name+'.csv'),index=False,encoding='utf-8-sig')
    metadata=dict(version='quality_workers_v21_20261028',data_release='v2.1',primary_metric='B8L2',parallel_metric='D10',n1_applied=False,
        counts=dict(inventory=len(inventory),quality_rows=int(inventory.quality_usable.sum()),quality_images=int(inventory.loc[inventory.quality_usable,'image_id'].nunique()),computed=int(inventory.score_status.eq('complete').sum())),
        full_inventory_with_metric_eligibility=str((OUT/'quality_inventory.csv').relative_to(ROOT).as_posix()),
        all_pre_score_bindings=str((OUT/'reference_bindings.csv').relative_to(ROOT).as_posix()),
        recommended_qualified_scores=str((OUT/'quality_records.csv').relative_to(ROOT).as_posix()),
        reference_catalog=str((OUT/'reference_catalog.json').relative_to(ROOT).as_posix()),
        difficulty_records=str((OUT/'difficulty_records.json').relative_to(ROOT).as_posix()))
    (OUT/'CROSS_MODULE_INPUTS.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf8')
    source=OUT.parent/'v2/analysis_input';target=OUT/'analysis_input';target.mkdir(exist_ok=True)
    original=read(source/'manifest.json')
    # loader要求bundle入口留在同一目录；仅复制未改动的冻结原始输入。
    for relative in original['entrypoints'].values():
        src=source/relative;dst=target/relative
        if not dst.exists():shutil.copy2(src,dst)
        assert dst.stat().st_size==src.stat().st_size
    manifest={k:original[k] for k in ['schema','contract_version','entrypoints']}
    manifest.update(data_release='v2.1',effective_input_revision='reviewed_references_v21_20261028',base_manifest=str((source/'manifest.json').relative_to(ROOT).as_posix()),
        annotation_inventory_release='v2',raw_annotations_unchanged=True,status='current_quality_context_ready_other_stages_in_progress',
        score_context=str((OUT/'CROSS_MODULE_INPUTS.json').relative_to(ROOT).as_posix()),
        reference_catalog='../reference_catalog.json',difficulty_records='../difficulty_records.json',reference_bindings='../reference_bindings.json',
        consumer_rule='原始作答/采集和评论复用v2；质量、参考和当前难度须通过load_scored_context读取v2.1。研究统计见各专题收据；本manifest不代表全流程验收。')
    (target/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    bundle=load_current_bundle(target/'manifest.json');context=load_scored_context(bundle)
    assert len(context['quality_records'])==10439 and sum(r['quality_usable'] for r in context['quality_records'])==8154
    checks=dict(data_release='v2.1',full_bundle_validation=bundle['validation'],current_context_identity_masks_bindings_passed=True,raw_annotations_unchanged=True,current_pointer_advanced=False,file_hashes_computed=False)
    (OUT/'SCORE_CONTEXT_CHECKS.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(metadata['counts']),flush=True)


if __name__=='__main__':main()
