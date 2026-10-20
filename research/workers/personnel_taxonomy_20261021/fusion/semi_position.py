"""Final targeted Semi lower-height-vs-typical exchange, independently fitted folds."""
import argparse
from collections import defaultdict
import hashlib
import pandas as pd
import study as s
import a2_specific as runner

OUT=s.OUT/'semi_position'
SOURCE=s.TAX/'route_b/semi_new_candidate/lobo_labels.csv'


def labels():
    f=pd.read_csv(SOURCE,keep_default_na=False);f=f[f.candidate=='semi_position_scale']
    return {('semi',b):{r.worker_id:{'coarse':r.class_id,'fine':r.class_id} for r in g.itertuples()}
            for b,g in f.groupby('heldout_building')}


def prepare():
    pools=s.read(s.FUSION/'INPUT_SNAPSHOT.json.gz')['images'];maps=labels();groups=defaultdict(list)
    for p in pools:
        if p['meta']['layer']=='ordinary_semi' and len(p['records'])>=7:groups[p['meta']['building']].append(p)
    selected=[min(g,key=lambda p:(-len(p['records']),s.digest(p['pool_id']))) for b,g in sorted(groups.items())]
    events=[];capacity=[]
    for p in selected:
        meta=p['meta'];lab=maps.get(('semi',meta['building']),{})
        for n,m in [(5,1),(9,2)]:
            for c,d in [('SP_L','SP_T'),('SP_T','SP_L')]:
                blocks,reason=s.draw_blocks(p,lab,'coarse',c,d,n,m,811)
                row=dict(pool_id=p['pool_id'],image=meta['image'],building=meta['building'],condition='semi',layer=meta['layer'],
                         difficulty=meta['difficulty'],design_tier='coarse',n=n,m=m,repeat=0,outgoing_class=c,incoming_class=d,reason=reason)
                capacity.append(dict(row,feasible=blocks is not None))
                if blocks is None:continue
                e=dict(row,**blocks);e['event_id']='SPX_'+s.digest(e)[:22];s.validate(e,lab);events.append(e)
    s.save(OUT/'REQUESTS.json.gz',dict(events=events));s.csv(OUT/'CAPACITY.csv',pd.DataFrame(capacity));s.csv(OUT/'SELECTED_POOLS.csv',pd.DataFrame([p['meta'] for p in selected]))
    s.save(OUT/'REGISTRATION.json',dict(labels=str(SOURCE.relative_to(s.ROOT)),label_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        candidate='semi_position_scale',training='ordinary Semi alone, target building entirely held out; missing-fold workers excluded',
        selection='one largest ordinary-Semi eligible pool per building; stable-hash tie break',
        contrast='SP_L lower derived height versus SP_T typical; SP_A may remain in common background',
        design='fixed n5/m1 or n9/m2; same actual common background; disjoint blocks; identical source-origin counts',
        events=len(events),images=len(selected),registered_before_fusion=True,
        boundary='Final targeted internal candidate followup, not external confirmation; reference binding and native fusion/scorer unchanged'))
    print('Semi position',len(events),'ABC events,',len(selected),'selected pools',flush=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['prepare','run']);ap.add_argument('--jobs',type=int,default=4);a=ap.parse_args()
    runner.OUT=OUT;runner.labels=labels
    prepare() if a.stage=='prepare' else runner.run(a.jobs)
