"""六图视觉提出的点对候选；独立预览，不修复坐标或替换全量分区。"""
import importlib.util
import itertools
import json
import re
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

from . import local_points as lp
from .precision_audit import stable_angles

REPO = Path(__file__).resolve().parents[4]
OUT = lp.ROOT/'pair_pilot'
STUDIO = REPO/'analysis_results/image_portrait_20260914_v1/local_review_studio/key39'
HISTORY = REPO/'analysis_results/panorama_studio_20260907_v3'


def _paired(points, pairs):
    p = np.asarray(points,float); ix = np.asarray(pairs,int)-1
    if p.ndim != 2 or p.shape[1] != 2 or not len(p) or not np.isfinite(p).all(): raise ValueError('invalid points')
    if (p<0).any() or (p[:,0]>1024).any() or (p[:,1]>=512).any(): raise ValueError('point outside panorama')
    if ix.ndim != 2 or ix.shape[1] != 2 or sorted(ix.ravel()) != list(range(len(p))):
        raise ValueError('pairs must use each original endpoint exactly once')
    if np.any(p[ix[:,0],1] >= p[ix[:,1],1]): raise ValueError('top/bottom candidate reversed')
    return p[ix[:,0]],p[ix[:,1]]


def compare_pairs(a,b,pairs_a,pairs_b):
    at,ab = _paired(a,pairs_a);bt,bb = _paired(b,pairs_b)
    top,bottom = stable_angles(at,bt),stable_angles(ab,bb)
    bound = np.maximum(top,bottom)
    ft,fb,fc = [lp.features(c) for c in [top,bottom,bound]]
    same = len(a)==len(b)
    threshold = fc['bottleneck'] if same else None
    if same:
        i,j=linear_sum_assignment((bound>threshold+1e-10).astype(int))
    else:
        i,j=linear_sum_assignment(bound)
    witness=[dict(a_pair=int(x+1),b_pair=int(y+1),top_deg=float(top[x,y]),bottom_deg=float(bottom[x,y]),max_deg=float(bound[x,y])) for x,y in zip(i,j)]
    return dict(same_count=same,
                separate_bottleneck_deg=max(ft['bottleneck'],fb['bottleneck']) if same else None,
                bound_bottleneck_deg=threshold,example_matching=witness,
                radii=[dict(radius=r,top_matched=ft[f'matched_{int(r)}'],bottom_matched=fb[f'matched_{int(r)}'],
                            bound_matched_pairs=fc[f'matched_{int(r)}'],
                            strict_compatible=bool(same and fc[f'matched_{int(r)}']==len(at))) for r in lp.RADII])


def _candidate(name,pairs,note): return dict(name=name,pairs=pairs,note=note,status='AI候选，待用户确认')


