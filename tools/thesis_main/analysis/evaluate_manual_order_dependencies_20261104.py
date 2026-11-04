"""Audit actual current consumers of the 57 exact returned endpoint identities.

Read saved results only. This does not fuse, score, relabel, or mutate baselines.
The previously registered 558 source tables are re-read with their actual gates;
all unfiltered exact matches are also retained as frozen/secondary references.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT/'research/fusion/missing_ring_review_20261104'
OUT = ROOT/'research/fusion/manual_order_impact_20261104/dependencies'

def norm(value):
    return '/'.join(x for x in str(value).replace('\\', '/').split('/') if x)

def truth(values):
    return values.fillna(False).astype(str).str.lower().isin(['true','1','1.0'])

def save(name, frame):
    OUT.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUT/name, index=False, encoding='utf-8-sig')

def active_gate(module, frame):
    keep = pd.Series(True, index=frame.index)
    if module == 'current_half': keep &= truth(frame.updated_class_legal)
    elif module == 'legacy_role_policy': keep &= pd.to_numeric(frame.k).ge(3)
    elif module == 'fusion_baseline': keep &= frame.method.eq('wall_auto')
    elif module.startswith('natural_') and not module.startswith('natural_doorway_'):
        keep &= pd.to_numeric(frame.k).ne(2)
    return keep

def run():
    OUT.mkdir(parents=True, exist_ok=True)
    orders = pd.read_csv(BASE/'user_order_return/VALIDATED_ENDPOINT_ORDERS.csv.gz')
    wanted = set(orders.team_key)
    sources = pd.read_csv(BASE/'CURRENT_REFERENCE_SOURCES.csv')
    hits, all_hits, checks, alias_checks = [], [], [], []
    meta = ['image','image_a','image_b','building','condition','pool_id','pair_key','event_id','replicate_id','panel_id','n','m','k','N','reference_id','reference_version','score_status','method','method_updated','updated_direction','updated_class_legal','policy','member_workers','member_object_ids']
    for num, item in enumerate(sources.to_dict('records'), 1):
        path = ROOT/norm(item['source'])
        header = pd.read_csv(path, nrows=0).columns.tolist()
        keys = ['endpoint_source_key'] if 'endpoint_source_key' in header else [c for c in header if c == 'team_key' or c.endswith('_team_key') or c.startswith('team_key_')]
        assert keys, (path, 'no exact endpoint identity column')
        otherkeys = [c for c in header if c not in keys and ('team_key' in c or c.startswith('team_') and c not in ['team_members','team_size'])]
        use = list(dict.fromkeys(keys+otherkeys+[c for c in meta if c in header]))
        rows = eligible = count = 0
        for frame in pd.read_csv(path, usecols=use, chunksize=50000, low_memory=False):
            gate = active_gate(item['module'], frame)
            rows += len(frame); eligible += int(gate.sum())
            for col in keys:
                for ix, row in frame[frame[col].isin(wanted)].iterrows():
                    out = {c:row[c] for c in meta if c in frame}
                    out.update(module=item['module'], source=norm(item['source']), source_row=int(ix), arm=col,
                               team_key=row[col], current_gate_included=bool(gate.loc[ix]))
                    if 'event_id' not in out or pd.isna(out['event_id']): out['event_id'] = str(row.get('replicate_id',row.get('panel_id',ix)))
                    all_hits.append(out)
                    if gate.loc[ix]: hits.append(out); count += 1
            for col in otherkeys:
                selected=frame[frame[col].isin(wanted)]
                for ix,row in selected.iterrows():
                    represented=any(row[col]==row[k] for k in keys)
                    alias_checks.append(dict(module=item['module'],source=norm(item['source']),source_row=int(ix),column=col,team_key=row[col],represented_by_canonical_key=represented,current_gate_included=bool(gate.loc[ix])))
                    assert represented, ('additional exact consumer requires propagation', item['source'],ix,col,row[col])
        assert eligible == int(item['rows']), ('source registration row mismatch', item['source'],eligible,item['rows'])
        checks.append(dict(module=item['module'],source=norm(item['source']),raw_rows=rows,current_rows=eligible,registered_current_rows=int(item['rows']),exact_returned_references=count,read_complete=True))
        if num%50==0: print('read current consumers',num,'/',len(sources),flush=True)
    hit=pd.DataFrame(hits); full=pd.DataFrame(all_hits)
    old=pd.read_csv(BASE/'user_order_return/AFFECTED_CURRENT_REFERENCES.csv.gz')
    old['source']=old.source.map(norm)
    ids=['module','source','source_row','arm','team_key']
    expected=set(old[ids].itertuples(index=False,name=None)); observed=set(hit[ids].itertuples(index=False,name=None))
    assert expected == observed, ('registered reference mismatch',len(expected-observed),len(observed-expected))
    save('CURRENT_SOURCE_READ_CHECKS.csv',pd.DataFrame(checks))
    save('CURRENT_EXACT_REFERENCES.csv.gz',hit)
    save('ALL_EXACT_REFERENCES_WITH_GATES.csv.gz',full)
    save('ALIAS_COLUMN_CHECKS.csv.gz',pd.DataFrame(alias_checks))
    save('OUTSIDE_CURRENT_GATE_REFERENCES.csv',full[~full.current_gate_included])
    group=[]
    for module,frame in hit.groupby('module'):
        images=set(frame.get('image',pd.Series(dtype=str)).dropna())-set([''])
        images|=set(frame.get('image_a',pd.Series(dtype=str)).dropna())-set([''])
        images|=set(frame.get('image_b',pd.Series(dtype=str)).dropna())-set([''])
        if not images:images=set(orders[orders.team_key.isin(frame.team_key)].image)
        group.append(dict(module=module,endpoint_identities=frame.team_key.nunique(),references=len(frame),source_rows=len(frame[['source','source_row']].drop_duplicates()),events=len(frame[['source','event_id']].drop_duplicates()),images=len(images),image_pairs=frame.pair_key.nunique() if 'pair_key' in frame else 0,buildings=len({x.split('-')[0] for x in images}),n_values='|'.join(map(str,sorted(set(orders[orders.team_key.isin(frame.team_key)].merge(pd.read_csv(BASE/'user_order_return/REVIEW_DECISIONS.csv')[['team_key','k']],on='team_key').k)))),status='requires_targeted_reaggregation'))
    save('MODULE_REFERENCE_SCOPE.csv',pd.DataFrame(group))
    modules=set(sources.module)-set(hit.module)
    save('UNHIT_CURRENT_MODULES.csv',pd.DataFrame([dict(module=m,sources=sum(sources.module.eq(m)),reason='All registered current source tables re-read; exact returned endpoint intersection is empty',requires_recalculation=False) for m in sorted(modules)]))
    rf=ROOT/'research/data/releases/v2.1/admitted_space_extension/image_difficulty_20261030/rfuse/NATURAL_TRAINING_ENDPOINTS.csv.gz'
    train=pd.read_csv(rf,low_memory=False)
    rfhits=train[train.team_key.isin(wanted)]
    assert rfhits.empty
    save('RFUSE_EXACT_TRAINING_INTERSECTION.csv',rfhits)
    indirect=[
      ('DSTRUCT','original_annotation_features','research/data/releases/v2.1/admitted_space_extension/image_difficulty_20261030/classification/RAW_TARGET_RESPONSE_RECORDS.csv.gz','tools/thesis_main/analysis/recompute_v21_image_difficulty_20261030.py:target_fit','No original response, reference, difficulty, or feature changed; no fusion endpoint input',False),
      ('historical_Q_only','original_annotation_LOBO_quality','research/data/releases/v2.1/q_only_exchange_20261031/HISTORY_LOBO.csv','tools/thesis_main/analysis/q_only_exchange_v21_20261031.py','Selection history uses original responses outside target building; selections remain fixed',False),
      ('RFUSE_and_TARGET_RFUSE','saved_fusion_training_endpoints',str(rf.relative_to(ROOT)),'tools/thesis_main/analysis/recompute_v21_image_difficulty_20261030.py:rfuse_fit',f'Exact 57-key intersection=0; training rows={len(train)}, training unique teams={train.team_key.nunique()}',False),
      ('image_difficulty','one_grade_per_image','research/data/releases/v2.1/difficulty_records.json','tools/thesis_main/analysis/recompute_v21_image_difficulty_20261030.py:grades','User-confirmed image grade is fixed; only conditional output summaries change',False),
      ('JOINT_profiles','original_response_quality_and_recorded_time','research/data/releases/v2.1/admitted_space_extension/joint_history_classification/BEHAVIOR_RECORDS.csv.gz','tools/thesis_main/analysis/recompute_v21_image_difficulty_20261030.py:inputs','Original response geometry/quality and recorded labor fixed; policy outcomes checked separately',False),
      ('same_room_original_Q_and_room_use','original_response_statistics','research/data/releases/v2.1/room_type_similarity/README.md','tools/thesis_main/analysis/recompute_v21_image_difficulty_20261030.py','Original-response means/personal repeatability are not fused-team outcomes',False),
      ('annotation_labor','original_recorded_annotations','all original endpoint labor fields','all targeted overlays','Preserve each labor value and recording-source signature; recompute only Q-conditioned comparisons',False),
      ('human_connection_labor','new_human_assistance','research/fusion/missing_ring_review_20261104/user_order_return/REVIEW_DECISIONS.csv','updated_at is a save timestamp, not duration','Duration unmeasured; do not assign zero or infer duration from timestamps',False),
    ]
    save('INDIRECT_DEPENDENCIES.csv',pd.DataFrame(indirect,columns=['module','input_kind','input_source','consumer','evidence','refit_or_recompute_input']))
    receipt=dict(source_commit='ac395e703d1fef573d1ef3e105df0286d62a0468',source_tables_read=len(checks),all_source_rows_match=True,returned_endpoint_identities=len(wanted),current_references=len(hit),current_modules=hit.module.nunique(),exact_map_reproduced=True,other_alias_matches=len(alias_checks),outside_current_gates=len(full)-len(hit),rfuse_training_rows=len(train),rfuse_affected_rows=0,full_library_fusion_replayed=False,classification_refitted=False)
    (OUT/'CHECKS.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(receipt,ensure_ascii=False),flush=True)

if __name__=='__main__':run()
