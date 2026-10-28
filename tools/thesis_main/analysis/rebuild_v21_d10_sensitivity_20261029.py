"""原D10形成链敏感性：更新输入/楼外基线及既有有限团队评分，不新增融合。"""
import argparse
import gzip
import json
import shutil
import types
from pathlib import Path
import numpy as np
import pandas as pd
from .rebuild_v21_20261028 import ROOT,OUT,read
from .refit_v21_joint_history_20261028 import modules

TARGET=OUT/'d10_formation_sensitivity'
SOURCE=TARGET/'current_B8_source'
CONFIG=TARGET/'configuration_inputs'
TOOLS=Path(__file__).parent


def load(name,replacements=()):
    path=TOOLS/(name+'.py');text=path.read_text(encoding='utf8')
    for a,b in replacements:
        assert text.count(a)==1,(name,a);text=text.replace(a,b)
    module=types.ModuleType('v21_'+name);module.__file__=str(path)
    exec(compile(text,str(path),'exec'),module.__dict__)
    module.OUT=TARGET;module.SOURCE=SOURCE;module.CONFIG=CONFIG
    return module


def prepare():
    SOURCE.mkdir(parents=True,exist_ok=True);CONFIG.mkdir(exist_ok=True)
    labels=pd.read_csv(OUT/'joint_history_classification/ALL_METHOD_LABELS_LOBO.csv.gz',low_memory=False)
    joint=labels[labels.method.eq('V3_JOINT_QT')]
    joint[joint.heldout_building.eq('ALL')].to_csv(SOURCE/'JOINT_LABELS_ALL_DATA.csv',index=False)
    joint[joint.heldout_building.ne('ALL')].to_csv(SOURCE/'JOINT_LABELS_LOBO.csv.gz',index=False)
    labels[labels.method.eq('V3_BEHAVIOR')&labels.heldout_building.ne('ALL')].to_csv(SOURCE/'LABELS_LOBO.csv.gz',index=False)
    choices=[read(p) for p in sorted((OUT/'joint_history_classification').glob('*_SELECTION.json'))]
    assert len(choices)==46
    (SOURCE/'JOINT_SELECTED_MODELS.json').write_text(json.dumps(choices,ensure_ascii=False,indent=2),encoding='utf8')
    frozen=ROOT/'research/workers/personnel_mixture_comparison_20261022/configurations'
    for name in ['PANELS_USED.csv','PANEL_TEAMS.csv.gz']:shutil.copy2(frozen/name,CONFIG/name)
    patches={}
    for path in (OUT/'composition_rescore').rglob('*.jsonl.gz'):
        with gzip.open(path,'rt',encoding='utf8') as f:
            for line in f:
                r=json.loads(line);assert r['team_key'] not in patches;patches[r['team_key']]=r
    affected={r['pool_id'] for r in read(OUT/'pools/DEPENDENCIES.json') if r['action']=='reuse_geometry_rescore'}
    counts={}
    for condition in ['manual','semi']:
        d=pd.read_csv(frozen/f'ENDPOINT_OUTCOMES_{condition}.csv.gz',low_memory=False).set_index('team_key',drop=False)
        wanted=set(d[d.pool_id.isin(affected)].index);assert wanted<=patches.keys()
        for key in wanted:
            r=patches[key]
            assert r['k']==d.at[key,'k']
            for metric in ['B8L2','D10','iou_2d','IoU3D100','S_bottom_deg','dir','Hmean','Hcenter']:
                d.at[key,metric]=r.get(metric)
            assert bool(d.at[key,'failure'])==(r.get('B8L2') is None)
        d['data_release']='v2.1';d.to_csv(CONFIG/f'ENDPOINT_OUTCOMES_{condition}.csv.gz',index=False,encoding='utf-8-sig')
        counts[condition]=dict(teams=len(d),updated=len(wanted))
    (TARGET/'INPUT_CHECKS.json').write_text(json.dumps(dict(data_release='v2.1',baseline='current_v21_B8_labels_and_selected_models',finite_design='frozen336panels_924teams_each',endpoints=counts,new_fusion=0),indent=2),encoding='utf8')


def main(stage):
    if stage=='prepare':prepare();return
    if stage=='formation':
        module=load('personnel_d10_formation_sensitivity_20261024',[("ROOT / \"research/quality/quality_b8l2_d10_20261017/quality_records.csv\"","ROOT / 'research/data/releases/v2.1/quality_records.csv'")])
        base,joint=modules();raw=pd.read_csv(OUT/'joint_history_classification/BEHAVIOR_RECORDS.csv.gz',low_memory=False)
        base.load=lambda:raw.copy();module.behavior=base;module.joint=joint;module.FOLDS=TARGET/'formation/folds'
    elif stage=='response':module=load('personnel_d10_panel_response_20261024')
    elif stage=='summary':module=load('personnel_d10_response_summary_20261024',[("OUT.parent / \"personnel_mixture_comparison_20261022/configurations\"","OUT / 'configuration_inputs'")])
    elif stage=='structure':module=load('personnel_d10_structure_role_20261024')
    else:raise ValueError(stage)
    module.main()
    (TARGET/(stage.upper()+'_COMPLETE.json')).write_text(json.dumps(dict(data_release='v2.1',complete=True,stage=stage,no_new_fusion=True,baseline='current_v21_B8L2',original_label_strings_retained_for_reader_compatibility=True)),encoding='utf8')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare','formation','response','summary','structure']);main(p.parse_args().stage)
