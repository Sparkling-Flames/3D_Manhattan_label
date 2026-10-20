"""Embed only the exact selected member inputs/reference and native final outputs.

Selection is an explicit reviewable JSON manifest. It is never performed by
this export utility. Cached native outputs are used only for export; the paired
replay entry independently reconstructs them from the embedded inputs.
"""
from __future__ import annotations
import argparse,copy,hashlib,json,sys
from pathlib import Path
from design_history_panel import read,write,digest
from design_blocks import labels_from,counts
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'analysis/composition'))
sys.path.insert(0,str(ROOT/'interchangeability_20261020/independent'))
import pair_diagnostics
import case_visuals
from geometry_diagnostics import diagnose

def normalize_event(event,bykey,mapping,pool):
 """Expand the legacy baseline row using its exact member-keyed native arms."""
 e=copy.deepcopy(event)
 if 'A_workers' in e:return e
 e['legacy_counts']={a:e.get(a+'_counts') for a in 'ABC'}
 for a in 'ABC':
  workers=bykey[e[a+'_team_key']]['member_workers'];observed=counts(workers,mapping)
  old=e.get(a+'_counts')
  if isinstance(old,str):
   old={c:int(q) for c,q in (x.split(':') for x in old.split('|')) if int(q)}
  if old is not None:assert observed==old
  e[a+'_workers']=workers;e[a+'_counts']=observed
 core=set(e['A_workers'])&set(e['B_workers'])
 assert core==set(e['A_workers'])&set(e['C_workers'])
 e['core_workers']=sorted(core);e['core_counts']=counts(core,mapping)
 for a,key in [('A','outgoing_workers'),('B','within_incoming'),('C','cross_incoming')]:e[key]=sorted(set(e[a+'_workers'])-core)
 origins={r['worker_id']:r['origin'] for r in pool['records']}
 src=[dict(__import__('collections').Counter(origins[w] for w in e[k])) for k in ['outgoing_workers','within_incoming','cross_incoming']]
 assert src[0]==src[1]==src[2]
 e.update(matching='source_matched',actual_source_match=True,background_policy='random_nested',
  member_expansion='Legacy row expanded from its exact member-keyed native arms, each class count and source count checked.')
 for k in ['nested_event_after','other_registered_draw']:e.pop(k,None)
 return e

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--selection',type=Path,required=True)
 ap.add_argument('--snapshot',type=Path,required=True);ap.add_argument('--labels',type=Path,action='append',required=True)
 ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 specs=read(a.selection);maps=labels_from(a.labels);pools={p['pool_id']:p for p in read(a.snapshot)['images']};receipts=[]
 for item in specs['cases']:
  event=item.get('event')
  if event is None:
   payload=read(ROOT/item['requests_file']);event=next(e for e in payload['events'] if e['event_id']==item['event_id'])
  pid=event['pool_id'];pool=pools[pid];mapping=maps[event['method_id'],event['domain']]
  nativepath=ROOT/item['native_dir']/'pools'/(pid+'.json.gz');native=read(nativepath)
  bykey={t['team_key']:t for t in native['teams']};wanted=item.get('team_keys') or [event[x+'_team_key'] for x in 'ABC']
  teams=[copy.deepcopy(bykey[k]) for k in wanted];workers=sorted({w for t in teams for w in t['member_workers']})
  records=[copy.deepcopy(r) for r in pool['records'] if r['worker_id'] in workers]
  assert len(records)==len(workers)
  emb=dict(pool_id=pid,meta=copy.deepcopy(pool['meta']),reference=copy.deepcopy(pool['reference']),records=records)
  members=[]
  for r in records:
   members.append(dict(worker_id=r['worker_id'],object_id=r['object_id'],origin=r['origin'],class_id=mapping.get(r['worker_id'],'outside_group'),
    points=r['points'],frozen_record=r))
  for i,t in enumerate(teams):
   t['label']=item.get('team_labels',{}).get(t['team_key'],list('ABCDEF')[i])
   t['counts']=counts(t['member_workers'],mapping)
   t['diagnostics']=diagnose((t.get('geometry') or {}).get('footprint'),pool['reference']['floor_xz_h'])
  other_events=list(item.get('additional_events',[]))
  if event.get('nested_event_after'):other_events.append(event['nested_event_after'])
  if event.get('other_registered_draw'):other_events.append(event['other_registered_draw'])
  event=normalize_event(event,bykey,mapping,pool)
  other_events=[normalize_event(e,bykey,mapping,pool) for e in other_events]
  pairs=[]
  for ei,ev in enumerate([event]+other_events):
   for label,left,right in [('同构成 A→B','A','B'),('变构成 A→C','A','C')]:
    if ev[left+'_team_key'] in wanted and ev[right+'_team_key'] in wanted:
     result=pair_diagnostics.pair_metrics(bykey[ev[left+'_team_key']],bykey[ev[right+'_team_key']],cache={})
     pairs.append(dict(label=str(ei+1)+' / '+label,event_id=ev['event_id'],metric_kind='same_n_pair',a_team_key=ev[left+'_team_key'],b_team_key=ev[right+'_team_key'],metrics=result))
  mechanism=item.get('mechanism')
  if mechanism and mechanism.get('team_before') in wanted and mechanism.get('team_after') in wanted:
   left,right=mechanism['team_before'],mechanism['team_after']
   pairs.append(dict(label='固定块 / 嵌套共同背景增一人',metric_kind='nested_geometry',a_team_key=left,b_team_key=right,
    metrics=pair_diagnostics.geometry_metrics(bykey[left],bykey[right],cache={})))
  reference=dict(pool['reference'],reference_id=pool['meta']['reference_id'])
  case=dict(schema='interchangeability_case_v1',case_id=item['case_id'],title=item['title'],
   subtitle=item.get('subtitle',pid+' | '+event['direction']+' | n='+str(event['n'])+', m='+str(event['m'])),
   selection_reason=item['reason'],phase=event['phase'],pool_id=pid,method_id=event['method_id'],domain=event['domain'],
   main_commit='445686f8f3cf6039c4ce1f60016cad1d26829044',scientific_commit='82c6164b0d4630de5316199c92aa405930973168',
   original_pool_digest=native['context']['pool_digest'],original_pool_member_n=len(pool['records']),
   embedded_pool=emb,event=event,additional_events=other_events,mechanism=mechanism,
   worker_classes={w:mapping.get(w,'outside_group') for w in workers},
   reference=reference,members=members,teams=teams,pairs=pairs,
   fusion_parameters=dict(gap=native['context']['fusion_gap'],entry='consensus_delivery_20261008.fuse',
    automatic_branch=True,B8L2_primary=True,D10_sensitivity=True,N1_applied=False,manual_order=None),
   source=dict(native_file=item['native_dir']+'/pools/'+pid+'.json.gz',native_sha256=hashlib.sha256(nativepath.read_bytes()).hexdigest(),
    snapshot_sha256=hashlib.sha256(a.snapshot.read_bytes()).hexdigest(),selection_sha256=hashlib.sha256(a.selection.read_bytes()).hexdigest()),
   member_scope='exact union of the displayed teams',class_names=item.get('class_names',{}),
   image_path=item.get('image_path'),image_sha256=item.get('image_sha256'),view=item.get('view',{}))
  for key in ['zoom_bev','zoom_erp','highlight_reference_edges','focus_title']:
   if key in item:case[key]=item[key]
  path=a.out/(item['case_id']+'.json');write(path,case)
  receipts.append(dict(case_id=case['case_id'],file=path.name,members=len(workers),teams=len(teams),
   sha256=hashlib.sha256(path.read_bytes()).hexdigest(),image=pool['meta']['image'],reference_id=reference['reference_id']))
 write(a.out/'CASE_EXPORT_RECEIPT.json',dict(cases=receipts,full_native_states_included=False,inputs='Only necessary selected-case final processed member records, exact fixed reference and final native geometries.'))

if __name__=='__main__':main()
