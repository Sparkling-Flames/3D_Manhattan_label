"""Screen every frozen historical unit; select additional visual checks, not verdicts."""
import base64
import io
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

from . import study
from .diagnostics import data

REPO = Path(__file__).resolve().parents[4]
OUT = study.ROOT / 'history_visual_review'
FOUNDATION = REPO / 'analysis_results/panorama_studio_20260907_v3'


def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))


def previous_images(value):
    if isinstance(value, dict):
        return ({value['image_id']} if 'image_id' in value else set()).union(
            *(previous_images(v) for v in value.values()))
    if isinstance(value, list):
        return set().union(*(previous_images(v) for v in value))
    return set()


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    _, recs, eligibility = data(study.ROOT)
    result = study.ROOT / 'local_recheck/results'
    pairs = pd.read_csv(result / 'pairwise_rules.csv')
    cache = read(result / 'cache.json')
    seen = set()
    for p in [study.ROOT/'inputs/key39_source.json',
              REPO/'analysis_results/cluster_review_extra_20260919/evidence.json',
              study.ROOT/'inputs/pilot_evidence.json', study.ROOT/'inputs/new_six_evidence.json']:
        seen |= previous_images(read(p))
    reasons = ['接缝改变相容判断', '绑定改变相容判断', '自由匹配改变相容判断',
               '相近作答被整图分开', '同簇局部差异集中', '普通相近对照']
    units, candidates = [], []
    findings = read(OUT/'visual_findings.json') if (OUT/'visual_findings.json').exists() else []
    checked = {(f['code'], f['condition']) for f in findings}
    for key, group in cache.items():
        iid, cond = key.split('|')
        q = pairs[(pairs.image_id == iid) & (pairs.condition == cond)]
        lab = group['labels']['split_fixed_9']
        labels = dict(zip(lab['ids'], lab['labels']))
        counts = pd.Series(lab['labels']).value_counts().to_dict()
        flags = {name: [] for name in reasons}
        for _, p in q.iterrows():
            if p.status not in ['split_available', 'both_available']:
                continue
            same = labels[p.id_a] == labels[p.id_b]
            item = dict(image_id=iid, code=group['code'], condition=cond,
                        id_a=p.id_a, id_b=p.id_b, workers=[p.worker_a, p.worker_b],
                        count=int(p.count_a), split_fixed=float(p.split_fixed),
                        split_cyclic=float(p.split_cyclic), split_free=float(p.split_free),
                        bound_fixed=float(p.bound_fixed) if pd.notna(p.bound_fixed) else None,
                        same_cluster=bool(same), cluster_sizes=[int(counts[labels[p.id_a]]), int(counts[labels[p.id_b]])])
            marks = [p.split_fixed > 9 and p.split_cyclic <= 9,
                     pd.notna(p.bound_fixed) and (p.split_fixed <= 9) != (p.bound_fixed <= 9),
                     p.split_cyclic > 9 and p.split_free <= 9,
                     p.split_fixed <= 4.5 and not same,
                     same and p.split_fixed >= 6 and p.split_fixed > 3*p.split_fixed_mean,
                     same and .5 <= p.split_fixed <= 3 and len(group['ids']) >= 8 and cond == 'manual']
            for reason, yes in zip(reasons, marks):
                if yes:
                    score = -p.split_fixed if reason in reasons[3:4]+reasons[5:] else p.split_fixed
                    flags[reason].append(dict(item, reason=reason, score=float(score)))
        available = eligibility[(eligibility.image_id == iid) & (eligibility.condition == cond)]
        units.append(dict(key=key, code=group['code'], image_id=iid, condition=cond,
                          responses=len(group['ids']), previously_in_selected_reviews=iid in seen,
                          raw_records=len(available), excluded_workers=int(available.excluded_worker.sum()),
                          trigger_counts={r: len(a) for r, a in flags.items()},
                          visual_status='本轮指定作答对已目视；非全图逐人验收' if (group['code'],cond) in checked else '本轮尚未目视'))
        for reason, items in flags.items():
            if items:
                candidates.append(max(items, key=lambda a: a['score']))
    candidates.sort(key=lambda a: (a['image_id'] in seen, reasons.index(a['reason']), -a['score'], a['code']))
    selected, chosen = [], set()
    # Cover failure types first; never silently reuse the 39/12/6/6 development cases.
    for reason in reasons:
        options = [c for c in candidates if c['reason'] == reason and c['image_id'] not in seen|chosen]
        for c in options[:2 if reason in reasons[3:] else 1]:
            selected.append(c); chosen.add(c['image_id'])
    for rank, c in enumerate(selected, 1):
        c.update(priority=rank, user_decision=None,
                 visual_status='指定作答对已初核；待用户' if (c['code'],c['condition']) in checked else '待本轮目视')
        g = cache[c['image_id']+'|'+c['condition']]
        c['full_members'] = dict(workers=g['workers'], ids=g['ids'], counts=g['counts'],
                                 split_fixed_9=g['labels']['split_fixed_9'])
    def priority(u):
        triggered = [i for i,r in enumerate(reasons[:-1]) if u['trigger_counts'][r]]
        return (u['previously_in_selected_reviews'], min(triggered, default=6), -u['responses'], u['code'], u['condition'])
    units.sort(key=priority)
    for rank,u in enumerate(units,1):u['screening_priority']=rank
    study.dump(OUT/'all_history_queue.json', units)
    study.dump(OUT/'candidate_pairs.json', candidates)
    study.dump(OUT/'selected_evidence.json', selected)
    assert len(units) == 239 and len({u['image_id'] for u in units}) == 214
    assert all(c['image_id'] not in seen for c in selected)
    assert len({c['image_id'] for c in selected}) == len(selected)
    assert all(c['user_decision'] is None for c in selected)
    summaries = json.JSONDecoder().raw_decode((FOUNDATION/'history_data.js').read_text(encoding='utf-8').split('push(...', 1)[1])[0]
    lookup = {s['image_id']: s for s in summaries}
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 16)
    for c in selected:
        raw = (FOUNDATION/lookup[c['image_id']]['history_script']).read_text(encoding='utf-8')
        encoded = re.search(r'\{const image="data:image/[^;]+;base64,([^"]+)"', raw).group(1)
        bg = Image.open(io.BytesIO(base64.b64decode(encoded))).convert('RGB').resize((1024,512))
        canvas = Image.new('RGB', (1024,1120), 'white')
        for side, cid in enumerate([c['id_a'], c['id_b']]):
            a = recs[cid]; im = bg.copy(); d = ImageDraw.Draw(im)
            color = '#ff5030' if side == 0 else '#00c7ff'
            for role, indices in [('T', a['up']), ('B', a['dn'])]:
                for ordinal, idx in enumerate(indices, 1):
                    x, y = a['p'][idx]; d.ellipse((x-3,y-3,x+3,y+3),fill=color,outline='black')
                    d.text((min(x+4,965),y-15), f'{role}{ordinal}/p{idx+1}', fill=color,
                           font=font, stroke_width=1, stroke_fill='black')
            canvas.paste(im,(0,side*560+48)); d=ImageDraw.Draw(canvas)
            d.text((8,side*560+6),f"{c['priority']}. {c['code']} {c['condition']} {a['audit']['worker']} | {len(a['p'])} points",fill='black',font=font)
            d.text((8,side*560+27),'T/B: conditional roles, separate x rank. p: effective source index. No inferred wall edges.',fill='black',font=font)
        canvas.save(OUT/f"{c['priority']:02}_{c['code']}.jpg",quality=93)
    print(json.dumps(dict(units=len(units),images=214,selected=[{k:c[k] for k in
        ['priority','code','condition','workers','reason','split_fixed']} for c in selected]),ensure_ascii=True))


if __name__ == '__main__':
    build()