def build_evidence():
    rows,audit=lp.load();by={r['canonical_annotation_id']:r for r in rows}
    cases=json.loads((lp.ROOT/'received_results/visual_cases.json').read_text(encoding='utf-8'))
    chosen={c['case_id']:c for c in cases}
    image='b8cTxDM8gDG_51c90ec9afc4495ab3788c6badc303df'
    br={r['worker_id']:r for r in rows if r['image_id']==image and r['raw_condition']=='semi'}
    b8=dict(code='b8cTxDM8gDG-07',condition='semi',id_a=br['W010']['canonical_annotation_id'],id_b=br['W014']['canonical_annotation_id'],worker_a='W010',worker_b='W014')
    selected=[b8,chosen[14],chosen[3],chosen[15],chosen[9],chosen[8]]
    seq=lambda n:[[i,i+1] for i in range(1,n+1,2)]
    configs=[
      ([seq(8)+[[9,12],[10,11]]],[seq(8)+[[9,12],[10,11]]],
       '左侧近墙的9/10均为上点，11/12均为下点。依据各自横向位置，候选为9–12、10–11；旧相邻数组配对不成立。',
       '表示修正正对照：不能把消除旧错误的收益归为点对优于单点。',[160,270]),
      ([seq(20)], [[[1,2],[3,4],[6,5],[7,8],[9,10],[11,12],[13,14],[15,16],[17,18],[19,20]],
                    [[1,2],[3,4],[6,8],[7,5],[9,10],[11,12],[13,14],[15,16],[17,18],[19,20]]],
       'W001右侧有15–16与19–20两组，W031右侧仅1–2；W031在中央x528–543区域更密集。6/7上点与5/8下点很近，第二方案仅用于展示这处对应歧义。',
       '同总点数、局部数量重新分配；检查一一匹配是否已经足够，绑定是否有额外帮助。',[535,265]),
      ([[[1,2],[4,3],[5,6],[8,7],[9,10],[11,12],[13,14]]],
       [[[1,2],[4,3],[6,5],[8,7],[9,10],[11,12],[13,14]]],
       'W030右侧1–2取近门框，W034的13–14取门内较远位置；两端都变化。其他凹角大多相近。',
       '同点数局部差异：检验局部检查能否避免平均值稀释；不预设优势来自绑定。',[860,260]),
      ([seq(8)],[seq(8)],'两份均表达四组墙角，中央淋浴区及右侧台盆附近端点仅有小偏移；保留用户“基本一致”的原意见。',
       '相近正对照；已有整图分区拆开不能自动归咎于这两份的点距离。',[438,270]),
      ([seq(12)],[[[1,2],[3,4],[5,6],[7,8],[11,9],[12,10],[13,14],[15,18],[16,19],[17,20]],
                   [[1,2],[3,4],[5,6],[7,8],[11,10],[12,9],[13,14],[15,18],[16,19],[17,20]]],
       '右侧壁炉附近和返回墙有紧凑转折。W011在x886–890和x942–961增点；11/12上点与9/10下点无法仅凭此图唯一配对。两个候选均不认证20点全部正确。',
       '不同点数对照：只因12/20点分开，不计为点对方法优势；观察邻近结构是否仍混淆。',[925,260]),
      ([seq(8)],[seq(10)],'W002的8个点在W006中原样保留；W006的5–6邻近3–4，额外一组是否应保留由用户判断。',
       '不同点数对照：覆盖接近和表达数量不同可以同时成立。',[466,250]),
    ]
    legacy_path=REPO/'analysis_results/full_corpus_research_received_20260918/full_study_20260918/code/legacy_reproduction.py'
    spec=importlib.util.spec_from_file_location('pair_pilot_legacy',legacy_path);old=importlib.util.module_from_spec(spec)
    before=sys.dont_write_bytecode
    try:sys.dont_write_bytecode=True;spec.loader.exec_module(old)
    finally:sys.dont_write_bytecode=before
    ns=old.legacy_functions(json.loads((lp.ROOT/'inputs/key39.json').read_text(encoding='utf-8')))
    frozen=json.loads((lp.ROOT/'local_recheck/cache.json').read_text(encoding='utf-8'))
    user=json.loads((REPO/'analysis_results/cluster_review_extra_20260919/用户_12图审核_原始.json').read_text(encoding='utf-8'))
    output=[]
    for index,(case,config) in enumerate(zip(selected,configs),1):
        ca,cb,note,purpose,focus=config;a,b=by[case['id_a']],by[case['id_b']]
        pa,pb=a['effective_points_1024x512'],b['effective_points_1024x512']
        geom=lp.features(stable_angles(pa,pb));na,nb=ns['normalize_geometry'](pa),ns['normalize_geometry'](pb)
        mask=old.dmask(old.dense(ns,na),old.dense(ns,nb)) if na['valid'] and nb['valid'] else None
        key=a['image_id']+'|'+a['raw_condition'];g=frozen[key];ia,ib=g['ids'].index(case['id_a']),g['ids'].index(case['id_b'])
        alternatives=[]
        for i,j in itertools.product(range(len(ca)),range(len(cb))):
            alternatives.append(dict(a_candidate=i,b_candidate=j,**compare_pairs(pa,pb,ca[i],cb[j])))
        saved=[dict(key=k,answer=v) for k,v in user['decisions'].items() if k.startswith(key+'|') and set(k.split('|')[-2:])=={case['id_a'],case['id_b']}]
        r=dict(key=key+'|'+case['id_a']+'|'+case['id_b'],priority=index,code=case['code'],image_id=a['image_id'],condition=a['raw_condition'],
               id_a=case['id_a'],id_b=case['id_b'],worker_a=a['worker_id'],worker_b=b['worker_id'],points_a=pa,points_b=pb,
               candidates_a=[_candidate('候选'+str(i+1),p,note) for i,p in enumerate(ca)],
               candidates_b=[_candidate('候选'+str(i+1),p,note) for i,p in enumerate(cb)],
               observation=note,purpose=purpose,focus=focus,user_original=saved,user_decision=None,
               baseline=dict(legacy_mask_distance=mask,stable_ospa1=geom['ospa1'],hausdorff=geom['hausdorff'],
                             untyped_bottleneck=geom['bottleneck'] if len(pa)==len(pb) else None,
                             frozen_membership={name:g['labels'][name][ia]==g['labels'][name][ib] for name in ['OSPA1_6','Hausdorff_9']}),
               comparisons=alternatives)
        output.append(r)
    return output


