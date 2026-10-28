"""严格换类沿用原分层汇总；原参考池、新增参考池及合并范围分别报告。"""
import json
import subprocess
import sys
import numpy as np
import pandas as pd
from .rebuild_v21_20261028 import ROOT,OUT,read


def main():
    script=ROOT/'analysis_results/personnel_exchange_discrimination_audit_20261025/unpacked/02A/analysis/summarize_exchange.py'
    added={r['pool_id'] for r in read(OUT/'pools/DEPENDENCIES.json') if r['action']=='new_or_changed_pool'}
    checks=[]
    for stage in ['confirm','reverse_confirm']:
        result=OUT/'current_exchange_results'/stage;design=OUT/'current_exchange_design/design'/stage
        assert read(result/'COMPLETION.json')['complete']
        ev=pd.read_csv(design/'EVENTS_EXACT.csv.gz');metric=pd.read_csv(result/'EVENT_METRICS.csv.gz',low_memory=False)
        assert set(ev.event_id)==set(metric.event_id) and ev.event_id.is_unique and metric.event_id.is_unique
        for contrast,a,b in [('CA','C','A'),('CB','C','B'),('BA','B','A')]:
            assert np.allclose(metric['B8L2_'+contrast],metric[a+'_B8L2']-metric[b+'_B8L2'],atol=1e-8,equal_nan=True)
        for cohort,mask in [('combined',pd.Series(True,index=ev.index)),('original_reference',~ev.pool_id.isin(added)),('added_reference',ev.pool_id.isin(added))]:
            e=ev[mask].copy();d=metric[metric.event_id.isin(e.event_id)].copy()
            if not len(e):continue
            out=result/cohort;out.mkdir(exist_ok=True);e['reference_support']=cohort;e['data_release']='v2.1'
            e.to_csv(out/'EVENTS_EXACT.csv.gz',index=False,encoding='utf-8-sig');d.to_csv(out/'EVENT_METRICS.csv.gz',index=False,encoding='utf-8-sig')
            command=[sys.executable,'-X','utf8','-B',str(script),'--events',str(out/'EVENTS_EXACT.csv.gz'),'--metrics',str(out/'EVENT_METRICS.csv.gz'),'--output',str(out/'summary')]
            centers=design/'FOLD_ROLE_CENTERS.csv.gz'
            if centers.exists():command+=['--centers',str(centers)]
            subprocess.run(command,check=True)
            check=dict(data_release='v2.1',stage=stage,cohort=cohort,events=len(e),images=e.pool_id.nunique(),buildings=e.building.nunique(),three_arm_Q=int(d.ABC_scored.sum()),complete=True,
                comparison='current_LOBO_classification_frozen_confirmation_design',old_and_added_reference_support_separate=True)
            (out/'CHECKS.json').write_text(json.dumps(check,indent=2),encoding='utf8');checks.append(check)
    (OUT/'current_exchange_results/SUMMARY_CHECKS.json').write_text(json.dumps(checks,indent=2),encoding='utf8')


if __name__=='__main__':main()
