"""独立图片语义补审；不改现有个人裁决，不自动回写CSV。"""
import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FINAL = ROOT/'analysis_results/review_final_20260928'
OUT = ROOT/'analysis_results/review_coverage_followup_20260928'
QUESTIONS = {
    '7y3sRwLe3Va-22': '你的“同图”未找到你本人明确前文；一正仅问走廊是否包括。只需确认是否存在可接受的空间范围差异，以及图片适用性；不重判已保留作答。',
    '7y3sRwLe3Va-26': '你指出GT的p9、p11两对不应标。这是GT明显实质错误，还是同一空间的细节/范围表达不同？原保留意见不变。',
    'pRbA3pwrgk9-16': '你写“感觉是OOS”，又说按最低一层可以标。请确认：整图OOS但局部可标，还是普通可标空间的范围选择；不要求删除已有标注。',
    'q9vSo1VnCiC-34': '你写空间范围不同且GT存在一点问题。请补充是实质错误、细节省略，还是空间范围不同；无需为GT问题修改点。',
}

def build():
    csv.field_size_limit(32*1024*1024)
    with (FINAL/'全量复核.csv').open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    with (FINAL/'逐图审核覆盖.csv').open(encoding='utf-8-sig',newline='') as f:
        coverage=list(csv.DictReader(f))
    grouped=defaultdict(list)
    for row in rows:grouped[row['image_id']].append(row)
    cases=[]
    for cv in coverage:
        iid=cv['image_id']
        source=ROOT/'analysis_results/consensus_visual_review_20260923/cases'/f'{iid}.js'
        raw=json.loads(source.read_text(encoding='utf-8').split('=',1)[1].rstrip(';\n'))
        code=raw['code']
        question=QUESTIONS.get(code)
        if cv['structured_image_review_covered']=='true':
            continue
        if not question and cv['coverage_group']!='not_in_current_review_files':continue
        members=[]
        for r in grouped[iid]:
            if r['cleaning_disposition'] in {'excluded_by_review','historical_not_accepted'}:continue
            members.append(dict(id=r['canonical_annotation_id'],worker=r['worker_id'],condition=r['condition'],
                points=json.loads(r['effective_points_1024x512']),labels=json.loads(r['effective_point_labels']),
                verdict=r['verdict'],comment=r['current_decision_comment'],traits=json.loads(r['annotation_traits']),
                trap=r['trap_status'],model_edit=r['model_edit_status']))
        if not members:continue
        cases.append(dict(image_id=iid,code=code,image_src=raw['image_src'],
            group='semantic' if question else 'coverage',
            references=[dict(name=r['name'],points=r['raw_points'],labels=['GT p'+str(i+1) for i in range(len(r['raw_points']))],source=r['source']) for r in raw['references'] if r['name'] in {'gt_original','gt_revised'}],
            question=question or '本轮文件没有本图审核。先看原图和多人点位：只补图片适用性；正常可直接确认，不需要逐份重审或为了缺记录而排除。',
            comments=json.loads(cv['original_comments']),annotations=members))
    cases.sort(key=lambda c:(c['group']!='semantic',c['code']))
    assert sum(c['group']=='semantic' for c in cases)==4
    assert sum(c['group']=='coverage' for c in cases)==20
    OUT.mkdir(exist_ok=True)
    data=dict(schema='coverage_followup_input_v1',binding='coverage_followup_20260928_v1',cases=cases)
    if not (OUT/'applied_reviews.js').exists():
        (OUT/'applied_reviews.js').write_text('window.COVERAGE_APPLIED=null;',encoding='utf-8')
    (OUT/'data.js').write_text('window.COVERAGE_DATA='+json.dumps(data,ensure_ascii=False).replace('<','\\u003c')+';',encoding='utf-8')
    (OUT/'index.html').write_text(HTML,encoding='utf-8')
    (OUT/'manifest.json').write_text(json.dumps(dict(binding=data['binding'],semantic_images=4,uncovered_images=20,
        image_ids=[c['image_id'] for c in cases],excluded_filtered=True,decisions_applied=False),ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'README.md').write_text('# 图片覆盖补审\n\n4张旧评论语义补充与20张本轮未覆盖核查分区显示。后者不是已判异常。已二审明确选项及已解决续审均不重新送审。只显示最新CSV保留作答的有效点；原始/人工修订GT可切换。\n\n导出schema为coverage_followup_decisions_v1，binding为coverage_followup_20260928_v1，decisions以image_id为键；status为draft/pending/resolved。OOS与门洞独立；tags记录参考/空间属性。view_context保存作答canonical ID、GT版本/来源与是否多人叠加。浏览器独立保存；新导出尚不自动应用到CSV。导入绑定与枚举校验，冲突拒绝覆盖。\n',encoding='utf-8')
    return dict(images=len(cases),semantic=4,uncovered=20)

HTML = r'''<!doctype html><html lang="zh"><meta charset="utf-8"><title>图片语义与覆盖补审</title>
<style>body{font:16px system-ui;margin:24px;background:#f5f7f5;color:#24332c}button,select,textarea{font:inherit;padding:9px;margin:4px}button{cursor:pointer}section{background:white;padding:18px;margin:14px 0;border:1px solid #ccd7cc;border-radius:8px}canvas{width:100%;display:block}textarea{width:95%;min-height:80px}label{display:inline-block;margin:6px}#problem{color:#8c4b13}pre{white-space:pre-wrap}#status{color:#17633a}fieldset{margin:10px 0}small{color:#5d665f}</style>
<h1>图片语义与覆盖补审</h1><p>4张旧评论语义待明确；另20张只是本轮未覆盖，并非已判可疑。不会重问已二审图片，也不会修改现有个人排除/保留。</p>
<select id="group"><option value="semantic">4张语义补充</option><option value="coverage">20张未覆盖核查（单独区）</option></select><select id="case"></select><button id="prev">上一张</button><button id="next">下一张</button><button id="export">导出本轮JSON</button><label>导入<input id="import" type="file" accept=".json"></label><span id="progress"></span>
<section><h2 id="title"></h2><p id="problem"></p><label>当前作答<select id="worker"></select></label><label><input id="all" type="checkbox" checked>叠加全部保留作答（淡蓝）；当前作答橙色</label><label>参考GT<select id="gt"><option value="">不显示</option></select></label><canvas id="canvas" width="1024" height="512"></canvas><p id="ann"></p><details><summary>原评论（来源和对象独立保留）</summary><pre id="comments"></pre></details></section>
<section><h2>本图补充判断</h2><small>OOS和门洞独立填写，可同时成立。结构复杂本身不算OOS。下列内容只保存本轮增量，不覆盖旧审核。</small>
<fieldset><legend>图片适用性</legend><select id="oos"><option value="">未填写</option><option value="in_scope">合规图片（含结构复杂/难图）</option><option value="oos">OOS（可标性请在说明中补充）</option><option value="stable_nonorthogonal">非正交但可稳定标注</option><option value="pending">尚不能确定</option></select>
<select id="doorway"><option value="">未填写门洞属性</option><option value="none">非门洞交界</option><option value="annotatable">门洞交界但可标</option><option value="difficult">门洞交界且难标</option><option value="pending">门洞属性待定</option></select></fieldset>
<fieldset><legend>参考/空间问题（按需多选；OOS/难标门洞可不填）</legend><label><input class="tag" value="reference_error" type="checkbox">GT明显实质错误</label><label><input class="tag" value="reference_omission" type="checkbox">GT省略细节</label><label><input class="tag" value="detail" type="checkbox">同一空间细节表达不同</label><label><input class="tag" value="scope" type="checkbox">空间范围不同</label><label><input class="tag" value="reference_uncertain" type="checkbox">参考情况仍不确定</label></fieldset>
<textarea id="comment" placeholder="解释本图问题；不会作为补删点授权"></textarea><p><button id="pending">保存待定</button><button id="confirm">确认本图补充判断</button><span id="status"></span></p></section>
<script src="data.js"></script><script src="applied_reviews.js"></script><script>
const D=window.COVERAGE_DATA, $=id=>document.getElementById(id), KEY=D.binding, allowed=new Set(D.cases.map(c=>c.image_id));let saved={},ci=0,img=new Image();
function validate(x){if(x.schema!=='coverage_followup_decisions_v1'||x.binding!==KEY||!x.decisions||typeof x.decisions!=='object'||Array.isArray(x.decisions))throw Error('文件类型或绑定错误');for(const [id,r] of Object.entries(x.decisions)){if(!allowed.has(id)||!['draft','pending','resolved'].includes(r.status)||!['','in_scope','oos','stable_nonorthogonal','pending'].includes(r.oos)||!['','none','annotatable','difficult','pending'].includes(r.doorway)||typeof r.comment!=='string'||!Array.isArray(r.tags)||r.tags.some(t=>!['reference_error','reference_omission','detail','scope','reference_uncertain'].includes(t)))throw Error('未知图片或无效字段');}return x.decisions;}
try{const old=localStorage.getItem(KEY);if(old)saved=validate(JSON.parse(old));}catch(e){alert('已有保存读取失败，未覆盖：'+e.message);}
if(window.COVERAGE_APPLIED){const {original,applied}=window.COVERAGE_APPLIED;validate(applied);for(const [id,r] of Object.entries(applied.decisions)){if(!saved[id]||JSON.stringify(saved[id])===JSON.stringify(original.decisions[id]))saved[id]=r;}const note=document.createElement('p');note.textContent='本轮已合并到全量台账；wc-61按最新明确意见只勾选空间范围不同。浏览器中另有改动的记录不会被覆盖。';document.querySelector('h1 + p').textContent='24张补审已提交，以下保留原分组供查看，不是新的复审任务。';$('group').options[0].textContent='4张语义补充（已回收）';$('group').options[1].textContent='20张覆盖核查（已回收）';document.querySelector('h1').after(note);}
const current=()=>D.cases.find(c=>c.image_id===$('case').value);const payload=()=>({schema:'coverage_followup_decisions_v1',binding:KEY,exported_at:new Date().toISOString(),decisions:saved});
function save(status='draft'){const c=current();if(!c)return;const r={status,oos:$('oos').value,doorway:$('doorway').value,tags:[...document.querySelectorAll('.tag:checked')].map(e=>e.value),comment:$('comment').value,view_context:{annotation_id:c.annotations[+$('worker').value]?.id||'',gt:$('gt').value,gt_source:c.references.find(r=>r.name===$('gt').value)?.source||'',all_workers:$('all').checked},updated_at:new Date().toISOString()};if(status==='resolved'&&!r.oos&&!r.doorway&&!r.tags.length&&!r.comment.trim()){alert('请至少填写一项判断或说明');return;}saved[c.image_id]=r;try{localStorage.setItem(KEY,JSON.stringify(payload()));$('status').textContent={draft:'草稿已保存',pending:'已记录待定',resolved:'本轮已确认'}[status];}catch(e){alert('本地保存失败，请立即导出：'+e.message);}progress();}
function progress(){$('progress').textContent='已确认 '+Object.values(saved).filter(r=>r.status==='resolved').length+'/'+D.cases.length;}
function draw(){const c=current(),ctx=$('canvas').getContext('2d');ctx.clearRect(0,0,1024,512);if(img.complete&&img.naturalWidth)ctx.drawImage(img,0,0,1024,512);const active=c.annotations[+$('worker').value];function points(a,color,labels){ctx.font='bold 13px system-ui';ctx.fillStyle=color;ctx.strokeStyle='white';ctx.lineWidth=2;for(let i=0;i<(a.points||[]).length;i++){let [x,y]=a.points[i];ctx.beginPath();ctx.arc(x,y,labels?4:2.5,0,7);ctx.fill();if(labels){ctx.stroke();ctx.strokeText(a.labels[i]||'p'+(i+1),x+5,y-5);ctx.fillText(a.labels[i]||'p'+(i+1),x+5,y-5);}}}if($('all').checked)c.annotations.filter(a=>a!==active).forEach(a=>points(a,'#2d98d175',false));if(active)points(active,'#fa790e',true);const gt=c.references.find(r=>r.name===$('gt').value);if(gt)points(gt,'#8b24bb',true);$('ann').textContent=active?`${active.worker} · ${active.condition} · ${active.points?.length||0}点；原结论 ${active.verdict}；${active.comment||''}；Trap ${active.trap}；模型修改 ${active.model_edit}`:'';}
function show(){const c=current();$('title').textContent=c.code;$('problem').textContent=window.COVERAGE_APPLIED?'原补审问题（已回收）：'+c.question:c.question;$('gt').replaceChildren(new Option('不显示',''),...c.references.map(r=>new Option(r.name==='gt_original'?'原始Matterport GT':r.source.includes('groudTruth.json')?'人工修订GT':'当前参考（原始Matterport，未人工修订）',r.name)));$('worker').replaceChildren(...c.annotations.map((a,i)=>new Option(a.worker+' · '+a.condition,i)));$('comments').textContent=c.comments.map(e=>`${e.reviewer} · ${e.worker_id} · ${e.verdict}\n${e.comment}`).join('\n\n')||'本轮没有原评论；这不是异常判定。';const r=saved[c.image_id]||{};if(r.view_context){const wi=c.annotations.findIndex(a=>a.id===r.view_context.annotation_id);if(wi>=0)$('worker').value=String(wi);$('gt').value=r.view_context.gt||'';$('all').checked=r.view_context.all_workers!==false;}$('oos').value=r.oos||'';$('doorway').value=r.doorway||'';$('comment').value=r.comment||'';document.querySelectorAll('.tag').forEach(e=>e.checked=(r.tags||[]).includes(e.value));$('status').textContent=r.status==='resolved'?'本轮已确认':r.status==='pending'?'已记录待定':r.status==='draft'?'已保存草稿':'本轮未填写';img=new Image();img.onload=draw;img.onerror=()=>{$('ann').textContent='原图加载失败，仍可查看点位';draw();};img.src=c.image_src;draw();progress();}
function populate(){$('case').replaceChildren(...D.cases.filter(c=>c.group===$('group').value).map(c=>new Option(c.code,c.image_id)));show();}
$('group').onchange=populate;$('case').onchange=show;$('worker').onchange=draw;$('gt').onchange=draw;$('all').onchange=draw;['oos','doorway','comment'].forEach(id=>$(id).onchange=()=>save());document.querySelectorAll('.tag').forEach(e=>e.onchange=()=>save());$('comment').oninput=()=>save();$('pending').onclick=()=>save('pending');$('confirm').onclick=()=>save('resolved');['prev','next'].forEach(id=>$(id).onclick=()=>{const e=$('case');e.selectedIndex=(e.selectedIndex+(id==='next'?1:-1)+e.options.length)%e.options.length;show();});
$('export').onclick=()=>{const a=document.createElement('a'),u=URL.createObjectURL(new Blob([JSON.stringify(payload(),null,2)],{type:'application/json'}));a.href=u;a.download='全历史标注_图片覆盖补审_20260928.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);};
$('import').onchange=async e=>{try{const d=validate(JSON.parse(await e.target.files[0].text()));const conflicts=Object.keys(d).filter(k=>saved[k]&&JSON.stringify(saved[k])!==JSON.stringify(d[k]));if(conflicts.length)throw Error('存在已有不同记录，未覆盖；请先导出当前记录：'+conflicts.length+'张');saved={...saved,...d};localStorage.setItem(KEY,JSON.stringify(payload()));show();}catch(e){alert(e.message);}};populate();
window.coverageReview={validate,payload};
</script></html>'''

if __name__=='__main__':print(build())
