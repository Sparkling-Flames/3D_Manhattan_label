"""保留原scope回答与门槛，更新难度分组后重拟合联合scope和轴对照。"""
import importlib.util
import json
import sys
from types import SimpleNamespace
import numpy as np
import pandas as pd
from .rebuild_v21_20261028 import OUT, ROOT, read

SOURCE=ROOT/'analysis_results/personnel_exchange_discrimination_audit_20261025/unpacked'
TARGET=OUT/'scope_axis_classification'


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module


def main():
    TARGET.mkdir(exist_ok=True)
    old=SOURCE/'01/features_scope'
    d=pd.read_csv(old/'SCOPE_RECORDS_WITH_OPPORTUNITIES.csv.gz',low_memory=False)
    quality=pd.DataFrame(read(OUT/'quality_inventory.json')).set_index('object_id')
    diff={r['image_id']:r['current_class'] for r in read(OUT/'difficulty_records.json')['records']}
    before=d.difficulty_coarse.copy();d['difficulty_coarse']=d.image_id.map(diff)
    for field in ['quality_usable','quality_use']:d[field]=d.object_id.map(quality[field])
    source=(old/'build_scope_features.py').read_text(encoding='utf-8')
    native=load('v21_scope_features',old/'build_scope_features.py')
    start=source.index(' # Same person-image-condition');end=source.index(" evidence={'actual_commit'")
    block='\n'.join(line[1:] if line.startswith(' ') else line for line in source[start:end].splitlines())
    namespace=dict(d=d,out=TARGET,np=np,pd=pd,summarize=native.summarize)
    exec(compile(block,str(old/'build_scope_features.py'),'exec'),namespace)
    core=load('build_condition_response_classes',SOURCE/'03/classifications/code/build_condition_response_classes.py')
    core.save_json=lambda obj,path:path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
    core.sha=lambda path:None
    scope=load('v21_scope_increment',SOURCE/'03/classifications/code/build_scope_increment.py')
    axes=load('v21_axes',SOURCE/'03/classifications/code/build_axis_controls.py')
    features=OUT/'condition_classification/HISTORY_FEATURES_ALL_LOBO.csv.gz'
    scope.main(SimpleNamespace(output=str(TARGET),features=str(features),scope=str(TARGET/'SCOPE_FEATURES_ALL_LOBO.csv.gz'),feature_output=str(TARGET)))
    axes.main(SimpleNamespace(output=str(TARGET),features=str(features)))
    for name in ['SCOPE_INCREMENT_LABELS_ALL_LOBO.csv.gz','AXIS_METHOD_LABELS_ALL_LOBO.csv.gz']:
        labels=pd.read_csv(TARGET/name);labels['underlying_data_version']='v2.1';labels.to_csv(TARGET/name,index=False,encoding='utf-8-sig')
    receipt=read(TARGET/'SCOPE_INCREMENT_RECEIPT.json');receipt['underlying_data_version']='v2.1';receipt.pop('scope_sha256',None)
    receipt['scope_input_note']='复用原逐对象回答及286条历史恢复，仅更新当前难度分组及资格诊断；不将scope回答当正确率。'
    (TARGET/'SCOPE_INCREMENT_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    (TARGET/'CHECKS.json').write_text(json.dumps(dict(records=len(d),difficulty_changed_records=int((before.fillna('')!=d.difficulty_coarse.fillna('')).sum()),
        scope_answers_reused=True,target_building_excluded_before_residual=True,new_fusion=0),ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
