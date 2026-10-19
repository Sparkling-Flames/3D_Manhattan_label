#!/usr/bin/env python3
"""Recreate the identical analysis input using an atomic, verified CSV export.

The first direct gzip export had an incomplete stream tail when opened by an
independent reader. No incomplete file is used for reported numerical results.
"""
from pathlib import Path
import gzip,hashlib,json,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sys.path.insert(0,str(HERE));sys.path.insert(0,str(ROOT/'forward'))
from evaluate_common import events,labels,add_history,savej
from atomic_exports import csv_verified
def main():
    p=HERE/'COMMON_EVENT_ANALYSIS_INPUT.csv.gz';before={'path':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    try:
        with gzip.open(p,'rb') as f:
            while f.read(1024*1024):pass
        before['gzip_crc']='PASS'
    except Exception as err:before['gzip_crc']=repr(err)
    e=events();l,old=labels();e=add_history(e,old)
    info=csv_verified(e,p)
    savej(HERE/'ANALYSIS_INPUT_EXPORT_RECOVERY.json',{'before':before,'recovery':info,'changes_to_formulas_or_rows':False,'new_source':'same frozen common_events and exact archived outer historical profiles','actual_rows':len(e)})
    print(json.dumps(info),flush=True)
if __name__=='__main__':main()
