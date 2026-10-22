"""Extract a named exact two-view replacement from delivered design and scalar evidence."""
from pathlib import Path
import argparse,json
import pandas as pd

def main(root,panel_id,mask_from,mask_to,out):
    p=pd.read_csv(root/'design/PANELS.csv');p=p[p.panel_id==panel_id]
    if len(p)!=1:raise ValueError('Unknown/duplicate panel_id')
    l=pd.read_csv(root/'design/PANEL_TEAM_LINKS.csv.gz')
    l=l[(l.panel_id==panel_id)&l.selected_mask.isin([mask_from,mask_to])].set_index('selected_mask')
    if len(l)!=2:raise ValueError('Two distinct registered selected_mask values required')
    f,t=l.loc[mask_from],l.loc[mask_to]
    s0=set(str(f.member_set_key).split('|'));s1=set(str(t.member_set_key).split('|'))
    wanted={f.team_key_a,f.team_key_b,t.team_key_a,t.team_key_b}
    d=pd.read_csv(root/'results/native/ENDPOINT_SCALARS.csv.gz',low_memory=False)
    d=d[d.team_key.isin(wanted)].set_index('team_key')
    metrics=['B8L2','D10','nodes','fusion_turn_n','fusion_short_turn_edges','S_bottom_deg','dir','Hmean','Hcenter','iou_2d','omission','extension','recorded_time_total_seconds']
    result={'panel':p.iloc[0].to_dict(),'from_mask':mask_from,'to_mask':mask_to,
            'core':sorted(s0&s1),'removed':sorted(s0-s1),'added':sorted(s1-s0),
            'm':len(s0-s1),'endpoints':[],'deltas':{}}
    for side in ['a','b']:
        rows=[]
        for phase,lr in [('before',f),('after',t)]:
            r=d.loc[lr['team_key_'+side]].copy()
            item=r.astype(object).where(pd.notna(r),None).to_dict()
            item.update(side=side,phase=phase,team_key=lr['team_key_'+side]);rows.append(item)
        result['endpoints']+=rows
        result['deltas'][side]={m:rows[1][m]-rows[0][m] if rows[0].get(m) is not None and rows[1].get(m) is not None else None for m in metrics}
    # Pandas scalar conversion via JSON roundtrip; unavailable values remain null.
    result=json.loads(pd.Series(result).to_json(force_ascii=False))
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2));print(out)

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--root',type=Path,default=Path('.'))
    a.add_argument('--panel',required=True);a.add_argument('--from-mask',type=int,required=True);a.add_argument('--to-mask',type=int,required=True)
    a.add_argument('--out',type=Path,required=True);v=a.parse_args();main(v.root,v.panel,v.from_mask,v.to_mask,v.out)
