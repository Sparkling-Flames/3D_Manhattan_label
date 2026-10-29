"""选择少量正反事件，原生重放完整票账并提供离线原答/ABC浏览。"""
from pathlib import Path
import base64
import gzip
import json
import itertools
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from strict_large_blocks_v21_20261029 import ROOT, SOURCE, OUT, write_json, write_csv
sys.path.insert(0, str(SOURCE / 'experiment'))
from benchmark_engine import load_engine


def main():
    events = pd.read_csv(OUT / 'results/EVENT_METRICS.csv.gz', low_memory=False)
    im = pd.read_csv(OUT / 'results/IMAGE_CONDITION_RESULTS.csv')
    selections = []
    for _, group in events[events.m.eq(10)].groupby(['method', 'n']):
        valid = group.dropna(subset=['G_A'])
        selections.append(valid.loc[(valid.G_A-valid.G_A.median()).abs().idxmin()])
    target = im[im.method.eq('TARGET_DSTRUCT_K3') & im.m.eq(9)].sort_values('n').drop_duplicates('pool_id', keep='last').dropna(subset=['G_A'])
    for index in [target.G_A.idxmin(), target.G_A.idxmax()]:
        row = target.loc[index]
        group = events[events.pool_id.eq(row.pool_id) & events.method.eq(row.method) & events.n.eq(row.n) & events.m.eq(9)].dropna(subset=['G_A'])
        selections.append(group.loc[(group.G_A-row.G_A).abs().idxmin()])
    pools = {p['pool_id']: p for p in json.loads((OUT / 'INPUT_SNAPSHOT.json').read_text(encoding='utf-8'))['images']}
    dest = OUT / 'cases'
    dest.mkdir(exist_ok=True)
    native = load_engine(ROOT)
    votes, parity, index, browser_cases, connections = [], [], [], [], []
    for number, series in enumerate(selections, 1):
        event = series.to_dict()
        pool = pools[event['pool_id']]
        arms = {}
        with native.Engine(full_state=True) as engine:
            for arm in 'ABC':
                workers = event[arm+'_members'].split('|')
                row = engine.evaluate(pool, workers)
                for field in ['B8L2', 'D10', 'nodes', 'minimum_support', 'geometry_area_h2', 'height_mean_h']:
                    expected = event.get(arm+'_'+field)
                    actual = row.get(field)
                    assert (pd.isna(expected) and actual is None) or abs(expected-actual) < 1e-8, (arm, field, expected, actual)
                parity.append(dict(event_id=event['event_id'], arm=arm, parity=True))
                row['data_release'] = row['underlying_data_version'] = 'v2.1'
                arms[arm] = row
                d = set(event['D'].split('|'))
                for group in row['full_state']['identity_groups']:
                    members = group['members']
                    assert len({m['worker'] for m in members}) == group['support']
                    ds = sum(m['worker'] in d for m in members)
                    votes.append(dict(case=number, event_id=event['event_id'], arm=arm, feature_id=group['feature_id'], support=group['support'], selected=group['selected'], minimum_support=row['minimum_support'], D_support=ds, replacement_support=group['support']-ds, D_alone_passes=ds>=row['minimum_support'], replacement_alone_passes=group['support']-ds>=row['minimum_support'], center=json.dumps(group['center']), members=json.dumps(members, ensure_ascii=False)))
        case = native.gs.clean(dict(event=event, pool=pool, arms=arms))
        for arm, row in arms.items():
            selected = [g for g in row['full_state']['identity_groups'] if g['selected']]
            disjoint = sum(not ({x['worker'] for x in a['members']} & {x['worker'] for x in b['members']}) for a, b in itertools.combinations(selected, 2))
            connections.append(dict(case=f'case_{number:02d}.json', arm=arm, selected=len(selected), disjoint_support_selected_pairs=disjoint, ring_json=json.dumps(row['full_state']['ring_diagnostics'], ensure_ascii=False)))
        write_json(dest / f'case_{number:02d}.json.gz', case)
        files = list((ROOT / 'data/mp3d_layout').glob('*/img/' + pool['meta']['image_id'] + '.png'))
        assert files, pool['meta']['image_id']
        photo = sorted(files, key=lambda p: ('no_occ' in str(p), str(p)))[0]
        photo_data = 'data:image/png;base64,' + base64.b64encode(photo.read_bytes()).decode()
        fig, axes = plt.subplots(2, 2, figsize=(16, 8))
        rgb = plt.imread(photo)
        for ax, arm in zip(axes.flat, ['reference', 'A', 'B', 'C']):
            ax.imshow(rgb, extent=(0, 1024, 512, 0))
            ref = np.asarray(pool['reference']['points_1024x512'])
            ax.scatter(ref[:, 0], ref[:, 1], s=18, facecolors='none', edgecolors='white', linewidths=1)
            points = ref if arm == 'reference' else np.asarray((arms[arm].get('geometry') or {}).get('points') or [])
            if len(points):
                for i in range(len(points)//2):
                    ax.plot(points[2*i:2*i+2, 0], points[2*i:2*i+2, 1], color='#ffc400', linewidth=1)
                ax.scatter(points[:, 0], points[:, 1], s=12, c='#ffeb00')
            title = pool['meta']['image'] + ' / reference' if arm == 'reference' else f'{arm}: Q={arms[arm].get("B8L2"):.3f}, nodes={arms[arm]["nodes"]}, MV50={arms[arm]["minimum_support"]}'
            ax.set_title(title)
            ax.set_xlim(0, 1024); ax.set_ylim(512, 0); ax.axis('off')
        fig.suptitle(f'{event["method"]} n={event["n"]} m={event["m"]}; G_A={event["G_A"]:.3f}, G_S={event["G_S"]:.3f}')
        fig.tight_layout()
        fig.savefig(dest / f'case_{number:02d}.png', dpi=130)
        plt.close(fig)
        index.append(dict(case=number, image=event['image'], event_id=event['event_id'], method=event['method'], n=event['n'], m=event['m'], G_A=event['G_A'], G_S=event['G_S'], photo_source=str(photo.relative_to(ROOT)), selection='m10 median event; m9 TARGET strongest/weakest image then nearest-to-image-mean event'))
        browser_cases.append(dict(index=index[-1], photo=photo_data, reference=pool['reference']['points_1024x512'], records=pool['records'], event={k:event[k] for k in ['D','X','Y','Z']}, arms={a:dict(points=(arms[a].get('geometry') or {}).get('points'), Q=arms[a].get('B8L2'), status=arms[a]['score_status'], state=arms[a]['full_state']) for a in 'ABC'}))
    write_csv(dest / 'CASE_INDEX.csv', index)
    write_csv(dest / 'VOTE_GROUPS.csv.gz', votes)
    write_csv(dest / 'CONNECTION_AND_DISJOINT_SUPPORT_CHECK.csv', connections)
    write_json(dest / 'TRACE_PARITY.json', parity)
    (dest / 'data.js').write_text('const CASES=' + json.dumps(native.gs.clean(browser_cases), ensure_ascii=False, allow_nan=False) + ';', encoding='utf-8')
    (dest / 'index.html').write_text('''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>九/十人严格ABC案例</title>
<style>body{font:16px system-ui;margin:24px;background:#f4f5f7;color:#17202b}canvas{width:100%;max-width:1200px;background:#222}select{padding:8px;margin:8px}pre{white-space:pre-wrap}table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:5px}</style>
<h1>九/十人严格 ABC：原答、参考与投票账</h1><p>白色：当前参考；黄色：所选完整原答或融合结果。案例为事后机制展示，不替代全部事件统计。上下点共同决定几何高度。</p>
<label>案例<select id="case"></select></label><label>显示<select id="view"></select></label><canvas width="1024" height="512" id="canvas"></canvas><pre id="info"></pre><div id="votes"></div>
<script src="data.js"></script><script>
const cs=document.getElementById('case'),vs=document.getElementById('view'),ctx=document.getElementById('canvas').getContext('2d');
CASES.forEach((c,i)=>cs.add(new Option(`${i+1}: ${c.index.image} ${c.index.method} ${c.index.n}/${c.index.m}`,i)));
function outline(p,color){if(!p)return;ctx.strokeStyle=color;ctx.fillStyle=color;ctx.lineWidth=1.4;for(let i=0;i<p.length;i+=2){ctx.beginPath();ctx.moveTo(...p[i]);ctx.lineTo(...p[i+1]);ctx.stroke();}for(let k=0;k<2;k++){for(let i=k;i<p.length;i+=2){let a=p[i],b=p[(i+2)%p.length],dx=b[0]-a[0];if(dx>512)dx-=1024;if(dx< -512)dx+=1024;for(let shift of [-1024,0,1024]){ctx.beginPath();ctx.moveTo(a[0]+shift,a[1]);ctx.lineTo(a[0]+dx+shift,b[1]);ctx.stroke();}}}p.forEach((v,i)=>{ctx.beginPath();ctx.arc(v[0],v[1],3,0,7);ctx.fill();if(i%2===0)ctx.fillText(i/2+1,v[0]+4,v[1]-4);});}
function draw(){const c=CASES[+cs.value],v=vs.value,img=new Image();img.onload=()=>{ctx.drawImage(img,0,0,1024,512);outline(c.reference,'white');outline(v.startsWith('worker:')?c.records.find(r=>r.worker_id===v.slice(7)).points:c.arms[v]?.points,'#ffe600');};img.src=c.photo;document.getElementById('info').textContent=JSON.stringify({...c.index,blocks:c.event,selected:v,Q:c.arms[v]?.Q,status:c.arms[v]?.status},null,2);const arm=c.arms[v];document.getElementById('votes').textContent=arm?JSON.stringify(arm.state,null,2):'原答点号保持输入环序；完整人员与参考保存在对应JSON。';}
function change(){vs.innerHTML='';for(let a of ['reference','A','B','C'])vs.add(new Option(a,a));CASES[+cs.value].records.forEach(r=>vs.add(new Option(r.worker_id,'worker:'+r.worker_id)));vs.value='A';draw();}cs.onchange=change;vs.onchange=draw;change();
</script></html>''', encoding='utf-8')
    print(json.dumps(dict(cases=len(index), trace_arms=len(parity), vote_groups=len(votes))), flush=True)


if __name__ == '__main__':
    main()
