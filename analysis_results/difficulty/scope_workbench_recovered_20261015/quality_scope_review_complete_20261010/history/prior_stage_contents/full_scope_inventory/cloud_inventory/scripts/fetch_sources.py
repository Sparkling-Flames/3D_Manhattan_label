import pathlib,subprocess,json,hashlib
repo=pathlib.Path('/workspace/scratch/a365811da80c/quality_scope_current');out=pathlib.Path(__file__).parent
paths=subprocess.check_output(['git','-c','core.quotepath=false','ls-tree','-r','--name-only','HEAD'],cwd=repo,text=True).splitlines()
prefixes=['analysis_results/review_final_20260928/evidence/','analysis_results/review_reconciliation_20260925/evidence/','analysis_results/review_return_20260927/evidence/','analysis_results/review_closeout_20260928/evidence/','analysis_results/human_review_reconciliation_20260907_v1/','analysis_results/human_review_reconciliation_20260918/','analysis_results/new_manual_reviewed_20260921/evidence/','analysis_results/clustering_numeric_received_20260920/evidence/','analysis_results/annotation_uncertainty_prescreen_20260903_v1/']
extra=['analysis_results/cluster_visual_20260918_v2/results/source_review_comments.json','analysis_results/scene_image_exploration_20260910_v1/image_classification.json','analysis_results/scene_image_exploration_20260910_v1/same_room_selection_registry_v2_20260912.json','analysis_results/review_final_20260928/current_semantic_findings.json','analysis_results/review_final_20260928/semantic_findings.json']
selected=[p for p in paths if p.endswith('.json') and (any(p.startswith(pre) for pre in prefixes) or p in extra)]
manifest=[]
for p in selected:
 dest=out/'sources'/p;dest.parent.mkdir(parents=True,exist_ok=True)
 try:
  data=dest.read_bytes() if dest.exists() else (repo/p).read_bytes() if (repo/p).exists() else subprocess.check_output(['git','show','HEAD:'+p],cwd=repo,timeout=40)
  dest.write_bytes(data)
  state='lfs_pointer_unread' if data.startswith(b'version https://git-lfs') else 'readable'
  manifest.append(dict(path=p,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),state=state))
  print(state,p,len(data),flush=True)
 except Exception as e:manifest.append(dict(path=p,state='unavailable',error=str(e)));print('ERROR',p,str(e),flush=True)
 (out/'fetch_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
