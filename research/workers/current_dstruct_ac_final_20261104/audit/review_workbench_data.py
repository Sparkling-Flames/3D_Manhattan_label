"""Independently check the offline workbench payload against frozen CSV sources."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess

import pandas as pd

HERE=Path(__file__).resolve().parent
STUDY=HERE.parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    html_path=STUDY/'workbench/index.html'
    html=html_path.read_text(encoding='utf-8')
    raw=re.search(r'<script id="ac-data" type="application/json">(.*?)</script>',html,re.S).group(1)
    data=json.loads(raw)
    checks=[];failures=[]
    mapping={'summary':'SIX_DIRECTION_Q_BY_BUDGET.csv','images':'MAIN_IMAGE_EFFECTS.csv.gz','strata':'CONDITION_STRATIFIED_Q.csv'}
    hashes={str(html_path.relative_to(STUDY)):digest(html_path),'build_workbench.py':digest(STUDY/'build_workbench.py')}
    for name,source in mapping.items():
        path=STUDY/'analysis'/source
        frame=pd.read_csv(path,low_memory=False)
        hashes['analysis/'+source]=digest(path)
        rows=data[name];bad=0;missing=0
        if len(rows)!=len(frame):failures.append({'check':'row_count','table':name,'actual':len(rows),'expected':len(frame)})
        for i,row in enumerate(rows):
            if i>=len(frame):break
            for key,value in row.items():
                if key not in frame:bad+=1;continue
                expected=frame.iloc[i][key]
                if pd.isna(expected):
                    missing+=1
                    if value is not None:bad+=1
                elif isinstance(expected,(float,int)) and isinstance(value,(float,int)):
                    if abs(float(expected)-float(value))>1e-12:bad+=1
                elif expected!=value:bad+=1
        if bad:failures.append({'check':'payload_source_identity','table':name,'mismatched_cells':bad})
        checks.append({'check':'payload_source_identity','table':name,'rows':len(rows),'columns':len(rows[0]) if rows else 0,'missing_cells_preserved_as_null':missing,'mismatches':bad})
        if set(frame.condition.dropna())!={'manual'}:failures.append({'check':'single_condition','table':name})
    # The embedded image table is a common-Q table; zero-support summary rows
    # remain available, while no missing-Q image is converted to a scored row.
    summary=pd.DataFrame(data['summary']);images=pd.DataFrame(data['images']);strata=pd.DataFrame(data['strata'])
    image_missing=int(images[['dQ','Q_A','Q_C','abs_dQ']].isna().sum().sum())
    if image_missing:failures.append({'check':'common_Q_image_data_contract','missing':image_missing})
    empty=summary.loc[summary.images.eq(0)]
    if empty.image_equal_mean.notna().any():failures.append({'check':'empty_summary_mean','detail':'numeric mean in no-Q support'})
    keys=['analysis_cohort','version','scope','support','n','m']
    for name,frame,key in [('summary',summary,keys+['direction']),('images',images,keys+['class_pair','image']),('strata',strata,[x for x in keys if x!='support']+['direction','stratum_type','stratum'])]:
        duplicates=int(frame.duplicated(key).sum())
        checks.append({'check':'UI_filter_key_unique','table':name,'duplicates':duplicates})
        if duplicates:failures.append({'check':'UI_filter_key_unique','table':name,'duplicates':duplicates})
    proc=subprocess.run(['node',str(HERE/'workbench_vm_review.cjs')],text=True,encoding='utf-8',capture_output=True)
    vm_path=HERE/'WORKBENCH_JS_REVIEW.json'
    js=json.loads(vm_path.read_text(encoding='utf-8')) if vm_path.exists() else {'status':'failed','stderr':proc.stderr}
    if proc.returncode or js.get('status')!='passed':failures.append({'check':'actual_javascript_transforms','detail':js,'stderr':proc.stderr})
    result={'status':'passed' if not failures else 'failed','source_hashes':hashes,
            'checks':checks,'summary_rows':len(summary),'image_rows':len(images),'strata_rows':len(strata),
            'empty_common_support_summary_rows':len(empty),'numeric_image_missing_cells':image_missing,
            'javascript_review':js,'failures':failures,
            'scope_note':'Data provenance, actual JS direction transforms, selector support guards and missing preservation were checked. This receipt does not claim browser visual-layout testing.'}
    (HERE/'WORKBENCH_DATA_REVIEW.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':result['status'],'summary_rows':len(summary),'image_rows':len(images),'strata_rows':len(strata),'failures':len(failures),'javascript_checks':js.get('checks')},ensure_ascii=False,indent=2))
    if failures:raise SystemExit(1)


if __name__=='__main__':main()
