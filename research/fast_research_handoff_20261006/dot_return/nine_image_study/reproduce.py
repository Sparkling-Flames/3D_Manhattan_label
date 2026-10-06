import argparse
from run_study import run
from check_study import audit
from summarize_results import summarize

p=argparse.ArgumentParser();p.add_argument('--out',required=True);args=p.parse_args()
run(args.out);audit(args.out);summarize(args.out)
