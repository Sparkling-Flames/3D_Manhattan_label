"""Replay 38 unchanged historical controls; preserve numerical failures and nulls."""
from pathlib import Path
import math,sys
from common import read,save,csvwrite
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'frozen/scope_engine/core'))
from quality_v11 import score_geometry
def main():
    cases=read(ROOT/'inputs/controls38_frozen.json')['cases'];results=[];checks=[]
    for c in cases:
        r=score_geometry(c['annotation'],c['reference']);expected=c['expected_result'];errors=[];deltas=[]
        for key in ['status','reason_codes']:
            if key in expected and r[key]!=expected[key]:errors.append(key)
        for key,value in expected.get('metrics',{}).items():
            actual=r['metrics'].get(key)
            if isinstance(value,(int,float)) and not isinstance(value,bool):
                if actual is None:errors.append(key+'_missing')
                else:
                    delta=abs(value-actual);deltas.append(delta)
                    if not math.isclose(value,actual,rel_tol=1e-10,abs_tol=1e-9):errors.append(key+'_numeric')
            elif value is None and actual is not None:errors.append(key+'_unexpected_available')
        for key in ['quality_score']:
            value=expected.get(key);actual=r.get(key)
            if value is None or actual is None:
                if value!=actual:errors.append('Q_null')
            elif abs(value-actual)>1e-9:errors.append('Q_numeric')
        checks.append({'case_id':c['case_id'],'family':c['family'],'passed':not errors,'errors':errors,'max_numeric_delta':max(deltas,default=0),'expected_status':expected.get('status'),'actual_status':r['status']});results.append({'case_id':c['case_id'],'family':c['family'],'result':r})
    save(ROOT/'results/controls38_current_replay.json',results);csvwrite(ROOT/'results/controls38_replay_checks.csv',checks);summary={'cases':len(checks),'passed':all(r['passed'] for r in checks),'failed':sum(not r['passed'] for r in checks),'max_numeric_delta':max(r['max_numeric_delta'] for r in checks),'preserves_original_control_inputs':True,'Pro_controls_not_available':True};save(ROOT/'results/controls38_replay_summary.json',summary);print(summary)
    # A mismatch remains archived and visible; do not modify the frozen kernel to force success.
if __name__=='__main__':main()
