"""Build the fixed offline overall-quality review; private identity key stays separate."""
from pathlib import Path
from itertools import combinations
import argparse
import base64
import copy
import gzip
import json
import random
import re
import zipfile
import csv

import numpy as np

from .quality_validation_followup_20261107 import ROOT, OUT, ENGINE
from .quality_independent_validation_20261024 import display_layout, image_path
from .scope_quality_scoring_20261016 import scoring_engine

SEED=20261107
HERE=OUT/'human_review'
TEMPLATE=ROOT/'tools/thesis_main/analysis/independent_review_20261107.html'


def packet(cases, reviewer, excluded_worker=None):
    rng=random.Random(SEED+int(reviewer[1:]))
    selected=[];key=[]
    for c in cases:
        if excluded_worker and excluded_worker in c['excluded_workers']:continue
        item=copy.deepcopy(c['public']);flip=rng.choice([False,True])
        if flip:
            item['left'],item['right']=item['right'],item['left']
            if 'scores' in item:item['scores']['left'],item['scores']['right']=item['scores']['right'],item['scores']['left']
        key.append(dict(case_id=item['id'],flip=flip,**c['private']))
        selected.append(item)
    practice=[v for v in selected if v['practice']];formal=[v for v in selected if not v['practice']]
    rng.shuffle(formal)
    return practice+formal,key


def make_cases():
    pools=json.loads((ROOT/'research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json').read_text(encoding='utf-8'))['images']
    difficulty={r['image']:r for r in json.loads((ROOT/'research/data/releases/v2.1/difficulty_records.json').read_text(encoding='utf-8'))['records']}
    conditions=list(csv.DictReader((ROOT/'research/data/releases/v2.1/admitted_space_extension/image_difficulty_20261030/POOL_TARGET_CONDITIONS.csv').open(encoding='utf-8-sig')))
    grades={r['image']:r['official_difficulty'] for r in conditions if r['official_difficulty'] in ['简单','中等','困难']}
    multi={r['image'] for r in conditions if int(r['legal_targets_in_image_condition'])>1}
    screened=json.loads((ROOT/'research/data/doorway_review_20261030/screen439_results_20261031/POOLS.json').read_text(encoding='utf-8'))
    retained={r for p in screened if p['version']=='after_screen' and not p['sensitivity'] for r in p['records']}
    pools={p['pool_id']:p for p in pools if p['meta']['condition']=='manual' and p['meta']['layer'] in ['ordinary_manual','doorway_manual']
           and not difficulty[p['meta']['image']]['gt_error_excluded'] and difficulty[p['meta']['image']]['current_class'] not in ['待修正GT','待复核']}
    for p in pools.values():
        m=p['meta'];m['difficulty']=grades.get(m['image'],'门洞单列');m['multi_space']=m['image'] in multi or m['layer']=='doorway_manual'
        if m['layer']=='doorway_manual':p['records']=[r for r in p['records'] if r['id'] in retained]
    rng=random.Random(SEED)
    eligible=[]
    with scoring_engine(ENGINE/'measurement_engine.zip',ENGINE/'working_models.py') as (engine,_):
        def layout(record):return display_layout(record['points'],engine.geometry(record['points']))
        for pool in sorted(pools.values(),key=lambda p:p['pool_id']):
            path=image_path({'image_id':pool['meta']['image_id']})
            if path is None:continue
            records=[]
            for r in pool['records']:
                if len(r['points'])<8 or not r.get('quality_usable'):continue
                try:
                    result=engine.measure(engine.geometry(r['points']),engine.geometry(pool['reference']['points_1024x512']))
                except (ValueError,ArithmeticError):continue
                if result['status']=='complete':records.append(r)
            if len(records)>=2:eligible.append((pool,records,path))
        rng.shuffle(eligible)
        chosen=[];used=set();buildings={}
        # Difficulty is an image attribute; doorway stays a separate stratum.
        for stratum,quota in [('简单',9),('中等',9),('困难',9),('门洞单列',3)]:
            count=0
            candidates=[v for v in eligible if v[0]['meta']['difficulty']==stratum]
            candidates.sort(key=lambda v:not v[0]['meta']['multi_space'])
            for pool,records,path in candidates:
                m=pool['meta'];b=m['building']
                if m['image'] in used or buildings.get(b,0)>=4:continue
                pairs=list(combinations(sorted(records,key=lambda r:r['id']),2))
                if not pairs:continue
                a,b=rng.choice(pairs);chosen.append((pool,a,b,path,stratum));used.add(m['image']);buildings[m['building']]=buildings.get(m['building'],0)+1;count+=1
                if count==quota:break
            assert count==quota,(stratum,count)
        cases=[];image_cache={}
        def image_data(path):
            if str(path) not in image_cache:image_cache[str(path)]='data:image/'+('png' if path.suffix.lower()=='.png' else 'jpeg')+';base64,'+base64.b64encode(path.read_bytes()).decode()
            return image_cache[str(path)]
        for j,(pool,a,b,path,stratum) in enumerate(chosen):
            ref=pool['reference']['points_1024x512'];m=pool['meta']
            cases.append(dict(public=dict(id=f'Q{j+1:03}',type='quality',practice=False,image=m['image'],image_data=image_data(path),
                left=layout(a),right=layout(b),reference=display_layout(ref,engine.geometry(ref)),pair_indices=None,
                scores={'left':{'B8L2':float(a['B8L2']),'D10':float(a['D10'])},'right':{'B8L2':float(b['B8L2']),'D10':float(b['D10'])}},
                difficulty=m['difficulty'],condition='manual',doorway=m['layer']=='doorway_manual',multi_space=m['multi_space'],
                target_note='分数以黄色主目标参考计算；另一合理空间不能仅因低分判为乱标。' if m['multi_space'] else '两份作答均来自本题主目标池，黄色虚线为评分参考。'),
                excluded_workers=[a['worker'],b['worker']],private=dict(pool_id=pool['pool_id'],left_object=a['id'],right_object=b['id'],
                reference_id=m['reference_id'],reference_version=m['reference_version'],sampling=stratum)))
    HERE.mkdir(parents=True,exist_ok=True)
    with gzip.open(HERE/'CASES_PRIVATE.json.gz','wt',encoding='utf-8') as f:json.dump(cases,f,ensure_ascii=False)
    (HERE/'DESIGN.json').write_text(json.dumps(dict(seed=SEED,quality_pairs=30,teams=0,correspondence_pairs=0,practice=0,
        quality_sampling='9 easy + 9 moderate + 9 difficult ordinary Manual; 3 doorway Manual images using current retained records; no excluded GT images',
        correspondence_sampling='removed by user; overall quality only',
        minimum_independent_reviews=3,planned_reviewers='3-5; actual roster pending',
        exclusion='whole participating team excluded from correspondence review; each original author excluded from quality pair',
        blindness='worker IDs and classes hidden; scores available after initial grading',
        independence='new evaluation round; images may have been seen; no recruitment performed'),ensure_ascii=False,indent=2),encoding='utf-8')
    return cases


