"""Extract requested real events, whole pools and A/B states for offline review.

Selection must be documented by the caller; this utility does not choose winners.
"""
from pathlib import Path
import argparse,csv,gzip,json,hashlib
HERE=Path(__file__).resolve().parent

def read(p):
    with gzip.open(p,'rt',encoding='utf-8') as f:return json.load(f)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--event-id',action='append',required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--selection-description',required=True)
    args=ap.parse_args();wanted=set(args.event_id)
    selected={}
    with gzip.open(HERE/'common_events.csv.gz','rt',encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            if r['event_id'] in wanted:selected[r['event_id']]=r
    assert set(selected)==wanted,'unknown requested event ID'
    pools={p['pool_id']:p for p in read(HERE.parent/'recovered'/'work_v2_20261019'/'fusion'/'INPUT_SNAPSHOT.json.gz')['images']}
    bypool={}
    for r in selected.values():
        pid=r['pool_id']
        if pid not in bypool:
            folder=HERE/'native_runs'/'pools'/pid
            rows=[e for e in selected.values() if e['pool_id']==pid]
            teamids={e['team_id_'+s] for e in rows for s in ('a','b')}
            requestids={e['request_'+s] for e in rows for s in ('a','b')}
            bypool[pid]=dict(states={x['team_id']:x['automatic'] for x in read(folder/'states.json.gz')['states'] if x['team_id'] in teamids},
                             results={x['request_id']:x for x in read(folder/'request_results.json.gz')['results'] if x['request_id'] in requestids},
                             requests={x['request_id']:x for x in read(folder/'requests.json.gz')['requests'] if x['request_id'] in requestids})
    cases=[]
    for event_id in args.event_id:
        r=selected[event_id];pool=pools[r['pool_id']];cached=bypool[r['pool_id']]
        teams={s:dict(request=cached['requests'][r['request_'+s]],result=cached['results'][r['request_'+s]],state=cached['states'][r['team_id_'+s]]) for s in ('a','b')}
        cases.append(dict(event_id=event_id,event=r,pool=pool,teams=teams))
    out=dict(schema='PartA_real_event_review_cases_v1',selection_description=args.selection_description,
             no_new_fusion=True,includes_whole_pool=True,original_image_embedded=False,
             event_fields_are_original_csv_text=True,team_result_and_state_fields_are_original_json_types=True,cases=cases)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    raw=json.dumps(out,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
    if args.out.suffix=='.gz':args.out.write_bytes(gzip.compress(raw,mtime=0))
    else:args.out.write_bytes(raw)
    print(json.dumps(dict(cases=len(cases),file=str(args.out),sha256=hashlib.sha256(args.out.read_bytes()).hexdigest())))

if __name__=='__main__':main()
