from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[3]
B=ROOT/'analysis_results/candidate_review_20260912_v2'
data=json.loads((B/'candidate_payload.json').read_text(encoding='utf-8'))
template=r'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>全景标注候选审查｜非派发表</title>
<style>
:root{font-family:Arial,"Microsoft YaHei",sans-serif;color:#172b3a;background:#f2f5f7}*{box-sizing:border-box}body{margin:0}header{background:#152e40;color:white;padding:24px max(22px,calc((100vw - 1500px)/2))}header h1{font-size:25px;margin:0 0 12px}header p{margin:6px 0;line-height:1.65;font-size:14px;color:#dce7ef}.bar{position:sticky;top:0;z-index:8;background:#fff;box-shadow:0 2px 12px #22334420;padding:12px 22px}.controls{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:6px 0}button,select,input,textarea{font:inherit;font-size:14px;padding:8px 10px;border:1px solid #b6c4ce;border-radius:5px;background:white;color:#173248}button{cursor:pointer}button:hover{background:#eaf3f8}label{font-size:13px}#stats{display:flex;gap:18px;flex-wrap:wrap;font-size:14px}#stats strong{font-size:21px}#warning{font-size:13px;color:#9d3c20;white-space:pre-wrap;margin-top:6px}main{max-width:1500px;margin:auto;padding:22px}.group{border:1px solid #d3dfe7;border-radius:8px;background:white;margin-bottom:26px;padding:20px}.group h2{font-size:21px;margin:0 0 10px}.group p{font-size:14px;line-height:1.75;margin:5px 0}.reviewRisk{background:#fff4df;padding:10px;border-radius:4px}.cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin-top:18px}.card{border:1px solid #c9d5df;border-radius:5px;overflow:hidden;background:#fafcfd}.head{padding:12px;display:flex;justify-content:space-between;font-size:16px;gap:10px}.pano{display:block;width:100%;aspect-ratio:2/1;background:#e5ecf1;object-fit:contain;cursor:zoom-in}.status{font-size:12px;padding:5px 12px;color:#546d7d;word-break:break-word}.meta{padding:10px 12px;font-size:13px;line-height:1.65}.meta p{font-size:13px;margin:4px 0}.pill{display:inline-block;padding:2px 6px;border-radius:4px;background:#e6edf3;margin:1px 3px 1px 0}.counts{display:grid;grid-template-columns:repeat(3,1fr);gap:5px;margin:10px 0}.counts div{background:#eef3f7;padding:6px}.cost{border-collapse:collapse;width:100%;margin:8px 0}.cost th,.cost td{border:1px solid #d7e1e8;padding:5px;text-align:center;font-size:12px}.cost th{background:#e9f0f5}.edit{display:flex;gap:7px;flex-wrap:wrap;padding:10px 12px;background:#edf4f8}.edit select{font-size:12px;padding:6px;max-width:100%}.notes{width:100%;margin-top:5px;resize:vertical;min-height:50px}.small{font-size:12px;color:#587080}.links a{color:#24587d;margin-right:12px}details{margin-top:7px}summary{cursor:pointer}.empty{display:none}.legend{line-height:1.7;background:#fff;padding:16px;border-left:4px solid #6e8ba0;margin-bottom:18px}footer{font-size:12px;line-height:1.7;color:#5d7180;margin-top:26px}dialog{max-width:96vw;max-height:94vh;border:0;padding:12px;background:#fff;border-radius:8px}dialog img{width:min(1600px,92vw);height:auto}dialog::backdrop{background:#0009}@media(max-width:800px){.cards{grid-template-columns:1fr}.bar{position:relative}main{padding:12px}.group{padding:12px}.counts{grid-template-columns:repeat(2,1fr)}}
</style>
<header><h1>全景标注：候选图片审查台</h1><p>22个候选组 · 112张原图位置（含历史来源） · 13栋楼。全部默认为待审，不等于已选样本，不含人员派发。</p><p>仓库整合版：空间关联表 v2；当前19人是后续人员假设，尚无最终选图或人数。理由依据已保存的人工评论、图像描述及逐份历史重算；本轮没有重新逐像素裁定房间/GT。</p></header>
<div class="bar"><div class="controls"><input id="q" placeholder="搜索组号、楼名、图号、描述" size="32"><select id="tier"><option value="">全部原包建议分类</option></select><select id="adoptionFilter"><option value="">全部整组采用判断</option><option>待定</option><option>建议采用</option><option>满足条件后采用</option><option>暂不采用</option></select><select id="purposeFilter"><option value="">全部研究用途</option></select><label><input type="checkbox" id="selectedOnly">只看组内拟采用图片</label><select id="basis"><option value="pooled">全历史＋新增：计算补齐缺口</option><option value="active19">当前19人：计算共同覆盖缺口</option></select></div>
<div class="controls"><button id="export">导出审查JSON</button><label>导入审查JSON <input id="import" type="file" accept=".json" style="width:190px"></label><button id="reset">清除本页审查选择</button><label>本地图片文件夹 <input id="folder" type="file" webkitdirectory directory multiple style="width:220px"></label></div><label>新增人图预算（可不填） <input id="budget" type="number" min="0" step="1" placeholder="未确定" style="width:110px"></label><div id="stats"></div><details id="warningPanel"><summary id="warningSummary">提示（0条）</summary><div id="warning" style="max-height:25vh;overflow:auto"></div></details></div>
<main><div class="legend"><b>研究主线：</b>标注随人数增加的稳定过程；同房间收敛预测；相似场景标注与跨房间预测（卧室、厨房、开放空间、门洞交界等）；可解释的人员子类与组合。<br><b>一个batch是什么：</b>一个物理房间／实际场景的研究标注组，不是第几轮。相似但不同房间仍分组；门洞交界是另记的场景条件，不替代卧室等类型。<br><b>填写顺序：</b>①整组是否值得采用，并勾选研究用途；②逐图选采用／备选／不采用及预期难度；③填采集安排、人数与理由。标注收齐后，再按方案反复划分图片、重排人员验证预测；审图不固定来源／目标，不表示第几批。备选不计预算。共同人员为主，允许按图调整，组内不必连续呈现。<br><b>离线预测验证：</b>所选图片先完成各自计划标注；每次模拟再划分依据图与检验图，允许轮换。预测程序只能使用该次允许的资料，检验标注用于评分；随机重排不会增加独立图片数量。<br><b>预期难度：</b>简单：基本无歧义，预计较早稳定；中等：可以标但可能有歧义或画不好，可能稳定多簇；困难：预计观察范围内仍持续变化。均为待检验预期，不要求实验符合，不自动绑定人数。<br><b>预算：</b>建议采用组与条件组分开汇总，未知人数另列；0–8、9–15、16–20、21人及以上均为计划总人数，含可复用历史，不是预计收敛人数。实际≤2人不判断持续稳定。<br><b>分类依据：</b>最新v2明确首次648图区域分类由用户全量亲审；该声明不自动确认全部同房关系。同房判断沿用已有工作依据，不全面重审；重点复核特别圈出的门洞交界及已有明确未决项。整组“待定”仅指是否采用，不代表同房关系不可用。<br><b>资料与图片：</b>本地原图可点击放大；M为全历史可用Manual（含W19／W26，其主分析归属未定），M19为当前19人覆盖，Semi单列。采用意见不会重写原分类，当前候选不代表已覆盖全部室内类型和门洞条件。完整选择原则见<a href="README_整合审查.md">填写说明</a>。</div><div id="groups"></div><footer>本页仅估算逐图缺口；在用户确定图片与观察终点后，仍须检查人员—图片匹配、任务量、已知预览和语言/批次覆盖。0条历史只表示当前快照没找到。自愿追加任务单列，不改变同一图片的独立人员上限。<br>各项原始来源和校验在配套CSV、工作簿和复算包中；不会向GitHub或标注平台写入任何内容。</footer></main><dialog id="zoom"><button onclick="document.getElementById('zoom').close()">关闭</button><div id="zoomTitle"></div><img id="zoomImg"></dialog>
<script>
const D=__DATA__;
const KEY='pano-review-repo-v2-'+D.commit;
const ROLES=['待定','预测依据图','预测检验图','标注规律观察图'];
const SELECTIONS=['待定','采用','备选','不采用'];
const COLLECTIONS=['待定','仅复用历史','需要新增标注'];
const ROLE_HELP='先完成所选图片的计划标注，再离线反复划分预测依据与检验图片，并重排／抽取人员标注。依据与检验是每次模拟的角色，不在审图时永久指定。';
const ADOPTIONS=['待定','建议采用','满足条件后采用','暂不采用'];
const PURPOSES=['人数增加与稳定过程','同房间收敛预测','相似场景标注与跨房间预测','人员子类与组合'];
const BANDS={'未定':null,'0–8人':[0,8],'9–15人':[9,15],'16–20人':[16,20],'21人及以上':[21,null]};

function bandFor(n){return n===0?'未定':n<=8?'0–8人':n<=15?'9–15人':n<=20?'16–20人':'21人及以上';}
const DIFFICULTIES=['未定','简单','中等','困难'];
const DIFFICULTY_HELP='审图预期：简单＝基本无歧义，预计少人数后稳定；中等＝可以标，但可能有歧义或画不好，可能稳定形成多个簇；困难＝预计本次观察人数内分歧仍持续变化。不是实验结论，不自动决定人数或收敛判定。稳定多簇也算稳定，困难图也可能稳定。';
let state={},groupState={},loadError='';
function G(id){return groupState[id]||{adoption:'待定',purposes:[],note:''};}
function validateImport(v){
 if(!['candidate_review_user_decisions_v1','candidate_review_user_decisions_v2','candidate_review_user_decisions_v3','candidate_review_user_decisions_v4','candidate_review_user_decisions_v5'].includes(v.schema)||v.commit!==D.commit||v.registry_blob!==D.registry_blob_sha)throw Error('文件类型或分类版本不匹配');
 if(!['pooled','active19'].includes(v.budget_basis))throw Error('人数口径无效');
 if(!v.schema.endsWith('_v1')&&JSON.stringify(v.participants)!==JSON.stringify(D.participants))throw Error('人员名单不匹配');
 if(!Array.isArray(v.decisions)||v.decisions.length!==D.images.length)throw Error('图片记录不完整');
 const next={},nextGroups={},allowed=new Map(D.images.map(r=>[r.image_id,r])),current=v.schema.endsWith('_v5'),v4=v.schema.endsWith('_v4');
 for(const s of v.decisions){
  const r=allowed.get(s.image_id);
  if(!r||s.group!==r.group||s.number!==r.number||Object.hasOwn(next,s.image_id))throw Error('图片身份或重复记录有误');
  if(!(current?DIFFICULTIES:['未定','审查确认简单','非简单']).includes(s.difficulty)||typeof s.note!=='string')throw Error('难度或备注无效');
  if(current||v4){
   if(!(current?ROLES:['待定','复用历史来源','新增来源','预测目标','特殊对照','可替代视点','本组不采用']).includes(s.role)||!Object.hasOwn(BANDS,s.target_band))throw Error('用途或人数区间无效');
   if(s.legacy_review!==null&&(typeof s.legacy_review!=='object'||Array.isArray(s.legacy_review)))throw Error('旧记录格式无效');
   if(current){
    if(!SELECTIONS.includes(s.selection)||!COLLECTIONS.includes(s.collection))throw Error('逐图采用或采集安排无效');
    next[s.image_id]={selection:s.selection,collection:s.collection,role:s.role,target_band:s.target_band,difficulty:s.difficulty,note:s.note,legacy_review:s.legacy_review};
   }else{
    const active=['复用历史来源','新增来源','预测目标','特殊对照'].includes(s.role);
    next[s.image_id]={selection:active?'采用':s.role==='可替代视点'?'备选':s.role==='本组不采用'?'不采用':'待定',collection:s.role==='复用历史来源'?'仅复用历史':active?'需要新增标注':'待定',role:['复用历史来源','新增来源'].includes(s.role)?'预测依据图':s.role==='预测目标'?'预测检验图':s.role==='特殊对照'?'标注规律观察图':'待定',target_band:s.target_band,difficulty:s.difficulty==='审查确认简单'?'简单':'未定',note:s.note,legacy_review:s};
   }
  }else{
   if(!['待审','候选纳入','仅复用来源','特殊对照','暂缓','排除本轮'].includes(s.decision))throw Error('旧选择无效');
   const numeric=!v.schema.endsWith('_v3');
   if(numeric&&(!Number.isInteger(s.target)||s.target<0||s.target>30))throw Error('旧人数无效');
   if(!numeric&&!['未定','P1 首批优先','P2 候补','P3 后续'].includes(s.priority))throw Error('旧优先级无效');
   const band=numeric?bandFor(s.target):s.target_band;
   if(!Object.hasOwn(BANDS,band))throw Error('人数区间无效');
   next[s.image_id]={selection:'待定',collection:'待定',role:'待定',difficulty:s.difficulty==='审查确认简单'?'简单':'未定',target_band:band,note:s.note,legacy_review:s};
  }
 }
 if(current||v4){
  if(!Array.isArray(v.groups)||v.groups.length!==D.groups.length)throw Error('整组记录不完整');
  for(const g of v.groups){
   if(!D.groups.some(x=>x.group===g.group)||Object.hasOwn(nextGroups,g.group))throw Error('组号或重复组有误');
   if(!ADOPTIONS.includes(g.adoption)||typeof g.note!=='string'||!Array.isArray(g.purposes)||g.purposes.some(x=>!PURPOSES.includes(x))||new Set(g.purposes).size!==g.purposes.length)throw Error('整组采用或用途无效');
   nextGroups[g.group]={adoption:g.adoption,purposes:g.purposes,note:g.note};
  }
 }
 if(v.budget!=null&&(!Number.isInteger(v.budget)||v.budget<0))throw Error('预算无效');
 return {images:next,groups:nextGroups};
}
function restore(v){const next=validateImport(v);state=next.images;groupState=next.groups;document.getElementById('basis').value=v.budget_basis;document.getElementById('budget').value=v.budget??'';loadError='';}
try{const saved=localStorage.getItem(KEY);if(saved)restore(JSON.parse(saved));}catch(e){loadError='旧保存内容未读取：'+e.message+'；原保存未改，请先备份。';}
const files=new Map(), urls=[];
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function S(id){return state[id]||{selection:'待定',collection:'待定',role:'待定',difficulty:'未定',target_band:'未定',note:'',legacy_review:null};}
function exportData(){return {schema:'candidate_review_user_decisions_v5',commit:D.commit,registry_blob:D.registry_blob_sha,participants:D.participants,budget_basis:document.getElementById('basis').value,budget:document.getElementById('budget').value===''?null:Number(document.getElementById('budget').value),created_at:new Date().toISOString(),status:'USER_REVIEW_NOT_ASSIGNMENT',groups:D.groups.map(g=>({group:g.group,...G(g.group)})),decisions:D.images.map(r=>({group:r.group,image_id:r.image_id,number:r.number,...S(r.image_id)}))};}
function persist(){try{localStorage.setItem(KEY,JSON.stringify(exportData()));}catch(e){loadError='本浏览器不能自动保存，请导出JSON。';update();}}
function opt(v,label,current){return `<option value="${esc(v)}" ${String(v)===String(current)?'selected':''}>${esc(label)}</option>`;}
document.getElementById('purposeFilter').innerHTML+=PURPOSES.map(x=>opt(x,x,'')).join('');
const tiers=[...new Set(D.groups.map(g=>g.tier))];document.getElementById('tier').innerHTML+=[...tiers].map(x=>opt(x,x,'')).join('');
function render(){const q=document.getElementById('q').value.trim().toLowerCase(),tier=document.getElementById('tier').value,only=document.getElementById('selectedOnly').checked;
let html='';for(const g of D.groups){if(tier&&tier!==g.tier)continue;if(document.getElementById('adoptionFilter').value&&G(g.group).adoption!==document.getElementById('adoptionFilter').value)continue;if(document.getElementById('purposeFilter').value&&!G(g.group).purposes.includes(document.getElementById('purposeFilter').value))continue;const rr=D.images.filter(r=>r.group===g.group).filter(r=>(!q||JSON.stringify([r.group,r.building,String(r.number).padStart(2,'0'),r.main_visual_space,r.information,r.group_original_note,r.adopted_coarse_type,r.doorway,G(g.group).note]).toLowerCase().includes(q))&&(!only||S(r.image_id).selection==='采用'));if(!rr.length)continue;
html+=`<section class="group" id="${g.group}"><h2>${g.group} / ${esc(g.building)} <span class="small">${esc(g.tier)} · ${g.n_images}图 · ${esc(g.review_state)}</span></h2><div class="edit group-edit"><label>整组采用判断 <select data-group-key="adoption" data-group="${g.group}">${ADOPTIONS.map(v=>opt(v,v,G(g.group).adoption)).join('')}</select></label><span>研究用途（可多选）：</span>${PURPOSES.map(v=>`<label><input type="checkbox" data-purpose="${v}" data-group="${g.group}" ${G(g.group).purposes.includes(v)?'checked':''}>${v}</label>`).join('')}<textarea class="notes" data-group-key="note" data-group="${g.group}" placeholder="采用理由／待解决条件；可写同房子组图号、相似场景类型或门洞条件，均不自动改分类">${esc(G(g.group).note)}</textarea><div class="group-summary" id="summary-${g.group}"></div></div><p><b>为什么审：</b>${esc(g.rationale)}</p><p class="reviewRisk"><b>需要你判断：</b>${esc(g.review_issue)}</p><p><b>原评论：</b>${esc(g.original_judgment.note||'无非空评论；不代表没有问题')}</p><p class="small">现有判断：物理同房 ${esc(g.original_judgment.physical_same)}；主空间 ${esc(g.original_judgment.main_visual_alignment)}；标注范围 ${esc(g.original_judgment.extent_alignment)}；视点难度相似性 ${esc(g.original_judgment.difficulty_similarity)}。当前19人中已有同房Semi接触：${g.current19_same_room_semi}人。</p><div class="cards">`;
for(const r of rr){const st=S(r.image_id), local=files.get(r.image_id+'.png'),src=local||('../../'+r.path);
html+=`<article class="card" id="card-${r.image_id}"><div class="head"><b>${g.group} · ${String(r.number).padStart(2,'0')}</b><span class="small">原包建议：${esc(r.review_role)}</span></div><img class="pano" loading="lazy" src="${esc(src)}" alt="仓库原图待加载：${esc(r.image_id)}" data-id="${r.image_id}" onload="this.nextElementSibling.textContent='${local?'已读取所选文件夹原图':'已读取仓库本地原图'} · 点击放大'" onerror="this.nextElementSibling.textContent='当前未加载原图：请使用原图链接或选择本地图片文件夹。'" onclick="zoom('${r.image_id}',this.src)"><div class="status">正在加载原图</div><div class="meta"><p><b>采用粗类：</b>${esc(r.adopted_coarse_type??'待拆解（null）')} <span class="small">${esc(r.coarse_source)}</span></p><p><b>原表视觉描述：</b>${esc(r.main_visual_space)}</p><p><b>范围描述：</b>${esc(r.extent)}</p><p><b>信息差异：</b>${esc(r.information)}</p><div class="counts"><div>M 全历史：<b>${r.manual_included}</b></div><div>M19 当前队列：<b>${r.manual_active19}</b></div><div>Semi：<b>${r.semi}</b></div><div>可新标当前人员：<b>${r.clean_new_active19}</b></div><div>历史合并人数上限：<b>${r.max_pooled_manual}</b></div><div>当前19人可用人数上限：<b>${r.max_active19_manual}</b></div></div><p class="small">人数区间为计划总人数，含可复用历史；新增量按区间估算，实际可达人数见上方。</p><p class="links"><a href="${esc('../../'+r.path)}" target="_blank" rel="noopener">本地原图</a></p><details><summary>人员、来源差异与OOS线索</summary><p>M人员：${r.manual_workers.map(w=>'W'+w).join('、')||'无记录'}</p><p>Semi人员：${r.semi_workers.map(w=>'W'+w).join('、')||'无记录'}</p><p>可新增人员：${r.clean_workers.map(w=>'W'+w).join('、')||'无'}</p><p>旧粗类：${esc(r.legacy_coarse_type)}；AI建议：${esc(r.ai_coarse_type)}</p><p>空间冲突：${esc(JSON.stringify(r.spatial_conflicts))}</p><p>OOS线索：${esc(JSON.stringify(r.oos_evidence))}</p><p class="small">${esc(r.image_id)}</p></details></div><div class="edit"><label>本图是否采用 <select data-key="selection" data-id="${r.image_id}">${SELECTIONS.map(v=>opt(v,v,st.selection)).join('')}</select></label><label>采集安排 <select data-key="collection" data-id="${r.image_id}">${COLLECTIONS.map(v=>opt(v,v,st.collection)).join('')}</select></label><label title="${esc(DIFFICULTY_HELP)}">预期难度 <select data-key="difficulty" data-id="${r.image_id}">${DIFFICULTIES.map(v=>opt(v,v,st.difficulty)).join('')}</select></label><label>计划总人数 <select data-key="target_band" data-id="${r.image_id}">${Object.keys(BANDS).map(v=>opt(v,v,st.target_band)).join('')}</select></label><details><summary>怎么选择？</summary><p>${ROLE_HELP}</p><p>仅复用历史：本次不新增；需要新增标注：补齐已有历史，任何角色均可选择。备选／不采用不计预算。采用但安排未定会单列提示。</p><p>${DIFFICULTY_HELP}</p></details>${st.legacy_review?'<details><summary>旧版填写（未转为本次采用结论）</summary>'+esc(JSON.stringify(st.legacy_review))+'</details>':''}<textarea class="notes" data-key="note" data-id="${r.image_id}" placeholder="你的理由、可比视点子组、视点差异及疑点（不裁定唯一标法）">${esc(st.note)}</textarea></div></article>`;}
html+='</div></section>';}
document.getElementById('groups').innerHTML=html||'<p>当前筛选无图片。</p>';update();}
function needRange(r,s,basis){
 const b=BANDS[s.target_band];if(!b)return null;
 const have=basis==='pooled'?r.manual_included:r.manual_active19;
 return [Math.max(0,b[0]-have),b[1]===null?null:Math.max(0,b[1]-have)];
}
function rangeText(lo,hi){return hi===null?lo+'以上':lo===hi?String(lo):lo+'–'+hi;}
function sumImages(entries,basis){
 let lo=0,hi=0,pending=0,reuse=0,count=0;const seen=new Map();
 for(const {r,s} of entries){
  if(seen.has(r.image_id)){const old=seen.get(r.image_id);if(old.role!==s.role||old.selection!==s.selection||old.collection!==s.collection||old.target_band!==s.target_band)throw Error('同图重复引用的用途或人数不一致');continue;}
  seen.set(r.image_id,s);
  if(s.selection!=='采用')continue;
  if(s.collection==='仅复用历史'){reuse++;continue;}
  if(s.collection==='待定'){pending++;continue;}
  count++;const need=needRange(r,s,basis);if(!need){pending++;continue;}
  lo+=need[0];hi=hi===null||need[1]===null?null:hi+need[1];
 }return {lo,hi,pending,reuse,count};
}
function update(){
 const basis=document.getElementById('basis').value,accepted=[],conditional=[],errors=loadError?[loadError]:[];let adopted=0,held=0,undecided=0;
 for(const g of D.groups){
  const gs=G(g.group),entries=D.images.filter(r=>r.group===g.group).map(r=>({r,s:S(r.image_id)})).filter(x=>x.s.selection==='采用');
  const totals=sumImages(entries,basis),box=document.getElementById('summary-'+g.group);
  if(box)box.textContent='组内拟新增图片 '+totals.count+'；复用图 '+totals.reuse+'；新增 '+rangeText(totals.lo,totals.hi)+' 人图；人数／安排未定 '+totals.pending+'。'+(gs.adoption==='建议采用'?'计入拟采用合计。':'未计入拟采用合计。');
  if(gs.adoption==='建议采用'){adopted++;accepted.push(...entries);}
  else if(gs.adoption==='满足条件后采用'){held++;conditional.push(...entries);if(!gs.note.trim())errors.push(g.group+'：请写采用前需满足的条件。');}
  else {if(gs.adoption==='待定')undecided++;continue;}
  if(!gs.purposes.length)errors.push(g.group+'：研究用途未定。');
  if(gs.purposes.includes('同房间收敛预测')){
   if(g.original_judgment.physical_same!=='支持'||g.original_judgment.main_visual_alignment!=='一致')errors.push(g.group+'：同房／主空间的原记录仍需核对，勾选采用不等于已解决。');
  }
  if(gs.purposes.includes('相似场景标注与跨房间预测'))errors.push(g.group+'：相似场景须另匹配其他物理房间，类型／门洞身份沿用原记录；本组不代表独立的一整类。');
  for(const {r,s} of entries){
   if(s.collection==='待定')errors.push(g.group+'-'+r.number+'：采集安排未定，预算不完整。');
   if(s.collection==='仅复用历史'&&!(basis==='pooled'?r.manual_included:r.manual_active19))errors.push(g.group+'-'+r.number+'：所选口径没有可复用Manual来源。');
   if(s.collection!=='需要新增标注'||!BANDS[s.target_band])continue;
   const b=BANDS[s.target_band],cap=basis==='pooled'?r.max_pooled_manual:r.max_active19_manual,have=basis==='pooled'?r.manual_included:r.manual_active19;
   if(b[0]>cap)errors.push(g.group+'-'+r.number+'：区间当前不可达，最多'+cap+'人。');
   else if(b[1]===null||b[1]>cap)errors.push(g.group+'-'+r.number+'：区间上限尚不可达，当前最多'+cap+'人。');
   if(b[1]!==null&&have>b[1])errors.push(g.group+'-'+r.number+'：已有历史超过所选档，历史保留，子样本分析须注明。');
  }
 }
 const total=sumImages(accepted,basis),hold=sumImages(conditional,basis),budget=document.getElementById('budget').value;
 if(total.pending)errors.push('拟采用组还有'+total.pending+'张人数或采集安排未定，未计入已知区间。');
 if(budget!==''&&(total.hi===null||total.hi>Number(budget)))errors.push('拟采用新增区间可能超过预算；这是理论范围，还需逐人检查可达性。');
 document.getElementById('stats').innerHTML=`<span>建议采用组 <strong>${adopted}</strong></span><span>条件组 <strong>${held}</strong></span><span>待定组 <strong>${undecided}</strong></span><span>拟采用新增人图 <strong>${rangeText(total.lo,total.hi)}</strong></span><span>条件组新增 <strong>${rangeText(hold.lo,hold.hi)}</strong>（未定${hold.pending}图）</span><span>拟采用人数／安排未定 <strong>${total.pending}</strong></span><span>参考预算 ${budget===''?'未设':esc(budget)}</span>`;
 document.getElementById('warning').textContent=errors.join('\n');
 document.getElementById('warningSummary').textContent='提示（'+errors.length+'条，点击展开／收起）';
}
function zoom(id,src){const r=D.images.find(x=>x.image_id===id);document.getElementById('zoomTitle').textContent=r.group+' / '+r.number+' / '+r.image_id;document.getElementById('zoomImg').src=src;document.getElementById('zoom').showModal();}
document.getElementById('groups').addEventListener('input',e=>{
 const {id,key,group,groupKey,purpose}=e.target.dataset;
 if(group){const g=G(group);groupState[group]=purpose?{...g,purposes:PURPOSES.filter(x=>x===purpose?e.target.checked:g.purposes.includes(x))}:{...g,[groupKey]:e.target.value};}
 else if(id&&key)state[id]={...S(id),[key]:e.target.value};else return;
 persist();update();
});
for(const x of ['q','tier','selectedOnly','adoptionFilter','purposeFilter'])document.getElementById(x).addEventListener(x==='q'?'input':'change',render);document.getElementById('basis').addEventListener('change',()=>{persist();update();});document.getElementById('budget').addEventListener('change',()=>{persist();update();});
document.getElementById('folder').addEventListener('change',e=>{for(const u of urls)URL.revokeObjectURL(u);urls.length=0;files.clear();for(const f of e.target.files){if(!/\.(png|jpe?g|webp)$/i.test(f.name))continue;const u=URL.createObjectURL(f);urls.push(u);files.set(f.name,u);}render();});
document.getElementById('export').onclick=()=>{if(!document.getElementById('budget').reportValidity())return;const out=exportData();const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(out,null,2)],{type:'application/json'}));a.download='candidate_review_decisions_20260912.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);};
document.getElementById('import').addEventListener('change',async e=>{try{if(!e.target.files.length)return;const v=JSON.parse(await e.target.files[0].text());restore(v);persist();render();}catch(err){alert('导入失败：'+err.message);}});
document.getElementById('reset').onclick=()=>{if(confirm('清除本页所有审查选择？不会修改仓库或原始记录。')){state={};groupState={};loadError='';persist();render();}};render();
</script></html>'''
text=template.replace('__DATA__',json.dumps(data,ensure_ascii=False).replace('</','<\\/'))
(B/'候选图片审查台.html').write_text(text,encoding='utf-8')
# Syntax test input, only JavaScript not embedded images.
script=text.split('<script>',1)[1].split('</script>',1)[0];(B/'results/gallery_syntax.js').write_text(script,encoding='utf-8')
print('HTML bytes',(B/'候选图片审查台.html').stat().st_size)
