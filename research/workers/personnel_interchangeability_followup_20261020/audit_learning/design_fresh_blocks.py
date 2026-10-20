"""Finite metadata-only new-label block probe; never reads assessment outcomes."""
import json,gzip,hashlib,random,itertools,collections
from pathlib import Path
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent;P=ROOT/'unpacked';S=P/'interchangeability_20261020';OUT=BASE/'fresh_blocks';OUT.mkdir(exist_ok=True)
SEED=2026102029
SNAP=ROOT/'restored/work_personnel_typing_A_20261019/recovered/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz'
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def key(pid,ws):return pid+'__'+digest(sorted(ws))[:20]
def rng(*x):return random.Random(int(digest([SEED,*x])[:16],16))
def counts(ws,mapping):return dict(sorted(collections.Counter(mapping.get(w,'outside_group') for w in ws).items()))
def save(p,x):
 raw=json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode();p.write_bytes(gzip.compress(raw,mtime=0) if p.suffix=='.gz' else raw)
def main():
 snapshot=json.load(gzip.open(SNAP,'rt'));assert snapshot['git_commit']=='82c6164b0d4630de5316199c92aa405930973168' and not snapshot['N1_applied']
 split=json.load(open(P/'analysis/composition/SPLIT.json'));freeze=json.load(open(BASE/'BLOCK_PROBE_FREEZE.json'));primary=freeze['primary_method'];r_id='R_directswap_geometry_partition_b2_K2__ordinary_new__mixed_history_v1';rman=json.load(open(S/'reverse/mixed_fit/METHOD_MANIFEST.json'))[r_id]
 methods={primary:freeze['methods'][primary]['classes'],r_id:rman['classes']};maps={m:{w:c for c,ws in cl.items() for w in ws} for m,cl in methods.items()}
 eligible=[p for p in snapshot['images'] if p['meta']['building'] in split['validation_buildings'] and p['meta']['layer']=='ordinary_manual' and sum(r['origin']=='new' for r in p['records'])>=6]
 selected=[];selection=[]
 for b in split['validation_buildings']:
  options=sorted([p for p in eligible if p['meta']['building']==b],key=lambda p:digest([SEED,'images',p['pool_id']]))
  selected+=options[:2];selection.append({'building':b,'eligible_pool_ids':[p['pool_id'] for p in options],'selected_pool_ids':[p['pool_id'] for p in options[:2]],'selection':'first_two_fixed_sha256_order_of_pool_id; no outcome read'})
 requests={};events=[];ledger=[];common=[]
 def request(pid,ws):
  tk=key(pid,ws);requests.setdefault(tk,{'request_id':tk,'pool_id':pid,'k':len(ws),'worker_ids':sorted(ws)});return tk
 for pool in selected:
  pid=pool['pool_id'];meta=pool['meta'];ws=sorted(r['worker_id'] for r in pool['records']);new=sorted(r['worker_id'] for r in pool['records'] if r['origin']=='new')
  for mid,classes in methods.items():
   mapping=maps[mid];groups={c:sorted(set(v)&set(ws)) for c,v in classes.items()}
   for out,inc in itertools.permutations(sorted(groups),2):
    for m in [2,5]:
     reason='outgoing_fewer_than_2m' if len(groups[out])<2*m else 'incoming_fewer_than_m' if len(groups[inc])<m else None
     for rep in range(2):
      rr=rng('class_specific',mid,pid,out,inc,m,rep)
      blocks=None;core_order=[]
      if reason is None:
       chosen=rr.sample(groups[out],2*m);blocks=[sorted(chosen[:m]),sorted(chosen[m:]),sorted(rr.sample(groups[inc],m))];reserved=set(sum(blocks,[]));core_order=sorted(set(ws)-reserved);rr.shuffle(core_order)
      for n in range(5,18):
       why=reason or ('insufficient_common_core' if len(core_order)<n-m else None)
       led={'design':'class_specific','method_id':mid,'pool_id':pid,'building':meta['building'],'n':n,'m':m,'outgoing_class':out,'incoming_class':inc,'replicate':rep,'out_capacity':len(groups[out]),'in_capacity':len(groups[inc]),'status':why or 'accepted'};ledger.append(led)
       if why:continue
       core=core_order[:n-m];arms=[sorted(core+bl) for bl in blocks];ca,cb,cc=[counts(a,mapping) for a in arms];assert ca==cb and ca!=cc;assert all(len(a)==len(set(a))==n for a in arms)
       assert set(arms[0])&set(arms[1])==set(arms[0])&set(arms[2])==set(core)
       eid='CB29_'+digest([mid,pid,out,inc,m,rep,n])[:22]
       event={'event_id':eid,'design':'class_specific','phase':'discovery_nominated_exploratory_block_probe','replay_group':'fresh_class_specific','assessment_status':'reused_internal_assessment_images','method_id':mid,'domain':'ordinary_new','pool_id':pid,**{k:meta.get(k) for k in ['building','image','image_id','difficulty','layer','condition','reference_id','reference_version']},'n':n,'k':n,'m':m,'direction':out+'>'+inc,'outgoing_class':out,'incoming_class':inc,'replicate':rep,'core_workers':sorted(core),'core_prefix_order':core_order,'outgoing_workers':blocks[0],'within_incoming':blocks[1],'cross_incoming':blocks[2],'A_counts':ca,'B_counts':cb,'C_counts':cc,'actual_source_match':True,'source_policy':'all three exchanged blocks new-source; identical core','nested_group_id':digest([mid,pid,out,inc,m,rep]),'complete_turnover':n==m,'comparison_limit':'Own-rule class-specific sampling; not direct cross-method ranking on different teams.'}
       for arm,people in zip('ABC',arms):event[arm+'_workers']=people;event[arm+'_team_key']=request(pid,people)
       events.append(event)
  # Independent entrant reservoir/block libraries, identical endpoint cache for all classifications.
  for m,library_size in [(2,48),(5,12)]:
   for rep in range(2):
    rr=rng('common_library',pid,m,rep);maxcore=17-m;reservoir_n=min(20,len(new),len(ws)-maxcore)
    if reservoir_n<2*m:
     ledger.append({'design':'common_library','pool_id':pid,'m':m,'replicate':rep,'status':'insufficient_reservoir_for_disjoint_blocks'});continue
    reservoir=sorted(rr.sample(new,reservoir_n));core_order=sorted(set(ws)-set(reservoir));rr.shuffle(core_order)
    possibilities=list(itertools.combinations(reservoir,m));rr.shuffle(possibilities);blocks=[list(x) for x in possibilities[:library_size]]
    for n in [5,9,13,17]:
     if len(core_order)<n-m:
      ledger.append({'design':'common_library','pool_id':pid,'n':n,'m':m,'replicate':rep,'status':'insufficient_core'});continue
     core=core_order[:n-m];block_rows=[]
     for j,bl in enumerate(blocks):block_rows.append({'block_index':j,'workers':bl,'team_key':request(pid,sorted(core+bl))})
     validpairs=[(a,b) for a,b in itertools.combinations(range(len(blocks)),2) if not set(blocks[a])&set(blocks[b])]
     common.append({'anchor_id':'CA29_'+digest([pid,n,m,rep])[:22],'design':'category_independent_library','pool_id':pid,**{k:meta.get(k) for k in ['building','image','image_id','difficulty','reference_id','reference_version']},'n':n,'k':n,'m':m,'replicate':rep,'core_workers':sorted(core),'core_prefix_order':core_order,'entrant_reservoir':reservoir,'blocks':block_rows,'disjoint_block_pairs':validpairs,'nested_group_id':digest([pid,m,rep]),'classification':'Pair is within when class-count vectors of exchanged blocks agree, between otherwise; unknown entrants excluded per method. Only disjoint pairs imply exact turnover m. Pure-class subset separate.'})
     ledger.append({'design':'common_library','pool_id':pid,'building':meta['building'],'n':n,'m':m,'replicate':rep,'status':'accepted','block_count':len(blocks),'disjoint_pair_count':len(validpairs)})
 payload={'schema':'fresh_corner_blocks_and_common_library_v1','spec':{'seed':SEED,'image_selection':selection,'primary_method':primary,'class_specific_methods':list(methods),'class_n':list(range(5,18)),'common_n':[5,9,13,17],'m':[2,5],'replicates':2,'common_library_sizes':{'2':48,'5':12},'assessment_status':'reused_internal12image_metadata_probe; not all assessment images and not fresh independent holdout','nomination_freeze_sha256':hashlib.sha256((BASE/'BLOCK_PROBE_FREEZE.json').read_bytes()).hexdigest(),'source_snapshot_sha256':hashlib.sha256(SNAP.read_bytes()).hexdigest(),'no_assessment_outcomes_read':True,'source_code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},'requests':list(requests.values()),'events':events,'common_anchors':common,'ledger':ledger,'label_maps':maps}
 save(OUT/'fresh_block_requests.json.gz',payload)
 # Exact membership and images frozen before any native replay.
 receipt={'unique_teams':len(requests),'class_specific_events':len(events),'common_anchors':len(common),'common_disjoint_pairs':sum(len(a['disjoint_block_pairs']) for a in common),'selected_images':len(selected),'selected_buildings':len({p['meta']['building'] for p in selected}),'all_requested_assessment_buildings':split['validation_buildings'],'request_sha256':hashlib.sha256((OUT/'fresh_block_requests.json.gz').read_bytes()).hexdigest(),'source_code_sha256':payload['spec']['source_code_sha256'],'capacity_status_counts':dict(collections.Counter(r['status'] for r in ledger)),'frozen_before_replay':True}
 save(OUT/'DESIGN_RECEIPT.json',receipt);save(OUT/'IMAGE_SELECTION.json',selection);print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
