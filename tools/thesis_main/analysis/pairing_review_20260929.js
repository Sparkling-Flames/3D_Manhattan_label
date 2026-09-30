'use strict';
const data=window.PAIRING_DATA, schema=data.schema, key=schema+':'+location.pathname,$=id=>document.getElementById(id);
let current=0, selected=null, pairs=[],records={},blocked=false,unsaved=false,image=new Image(),generation=0;
const row=()=>data.cases[current];
const completion=data.review_mode==='complete_pairing';let proposalId=null;
const proposal=()=>row().proposals?.find(p=>p.id===proposalId);
const deleted=()=>proposal()?.deleted||[];
const binding=r=>JSON.stringify({object_id:r.object_id,points:r.points,labels:r.labels,coordinate_source:r.coordinate_source,...(completion?{proposals:r.proposals,explicit_pairs:r.explicit_pairs}:{})});
function validatePairs(r,ps,complete=false,removed=[]){
 if(!Array.isArray(ps))throw Error('配对必须是数组');const used=new Set();
 for(const p of ps){if(!Array.isArray(p)||p.length!==2)throw Error('每对必须恰有两个点');
  for(const i of p){if(!Number.isInteger(i)||i<0||i>=r.points.length||used.has(i)||removed.includes(i))throw Error('点号无效、拟删除或被重复配对');used.add(i);}
  if(r.points[p[0]][1]>=r.points[p[1]][1])throw Error('请按上点、下点选择（上点y应更小）');
 }if(complete&&used.size!==r.points.length-removed.length)throw Error('仍有未配对点，不能确认；缺点或多点请暂缓并备注');
}
function validateRecord(id,r){if(completion){validateCompletionRecord(id,r);return;}const source=data.cases.find(c=>c.object_id===id);if(!source||!r||r.binding!==binding(source)||!['draft','paired','checked','deferred'].includes(r.status)||typeof r.note!=='string'||typeof r.updated_at!=='string'||r.order_confirmed!==false)throw Error('记录身份、绑定或字段不匹配：'+id);if(r.status==='checked'&&(!['corrections_only','legacy_full_pairing'].includes(r.review_mode)||r.untouched_points!=='accepted_without_correction'))throw Error('缺少局部修正审核语义');validatePairs(source,r.pairs,r.status==='paired');}
try{records=JSON.parse(localStorage.getItem(key)||'{}');if(!records||Array.isArray(records)||typeof records!=='object')throw Error('记录格式错误');for(const [id,r] of Object.entries(records))validateRecord(id,r);}catch(e){blocked=true;$('status').textContent='本地记录校验失败，编辑已停止；请导出备份。'+e.message;records={};}
function record(status){if(completion)return {binding:binding(row()),status,pairs:pairs.map(p=>[...p]),note:$('note').value,updated_at:new Date().toISOString(),order_confirmed:false,review_mode:'complete_pairing',proposal_id:proposalId,deleted_source_indices:deleted()};const old=records[row().object_id];return {binding:binding(row()),status,pairs:pairs.map(p=>[...p]).sort((a,b)=>a[0]-b[0]),note:$('note').value,updated_at:new Date().toISOString(),order_confirmed:false,review_mode:old?(old.review_mode||'legacy_full_pairing'):'corrections_only',untouched_points:status==='checked'?'accepted_without_correction':'not_confirmed'};}
function persist(status){if(blocked)return false;try{if(status==='checked'&&selected!==null)throw Error('还有一个已选点，请补选另一点或取消选点');const r=record(status);validateRecord(row().object_id,r);const next={...records,[row().object_id]:r};unsaved=true;localStorage.setItem(key,JSON.stringify(next));unsaved=false;records=next;render();$('status').textContent=({checked:'本图检查完成；未修正部分按无问题记录，未确认排序。当前图片保留。',draft:'局部配对修正已保存为草稿。',deferred:'已暂缓，保留问题；当前图片保留。'})[status];if(completion&&status==='checked')$('status').textContent='完整配对已确认；当前图片保留，尚未排序。';return true;}catch(e){$('status').textContent='未保存：'+e.message;return false;}}
function eligible(i){return $('mode').value==='all'||!['paired','checked','deferred'].includes(records[data.cases[i].object_id]?.status);}
function render(){
 const r=row(),used=new Set(pairs.flat()),state=records[r.object_id]?.status||'unreviewed';
 $('case').replaceChildren(...data.cases.flatMap((c,i)=>eligible(i)||i===current?[new Option(`${i+1} · ${c.image_code} · ${c.worker_id}`,i)]:[]));$('case').value=current;
 const counts={paired:0,checked:0,deferred:0};Object.values(records).forEach(r=>{if(r.status in counts)counts[r.status]++;});$('progress').textContent=`已检查 ${counts.paired+counts.checked} · 暂缓 ${counts.deferred} · 待处理 ${data.cases.length-counts.paired-counts.checked-counts.deferred}`;
 $('title').textContent=`${r.image_code} · ${r.worker_id} · ${r.condition} · ${r.points.length}点`;
 $('problem').textContent=`问题：${r.note||'现有配对不可用，需人工核对'}\n门洞：${r.doorway}；OOS：${r.oos}。显示平均x前有效点，不移动坐标。`;
 $('coverage').textContent=`本轮记录 ${pairs.length} 对；其余点无需逐一配对。状态：${{paired:'旧版完整配对已确认',checked:'本图检查完成，未改部分无问题',draft:'草稿',deferred:'暂缓',unreviewed:'未审'}[state]}${records[r.object_id]&&!records[r.object_id].review_mode?'（保留旧版配对记录，不将其自动解释为错误点对）':''}`;
 $('selection').textContent=selected===null?'请选择一对中的上点。':`已选上点 P${selected+1}，请选择下点。`;
 $('point-buttons').replaceChildren(...r.points.map((p,i)=>{const b=document.createElement('button');b.textContent=`P${i+1}${used.has(i)?' ✓':''}`;b.title=`${r.labels[i]} · x=${p[0].toFixed(2)}, y=${p[1].toFixed(2)}`;b.className=i===selected?'selected':'';b.disabled=blocked||(completion&&deleted().includes(i));b.onclick=()=>pick(i);return b;}));
 $('pair-list').replaceChildren(...pairs.map((p,i)=>{const li=document.createElement('li');li.append(`P${p[0]+1} 上 ↔ P${p[1]+1} 下 `);const b=document.createElement('button');b.textContent='解除';b.disabled=blocked;b.onclick=()=>{pairs.splice(i,1);selected=null;persist('draft');render();};li.append(b);return li;}));
 for(const id of ['confirm','save','defer','clear','note','import'])$(id).disabled=blocked;
 $('source').textContent=JSON.stringify({object_id:r.object_id,labels:r.labels,source:r.source,initial_pairs:r.initial_pairs,pairing_basis:r.pairing_basis,problem_sources:r.problem_sources},null,2);if(completion)renderCompletion();draw();
}
function pick(i){if(blocked||(completion&&deleted().includes(i)))return;if(pairs.flat().includes(i)){$('status').textContent='此点已有配对，请先点击对应配对的“解除”。';return;}if(selected===i){selected=null;render();return;}if(selected===null){selected=i;render();return;}try{validatePairs(row(),[...pairs,[selected,i]],false,completion?deleted():[]);pairs.push([selected,i]);selected=null;persist('draft');render();}catch(e){$('status').textContent=e.message;}}
function draw(){const canvas=$('panorama'),ctx=canvas.getContext('2d'),r=row();ctx.setTransform(2,0,0,2,0,0);ctx.clearRect(0,0,1024,512);if(image.complete&&image.naturalWidth)ctx.drawImage(image,0,0,1024,512);
 ctx.lineWidth=1.5;ctx.strokeStyle='#00f5ed';for(const [a,b] of pairs){if(completion)ctx.strokeStyle=pairOrigin([a,b]).color;const p=r.points[a],q=r.points[b],dx=((q[0]-p[0]+1536)%1024)-512;for(const offset of [-1024,0,1024]){ctx.beginPath();ctx.moveTo(p[0]+offset,p[1]);ctx.lineTo(p[0]+offset+dx,q[1]);ctx.stroke();}}
 const occupied=[];ctx.font='11px system-ui';
 r.points.forEach((p,i)=>{const removed=completion&&deleted().includes(i);if(removed){ctx.strokeStyle='#ddd';ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(p[0]-5,p[1]-5);ctx.lineTo(p[0]+5,p[1]+5);ctx.moveTo(p[0]+5,p[1]-5);ctx.lineTo(p[0]-5,p[1]+5);ctx.stroke();}ctx.fillStyle=removed?'#777':i===selected?'#ffe36a':'#ff4678';ctx.strokeStyle='white';ctx.beginPath();ctx.arc(p[0],p[1],3.5,0,Math.PI*2);ctx.fill();ctx.stroke();if(!$('labels').checked)return;
  const text='P'+(i+1)+(removed?'×':''),w=ctx.measureText(text).width+8,h=17;let box;
  for(let k=0;k<80;k++){const side=k%2? -1:1,level=Math.floor(k/2);const x=Math.max(0,Math.min(1024-w,p[0]+(side>0?7:-w-7))),y=Math.max(0,Math.min(512-h,p[1]-h/2+(level%2?1:-1)*Math.ceil(level/2)*19));const b={x,y,w,h};
   if(!occupied.some(a=>b.x<a.x+a.w&&b.x+b.w>a.x&&b.y<a.y+a.h&&b.y+b.h>a.y)&&!r.points.some((q,j)=>j!==i&&q[0]>x-4&&q[0]<x+w+4&&q[1]>y-4&&q[1]<y+h+4)){box=b;break;}}
  if(!box)box={x:Math.max(0,Math.min(1024-w,p[0]+7)),y:Math.max(0,Math.min(512-h,p[1]+7)),w,h};occupied.push(box);
  ctx.strokeStyle='#fff';ctx.lineWidth=.7;ctx.beginPath();ctx.moveTo(p[0],p[1]);ctx.lineTo(box.x+w/2,box.y+h/2);ctx.stroke();ctx.fillStyle='#16382ee6';ctx.fillRect(box.x,box.y,w,h);ctx.fillStyle='white';ctx.fillText(text,box.x+4,box.y+12);
 });
}
function load(i){if(unsaved){$('case').value=current;$('status').textContent='本地保存失败，尚有未保存配对；请先导出或重试保存，当前图保留。';return;}current=i;selected=null;const r=row();proposalId=records[r.object_id]?.proposal_id||(completion&&r.proposals.length===1?r.proposals[0].id:null);pairs=(records[r.object_id]?.pairs||(completion?(proposal()?.pairs||[]):[])).map(p=>[...p]);$('note').value=records[r.object_id]?.note||'';const token=++generation;image=new Image();image.onload=()=>{if(token===generation)draw();};image.onerror=()=>{$('status').textContent='图片载入失败，请保留data.js与入口的相对路径。';};image.src=data.images[r.image_id];if(!blocked)$('status').textContent='';render();}
$('panorama').onclick=e=>{const rect=e.currentTarget.getBoundingClientRect(),x=(e.clientX-rect.left)*1024/rect.width,y=(e.clientY-rect.top)*512/rect.height;let best=-1,d=12;row().points.forEach((p,i)=>{const n=Math.hypot(p[0]-x,p[1]-y);if(n<d){best=i;d=n;}});if(best>=0)pick(best);};
$('case').onchange=()=>load(Number($('case').value));$('mode').onchange=()=>{const i=data.cases.findIndex((_,i)=>eligible(i));load(i<0?current:i);};
for(const [id,delta] of [['next',1],['previous',-1]])$(id).onclick=()=>{for(let step=1;step<=data.cases.length;step++){const i=(current+delta*step+data.cases.length)%data.cases.length;if(eligible(i)){load(i);return;}}$('status').textContent='本筛选下没有其他待处理对象；可切换全部查看。';};
$('zoom').oninput=()=>{$('panorama').style.width=(Number($('zoom').value)*100)+'%';};$('labels').onchange=draw;$('cancel').onclick=()=>{selected=null;render();};
$('clear').onclick=()=>{pairs=(completion?(proposal()?.pairs||[]):[]).map(p=>[...p]);selected=null;persist('draft');render();};
$('save').onclick=()=>persist('draft');$('confirm').onclick=()=>persist('checked');$('defer').onclick=()=>{if(!$('note').value.trim()){$('status').textContent='请填写暂缓原因，便于下一阶段处理。';return;}persist('deferred');};$('note').oninput=()=>{unsaved=true;};$('note').onchange=()=>persist('draft');
function download(name,text){const url=URL.createObjectURL(new Blob([text],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
$('export').onclick=()=>{if(blocked){download('配对审核_损坏记录备份.txt',localStorage.getItem(key)||'');return;}const exported=unsaved?{...records,[row().object_id]:record('draft')}:records;download(completion?'补齐配对复核.json':'上下点配对审核.json',JSON.stringify({schema,scope:'pairing_only',order_confirmed:false,records:exported},null,2));};
$('import').onchange=async e=>{try{const doc=JSON.parse(await e.target.files[0].text());if(doc.schema!==schema||doc.scope!=='pairing_only'||doc.order_confirmed!==false||!doc.records||typeof doc.records!=='object'||Array.isArray(doc.records))throw Error('配对文件版本或范围不匹配');const next={...records};for(const [id,r] of Object.entries(doc.records)){validateRecord(id,r);if(next[id]&&JSON.stringify(next[id])!==JSON.stringify(r))throw Error('本地存在不同记录，拒绝覆盖：'+id);next[id]=r;}localStorage.setItem(key,JSON.stringify(next));records=next;load(current);$('status').textContent='导入完成。';}catch(e){$('status').textContent='导入未应用：'+e.message;}};

function validateCompletionRecord(id,r){
 const source=data.cases.find(c=>c.object_id===id);
 if(!source||!r||r.binding!==binding(source)||!['draft','checked','deferred'].includes(r.status)||typeof r.note!=='string'||typeof r.updated_at!=='string'||r.order_confirmed!==false||r.review_mode!=='complete_pairing')throw Error('完整配对记录绑定或字段不匹配');
 const option=source.proposals.find(p=>p.id===r.proposal_id);
 if((!option&&r.proposal_id!==null)||(!option&&r.status==='checked')||JSON.stringify(r.deleted_source_indices)!==JSON.stringify(option?.deleted||[]))throw Error('请先明确选择修点预览方案');
 validatePairs(source,r.pairs,r.status==='checked',option?.deleted||[]);
}
function pairOrigin(p){
 const same=q=>q[0]===p[0]&&q[1]===p[1];
 if(row().explicit_pairs.some(same))return {label:'上轮明确',color:'#21df97'};
 if(proposal()?.pairs.some(same))return {label:'按x补齐',color:'#ffb52e'};
 return {label:'本轮手动',color:'#58caff'};
}
function renderCompletion(){
 const r=row(),option=proposal(),state=records[r.object_id]?.status;
 $('proposal').replaceChildren(...(r.proposals.length>1?[new Option('请选择删P1或P3（未选择不可确认）','')]:[]),...r.proposals.map(p=>new Option(p.label,p.id)));
 $('proposal').value=proposalId||'';$('proposal').disabled=blocked;
 $('proposal-hint').textContent=option?.deleted.length?'预览删除点显示灰叉，确认仅写入本轮记录。':'P点号为固定身份，不代表连接顺序。';
 const reason={horizon_role_limit:'跨越旧地平线角色限制，检查上下端点身份',x_completion_required:'核对上轮未手动配对部分的x补齐',point_edit_pending:'按上轮备注核对删点预览'}[r.review_reason];
 $('problem').textContent=`复核原因：${reason}\n上轮备注：${r.note||'无'}\n门洞：${r.doorway}；OOS：${r.oos}。显示平均x前坐标。`;
 $('coverage').textContent=`完整预览 ${pairs.length} 对 / 保留 ${r.points.length-deleted().length} 点；${{checked:'本轮已确认配对',draft:'本轮草稿',deferred:'本轮暂缓'}[state]||'本轮未审'}；未确认排序。`;
 [...$('pair-list').children].forEach((li,i)=>{const origin=pairOrigin(pairs[i]);li.prepend(origin.label+' · ');li.style.borderLeft='6px solid '+origin.color;});
}
if(completion)$('proposal').onchange=()=>{
 const next=$('proposal').value||null;
 if(next===proposalId)return;
 if(records[row().object_id]&&!window.confirm('切换方案会恢复该方案的完整配对，并将本图改为草稿。继续？')){$('proposal').value=proposalId||'';return;}
 proposalId=next;selected=null;pairs=(proposal()?.pairs||[]).map(p=>[...p]);persist('draft');render();
};
window.addEventListener('beforeunload',e=>{if(unsaved){e.preventDefault();e.returnValue='';}});

load(Math.max(0,data.cases.findIndex((_,i)=>eligible(i))));
