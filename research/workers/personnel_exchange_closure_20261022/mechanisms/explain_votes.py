"""Derive local mechanism tables from saved native states, without new scoring."""
from pathlib import Path
import gzip, json, sys
import numpy as np
import pandas as pd
sys.path.insert(0, '/tmp/hohonet_deps')
from shapely.geometry import Polygon, LineString
from shapely.validation import explain_validity

HERE=Path(__file__).resolve().parent

def read(cid):
    with gzip.open(HERE/'cases'/(cid+'.json.gz'),'rt') as f:return json.load(f)

def main():
    votes=pd.read_csv(HERE/'GROUP_VOTES.csv.gz')
    rows=[]
    for cid in ['manual_structure','manual_failure','manual_threshold20','manual_threshold21']:
        case=read(cid)
        for arm,t in zip('ABC',case['teams']):
            q=votes[(votes.case_id==cid)&(votes.arm==arm)]
            for corner,g in q.groupby('nearest_reference_corner'):
                # Multiple identity groups can point to the same reference opportunity.
                # Keep each group; never sum their support as if already fused.
                for r in g.to_dict('records'):
                    r.update(image=case['pool_meta']['image'],event_id=case['event']['event_id'],n=case['n'],
                             selected_ref_opportunity=bool(g.selected.any()),
                             matching_is_posthoc_nearest_reference=True)
                    rows.append(r)
    pd.DataFrame(rows).to_csv(HERE/'LOCAL_STRUCTURE_VOTES.csv',index=False)
    c=read('manual_failure')['teams'][2]
    pts=c['geometry']['footprint'];ids=c['geometry']['feature_ids'];cross=[]
    for i in range(len(pts)):
        for j in range(i+1,len(pts)):
            if j==i+1 or (i==0 and j==len(pts)-1):continue
            a=LineString([pts[i],pts[(i+1)%len(pts)]]);b=LineString([pts[j],pts[(j+1)%len(pts)]])
            if a.intersects(b):
                cross.append(dict(edge1=[ids[i],ids[(i+1)%len(pts)]],edge2=[ids[j],ids[(j+1)%len(pts)]],
                                  intersection_wkt=a.intersection(b).wkt))
    (HERE/'FAILURE_CONNECTION_MECHANISM.json').write_text(json.dumps(dict(
        case='manual_failure',score_status=c['score_status'],validity=explain_validity(Polygon(pts)),
        intersections=cross,scoring_or_geometry_modified=False),indent=2)+'\n')
    a,b=read('manual_threshold20'),read('manual_threshold21')
    checks=[]
    for arm in 'ABC':
        ta=next(t for t in a['teams'] if t['label']==arm);tb=next(t for t in b['teams'] if t['label']==arm)
        g0=votes[(votes.case_id=='manual_threshold20')&(votes.arm==arm)&(votes.nearest_reference_corner==1)].iloc[0]
        g1=votes[(votes.case_id=='manual_threshold21')&(votes.arm==arm)&(votes.nearest_reference_corner==1)].iloc[0]
        def obs(t,group):
            g=next(g for g in t['full_state']['identity_groups'] if g['feature_id']==group)
            return sorted((x['worker'],x['id'],x['pair_index']) for x in g['members'])
        checks.append(dict(arm=arm,added_background='|'.join(sorted(set(tb['member_workers'])-set(ta['member_workers']))),
                           same_critical_observations=obs(ta,g0.group)==obs(tb,g1.group),
                           support20=int(g0.support),support21=int(g1.support),threshold20=10,threshold21=11,
                           selected20=bool(g0.selected),selected21=bool(g1.selected),
                           B8L2_n20=ta['B8L2'],B8L2_n21=tb['B8L2']))
    pd.DataFrame(checks).to_csv(HERE/'FIXED_BLOCK_THRESHOLD_MECHANISM.csv',index=False)
    assert all(r['same_critical_observations'] for r in checks)
    assert {r['added_background'] for r in checks}=={'W121'}
    print(json.dumps(dict(local_vote_rows=len(rows),intersection_count=len(cross),critical_threshold_checked=True)))

if __name__=='__main__':main()
