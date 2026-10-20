"""Evaluate the entire frozen direct-m2 family; never select from assessment."""
import argparse,gzip,json,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);a=p.parse_args();root=a.root.resolve();out=root/'audit_corner/direct_block_assessment';out.mkdir(parents=True,exist_ok=True)
q=json.load(gzip.open(root/'audit_learning/fresh_blocks/fresh_block_requests.json.gz','rt'));manifest=json.loads((root/'audit_learning/block_fit/METHOD_MANIFEST.json').read_text());baseline='R_directswap_geometry_partition_b2_K2__ordinary_new__mixed_history_v1'
assert set(manifest)=={'B_direct_m2_composition_K2','B_direct_m2_composition_K3'}
for mid,info in sorted(manifest.items()):
 dest=out/mid;dest.mkdir(exist_ok=True);override=dest/'LABEL_OVERRIDE.json'
 labels={w:c for c,workers in info['classes'].items() for w in workers}
 override.write_text(json.dumps({'primary_method':mid,'label_maps':{mid:labels,baseline:q['label_maps'][baseline]},'interpretation':'Full prespecified-family internal outcome check. Failed history CV recommendation is frozen; no assessment reselection.'},indent=2))
 subprocess.run([sys.executable,str(Path(__file__).with_name('evaluate_common_library.py')),'--requests',str(root/'audit_learning/fresh_blocks/fresh_block_requests.json.gz'),'--native',str(root/'audit_replay/fresh_corner_blocks'),'--reuse-pairs',str(root/'audit_corner/common_library/COMMON_ENDPOINT_PAIRS.csv.gz'),'--labels-json',str(override),'--out',str(dest),'--phase','full_prespecified_family_internal_outcome_check_no_reselection'],check=True)
