"""Metadata-only bounded history m2 endpoint library, registered before fusion."""
from design_fresh_blocks import *
OUT=BASE/'history_blocks';OUT.mkdir(exist_ok=True)
SEED=2026102037
# Local seed is explicit because imported rng closes over its original module.
def rng(*x):return random.Random(int(digest([SEED,*x])[:16],16))
def main():
 snapshot=json.load(gzip.open(SNAP,'rt'));split=json.load(open(P/'analysis/composition/SPLIT.json'))
 selected=[];selection=[];ledger=[];requests={};anchors=[]
 for b in split['history_buildings']:
  options=sorted([p for p in snapshot['images'] if p['meta']['building']==b and p['meta']['layer']=='ordinary_manual' and sum(r['origin']=='new' for r in p['records'])>=6],key=lambda p:digest([SEED,'images',p['pool_id']]))
  selected+=options[:2];selection.append({'building':b,'eligible_pool_ids':[p['pool_id'] for p in options],'selected_pool_ids':[p['pool_id'] for p in options[:2]]})
 for pool in selected:
  pid=pool['pool_id'];meta=pool['meta'];ws=sorted(r['worker_id'] for r in pool['records']);new=sorted(r['worker_id'] for r in pool['records'] if r['origin']=='new')
  for rep in range(2):
   rr=rng('history_library',pid,rep);nr=min(20,len(new),len(ws)-15)
   if nr<4:ledger.append({'pool_id':pid,'replicate':rep,'status':'insufficient_reservoir_for_n17_nested_path'});continue
   reservoir=sorted(rr.sample(new,nr));coreorder=sorted(set(ws)-set(reservoir));rr.shuffle(coreorder)
   blocks=list(itertools.combinations(reservoir,2));rr.shuffle(blocks);blocks=blocks[:48]
   pairs=[(a,b) for a,b in itertools.combinations(range(len(blocks)),2) if not set(blocks[a])&set(blocks[b])]
   for n in [5,9,13,17]:
    core=coreorder[:n-2];br=[]
    for j,bl in enumerate(blocks):
     people=sorted(core+list(bl));tk=key(pid,people);requests.setdefault(tk,{'request_id':tk,'pool_id':pid,'k':n,'worker_ids':people});br.append({'block_index':j,'workers':list(bl),'team_key':tk})
    anchors.append({'anchor_id':'HB37_'+digest([pid,n,rep])[:22],'design':'category_independent_library','phase':'history_block_training','pool_id':pid,**{k:meta.get(k) for k in ['building','image','image_id','difficulty','reference_id','reference_version']},'n':n,'k':n,'m':2,'replicate':rep,'core_workers':sorted(core),'core_prefix_order':coreorder,'entrant_reservoir':reservoir,'blocks':br,'disjoint_block_pairs':pairs,'nested_group_id':digest([pid,rep])})
    ledger.append({'pool_id':pid,'building':meta['building'],'n':n,'m':2,'replicate':rep,'status':'accepted','blocks':len(blocks),'pairs':len(pairs)})
 payload={'schema':'history_m2_common_library_v1','spec':{'seed':SEED,'phase':'history_only_training','n':[5,9,13,17],'m':2,'replicates':2,'block_library_size':48,'source_snapshot_sha256':hashlib.sha256(SNAP.read_bytes()).hexdigest(),'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'registration_sha256':hashlib.sha256((BASE/'BLOCK_LEARNING_REGISTRATION.json').read_bytes()).hexdigest(),'no_geometry_or_outcomes_read':True,'image_selection':selection},'requests':list(requests.values()),'events':[],'common_anchors':anchors,'ledger':ledger,'label_maps':{}}
 save(OUT/'history_block_requests.json.gz',payload)
 receipt={'unique_teams':len(requests),'anchors':len(anchors),'disjoint_pairs':sum(len(a['disjoint_block_pairs']) for a in anchors),'images':len(selected),'buildings':len({p['meta']['building'] for p in selected}),'request_sha256':hashlib.sha256((OUT/'history_block_requests.json.gz').read_bytes()).hexdigest(),'capacity':dict(collections.Counter(x['status'] for x in ledger)),'frozen_before_fusion':True}
 save(OUT/'DESIGN_RECEIPT.json',receipt);save(OUT/'IMAGE_SELECTION.json',selection);print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
