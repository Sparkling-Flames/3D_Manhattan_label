"""Run the current manifest loader before making derived evidence caches."""
import json
from paths import REPO,OUT
from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle

def main():
 bundle=load_current_bundle(REPO/'analysis_results/research_input_20261017/manifest.json')
 annotations=[o for o in bundle['data']['objects'] if o['object_kind']=='annotation']
 assert len(annotations)==3222 and bundle['manifest']['effective_input_revision']=='annotation_batch_98_20261017_v1'
 for name,obj in [('validated_annotations.json',annotations),('validated_images.json',bundle['data']['images']),('loader_receipt.json',dict(validation=bundle['validation'],manifest=bundle['manifest']))]:
  (OUT/name).write_text(json.dumps(obj,ensure_ascii=False),encoding='utf8')
 print(json.dumps(dict(validation=bundle['validation'],effective_input_revision=bundle['manifest']['effective_input_revision']),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
