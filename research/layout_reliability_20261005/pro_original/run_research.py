"""Recompute the frozen four-image study in a NEW directory. No network required."""
from pathlib import Path
import argparse,shutil,sys,json,hashlib
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'src'))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();target=a.out.resolve()
 if target.exists():raise SystemExit('Output directory must not exist; refusing to overwrite.')
 target.mkdir(parents=True)
 for d in ['inputs','evaluation','context']:shutil.copytree(ROOT/d,target/d)
 for d in ['results','logs']: (target/d).mkdir()
 import build_candidates,compression_study,mandatory_anchor,localize_failures,metric_study,witness_relaxation,refine_metrics
 for module in [build_candidates,compression_study,mandatory_anchor,localize_failures,metric_study,witness_relaxation,refine_metrics]:module.ROOT=target
 build_candidates.main()
 for image in ['2t7WUuJeko7-06','7y3sRwLe3Va-04']:compression_study.run(image)
 mandatory_anchor.run()
 rows=[]
 import pandas as pd
 for p in sorted((target/'inputs').glob('*.json')):
  r=json.loads(p.read_text());d=localize_failures.diagnostic(r['records']);compression_study.dump(target/'results/domain_locations'/p.name,d)
  rows.append(dict(image=r['image'],n=d['n'],non_single_valued_longitude_share=d['non_single_valued_longitude_share'],locations=json.dumps(d['merged_locations'])))
 pd.DataFrame(rows).to_csv(target/'results/domain_locations/summary.csv',index=False)
 metric_study.run();witness_relaxation.run();refine_metrics.run()
 print('Completed four-image recomputation:',target)
if __name__=='__main__':main()
