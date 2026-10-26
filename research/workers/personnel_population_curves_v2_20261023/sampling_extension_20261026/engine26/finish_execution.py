"""After both native stages close, verify exact artifacts and write final ledger."""
from pathlib import Path
import argparse, json, time
from execute_extension import savejson
from validate_execution_shards import validate
from summarize_execution import run as summarize


def run(base, wait=False, poll_seconds=30):
    base=Path(base)
    prerequisites=[base/'new_endpoints26'/f'stage{s}'/'PREFIX_COMPILE_RECEIPT.json' for s in (1,2)]
    while not all(p.exists() for p in prerequisites):
        if not wait:raise FileNotFoundError([str(p) for p in prerequisites if not p.exists()])
        time.sleep(min(60,max(1,poll_seconds)))
    t=time.monotonic()
    validation=validate(base,stages=(1,2),allow_partial=False)
    ledger=summarize(base,require_complete=True)
    assert validation['unique_new_endpoints']==ledger['completed_new_unique_endpoints']
    assert validation['prefix_rows']==ledger['registration_counts']['prefix_rows']
    result=dict(complete=True,new_unique_endpoints=validation['unique_new_endpoints'],
        new_prefix_occurrences=validation['prefix_rows'],
        native_part_count=validation['native_part_count'],
        exact_request_scalar_geometry_keys_joined=True,all_contents_read_to_EOF=True,
        elapsed_final_checks_seconds=time.monotonic()-t,
        execution_validation='new_endpoints26/COMPLETE_EXECUTION_VALIDATION.json',
        execution_ledger='new_endpoints26/FINAL_EXECUTION_LEDGER.json')
    savejson(base/'new_endpoints26/POSTEXEC_RECEIPT.json',result)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True)
    p.add_argument('--wait',action='store_true');p.add_argument('--poll-seconds',type=int,default=30)
    a=p.parse_args();print(json.dumps(run(a.base,a.wait,a.poll_seconds)))
