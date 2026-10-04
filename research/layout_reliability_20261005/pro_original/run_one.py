"""All-selected-roster, no-GT prototype for a handoff-format input JSON."""
from pathlib import Path
import argparse,sys,json
import numpy as np
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'src'))
from arc_consensus import fuse,footprint
from compression_study import circular_costs,make_candidate,bottom_turns
from continuous_metrics import depth_height_change,fixed_longitude,witness_and_provenance

def main():
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out',type=Path,required=True)
 p.add_argument('--edit-policy',choices=['none','pixel_only','bottom_locked'],default='none');p.add_argument('--epsilon',type=float,default=.5);p.add_argument('--max-exact-knots',type=int,default=250);a=p.parse_args()
 if a.out.exists():raise SystemExit('Refusing to overwrite output')
 raw=json.loads(a.input.read_text(encoding='utf-8'));records=raw['records'];result=fuse(records)
 if a.edit_policy!='none' and result['status']=='ok_conditional_representation':
  e=result['methods'][result['bev_mv50_complete_method']]
  if e['pair_count']>a.max_exact_knots:result['editor']={'status':'not_run','reason':'declared_computational_knot_budget','exact_preserved':True}
  else:
   lock=a.edit_policy=='bottom_locked';start=bottom_turns(e)[0] if lock else 0
   c=make_candidate(e,a.epsilon,circular_costs(e),start,lock);result['editor']=c
   result['editor_audit']={**fixed_longitude(c,e),**depth_height_change(c,e),'column_witnesses':witness_and_provenance(c,records,e['erp_threshold'])}
   if lock:result['editor']['anchor_rule']='mandatory bottom-break anchor'
 a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
