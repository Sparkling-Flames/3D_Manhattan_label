import json,pathlib,gzip,os
import pandas as pd
BASE=pathlib.Path(__file__).resolve().parent;ROOT=pathlib.Path(os.environ.get('INTERCHANGEABILITY_WORK_ROOT',BASE.parent));P=ROOT/'unpacked/interchangeability_20261020';out=BASE/'core'
s=pd.read_csv(out/'CORNER_SUMMARY.csv');s=s[s.gate.eq('all_common')];pairs=pd.read_csv(out/'CORNER_PAIRS.csv.gz')
baseline=json.loads((P/'independent/baseline/GLOBAL_CLASS_MEMBERS.json').read_text())['classes']
r=pd.read_csv(P/'reverse/mixed_fit/worker_labels.csv.gz');mid='R_directswap_geometry_partition_b2_K2__ordinary_new__mixed_history_v1';r=r[r.method_id.eq(mid)&r.known]
classes={k:v.worker_id.tolist() for k,v in r.groupby('class_id')}
events=json.load(gzip.open(P/'core_replay/CORE_REQUESTS.json.gz'))['events']
cards=[]
for group in ['Rnew2_C01>C02_m2','Rnew2_C02>C01_m2','Rnew2_C01>C02_m5','Rnew2_C02>C01_m5','old_G_anchor','old_R_anchor']:
 row=s[s.replay_group.eq(group)].iloc[0].to_dict();f=pairs[pairs.replay_group.eq(group)]
 if group.startswith('Rnew2'):membership=classes;direction=row['direction'];role='new-source, conditional direct-swap geometry roles'
 else:
  target='G' if group=='old_G_anchor' else 'R';membership={k:v['workers'] for k,v in baseline[target].items()};direction='C02>C01' if target=='G' else 'C05>C02';role='historical geometry-role anchor, compatible with previous 451-panel evidence'
 risk={}
 for arm,a in f.groupby('arm'):
  values={'exclusive_different_corner_count':a.status.eq('different_corner_count').astype(float),'noncomplete':(~a.both_complete).astype(float),'missing_connected_geometry':a.status.eq('missing_connected_geometry').astype(float),'node_count_difference_any':a.node_count_difference.ne(0).where(a.node_count_difference.notna()).astype(float),'shape_main':a.geometry_shape_main.astype(float),'legacy_joint_main':a.joint_stable_main.astype(float)}
  risk[arm]={}
  for key,value in values.items():
   z=a[['building','pool_id']].copy();z['value']=value;risk[arm][key]={'building_equal_rate':z.groupby(['building','pool_id']).value.mean().groupby('building').mean().mean(),'available_pairs':int(value.notna().sum()),'raw_nonzero_pairs':int(value.fillna(0).sum())}
 es=[e for e in events if e.get('replay_group')==group]
 represented=sorted(set().union(*(set(e['A_workers'])^set(e['B_workers']) | set(e['A_workers'])^set(e['C_workers']) for e in es)))
 warnings=['Same-count unique cyclic candidate does not establish semantic identity.','Core is enriched internal replication; no external-person generalization.','Whole source class may contain people not represented in this direction; exact event member lists remain in original frozen core requests.']
 if group=='Rnew2_C02>C01_m5':warnings+=['Conditional average separation only: cross-class BEV mean is larger in 28/50 jointly eligible events (56%; building-weighted 56.48%), and max-BEV is larger in 24/50 (48%). Six positive building means do not establish that most individual replacements differ clearly. No human-nearness threshold has been validated.']
 if group=='Rnew2_C02>C01_m2':warnings+=['Continuous mean distances do not show cross-class separation at m=2; do not generalize the m=5 role down to this condition.']
 card={'replay_group':group,'method_id':row['method_id'],'direction':direction,'direction_provenance':'frozen event direction' if group.startswith('Rnew2') else 'deduced from frozen A_counts to C_counts; old event has no direction field','role_description':role,'members_by_class':membership,'actual_replacement_participants':represented,'actual_replacement_participants_by_class':{c:[w for w in ws if w in represented] for c,ws in membership.items()},'continuous_common_support':{k:row[k] for k in ['attempted_events','joint_events','joint_images','joint_buildings','k','m']},'continuous_metrics':{k:v for k,v in row.items() if any(k.startswith(x) for x in ['within_','cross_','delta_'])},'all_attempt_risks':risk,'warnings':warnings}
 cards.append(card)
(out/'WORKING_TAXONOMY.json').write_text(json.dumps(cards,indent=2,ensure_ascii=False,allow_nan=False))
print(len(cards))
