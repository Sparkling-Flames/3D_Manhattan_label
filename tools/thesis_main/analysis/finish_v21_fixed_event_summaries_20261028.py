"""冻结换类设计的剩余省略/背景增长/大人数尾段，复用原汇总函数。"""
import argparse
import json
import sys
import warnings
import pandas as pd
from types import SimpleNamespace,ModuleType
from .rebuild_v21_20261028 import ROOT,OUT
from .rescore_v21_discrimination_20261028 import BASE
from .measure_v21_current_exchange_20261028 import load


def main(stage):
    warnings.filterwarnings('ignore',category=pd.errors.PerformanceWarning)
    target=OUT/'event_reaggregation/discrimination'/stage;out=target/'summary'
    if stage=='target_omissions':
        sys.path.insert(0,str(BASE/'02A/analysis'))
        stub=ModuleType('run_native');stub.ROOT=BASE/'03';stub.POP=ROOT
        stub.read=stub.save=stub.csv=None;sys.modules['run_native']=stub
        module=load(BASE/'03/analysis/analyze_target_omissions.py','v21_target_omissions')
        sys.argv=['analyze_target_omissions','--m6-metrics',str(target/'EVENT_METRICS.csv.gz'),'--m7-metrics',*[str(OUT/'event_reaggregation/discrimination'/s/'EVENT_METRICS.csv.gz') for s in ['screen','confirm']],'--output',str(out)]
        module.main()
    else:
        name='analyze_fixed_block_paths.py' if stage=='size_paths' else 'analyze_ac_tail.py'
        module=load(BASE/'05/analysis'/stage/'code'/name,'v21_'+stage)
        if stage=='size_paths':module.sha=lambda p:None
        else:
            module.hp.sha=lambda p:None
            module.ROOT=ROOT
        module.main(SimpleNamespace(design=str(BASE/'05/design'/stage),metrics=str(target/'EVENT_METRICS.csv.gz'),output=str(out),prepare=False,allow_partial=False,no_plots=True))
    (out/'V21_PROVENANCE.json').write_text(json.dumps(dict(data_release='v2.1',frozen_design_and_members=True,current_reference_metrics=True,extra_file_hashes=False,new_fusion=0,omission_direct_geometry_comparisons='unchanged_original_geometry_analysis_not_recomputed' if stage=='target_omissions' else None),indent=2),encoding='utf8')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['size_paths','large_team_ac_tail','target_omissions']);main(p.parse_args().stage)
