#!/usr/bin/env python3
"""A small balanced display shortlist; selection does not modify frozen rules."""
from pathlib import Path
import pandas as pd
from assessment_summary_common import BASE,ROOT,HERE,stream_events,write_json,sha

SELECTIONS=[
    ('nested_new2','I20_98ee8ec70484badcca5a88','N01','主类跨构成后清楚变坏','Uw-12：C01→C02，A/B保持6节点且高Q，C变5节点、质量下降。'),
    ('nested_new2','I20_a6156da6a162584540585e','N02','同构成稳定但较低质量，跨构成后更好','Uw-12：C02→C01，A/B约55–57分且联合/shape都稳，C约96分并恢复一个参考邻近角点。'),
    ('nested_new2','I20_194b6e79cd6871602b77c8','N03','同图同方向的新背景小效应反例','Uw-12：另一套已冻结块/共同背景下，A/B/C均约97–98分，主/shape均稳。与N02一起防止把大效应当同图所有团队必现。'),
    ('nested_new2','I20_7c2bb302842255defff2ae','N04','同构成换人严重不稳反例','q9v-30：同构成A约90分、B约38分且节点6→5；C约93分。很大C−B改善部分依赖B失误，不能只展示改善均值。'),
    ('direction','I20_53177bc96b540efdc46e4b','R08_POS','困难条件跨类改善正例','Uw-22：hard_new C06→C03，A/B约61.6分且同构成稳定，C约86.5分；这是一例改变后更好，并非跨类更稳定。'),
    ('direction','I20_0c581d2133cfc0679fda3b','R04_COUNTER','细类同构成不稳而跨构成接近的反例','X7-07：R04同构成A/B质量与形状不近，另一类C反而接近A；帮助解释R04固定n13/m2主gap未重现。'),
]


def main():
    output=[]
    for panel in ['nested_new2','direction']:
        sel={row[1]:row for row in SELECTIONS if row[0]==panel}
        request=BASE/'assessment'/(panel+'_requests.json.gz')
        md={e['event_id']:e for e in stream_events(request) if e['event_id'] in sel}
        assert set(md)==set(sel)
        metrics={}
        for pid in {e['pool_id'] for e in md.values()}:
            part=BASE/'assessment'/(panel+'_metrics')/'event_parts'/(pid+'.csv.gz')
            f=pd.read_csv(part)
            for r in f[f.event_id.isin(sel)].to_dict('records'):metrics[r['event_id']]=(r,sha(part))
        native='native_nested_new2' if panel=='nested_new2' else 'native_directions'
        for eid,(_,_,cid,category,reason) in sel.items():
            event=md[eid];metric,partsha=metrics[eid]
            output.append(dict(case_id=cid,case_category_zh=category,reason_zh=reason,
                selection='Frozen assessment outcomes read only to choose balanced display cases; not additional confirmation or rule selection.',
                panel=panel,event=event,metrics=metric,
                request_sha256=sha(request),metric_part_sha256=partsha,
                native_pool_path=str((BASE/'assessment'/native/'pools'/(event['pool_id']+'.json.gz')).relative_to(ROOT))))
    write_json(HERE/'FINAL_REVERSE_CASE_SUGGESTIONS.json',output)
    print('Saved 6 exact positive/counterexample suggestions',flush=True)


if __name__=='__main__':main()
