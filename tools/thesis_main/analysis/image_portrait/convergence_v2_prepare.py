"""Recover verified prior computations into a NEW output namespace."""
import json,hashlib,platform
from pathlib import Path
import numpy as np,pandas as pd
from tools.thesis_main.analysis.image_portrait.convergence_v2_common import *

def fast_features(pm):
    dest=FOUND/'features';dest.mkdir(exist_ok=True)
    ids=sorted({r['image_id'] for r in core.load(BUNDLE/'human/responses.jsonl.gz')})
    # Reuse finished previous-method arrays. Only missing global DA3 means are
    # reconstructed; each NPZ key is read lazily, without decoding huge local grids.
    for layer in (5,7,9,11):
        path=dest/f'C_da3_layer{layer}_global.npz'
        if path.exists():continue
        vals=[]
        for i in ids:
            with np.load(ROOT.parent/'numerics'/f'features/da3/{i}.npz',allow_pickle=False) as z:
                vals.append(np.mean([z[f'{f}_view0_out_layer_{layer}_global'] for f in pm.FACES],axis=0))
        np.savez_compressed(path,image_ids=np.array(ids),X=np.asarray(vals,np.float32))
    reg={}
    for path in sorted(dest.glob('*.npz')):
        with np.load(path,allow_pickle=False) as z:reg[path.stem]=dict(file=path.name,dimensions=z['X'].shape[1],rows=z['X'].shape[0])
    core.write_json(dest/'registry.json',reg)

def run():
 OUT.mkdir(parents=True,exist_ok=True);FOUND.mkdir(exist_ok=True)
 prior=[dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in OLD.rglob('*') if p.is_file()]
 js('audit/preceding_results_preservation.json',dict(files=prior,existing_prior_file_count=len(prior),note='Only files actually available from previous turn are preserved; no claim to have recovered unmounted old intermediate outputs.'))
 core.OUT=FOUND
 if not (FOUND/'human/dense_boundaries.npz').exists():core.run(skip_stability=True)
 from tools.thesis_main.analysis.image_portrait import pro_models as pm
 pm.OUT=FOUND
 if not (FOUND/'B/model_feedback.csv').exists():pm.model_feedback()
 # Preserve existing candidate representations. Deterministic numeric pooling only.
 fast_features(pm)
 orig=pd.read_csv(OLD/'human/response_metrics.csv.gz');new=read_responses()
 columns=['quality','active_seconds','effective_point_count','band_width_bias_pixels']
 audit=[]
 for c in columns:
  a=orig.set_index('canonical_annotation_id')[c].sort_index();b=new.set_index('canonical_annotation_id')[c].sort_index()
  audit.append(dict(column=c,rows=len(a),missing_identical=bool(a.isna().equals(b.isna())),max_abs_delta=float((a-b).abs().max())))
 csv('audit/recomputed_outcomes_vs_preserved.csv',audit)
 # Three separate image evidence layers; do NOT infer human accuracy from AI fields.
 rows=[];relationships=core.load(BUNDLE/'metadata/relationships.jsonl');rm=room_map()
 for s in core.load(BUNDLE/'metadata/spatial_history.jsonl.gz'):
  initial=s.get('spatial_classification')or{};prior=s.get('spatial_prior_user')or{};coverage=s.get('review_coverage')or{}
  source=s.get('spatial_field_sources')or{};current=s.get('current_coarse_review')or{}
  rows.append(dict(image_id=s['image_id'],building=s['building'],scene_human_adopted=initial.get('coarse_type') or prior.get('user_type') or 'unknown',scene_initial_human=prior.get('user_type')or'unknown',scene_provenance=source.get('coarse_type','unknown'),initial_classification_human_reviewed=coverage.get('initial_spatial_classification_personally_reviewed',False),current_coarse_separate=current.get('value','unknown'),current_coarse_source=current.get('source','unknown'),room_id=rm.get(s['image_id'],('unknown','not_in_supported_graph'))[0],relation_status=rm.get(s['image_id'],('unknown','not_in_supported_graph'))[1]))
 csv('images/evidence_layers.csv',rows)
 js('audit/preparation.json',dict(input_commit=core.COMMIT,method='followup_exploration_not_independent_validation',seed=SEED,python=platform.python_version(),original_images_read=False,visual_inference=False,weights_downloaded=False,old_results_overwritten=False,chronological_arrival_order='Not exported in bundled responses; all growth curves are explicitly order replays, not real calendar time.',rule_changes='This report does not modify any formal collection or stopping rule.'))
 print('PREPARED',OUT,flush=True)
if __name__=='__main__':run()
