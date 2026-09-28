"""Independent follow-up page built on the existing release-review foundation."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from .pipeline import read, sha
from ..paired_split_research.release_review import build, digest, validate_review

GUIDANCE = [
    '先确认遮挡处的对应；用户提供的W002 bottom顺序保留为原文，不能自动推成top完整映射。确认对应后再判断定位差异是否值得分开。',
    '当前是最大端点误差，不是累计偏差。W012自动上下绑定有并列，故绑定方法不作强制选择；先核对角色和点号。',
    'W029 p11/p12与W027 p5/p6的遮挡处对应是本图重点；W031遗漏属于另一件事。确认相似不自动并入全部成员。',
    '用户认为同一遮挡位置但偏差较大；请分别判断对应和差异。检查整图其他端点，不能只看这个局部。',
    '用户指出W008 p8所在点对与W006 p11；W008上下绑定数值并列，暂不由算法强选。需要明确上下原点号。',
    '用户指出W032 p12点对与W033 p6。对应更正后仍需检查其他位置的最大差异，不把局部确认升级成整图同簇。',
    '指定两份相近已确认，本轮不重复询问；重点比较阻挡成员与代表分组后的簇内最远成员。请在文字中写整簇结论。',
    '指定两份相近已确认；重点检查完整链接的阻挡成员，而不是把p6偏差再次解释为必然应分开。',
    '指定两份相近已确认；核对阻挡合簇的其他成员，并检查代表组是否混入明显不同作答。',
    'W032 p4与W028 p3的top高度差，以及W018相似偏移为何仍在组内，需结合所选方法查看；OOS不排除。',
    '指定两份不同截止位置的差异已确认。旧簇3的W017为14点，主12点组因有效点数硬门分开；簇号可能随方法变化。',
    '后续已澄清为W017 p10与W018 p6；原文W008保留，不冒充另一个人。defer=true仍未裁决，单处偏差是否值得分开由用户判断。'
]


def build_followup(run_root, visual_root, experiment, out):
    experiment, out = Path(experiment), Path(out)
    result = experiment/'results'
    manifest = read(result/'EXPERIMENT_MANIFEST.json')
    for name, expected in manifest['files'].items():
        if sha(result/name) != expected:
            raise ValueError('Changed experiment result: '+name)
    for name, expected in manifest['evidence'].items():
        if sha(experiment/'evidence'/name) != expected:
            raise ValueError('Changed experiment evidence: '+name)
    payload = build(run_root, visual_root, out)
    if read(Path(run_root)/'RUN_MANIFEST.json')['run_id'] != manifest['source_run_id']:
        raise ValueError('Mixed source run')
    previous = read(experiment/'evidence/review_manifest_16.json')
    user = read(experiment/'evidence/user_review_16.json')
    decisions = validate_review(user, previous['binding'], [c['key'] for c in previous['cases']])
    groups = read(result/'groups.json')
    methods = [('split_cyclic_9','旧RC1 · 球面／独立环序／完整链接 9°')]
    for metric, label, unit in [('sphere','球面','9°'), ('image','图上局部','25.6像素')]:
        for kind, group_label in [('complete','完整链接'),('representative','真实代表半径')]:
            methods.append((f'automatic:{metric}:{kind}:9',f'{label}／绑定固定顺序／{group_label} · {unit}'))
    payload['cases'] = payload['cases'][:12]
    for index, case in enumerate(payload['cases']):
        r = case['followup'];g = groups[r['key']]
        r['research_notes'] = dict(original_comment_order=index+1, guidance=GUIDANCE[index],
                                   original_decision=decisions[r['key']], final_decision=None,
                                   coverage='沿用已有原图/指定作答AI证据；本轮新分簇整簇尚未视觉验收')
        r['user_original'].append(dict(file='user_review_16.json', records=[decisions[r['key']]]))
        r['reasons'] = GUIDANCE[index]
        r['pairs_by_method'] = {'split_cyclic_9': r['pairs_detail']}
        workers = {v['source']['canonical_annotation_id']:v['source']['current_row']['worker_id'] for v in case['variants']}
        for method, _ in methods[1:]:
            labels=g['labels'][method];by=dict(zip(g['ids'],labels))
            r['labels'][method]=[by.get(cid,'unavailable') for cid in r['ids']]
            metric=method.split(':')[1];d=np.asarray(g['matrices']['automatic'][metric]);unit='°' if metric=='sphere' else '像素'
            ids=[r['id_a'],r['id_b']]
            detail=[dict(ids=ids,workers=[workers[c] for c in ids],kind='指定作答对',distance=None,unit=unit,
                         reason='至少一份无唯一自动绑定，未强行配对；可看旧分开角色对照')]
            if all(cid in by for cid in ids):
                a,b=[g['ids'].index(cid) for cid in ids]
                if d[a,b]<1e6:
                    detail[0]['distance']=float(d[a,b])
                    ix=np.flatnonzero(np.array(labels)==labels[a]);jx=np.flatnonzero(np.array(labels)==labels[b])
                    v,u=max((float(d[i,j]),(int(i),int(j))) for i in ix for j in jx)
                    witnesses=[g['ids'][k] for k in u]
                    detail.append(dict(ids=witnesses,workers=[workers[c] for c in witnesses],distance=v if v<1e6 else None,
                                       unit=unit,reason='不同有效点数硬门，不是观测距离',
                                       kind='该簇最大差异成员' if labels[a]==labels[b] else '两簇最大跨簇差异成员'))
                else: detail[0]['reason']='不同有效点数硬门，不是观测距离'
            r['pairs_by_method'][method]=detail
    image_order=sorted(range(len(payload['cases'])),key=lambda i:(not decisions[payload['cases'][i]['followup']['key']]['defer'],i))
    payload['cases']=[payload['cases'][i] for i in image_order]
    payload.update(review_title='12图局部点位复核 · 8项暂缓优先',export_filename='12图局部点位_我的审核.json',
        review_instructions='先比较指定两份，再看最大差异成员和整簇。当前四组是探查候选，容差未冻结。旧相近/不同判断已保留为只读证据；本轮文字请明确对应点号、整簇意见及所选方法。3D是辅助，先检查连接顺序。最终仍需核验全部历史图片。',
        method_options=[dict(value=value,label=label) for value,label in methods],
        counts=dict(cases=len(payload['cases']),variants=sum(len(c['variants']) for c in payload['cases'])))
    binding=payload['binding']
    binding['experiment']=sha(result/'EXPERIMENT_MANIFEST.json')
    binding['review_content']=digest([c['followup'] for c in payload['cases']])
    binding['review_builder']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    binding['id']=digest({k:v for k,v in binding.items() if k!='id'})
    old_images=(out/'data.js').read_text(encoding='utf8').split('window.STUDIO_IMAGES={};\n',1)[1].splitlines()[:12]
    images=[old_images[old].replace(f'STUDIO_IMAGES[{old}]',f'STUDIO_IMAGES[{new}]') for new,old in enumerate(image_order)]
    (out/'data.js').write_text('window.STUDIO_DATA='+json.dumps(payload,ensure_ascii=False,allow_nan=False)+';\nwindow.STUDIO_IMAGES={};\n'+'\n'.join(images),encoding='utf8')
    (out/'index.html').write_text((out/'index.html').read_text(encoding='utf8').replace('16图 · RC1分簇视觉验收','12图 · 局部点位方法复核'),encoding='utf8')
    (out/'REVIEW_MANIFEST.json').write_text(json.dumps(dict(binding=binding,cases=[c['followup'] for c in payload['cases']]),ensure_ascii=False,indent=2),encoding='utf8')
    return payload['counts']


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('run-root','visual-root','experiment','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();print(build_followup(a.run_root,a.visual_root,a.experiment,a.out))
