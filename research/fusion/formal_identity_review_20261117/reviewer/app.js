'use strict';
function validateReceipt(x,data){
 const fail=m=>{throw Error(m);};
 if(!x||x.schema!=='fresh_group_review_v2'||x.package!==data.package||!x.answers||typeof x.answers!=='object'||Array.isArray(x.answers))fail('不是本轮新版回执，旧判断不会导入');
 for(const[id,a]of Object.entries(x.answers)){
  const s=data.scenes.find(s=>s.id===id);if(!s||a.code!==s.code||!['','acceptable','issues','uncertain'].includes(a.verdict)||typeof a.done!=='boolean'||(a.done&&!a.verdict)||typeof a.note!=='string'||!Array.isArray(a.issues))fail('图片或判断格式不匹配');
  for(const issue of a.issues){
   if(!['acceptable','distinct_modes','merge','split','unresolved'].includes(issue.type)||typeof issue.note!=='string'||!Array.isArray(issue.groups)||!issue.groups.length||!Array.isArray(issue.members)||!issue.members.length)fail('局部判断不完整');
   if(issue.type!=='acceptable'&&!issue.note.trim())fail('问题判断缺少具体说明');
   for(const [field,values] of Object.entries({identity:['same','different','uncertain'],geometry:['similar','distinct','uncertain']})){if(issue[field]!==undefined&&!values.includes(issue[field]))fail('两层判断取值无效');}
   if(issue.type==='distinct_modes'&&(issue.identity!=='same'||issue.geometry!=='distinct'||issue.groups.length<2))fail('分开合理需选择至少两组，并确认同结构、不同几何表达');
   const groups=issue.groups.map(id=>s.groups.find(g=>g.id===id));if(groups.some(g=>!g))fail('分组不匹配');
   const allowed=new Set(groups.flatMap(g=>g.members));if(issue.members.some(k=>!Number.isInteger(k)||!allowed.has(k)))fail('原答观察不匹配');
  }
 }return x;
}
if(typeof module!=='undefined')module.exports={validateReceipt};
if(typeof document!=='undefined'){
const D=REVIEW_DATA,$=id=>document.getElementById(id),NS='http://www.w3.org/2000/svg',key=D.package;
const labels={acceptable:'归类可接受',distinct_modes:'同结构不同表达，分开合理',merge:'同结构同类表达，应合并',split:'混合了应区分的结构或表达，应拆开',unresolved:'标注意图不可判定'};
let index=0,groups=new Set(),members=new Set(),answers={},conflict=false;
const current=()=>D.scenes[index],A=()=>answers[current().id]||={code:current().code,verdict:'',note:'',done:false,issues:[]};
const receipt=()=>({schema:'fresh_group_review_v2',package:D.package,exported_at:new Date().toISOString(),answers});
const say=t=>$('saved').textContent=t;
try{const saved=localStorage.getItem(key);if(saved)answers=validateReceipt(JSON.parse(saved),D).answers;}catch(e){say('未载入暂存：'+e.message+'；可导出JSON保存。');}
function save(){if(conflict)return;snapshotProgress();try{localStorage.setItem(key,JSON.stringify(receipt()));say('已暂存；结束前请导出新判断。');}catch(e){say('浏览器暂存失败，请立即导出JSON：'+e.message);}}
function snapshotProgress(){$('progress').textContent=`${index+1}/${D.scenes.length}图 · 已看完 ${Object.values(answers).filter(a=>a.done).length}图`;}
function option(value,text){const o=document.createElement('option');o.value=value;o.textContent=text;return o;}
function make(tag,attrs={},text){const e=document.createElementNS(NS,tag);for(const[k,v]of Object.entries(attrs))e.setAttribute(k,v);if(text!==undefined)e.textContent=text;return e;}
const color=k=>`hsl(${(k*137.508)%360} 86% 60%)`;
function vector(p){const u=2*Math.PI*(p[0]/1024-.5),v=Math.PI*(.5-p[1]/512);return[Math.cos(v)*Math.sin(u),Math.sin(v),Math.cos(v)*Math.cos(u)];}
function arc(a,b){const u=vector(a),v=vector(b),ang=Math.acos(Math.max(-1,Math.min(1,u.reduce((s,c,i)=>s+c*v[i],0))));let path='',last=null;for(let j=0;j<=32;j++){const t=j/32,s=Math.sin(ang),q=Math.abs(s)<1e-8?u.map((c,i)=>c*(1-t)+v[i]*t):u.map((c,i)=>(Math.sin((1-t)*ang)*c+Math.sin(t*ang)*v[i])/s),len=Math.hypot(...q);if(!len)continue;const x=(Math.atan2(q[0],q[2])/(2*Math.PI)+.5)*1024,y=(.5-Math.asin(Math.max(-1,Math.min(1,q[1]/len)))/Math.PI)*512;path+=(last===null||Math.abs(x-last)>512?'M':'L')+x+','+y;last=x;}return path;}
function draw(){
 const s=current(),svg=$('pano');svg.replaceChildren();svg.append(make('image',{href:s.image,width:1024,height:512}));
 s.groups.forEach((g,gi)=>{const selected=!groups.size||groups.has(g.id),c=color(gi),layer=make('g',{'data-group':g.id,opacity:selected?1:.12});
 for(const k of g.members){const o=s.observations[k],active=(!groups.size||members.has(k))&&(!$('worker').value||o.id===$('worker').value),pair=make('g',{opacity:active?1:.15}),[a,b]=o.points;
 pair.append(make('title',{},`${g.id} · ${o.worker} 第${o.pair_index+1}对`));pair.append(make('path',{d:`M${a}L${b}`,stroke:'white','stroke-width':3,opacity:.6}));pair.append(make('path',{d:`M${a}L${b}`,stroke:c,'stroke-width':1.5,'stroke-dasharray':'4 2'}));for(const p of o.points)pair.append(make('circle',{cx:p[0],cy:p[1],r:3,fill:c}));layer.append(pair);}
 const anchor=s.observations[g.members[0]].points[0];layer.append(make('text',{x:anchor[0]+5,y:anchor[1]-9,fill:c,stroke:'#172b38','stroke-width':2,'paint-order':'stroke','font-size':13},g.id));svg.append(layer);});
 if($('worker').value){const obs=s.observations.filter(o=>o.id===$('worker').value).sort((a,b)=>a.pair_index-b.pair_index);const layer=make('g',{'pointer-events':'none'});for(let k=0;k<obs.length;k++){for(const side of [0,1])layer.append(make('path',{d:arc(obs[k].points[side],obs[(k+1)%obs.length].points[side]),fill:'none',stroke:'white','stroke-width':2.2}));for(const p of obs[k].points)layer.append(make('text',{x:p[0]+5,y:p[1]+15,fill:'white',stroke:'#101e29','stroke-width':2,'paint-order':'stroke','font-size':13},obs[k].pair_index+1));}svg.append(layer);}
 svg.style.width=$('zoom').value+'%';
 $('groups').replaceChildren();s.groups.forEach((g,i)=>{const b=document.createElement('button');b.className='group '+(g.selected?'':'minority ')+(groups.has(g.id)?'active':'');b.style.setProperty('--c',color(i));b.textContent=`${g.id} · ${g.members.length}/${s.n} ${g.selected?'达票':'未达票'}`;b.onclick=()=>toggle(g.id);$('groups').append(b);});
}
function toggle(id){groups.has(id)?groups.delete(id):groups.add(id);members=new Set(current().groups.filter(g=>groups.has(g.id)).flatMap(g=>g.members));draw();memberList();}
function memberList(){const s=current();$('selected').textContent=groups.size?`已选 ${[...groups].join('、')}；其中 ${members.size} 个观察将记录在判断里`:'先选择上方涉及的组。';$('members').replaceChildren();for(const g of s.groups.filter(g=>groups.has(g.id)))for(const k of g.members){const o=s.observations[k],label=document.createElement('label'),input=document.createElement('input');input.type='checkbox';input.checked=members.has(k);input.onchange=()=>{input.checked?members.add(k):members.delete(k);draw();$('selected').textContent=`已选 ${[...groups].join('、')}；其中 ${members.size} 个观察将记录在判断里`;};label.append(input,document.createTextNode(`${g.id} · ${o.worker} 第${o.pair_index+1}对`));label.onmouseenter=()=>{label.title=`来源 ${o.id}`;};$('members').append(label);}}
function issueList(){$('issues').replaceChildren();A().issues.forEach((issue,i)=>{const div=document.createElement('div');div.className='issue';const b=document.createElement('button');b.textContent='撤回';b.onclick=()=>{A().issues.splice(i,1);save();issueList();};const title=document.createElement('strong');title.textContent=`${labels[issue.type]} · ${issue.groups.join('、')} · ${issue.members.length}个观察`;const p=document.createElement('p');const il={same:'同一结构',different:'不同结构',uncertain:'结构指向不确定'},gl={similar:'相近表达',distinct:'明显不同表达',uncertain:'表达差异不确定'};p.textContent=`${il[issue.identity]||'结构层未记录'} / ${gl[issue.geometry]||'表达层未记录'}。${issue.note}`;div.append(b,title,p);$('issues').append(div);});}
function render(){const s=current();groups.clear();members.clear();$('imageSelect').value=index;$('title').textContent=`${s.code} · ${s.n}份原答 · ${s.groups.length}组`;$('worker').replaceChildren(option('','不叠加'));const records=new Map(s.observations.map(o=>[o.id,o.worker]));for(const[id,worker]of records)$('worker').append(option(id,worker));$('prev').disabled=index===0;$('next').disabled=index===D.scenes.length-1;$('note').value=A().note;$('verdict').value=A().verdict;$('done').checked=A().done;$('issueNote').value='';$('identity').value='';$('geometry').value='';draw();memberList();issueList();snapshotProgress();}
$('imageSelect').replaceChildren(...D.scenes.map((s,i)=>option(i,`${i+1}. ${s.code}`)));$('imageSelect').onchange=()=>{index=+$('imageSelect').value;render();};$('prev').onclick=()=>{index--;render();};$('next').onclick=()=>{index++;render();};$('pending').onclick=()=>{for(let i=1;i<=D.scenes.length;i++){const j=(index+i)%D.scenes.length;if(!answers[D.scenes[j].id]?.done){index=j;render();return;}}say('所有图片均已标记看完。');};
$('pano').onclick=e=>{const g=e.target.closest('[data-group]');if(g)toggle(g.dataset.group);};$('worker').onchange=draw;$('zoom').oninput=()=>{$('zoomText').textContent=$('zoom').value+'%';$('pano').style.width=$('zoom').value+'%';};$('clear').onclick=()=>{groups.clear();members.clear();draw();memberList();};$('allMembers').onclick=()=>{members=new Set(current().groups.filter(g=>groups.has(g.id)).flatMap(g=>g.members));draw();memberList();};$('noneMembers').onclick=()=>{members.clear();draw();memberList();};
$('add').onclick=()=>{const type=$('issueType').value,note=$('issueNote').value.trim();if(!groups.size||!members.size)return say('先选择涉及的组和原答。');if(type!=='acceptable'&&!note)return say('请简单说明问题部位或不可判定的原因。');const identity=$('identity').value,geometry=$('geometry').value;if(!identity||!geometry)return say('请选择结构指向和几何表达；不确定也可以记录。');if(type==='distinct_modes'&&(identity!=='same'||geometry!=='distinct'||groups.size<2))return say('此项需选至少两组，并确认同一结构、明显不同表达。');A().issues.push({identity,geometry,criterion:'structure_geometry_v1',type,note,groups:[...groups],members:[...members].sort((a,b)=>a-b),at:new Date().toISOString()});save();issueList();$('issueNote').value='';say('已保存这条新判断。');};
$('verdict').onchange=()=>{A().verdict=$('verdict').value;if(!A().verdict){A().done=false;$('done').checked=false;}save();};$('note').oninput=()=>{A().note=$('note').value;save();};$('done').onchange=()=>{if($('done').checked&&!A().verdict){if(A().issues.length){A().verdict='issues';$('verdict').value='issues';}else{$('done').checked=false;return say('请先选一下本图整体判断。');}}A().done=$('done').checked;save();};
function download(x,suffix=''){const u=URL.createObjectURL(new Blob([JSON.stringify(x,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=u;a.download=`墙线新判断${suffix}_${Date.now()}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);}
$('export').onclick=()=>{try{const x=validateReceipt(receipt(),D);download(x);say('已导出；旧判断不在此次回执中。');}catch(e){say(e.message);}};
$('import').onchange=async()=>{const f=$('import').files[0];if(!f)return;try{const x=validateReceipt(JSON.parse(await f.text()),D);if(Object.keys(answers).some(k=>answers[k].done||answers[k].issues.length||answers[k].note||answers[k].verdict)){if(!confirm('先导出当前进度备份，再恢复所选文件？'))return;download(receipt(),'_导入前备份');}answers=x.answers;save();render();say('已恢复这次的新判断。');}catch(e){say('导入失败，当前进度未变：'+e.message);}finally{$('import').value='';}};
for(const type of ['click','change','input'])document.body.addEventListener(type,e=>{if(conflict&&e.target.id!=='export'){e.preventDefault();e.stopImmediatePropagation();say('另一页修改了进度，请先导出本页备份，再重新打开。');}},true);
window.addEventListener('storage',e=>{if(e.key===key&&e.newValue){conflict=true;say('另一页修改了进度，请先导出本页备份，再重新打开。');}});
render();
}
