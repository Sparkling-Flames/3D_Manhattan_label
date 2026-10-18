(()=>{'use strict';
const D=window.CLUSTER_REVIEW,$=id=>document.getElementById(id), methods={complete:'完整链接',affinity:'全局亲近度'};
let image,state,selected=[],reviews={},groupReviews={},activeGroup=['complete',0];
const name=i=>`A${String(i+1).padStart(2,'0')}`+($('identity').checked?` · ${image.records[i].worker_id}`:'');
const groups=m=>state.groups[m],groupOf=(m,i)=>groups(m).findIndex(g=>g.includes(i));
const key=p=>[image.image_code,state.cut,p.a,p.b].join('|');
const pairDistance=(a,b)=>image.pairs.find(p=>p.a===Math.min(a,b)&&p.b===Math.max(a,b)).d;
function diameter(g){return Math.max(0,...g.flatMap((a,k)=>g.slice(k+1).map(b=>pairDistance(a,b))));}
function mount(id,a,b){WorkbenchGeometry.mount($(id),image,image.records[a],b===undefined?null:image.records[b]);if(b!==undefined){const label=$(id).querySelector('[data-layer="reference"]').parentElement;label.lastChild.textContent='作答 B（非GT）';}}
function showGroup(m,k){activeGroup=[m,k];const g=groups(m)[k];$('members-title').textContent=`${methods[m]} C${k+1} · 全部${g.length}份 · 直径 ${diameter(g).toFixed(3)}°`;
 $('members').replaceChildren();for(const i of g){const r=image.records[i],card=document.createElement('article'),h=document.createElement('h4'),note=document.createElement('p'),view=document.createElement('div');h.textContent=name(i);note.className='note';note.textContent=`${r.id} · ${r.points.length/2}对点 · ${r.ring_confirmed?'人工确认环序':'未人工确认环序（默认声明）'}`;card.append(h,note,view);$('members').append(card);WorkbenchGeometry.mount(view,image,r,null);}
 for(const method of Object.keys(methods))$(method).querySelectorAll('button').forEach((b,i)=>b.classList.toggle('active',method===m&&i===k));}
function stacks(){
 for(const m of Object.keys(methods)){const host=$(m+'-stacks');host.replaceChildren();
 const overview=document.createElement('div');overview.className='stack-card';host.append(overview);ClusterOverlay.mount(overview,image,groups(m).map((g,k)=>({label:`C${k+1} · ${g.length}份`,members:g})));
 groups(m).forEach((g,k)=>{const card=document.createElement('article'),title=document.createElement('h4'),view=document.createElement('div');card.className='stack-card';title.textContent=`C${k+1} · ${g.length}份 · ${image.records[g[0]].points.length/2}对点 · 直径${diameter(g).toFixed(2)}°`;card.append(title,view);host.append(card);ClusterOverlay.mount(view,image,g.map(i=>({label:name(i)+(image.records[i].ring_confirmed?'':' · 环序未审'),members:[i]})));});
 }
 $('group-comment').value=groupReviews[image.image_code+'|'+state.cut]?.comment||'';
}
function render(){image=D.images[+$('image').value];state=image.states.find(s=>s.cut===+$('cut').value);
 $('coverage').textContent=`${image.image_code} · ${image.records.length}份真实作答 · ${image.records.filter(r=>r.ring_confirmed).length}份人工确认环序 · 来源 ${D.revision}`;
 const disagreements=image.pairs.filter(p=>(groupOf('complete',p.a)===groupOf('complete',p.b))!==(groupOf('affinity',p.a)===groupOf('affinity',p.b))).length;
 $('stats').textContent=`两法同簇关系不同：${disagreements}对。全局求解：${state.solver.every(s=>s.optimal)?'全部点数层已证明目标最优（未证明唯一）':'含未证明最优的可行解'}。`;
 for(const m of Object.keys(methods)){ $(m).replaceChildren();groups(m).forEach((g,k)=>{const b=document.createElement('button');b.textContent=`C${k+1} · ${g.length}份 · ${image.records[g[0]].points.length/2}对点`;b.onclick=()=>showGroup(m,k);$(m).append(b);});$(m+'-info').textContent=`${groups(m).length}簇 · ${groups(m).filter(g=>g.length===1).length}单人簇 · 亲近度目标 ${state.objective[m].toFixed(4)}（不是质量分）`;}
 showGroup('complete',0);stacks();cases();}
function cases(){const f=$('filter').value;selected=image.pairs.filter(p=>{const c=groupOf('complete',p.a)===groupOf('complete',p.b),a=groupOf('affinity',p.a)===groupOf('affinity',p.b);if(f==='disagree')return c!==a;if(f==='cut')return p.d!==null&&p.d<=state.cut&&(!c||!a);if(f==='count')return p.d===null;if(f==='boundary')return ['complete','affinity'].some(m=>groupOf(m,p.a)===groupOf(m,p.b)&&Math.abs(p.d-diameter(groups(m)[groupOf(m,p.a)]))<1e-9);return true;});
 selected.sort((a,b)=>(a.d??Infinity)-(b.d??Infinity)||a.a-b.a||a.b-b.b);$('case').replaceChildren();selected.forEach((p,i)=>{const o=document.createElement('option');o.value=i;o.textContent=`${name(p.a)} ↔ ${name(p.b)} · ${p.d===null?'点对数不同':p.d.toFixed(3)+'°'}`;$('case').append(o);});$('case-count').textContent=`当前类型共${selected.length}对，全部可查。`;$('case').disabled=!selected.length;showPair();}
function showPair(){const p=selected[+$('case').value];for(const id of ['view-a','view-b','view-overlay'])$(id).replaceChildren();$('overlay').open=false;$('save').disabled=!p;if(!p){$('pair-info').textContent='当前条件没有此类案例，可切换类型或阈值。';$('label-a').textContent=$('label-b').textContent='';return;}
 $('label-a').textContent=name(p.a);$('label-b').textContent=name(p.b);$('pair-info').textContent=Object.keys(methods).map(m=>`${methods[m]}：C${groupOf(m,p.a)+1} / C${groupOf(m,p.b)+1}`).join('；')+(p.d===null?'；不同点对数，距离未定义':`；距离 ${p.d.toFixed(4)}°；循环偏移 ${p.shift}；次佳差 ${p.margin.toFixed(4)}°（非置信度）`);
 mount('view-a',p.a);mount('view-b',p.b);const r=reviews[key(p)];$('verdict').value=r?.verdict||'';$('comment').value=r?.comment||'';}
 $('overlay').ontoggle=()=>{const p=selected[+$('case').value];if($('overlay').open&&p)mount('view-overlay',p.a,p.b);};
 $('save').onclick=()=>{const p=selected[+$('case').value];reviews[key(p)]={image:image.image_code,cut:state.cut,distance:p.d,object_a:image.records[p.a].object_id,object_b:image.records[p.b].object_id,record_a:image.records[p.a].id,record_b:image.records[p.b].id,groups:Object.fromEntries(Object.keys(methods).map(m=>[m,[groupOf(m,p.a)+1,groupOf(m,p.b)+1]])),verdict:$('verdict').value,comment:$('comment').value};$('saved').textContent=`本次会话已保存${Object.keys(reviews).length}条，请导出后再关闭页面。`;};
 $('export').onclick=()=>{const blob=new Blob([JSON.stringify({schema:D.schema,revision:D.revision,reviews:Object.values(reviews),group_reviews:Object.values(groupReviews)},null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='cluster-human-review.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
 $('save-group').onclick=()=>{groupReviews[image.image_code+'|'+state.cut]={image:image.image_code,cut:state.cut,groups:state.groups,object_ids:image.records.map(r=>r.object_id),comment:$('group-comment').value};$('group-saved').textContent=`已保存${Object.keys(groupReviews).length}份整图意见，请导出后关闭。`;};$('export-group').onclick=()=>$('export').onclick();
 D.images.forEach((p,i)=>{const o=document.createElement('option');o.value=i;o.textContent=p.image_code;$('image').append(o);});$('image').onchange=$('cut').onchange=render;$('identity').onchange=()=>{showGroup(...activeGroup);stacks();cases();};$('filter').onchange=cases;$('case').onchange=showPair;$('image').value=String(D.images.findIndex(p=>p.image_code==='X7HyMhZNoso-13'));render();
})();
