"""Prepare and summarize paired k=6/10 exclusion sensitivity, not a full curve."""
import argparse,gzip,io,json,zipfile
from pathlib import Path
import pandas as pd
from tools.thesis_main.analysis.audit_doorway_delivery_20261031 import paired_metric
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'research/data/doorway_review_20261030/pro_delivery_independent_audit_20261031'
OUT=BASE/'computed_exclude13_selected'
P='HOHONET_doorway_v21_20261031/'
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--summarize',action='store_true');args=parser.parse_args()
    z2=zipfile.ZipFile('C:/Users/ASUS/Downloads/DOORWAY_02_RESULTS_CURVES_CASES.zip');z4=zipfile.ZipFile('C:/Users/ASUS/Downloads/DOORWAY_04_PHYSICAL_GEOMETRY.zip')
    def table(z,n,**kw):return pd.read_csv(io.BytesIO(gzip.decompress(z.read(P+n))),**kw)
    scores=table(z4,'stage04_computation/ENDPOINT_TARGET_SCORES.csv.gz',usecols=['physical_team_key','target','B8L2','D10','IoU3D100','complete_evaluable'])
    scores=pd.concat([scores,pd.read_csv(BASE/'computed_delta/NEW_TARGET_SCORES.csv.gz')],ignore_index=True)
    index=table(z4,'stage04_computation/PHYSICAL_ENDPOINT_INDEX.csv.gz')
    index=pd.concat([index,pd.read_csv(BASE/'computed_delta/NEW_PHYSICAL_INDEX.csv.gz')],ignore_index=True)
    order=table(z2,'stage04_computation/design/BASE_256_ORDERS.csv.gz')
    lookup={(r.image,tuple(sorted(r.member_object_ids.split('|')))):r.physical_team_key for r in index.itertuples()}
    whole=scores[scores.target=='全部'].set_index('physical_team_key')
    held={r['object_id'] for r in json.loads((BASE/'INDEPENDENT_HOLDS_13.json').read_text(encoding='utf8'))}
    pools=json.loads((BASE/'CORRECTED_PRIMARY_POOLS.json').read_text(encoding='utf8'))
    requests={};links=[]
    for p in pools:
        if p['family'] not in ['overall_before','overall_after','whole_compatible']:continue
        members=set(p['records'])-held
        for r in order[order.image==p['image']].itertuples():
            sequence=[x for x in r.base_member_object_ids.split('|') if x in members]
            for k in [6,10]:
                if k>len(sequence):continue
                team=tuple(sorted(sequence[:k]));key=(p['image'],team);phys=lookup.get(key)
                if phys not in whole.index:phys=None
                request=requests.setdefault(key,dict(image=p['image'],members=list(team),k=k,cached_physical_team_key=phys,targets=['全部']))
                links.append(dict(image=p['image'],family=p['family'],base_replicate=r.base_replicate,k=k,team=team))
    if not args.summarize:
        (BASE/'EXCLUDE13_SELECTED_REQUESTS.json').write_text(json.dumps(list(requests.values()),ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        print('unique teams',len(requests),'new native evaluations',sum(r['cached_physical_team_key'] is None for r in requests.values()));return
    assert (OUT/'COMPUTATION_RECEIPT.json').exists()
    new={}
    for path in OUT.glob('*.jsonl'):
        for line in path.read_text(encoding='utf8').splitlines():
            r=json.loads(line);new[(r['image'],tuple(r['members']))]=r['scores']['全部']
    result=[]
    for r in links:
        key=(r['image'],r.pop('team'));request=requests[key];phys=request['cached_physical_team_key']
        score=whole.loc[phys].to_dict() if phys else new[key]
        result.append(dict(r,**{m:score[m] for m in ['B8L2','D10','IoU3D100','complete_evaluable']}))
    frame=pd.DataFrame(result);frame.to_csv(OUT/'PAIRED_PATH_VALUES.csv.gz',index=False)
    headline={}
    for name,a,b,ka,kb in [('screening_k10','overall_before','overall_after',10,10),('whole_compatible_k10','overall_after','whole_compatible',10,10),('screened_6_to_10','overall_after','overall_after',6,10)]:
        pair=frame[(frame.family==a)&(frame.k==ka)].merge(frame[(frame.family==b)&(frame.k==kb)],on=['image','base_replicate'],suffixes=('_a','_b'),validate='one_to_one')
        headline[name]={m:paired_metric(pair[m+'_a'],pair[m+'_b'],pair.image,set()) for m in ['B8L2','D10','IoU3D100','complete_evaluable']}
        baseline=json.loads((BASE/'computed_delta/CORRECTED_HEADLINES.json').read_text(encoding='utf8'))[name]
        for m in headline[name]:
            supported=set(headline[name][m]['per_image'])
            headline[name][m]['corrected_baseline_same_image_panel_mean']=sum(v for im,v in baseline[m]['per_image'].items() if im in supported)/len(supported)
    (OUT/'HEADLINES.json').write_text(json.dumps(headline,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
    print({k:(v['B8L2']['mean'],v['complete_evaluable']['mean']) for k,v in headline.items()})
if __name__=='__main__':main()
