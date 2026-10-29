"""Copy a frozen execution plan and relocate only paths used to open inputs.

The original plan and all scientific hashes, member identities, reference hashes,
acquisition decisions and original provenance paths remain unchanged. This is
for reproducing the package under a different workspace root.
"""
from __future__ import annotations
import argparse,json,shutil
from pathlib import Path
from ac_endpoint_runtime import read_json,sha,write_json

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--source-plan',required=True)
    ap.add_argument('--destination-plan',required=True);ap.add_argument('--old-workspace-root',required=True)
    ap.add_argument('--new-workspace-root',required=True);ap.add_argument('--verify-inputs',action='store_true');a=ap.parse_args()
    source=Path(a.source_plan).resolve();dest=Path(a.destination_plan).resolve()
    old=Path(a.old_workspace_root).resolve();new=Path(a.new_workspace_root).resolve()
    assert source!=dest and not dest.exists(),'Destination must be new; the frozen source is never overwritten.'
    contract=read_json(source/'ENGINE_AND_INPUT_CONTRACT.json');plan=read_json(source/'CACHE_PLAN.json')
    before_contract=json.loads(json.dumps(contract));before_plan=json.loads(json.dumps(plan));changes=[]
    def relocated(value,label):
        value=str(value);p=Path(value)
        if not p.is_absolute():return value
        try:relative=p.relative_to(old)
        except ValueError:raise ValueError('Opening path is outside supplied old root: '+label+' '+value)
        result=str(new/relative);changes.append({'field':label,'old':value,'new':result});return result
    contract['engine_root']=relocated(contract['engine_root'],'engine_root')
    for i,row in enumerate(contract['pool_sources']):row['path']=relocated(row['path'],f'pool_sources[{i}].path')
    plan['requests_file']=relocated(plan['requests_file'],'requests_file')
    if a.verify_inputs:
        assert sha(plan['requests_file'])==plan['requests_sha256']
        for row in contract['pool_sources']:assert sha(row['path'])==row['sha256']
        for row in contract['engine_files']:assert sha(Path(contract['engine_root'])/row['path'])==row['sha256']
    for key in ['engine_digest','engine_files','runtime','pool_hashes','reference_hashes']:assert contract[key]==before_contract[key]
    for key in plan:
        if key!='requests_file':assert plan[key]==before_plan[key]
    shutil.copytree(source,dest)
    write_json(dest/'ENGINE_AND_INPUT_CONTRACT.json',contract);write_json(dest/'CACHE_PLAN.json',plan)
    receipt={'source_plan':str(source),'destination_plan':str(dest),'opening_path_changes':changes,
      'original_source_contract_sha256':sha(source/'ENGINE_AND_INPUT_CONTRACT.json'),
      'original_cache_plan_sha256':sha(source/'CACHE_PLAN.json'),
      'original_provenance_paths_in_endpoint_rows_preserved':True,
      'all_semantic_identities_and_acquisition_decisions_unchanged':True,
      'all_scientific_input_hashes_unchanged':True,'inputs_verified':a.verify_inputs,
      'no_fusion_scoring_label_fit_or_team_creation':True}
    write_json(dest/'RELOCATION_RECEIPT.json',receipt);print(json.dumps(receipt),flush=True)

if __name__=='__main__':main()