def integrate(evidence):
    # Append only missing image entries; existing 39/12 reviews and renderers stay in place.
    old=json.JSONDecoder().raw_decode((STUDIO/'data.js').read_text(encoding='utf-8').split('window.STUDIO_DATA=',1)[1])[0]['cases']
    extra=json.JSONDecoder().raw_decode((STUDIO/'extra-data.js').read_text(encoding='utf-8').split('push(...',1)[1])[0]
    all_cases=old+extra;h=(HISTORY/'history_data.js').read_text(encoding='utf-8')
    summaries=json.JSONDecoder().raw_decode(h.split('push(...',1)[1])[0];lookup={c['image_id']:c for c in summaries}
    added=[]
    for r in evidence:
        if any(c['image_id']==r['image_id'] for c in all_cases+added):continue
        idx=len(all_cases)+len(added);s=lookup[r['image_id']];raw=(HISTORY/s['history_script']).read_text(encoding='utf-8')
        payload=json.JSONDecoder().raw_decode(raw.split('],',1)[1])[0]
        photo=raw[raw.index('{const image='):];photo=re.sub(r'STUDIO_IMAGES\[\d+\]',f'STUDIO_IMAGES[{idx}]',photo)
        name=f'pair-pilot-{idx}.js'
        (STUDIO/'history'/name).write_text(f'Object.assign(window.STUDIO_DATA.cases[{idx}],'+json.dumps(payload,ensure_ascii=False)+');\n'+photo,encoding='utf-8')
        added.append(dict(image_id=r['image_id'],title=r['code'],category='点对初验 · 待用户确认',history_image=True,history_script='history/'+name,variants=[],pair_pilot=True))
    (STUDIO/'pair-pilot-data.js').write_text('window.STUDIO_DATA.cases.push(...'+json.dumps(added,ensure_ascii=False)+');\nwindow.POINT_PAIR_PILOT='+json.dumps(evidence,ensure_ascii=False)+';\n',encoding='utf-8')
    (STUDIO/'pair-pilot.js').write_text((Path(__file__).with_name('pair_pilot_panel.js')).read_text(encoding='utf-8'),encoding='utf-8')
    page=STUDIO/'index.html';html=page.read_text(encoding='utf-8')
    if 'pair-pilot-data.js' not in html:html=html.replace('<script defer src="studio.js">','<script defer src="pair-pilot-data.js"></script><script defer src="studio.js">')
    if 'src="pair-pilot.js"' not in html:html=html.replace('</body>','<script defer src="pair-pilot.js"></script>\n</body>')
    page.write_text(html,encoding='utf-8')


def main():
    evidence=build_evidence();OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    integrate(evidence)
    for r in evidence:
        print(r['code'],[(x['a_candidate'],x['b_candidate'],x['separate_bottleneck_deg'],x['bound_bottleneck_deg']) for x in r['comparisons']],flush=True)


if __name__=='__main__':main()
