"""Attach frozen research partitions to the existing Studio; reuse its 2D/3D renderer."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT/'analysis_results/cluster_review_extra_20260919'
STUDIO = ROOT/'analysis_results/image_portrait_20260914_v1/local_review_studio/key39'
HISTORY = ROOT/'analysis_results/panorama_studio_20260907_v3'


def main():
    source = OUT/'atlas_snapshot.json'
    if not source.exists():
        html=(OUT/'审核.html').read_text(encoding='utf8')
        data=json.loads(re.search(r'<script id="payload" type="application/json">(.*?)</script>',html,re.S)[1])
        for g in data['groups'].values(): g.pop('preview',None)
        data.pop('models',None)
        source.write_text(json.dumps(data,ensure_ascii=False),encoding='utf8')
    data=json.loads(source.read_text(encoding='utf8'))
    evidence=json.loads((OUT/'evidence.json').read_text(encoding='utf8'))
    for r in evidence:
        code=r['code']; same=r['memberships']['A3_cyclic'][0]==r['memberships']['A3_cyclic'][1]
        if code=='b8cTxDM8gDG-07' and same: priority,reason=1,'先核对配对伪差异'
        elif same and code in ['pRbA3pwrgk9-11','e9zR4mvMWw7-19','uNb9QFRL6hY-60','uNb9QFRL6hY-50','b8cTxDM8gDG-04']:priority,reason=2,'明显局部差异是否被合并'
        elif not same and code in ['X7HyMhZNoso-13','wc2JMjhGNzB-15','wc2JMjhGNzB-20','b8cTxDM8gDG-07','pRbA3pwrgk9-11','yqstnuAEVhm-31']:priority,reason=3,'相近表达是否被拆开'
        elif r['pair']['count_a']!=r['pair']['count_b'] or code in ['VFuaQ6m2Qom-07','yqstnuAEVhm-31']:priority,reason=4,'点数、细节与对应定义'
        else:priority,reason=5,'补充检查与正常对照'
        r.update(priority=priority,priority_reason=reason)
    evidence.sort(key=lambda r:(r['priority'],r['code'],r['pair']['id_a']))
    (OUT/'evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf8')
    old=json.loads((STUDIO/'data.js').read_text(encoding='utf8').split('window.STUDIO_DATA=',1)[1].split(';\n',1)[0].rstrip(';'))
    h=(HISTORY/'history_data.js').read_text(encoding='utf8')
    summaries=json.JSONDecoder().raw_decode(h.split('push(...',1)[1])[0]
    byimage={c['image_id']:c for c in summaries}
    added=[]; scripts=[]; images=[]
    for key,g in sorted(data['groups'].items(),key=lambda kv:min(i for i,r in enumerate(evidence) if r['key']==kv[0])):
        index=len(old['cases'])+len(added); summary=byimage[g['image_id']]
        raw=(HISTORY/summary['history_script']).read_text(encoding='utf8')
        payload=json.JSONDecoder().raw_decode(raw.split('],',1)[1])[0]
        variants={v['source']['canonical_annotation_id']:v for v in payload['variants']}
        chosen=[]
        for r in g['records']:
            assert r['id'] in variants, r['id']
            v=variants[r['id']]
            assert int(v['source']['worker_id'])==int(r['worker'][1:])
            v['source'].update(effective_points=r['effective'],raw_points=r['raw'],mode={'manual':'Manual','semi':'Semi','oos':'OOS'}[g['condition']])
            v['name']=f"{g['condition']} · {r['worker']} · 有效{len(r['effective'] or [])}点"
            chosen.append(v)
        ix={v['source']['canonical_annotation_id']:i for i,v in enumerate(chosen)}
        parts={}
        for mode in ['Manual','Semi','OOS']:
            names=[];candidates=[]
            if mode==chosen[0]['source']['mode']:
                for method,labels in g['methods'].items():
                    names.append(method)
                    candidates.append([[ix[cid] for cid,label in labels.items() if label==c] for c in sorted(set(labels.values()))])
            parts[mode]=dict(status='冻结研究结果；非语义真值',candidates=candidates,method_names=names)
        payload.update(variants=chosen,history=dict(partitions=parts),history_loaded=True)
        name=f'extra-{index}.js'
        photo=raw[raw.index('{const image='):]
        photo=re.sub(r'STUDIO_IMAGES\[\d+\]',f'STUDIO_IMAGES[{index}]',photo)
        (STUDIO/'history'/name).write_text(f'Object.assign(window.STUDIO_DATA.cases[{index}],'+json.dumps(payload,ensure_ascii=False)+');\n'+photo,encoding='utf8')
        added.append(dict(image_id=g['image_id'],title=g['code']+' · '+g['condition'],category='分簇复核 · 待用户裁决',history_image=True,history_script='history/'+name,variants=[],extra_review=True))
        images.append(dict(id=g['image_id'],number=int(g['code'].rsplit('-',1)[1]),manual=sum(v['source']['mode']=='Manual' for v in chosen),semi=sum(v['source']['mode']=='Semi' for v in chosen)))
    script='window.STUDIO_DATA.cases.push(...'+json.dumps(added,ensure_ascii=False)+');\n'
    script+='window.STUDIO_HISTORY.groups.unshift('+json.dumps(dict(code='优先复核12图',building='按待核查优先级',images=images),ensure_ascii=False)+');\n'
    script+='window.EXTRA_CLUSTER_EVIDENCE='+json.dumps(evidence,ensure_ascii=False)+';\n'
    (STUDIO/'extra-data.js').write_text(script,encoding='utf8')
    (STUDIO/'extra-review.js').write_text((OUT/'review_panel.js').read_text(encoding='utf8'),encoding='utf8')
    page=STUDIO/'index.html';html=page.read_text(encoding='utf8')
    if 'extra-data.js' not in html:html=html.replace('<script defer src="studio.js">','<script defer src="extra-data.js"></script><script defer src="studio.js">')
    if 'extra-review.js' not in html:html=html.replace('</body>','<script defer src="extra-review.js"></script>\n</body>')
    page.write_text(html,encoding='utf8')
    print('Integrated 12 images and 24 priority items into existing Studio; old39 data untouched.')


if __name__=='__main__': main()
