"""Export exact case evidence and replay every chosen real team with frozen code."""
import argparse,collections,hashlib,json,os,itertools
from pathlib import Path
import numpy as np
from fusion_runner import init_engine,read,write,digest,evaluate_one,SCORE_KEYS,team_key
from design_compositions import load_labels
from geometry_diagnostics import diagnose

def equal_number(a,b):
    if a is None or b is None:return a is None and b is None
    if isinstance(a,(int,float)) and isinstance(b,(int,float)):return abs(a-b)<=1e-10
    return a==b

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--selection',type=Path,required=True);ap.add_argument('--restored',type=Path,required=True);ap.add_argument('--labels',type=Path,action='append',required=True);ap.add_argument('--images',type=Path,default=Path('analysis/selected_originals'));ap.add_argument('--out',type=Path,required=True);ap.add_argument('--render',action='store_true');ap.add_argument('--font',type=Path);a=ap.parse_args()
    fe=init_engine(a.restored);pools={p['pool_id']:p for p in fe.load_pools()};labels=load_labels(a.labels);selection=read(a.selection);receipts=[];a.out.mkdir(parents=True,exist_ok=True)
    for cs in selection['cases']:
        pool=pools[cs['pool_id']];mapping=labels[cs['method_id'],cs['domain']]
        case={k:v for k,v in cs.items() if k!='arms'};case.update(meta=pool['meta'],reference=dict(pool['reference'],reference_id=pool['meta']['reference_id'],reference_version=pool['meta']['reference_version']),
            fusion_parameters=dict(entry='consensus_delivery_20261008.fuse',gap=7.5,assisted_partitions=[],manual_order=None,N1_applied=False),
            scientific_commit=fe.COMMIT,main_commit='e572eb73bedc4fe9056df838e458bab83c3fa423',pool_digest=digest(pool),members=[],teams=[])
        image=a.images/(pool['meta']['image_id']+'.png');case['image_path']=os.path.relpath(image,a.out);case['image_sha256']=hashlib.sha256(image.read_bytes()).hexdigest() if image.exists() else None
        case['image_source']=dict(release_tag='quality-original-images-20261015',repository='Sparkling-Flames/3D_Manhattan_label',image_id=pool['meta']['image_id'],image_code=pool['meta']['image'],sha256=case['image_sha256'],note='publisher entry CRC/size verified by partial extraction; individual SHA computed locally')
        active=set()
        with fe.cached_matching(),fe.scoring_engine(fe.ENGINE/'measurement_engine.zip',fe.ENGINE/'working_models.py') as (engine,models):
          for arm in cs['arms']:
            run=read(Path(arm['runs'])/'pools'/(pool['pool_id']+'.json.gz'));assert run['context']['pool_digest']==digest(pool)
            old=next(t for t in run['teams'] if t['team_key']==arm['team_key']);ws=old['member_workers'];assert all(w in mapping for w in ws)
            counts=dict(sorted(collections.Counter(mapping[w] for w in ws).items()));counts={c:counts.get(c,0) for c in sorted(set(mapping.values()))}
            if 'counts' in arm:assert arm['counts']==counts
            request=read(Path(arm['requests']));matched=[q for q in request['requests'] if q['team_key']==arm['team_key'] and q['worker_ids']==ws]
            assert matched,'selected team must belong to a recorded executed design'
            fresh=evaluate_one(pool,ws,engine,models,full_state=True);assert fresh['member_object_ids']==old['member_object_ids'];assert fresh['geometry']==old['geometry']
            assert all(equal_number(fresh.get(k),old.get(k)) for k in SCORE_KEYS+['nodes','minimum_support','complete_evaluable'])
            state=fresh.pop('full_state');case_team=dict(fresh,label=arm['label'],counts=counts,request_ids=sorted(q['request_id'] for q in matched),request_file=arm['requests'],request_file_sha256=hashlib.sha256(Path(arm['requests']).read_bytes()).hexdigest())
            for unused in ['fusion_seconds','score_seconds']:case_team.pop(unused,None)
            if 'color' in arm:case_team['color']=arm['color']
            case_team['diagnostics']=diagnose((fresh.get('geometry') or {}).get('footprint'),pool['reference']['floor_xz_h'])
            case_team['mechanism_groups']=[{k:g.get(k) for k in ['feature_id','support','selected','center']}|{'members':[{k:m.get(k) for k in ['id','worker','pair_index','points']} for m in g['members']]} for g in state['identity_groups']]
            case['teams'].append(case_team);active.update(c for c,n in counts.items() if n)
            receipts.append(dict(case_id=case['case_id'],pool_id=pool['pool_id'],team_key=fresh['team_key'],members_exact=True,object_ids_exact=True,geometry_exact=True,scores_exact=True,score_status=fresh.get('score_status'),B8L2=fresh.get('B8L2'),request_ids=case_team['request_ids']))
        for r in pool['records']:
            if mapping.get(r['worker_id']) not in active:continue
            case['members'].append(dict(worker_id=r['worker_id'],object_id=r['object_id'],class_id=mapping[r['worker_id']],origin=r['origin'],points=r['points'],ring_confirmed=r['ring_confirmed'],order_status=r['order_status'],geometry_status=r['geometry_status'],B8L2=r['B8L2'],D10=r['D10'],frozen_record=r))
        from summarize_grid import signature,pair_metrics
        case['same_size_pair_diagnostics']=[]
        for ta,tb in itertools.combinations(case['teams'],2):
            if ta['k']!=tb['k']:continue
            case['same_size_pair_diagnostics'].append(dict(team_a=ta['team_key'],team_b=tb['team_key'],**pair_metrics(ta,tb,signature(ta),signature(tb))))
        case['nested_vote_bookkeeping']=[]
        for ta,tb in zip(case['teams'],case['teams'][1:]):
            if not (set(ta['member_workers'])<set(tb['member_workers']) and tb['k']==ta['k']+1):continue
            old=dict(n=ta['k'],identity_groups=ta['mechanism_groups']);new=dict(n=tb['k'],identity_groups=tb['mechanism_groups'])
            identity=lambda groups:{frozenset((m['id'],m['pair_index']) for m in g['members']):g for g in groups}
            pa,pb=identity(old['identity_groups']),identity(new['identity_groups']);shared=set().union(*pa)
            restricted={ids & shared:g for ids,g in pb.items() if ids & shared};losses=[]
            for ids,g in pa.items():
                if g['selected'] and ids in restricted and not restricted[ids]['selected']:
                    h=restricted[ids];losses.append(dict(before_group=g['feature_id'],after_group=h['feature_id'],old_observations=sorted(ids),support_before=g['support'],support_after=h['support'],center_before=g['center'],center_after=h['center']))
            case['nested_vote_bookkeeping'].append(dict(before_team=ta['team_key'],after_team=tb['team_key'],added_workers=sorted(set(tb['member_workers'])-set(ta['member_workers'])),native_transition=fe.transition(old,new),unchanged_identity_lost_groups=losses))
        if cs.get('mechanism_chain_id'):
            chains=read(Path(cs['arms'][0]['requests']))['chains'];case['full_member_chain']=next(c for c in chains if c['chain_id']==cs['mechanism_chain_id'])
        if cs.get('block_event_id'):
            events=read(Path(cs['arms'][0]['requests']))['events'];case['matched_block_design']=next(e for e in events if e['event_id']==cs['block_event_id'])
        write(a.out/(case['case_id']+'.json'),case)
        if a.render:
            from case_visuals import render_case
            render_case(dict(case,image_path=str(image.resolve())),a.out.parent/'figures'/case['case_id'],font_path=a.font)
        print(json.dumps(dict(case_id=case['case_id'],arms=len(case['teams']),members=len(case['members']),original_available=image.exists())),flush=True)
    write(a.out/'CASE_REPLAY_RECEIPT.json',dict(selection_sha256=hashlib.sha256(a.selection.read_bytes()).hexdigest(),cases=len(selection['cases']),team_replays=len(receipts),all_exact=True,teams=receipts))

if __name__=='__main__':main()