def main():
    p=argparse.ArgumentParser();p.add_argument('--rebuild-cases',action='store_true');args=p.parse_args()
    if args.rebuild_cases or not (HERE/'CASES_PRIVATE.json.gz').exists():cases=make_cases()
    else:
        with gzip.open(HERE/'CASES_PRIVATE.json.gz','rt',encoding='utf-8') as f:cases=[c for c in json.load(f) if c['public']['type']=='quality']
        with gzip.open(HERE/'CASES_PRIVATE.json.gz','wt',encoding='utf-8') as f:json.dump(cases,f,ensure_ascii=False)
    # User requested one fixed randomised packet for all respondents, no roster.
    roster={'R00':None}
    design=json.loads((HERE/'DESIGN.json').read_text(encoding='utf-8'))
    design.update(teams=0,correspondence_pairs=0,correspondence_sampling='removed; overall quality only',quality_task='overall good/medium/poor plus per-answer defect choices',distribution='one fixed randomised shared ZIP; respondent-specific anonymous answer ID',
                  planned_reviewers='user distributes; 3-5 suggested, not assigned',
                  exclusion='self-reported own-answer/team opt-out; no personnel roster requested per user',
                  practice_source='none; user removed practice', schema='overall_quality_review_20261107_v3', blindness='identity and algorithm correspondence hidden; scores revealed after first grades; UI hiding only')
    (HERE/'DESIGN.json').write_text(json.dumps(design,ensure_ascii=False,indent=2),encoding='utf-8')
    mapping={};coverage={c['public']['id']:[] for c in cases if not c['public']['practice']}
    for reviewer,worker in roster.items():
        public,key=packet(cases,reviewer,worker);mapping[reviewer]=dict(worker=worker,key=key)
        payload=json.dumps(dict(packet_id=reviewer,formal=True,cases=public),ensure_ascii=False,separators=(',',':')).replace('</','<\\/')
        page=TEMPLATE.read_text(encoding='utf-8').replace('__PAYLOAD__',payload)
        (HERE/'index.html').write_text(page,encoding='utf-8')
        for c in public:
            if not c['practice']:coverage[c['id']].append(reviewer)
    (HERE/'ASSIGNMENT_PRIVATE.json').write_text(json.dumps(mapping,ensure_ascii=False,indent=2),encoding='utf-8')
    (HERE/'COVERAGE.json').write_text(json.dumps(dict(fixed_shared_packet=True,cases=list(coverage),
        responses_received=0,minimum_independent_reviews=3,self_exclusion='self-reported opt-out; no author roster collected',
        independent_review_coverage='pending actual returned answers'),ensure_ascii=False,indent=2),encoding='utf-8')
    instructions='布局标注调查 · 简洁版\n\n1. 完整解压ZIP，用Edge或Chrome双击index.html。无需联网或服务器。\n2. 使用自动匿名编号即可。如修改编号，请点击使用此编号。\n3. 无练习题。30道质量题：左右各选好/中/差，完成质量和问题选项后可查看分数。同时勾选每份标注的问题；不做独立结构对应题。\n4. 好：主体完整且位置/高度基本合理；中：局部缺漏偏移，主体可用；差：主要结构、范围或几何有明显问题。请先按原图独立判断；查看分数后会显示Q的暂定粗略分档，不是要求你服从的标准答案。\n5. 不要求判断多个合理空间。参考只表示当前评分目标。\n6. 点击全景放大，底面和三维同时显示。理由选填，认出自己的作答可回避。\n7. 看分前判断会单独保存。先独立判断，不互相讨论。\n8. 定期导出JSON，完成后只发回JSON，不用回传ZIP。浏览器自动保存，换设备使用同一编号导入答卷。\n\n全部Manual，普通图三个难度各9张，另3张门洞。分数内嵌在离线页面，请不要预先查看源码。影像仅用于本次研究，请勿另行公开传播。\n'
    (HERE/'使用说明.txt').write_text(instructions,encoding='utf-8-sig')
    destination=OUT/'独立人工调查_固定题集_20261107.zip'
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as z:
        for name in ['index.html','使用说明.txt']:z.write(HERE/name,name)
    with zipfile.ZipFile(destination) as z:
        assert z.namelist()==['index.html','使用说明.txt'];assert z.read('index.html')==(HERE/'index.html').read_bytes()
    print('fixed packet',len(public),'cases; ZIP',destination.stat().st_size,'bytes')


if __name__=='__main__':main()
