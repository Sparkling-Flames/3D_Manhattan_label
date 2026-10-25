#!/usr/bin/env python3
"""Use the existing frozen case exporter; save this new phase independently."""
from pathlib import Path
import importlib.util,hashlib,json
import pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
spec=importlib.util.spec_from_file_location('mechanism_export',ROOT/'cases/build_exchange_cases.py')
case=importlib.util.module_from_spec(spec);spec.loader.exec_module(case)

def main():
    event=pd.read_csv(HERE/'SELECTED_EVENT_EXACT.csv').iloc[0].to_dict()
    folder=case.export_case(event,HERE,ROOT/'native')
    case.plot_case(folder,HERE)
    (HERE/'CASE_SOURCE.json').write_text(json.dumps({'stage':'reverse_confirm_mechanism','event_id':event['event_id'],'data':'v2','source_commit':'972857b2b3f548316be215400e42d6ef6e639250','event_source':'design/reverse_confirm/EVENTS_EXACT.csv.gz','metric_source':'results/reverse_confirm/EVENT_METRICS.csv.gz','native_endpoint_source':'native/endpoints/'+event['pool_id']+'.json.gz','exporter_dependency':'../cases/build_exchange_cases.py','exporter_sha256':hashlib.sha256((ROOT/'cases/build_exchange_cases.py').read_bytes()).hexdigest(),'existing_four_cases_unchanged':True,'all_labels_used_for_event':False},ensure_ascii=False,indent=2))
    print('Saved reverse confirmation mechanism',event['event_id'],event['image'],flush=True)

if __name__=='__main__':main()
