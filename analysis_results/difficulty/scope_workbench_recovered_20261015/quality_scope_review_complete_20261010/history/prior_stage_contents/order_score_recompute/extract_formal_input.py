#!/usr/bin/env python3
"""Read and validate one formal bundle in an isolated process; never change it."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path

def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    repo=a.repo.resolve();sys.path.insert(0,str(repo))
    from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
    from tools.thesis_main.data_prep.materialize_current_research_input import load_current_input
    from tools.thesis_main.data_prep.project_public_research_20260929 import project_bundle
    b=load_current_bundle();assert b['data']==load_current_input()
    panel,mapping=project_bundle(b)
    selected='yqstnuAEVhm-07';objects=[o for o in b['data']['objects'] if o['image_code']==selected]
    paths=['analysis_results/research_input_20260929/'+n for n in ['preprocessed_source.json','comments.json','research_tables.json','manifest.json','quality_update_20261010.json']]
    protected=['original_export_points','before_preprocessing_points','preprocessed_points','point_labels','links_zero_based','worker_id','condition','cleaning_disposition','independent_vote_eligible','worker_quality_gate','main_quality_gate','main_consensus_gate','source','review']
    data={'schema':'order_score_formal_input_snapshot_v1','source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),'validation':b['validation'],'both_loaders_identical':True,'file_sha256':{n:sha(repo/n) for n in paths},'input_revision':b['data'].get('quality_update_revision'),'order_revision':b['data'].get('order_update_revision'),'object_digests':{o['object_id']:digest(o) for o in b['data']['objects']},'protected_object_digests':{o['object_id']:digest({k:o.get(k) for k in protected}) for o in b['data']['objects']},'image':next(i for i in b['data']['images'] if i['image_code']==selected),'objects':objects,'aliases':{o['object_id']:mapping['records'][o['object_id']] for o in objects},'panel_image':next(i for i in panel['images'] if i['code']==selected)}
    a.out.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(data['source_commit'],data['validation'])
if __name__=='__main__': main()
