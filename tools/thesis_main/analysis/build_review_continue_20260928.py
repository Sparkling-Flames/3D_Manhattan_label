"""仅将三图未决和两图历史修复问题接入既有Studio。"""
import copy
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OLD = ROOT / 'analysis_results/review_return_20260927'
FINAL = ROOT / 'analysis_results/review_final_20260928'
OUT = ROOT / 'analysis_results/review_continue_20260928'
HERE = Path(__file__).parent
BINDING = {'id': 'review_continue_20260928_v1'}
SPECS = {
    'S9hNv5qa7GM-04': ('范围是否仍无法确定？', '你已保留这份作答，但写了仅有一个结果，尚不能确定范围歧义。这里只确认图片层面：维持普通图并记录范围不确定，或明确场景分类。难度不用补，不能因人数少排除。', []),
    'uNb9QFRL6hY-32': ('该图保留在哪类分析？', 'GT右侧／阶梯下区域不妥已经记录。请说明：保留标注与共识研究、暂缓该GT人员评价；整图暂停分析；或仍待定。无需重复裁定GT错误。', []),
    'uNb9QFRL6hY-51': ('内侧空间可标，整图怎样处理？', '外扩玻璃区斜顶、GT有漂浮点，而内侧空间有较好标法。请确认：OOS并保留内侧探索；可标图片但参考存疑；整图暂缓；或继续待定。不需为了符合GT扩大范围。', []),
    'rPc6DW4iMge-09': ('历史补点来源待核（可选处理）', 'W029/W032/W037原始及有效层均6点，已核查台账未绑定已执行补点，这不证明从未修复。你原话为未补则排除。可明确按当前未修复版本排除，或保留待查；若记得记录位置请补充。不要求重判整图。', ['4a1158da9bd83ef9','6aed1eb1185c1318','6d192755ca096a2c']),
    'wc2JMjhGNzB-67': ('旧补点提议未落实（可选处理）', 'W034当前仍6点；历史有“按簇1第4对补充”的提议，但供体和执行坐标未绑定。可明确按当前版本排除，或继续待修复并点名供体worker／点对。旧簇1不能套用当前簇1。', ['032cd152706166629e82']),
}


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def build():
    OUT.mkdir(exist_ok=True)
    text = (OLD / 'data.js').read_text(encoding='utf-8')
    data = json.loads(text.split('window.STUDIO_DATA=',1)[1].split(';\nwindow.STUDIO_IMAGES=',1)[0])
    latest = read(FINAL / 'evidence/latest.json')
    cases = sorted([c for c in data['cases'] if c['code'] in SPECS],key=lambda c:list(SPECS).index(c['code']))
    assert len(cases)==5
    ids={c['image_id'] for c in cases}; aids={a for c in cases for a in c['review']['annotation_ids']}
    baseline=copy.deepcopy(latest);baseline['binding']=BINDING
    baseline['image_decisions']={k:v for k,v in latest['image_decisions'].items() if k in ids}
    baseline['annotation_decisions']={k:v for k,v in latest['annotation_decisions'].items() if k in aids}
    baseline['traits']={k:v for k,v in latest['traits'].items() if k.removeprefix('image:') in ids or k.removeprefix('annotation:') in aids}
    baseline['issue_decisions']={}
    data['cases']=cases;data['binding']=BINDING
    data['return_review']=dict(baseline=baseline,legacy_binding=BINDING,summary=dict(required_images=3,optional_history_images=2,source='最新定向补审(1)，本页只导出5图增量'))
    for idx,c in enumerate(cases):
        title,question,annids=SPECS[c['code']];kind='repair' if annids else 'undecided'
        issue=dict(id=c['image_id']+':continue',kind=kind,title=title,annotation_ids=annids,evidence=[dict(title=question,evidence=dict(latest_image=latest['image_decisions'].get(c['image_id']),annotations={a:latest['annotation_decisions'].get(a) for a in annids}))])
        c['return_review']['issues']=[issue];c['return_review']['background']=[]
        c['review'].update(flags=['followup',kind],followup_ids=annids,questions=[],summary=question,followup_reasons=[dict(kind=kind,title=title,annotation_ids=annids)])
        src=(OLD/c['history_script']).read_text(encoding='utf-8');pos=src.index('Object.assign(window.STUDIO_DATA.cases[')
        payload=json.loads(src[pos:].split('],',1)[1].rsplit(');',1)[0])
        payload['review']=c['review'];payload['return_review']=c['return_review']
        dest=OUT/c['history_script'];dest.parent.mkdir(parents=True,exist_ok=True)
        prefix=re.sub(r'window\.STUDIO_IMAGES\[\d+\]',f'window.STUDIO_IMAGES[{idx}]',src[:pos])
        dest.write_text(prefix+f'Object.assign(window.STUDIO_DATA.cases[{idx}],'+json.dumps(payload,ensure_ascii=False,separators=(',',':'))+');\n',encoding='utf-8')
    for name in ['studio.js','studio.css','three.min.js','OrbitControls.js','review.css']:
        shutil.copyfile(OLD/name,OUT/name)
    js=(HERE/'review_reconciliation_panel_20260925.js').read_text(encoding='utf-8').replace('全历史标注_定向补审_20260927.json','全历史标注_未决续审_20260928.json')
    (OUT/'review.js').write_text(js,encoding='utf-8')
    js=(HERE/'review_return_20260927.js').read_text(encoding='utf-8')
    js=js.replace('二审归并 · 定向补审','未决续审 · 3图判断＋2图历史核查').replace('四类待处理图片','本页5图（含2图可选核查）').replace('完整资料库（只查阅）','本页全部5图')
    js=js.replace('原二审已载入。保留误差与不同标法，只对具体问题补充确认。','最新复核已载入。先在大图下面橙框写本次处理说明；只有需要改分类或个人结论时再改其他表单。')
    start=js.index('function returnResolved(');end=js.index('function usageText(',start)
    js=js[:start]+"function returnResolved(c,d){return (c.return_review?.issues||[]).every(i=>d.issue_decisions[i.id]?.status==='resolved');}\n"+js[end:]
    js=js.replace("box.className='recon-question';", "box.className='recon-question';box.open=true;")
    js=js.replace("host.append(questions);", "host.insertBefore(questions,document.querySelector('.recon-final'));")
    (OUT/'return.js').write_text(js,encoding='utf-8')
    data['counts']['cases']=5
    (OUT/'data.js').write_text('window.STUDIO_DATA='+json.dumps(data,ensure_ascii=False,separators=(',',':'))+';\nwindow.STUDIO_IMAGES={};\n',encoding='utf-8')
    html=(OLD/'index.html').read_text(encoding='utf-8').replace('二审归并 · 定向补审','未决续审 · 20260928')
    html=html.replace('</head>','<style>#return-issues{background:#fff8eb;border:2px solid #dd963c;padding:16px;margin:12px 0}#return-issues textarea{min-height:100px}</style></head>')
    (OUT/'index.html').write_text(html,encoding='utf-8')
    (OUT/'README.md').write_text('# 未决续审\n\n3图实质未决；2图4份历史补点可选处理，非漏审。每图下橙框写说明并确认；仍不确定选待定。最新意见已载入，不必重复填写难度或GT。\n\n导出全历史标注_未决续审_20260928.json；仅覆盖5图，后续增量合并，不能替换全量JSON。独立binding和浏览器存储，不覆盖旧审核。\n',encoding='utf-8')
    (OUT/'manifest.json').write_text(json.dumps(dict(binding=BINDING,images=[c['code'] for c in cases],required=3,optional_history=2,annotation_ids=sorted(aids),raw_mutation=False),ensure_ascii=False,indent=2),encoding='utf-8')
    return [c['code'] for c in cases]


if __name__=='__main__':
    print(build())
