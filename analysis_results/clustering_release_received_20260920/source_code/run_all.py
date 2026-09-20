#!/usr/bin/env python3
"""One entrypoint for RC1 history and new independent canonical submissions."""
from pathlib import Path
import argparse,json,hashlib,time,platform,sys
import numpy as np,pandas as pd,scipy
from release import main,CONFIG,writejson
from diagnostics import run as diagnose
from history_analysis import run_history,run_composition,run_rooms,run_prediction
from extra_checks import run as check
from analysis_extensions import run as extend
from composition_sensitivity import run as composition_sensitivity

def run():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--out',type=Path);p.add_argument('--new-responses',type=Path);p.add_argument('--config',type=Path);p.add_argument('--skip-models',action='store_true');p.add_argument('--permutations',type=int,default=128);a=p.parse_args()
 root=a.root.resolve();out=(a.out or root/'results/release').resolve()
 if out==root or root/'input' in out.parents:raise ValueError('Output overlaps frozen inputs')
 if a.config and json.loads(a.config.read_text())!=CONFIG:raise ValueError('Configuration differs from RC1; create a new version before comparison')
 if a.permutations<2:raise ValueError('At least two replay permutations')
 start=time.time();main(root,out,a.new_responses)
 if not a.new_responses:diagnose(root,out)
 else:writejson(out/'NEW_DATA_EVIDENCE_BOUNDARY.json',{'historical_review_registry_not_promoted_to_new_labels':True,'cross_person_correspondences_need_versioned_review':True})
 cache=run_history(root,out,a.permutations,a.new_responses);run_composition(root,out,cache);run_rooms(root,out,cache)
 if not a.skip_models:run_prediction(root,out,cache)
 if not a.new_responses:
  check(root,out);extend(root,out)
 composition_sensitivity(root,out)
 writejson(out/'EXECUTION.json',dict(finished=True,elapsed_seconds=time.time()-start,python=sys.version,numpy=np.__version__,pandas=pd.__version__,scipy=scipy.__version__,new_response_input_sha256=hashlib.sha256(a.new_responses.read_bytes()).hexdigest() if a.new_responses else None,source_commit=CONFIG['source_commit'],visual_review_performed=False,figures_generated_separately=True))
if __name__=='__main__':run()
