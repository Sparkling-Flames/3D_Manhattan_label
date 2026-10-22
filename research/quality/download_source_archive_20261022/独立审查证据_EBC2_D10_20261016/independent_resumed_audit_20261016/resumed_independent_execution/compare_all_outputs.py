from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
R=Path(__import__('os').environ['PRO_PACKAGE']).resolve();O=Path(__file__).resolve().parent;N=O/'replay'
rows=[]
for p in sorted((N/'results').glob('*.csv')):
 q=R/'results'/p.name;a=pd.read_csv(q);b=pd.read_csv(p);bad=[];errors={}
 if a.shape!=b.shape or list(a.columns)!=list(b.columns):bad=['shape_or_columns']
 else:
  for c in a:
   if not a[c].isna().equals(b[c].isna()):bad.append(c+':missingness');continue
   mask=a[c].notna()
   if pd.api.types.is_numeric_dtype(a[c]) and pd.api.types.is_numeric_dtype(b[c]) and a[c].dtype!='bool':
    er=float(np.max(np.abs(a.loc[mask,c].to_numpy()-b.loc[mask,c].to_numpy()))) if mask.any() else 0
    if er>0:errors[c]=er
    if er>1e-12:bad.append(c+':numeric')
   elif not (a.loc[mask,c]==b.loc[mask,c]).all():bad.append(c+':exact')
 rows.append({'file':p.name,'rows':len(a),'bytes_identical':p.read_bytes()==q.read_bytes(),'all_fields_match_with_numeric_atol_1e-12':not bad,'max_numeric_difference':max(errors.values(),default=0),'numeric_differences':errors,'failures':bad})
out={'compared_csvs':len(rows),'bytes_identical':sum(r['bytes_identical'] for r in rows),'all_field_semantic_pass':all(r['all_fields_match_with_numeric_atol_1e-12'] for r in rows),'files':rows}
(O/'all_csv_independent_comparison.json').write_text(json.dumps(out,indent=2));print(json.dumps({k:v for k,v in out.items() if k!='files'},indent=2))
reg=json.loads((R/'MODEL_REGISTRY.json').read_text());h=lambda p:hashlib.sha256((R/p).read_bytes()).hexdigest()
rr={k:reg[k]==h(p) for k,p in [('fixed_pairs_sha256','inputs/fixed_pairs.json'),('baseline_formula_code_sha256','src/b8_models.py'),('baseline_source_code_sha256','vendor/working_models.py'),('new_code_sha256','src/envelope_quality.py')]};rr.update({p:h(p)==v for p,v in reg['baseline_geometry_files'].items()});(O/'model_registry_hash_checks.json').write_text(json.dumps(rr,indent=2));print('Registry hashes pass',all(rr.values()))
