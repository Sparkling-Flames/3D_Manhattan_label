'use strict';
(()=>{
const D=window.PERSONNEL_VALIDATION,$=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=(x,n=2)=>x===null||x===undefined?'—':Number(x).toFixed(n);
const flag=x=>x===null?'未知':x?'同类':'跨类';
const table=(headers,rows)=>'<table><thead><tr>'+headers.map(x=>'<th>'+esc(x)+'</th>').join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+r.map(x=>'<td>'+esc(x)+'</td>').join('')+'</tr>').join('')+'</tbody></table>';
const opts=(id,rows)=>{$(id).innerHTML=rows.map(([v,t])=>`<option value="${esc(v)}">${esc(t)}</option>`).join('');};
function layerChanged(){opts('image',Object.entries(D.images).filter(([,v])=>v.layer===$('layer').value).sort((a,b)=>a[1].image_code.localeCompare(b[1].image_code)).map(([k,v])=>[k,v.image_code+' · '+v.difficulty]));imageChanged();}
opts('k',[7,8,9,11,12,13,15,16,17,23,24,25].map(k=>[k,k]));$('k').value='16';
$('summary').innerHTML=table(['旧方法','可比图片／建筑','同类相近率','跨类相近率','跨−同及95%区间'],D.class_chains.filter(x=>x.metric==='all12_stable').map(x=>[x.method,x.images+'／'+x.buildings,fmt(x.near*100)+'%',fmt(x.far*100)+'%',`${fmt(x.delta*100)} [${fmt(x.low*100)}, ${fmt(x.high*100)}] 个百分点`]));
function imageChanged(){const rs=D.swaps.filter(r=>r.pool_id===$('image').value&&r.context===0&&r.k===7);opts('pair',rs.map(r=>[r.worker_a+'|'+r.worker_b,r.worker_a+' ↔ '+r.worker_b]));render();}
function render(){
 const pid=$('image').value,ctx=Number($('context').value),k=Number($('k').value),[a,b]=$('pair').value.split('|');
 const rs=D.swaps.filter(r=>r.pool_id===pid&&r.context===ctx&&r.worker_a===a&&r.worker_b===b).sort((x,y)=>x.k-y.k);
 const r=rs.find(x=>x.k===k),im=D.images[pid],ta=D.teams[r.request_a],tb=D.teams[r.request_b];
 $('metrics').textContent=`旧Q ${flag(r.Q_same)}；QT ${flag(r.QT_same)}；QTD ${flag(r.QTD_same)}。质量 A ${fmt(ta.Q)} → B ${fmt(tb.Q)}；底面变化 ${fmt(r.floor_jaccard_difference,4)}；节点数差 ${fmt(r.node_count_difference,0)}；共同观察对应变化 ${fmt(r.changed_coidentity_pairs,0)}。联合判据：${r.stable_main?'相近':'未通过'}。`;
 const common=ta.members.split('|').filter(w=>tb.members.split('|').includes(w));$('members').textContent=`固定背景（${common.length}人）：${common.join('、')}。替换 ${a} → ${b}。`;
 WorkbenchGeometry.mount($('fusion'),im,{points:ta.points,order_status:ta.status},im.reference,{points:tb.points,footprint:tb.floor,connected:!!tb.points});
 WorkbenchGeometry.mount($('answers'),im,{points:im.candidates[a],order_status:'冻结预处理环序'},im.reference,{points:im.candidates[b],connected:true});
 for(const [host,aa,bb] of [['fusion','团队A','团队B'],['answers','人员A','人员B']])for(const label of $(host).querySelectorAll('.legend label'))for(const node of label.childNodes)if(node.nodeType===3)node.textContent=node.textContent.replace('个人作答',aa).replace('已保存融合',bb);
 $('rows').innerHTML=table(['人数','A质量','B质量','|质量差|','底面变化','节点差','对应变化','两队完整','联合相近'],rs.map(x=>[x.k,fmt(D.teams[x.request_a].Q),fmt(D.teams[x.request_b].Q),fmt(x.abs_B8L2_change),fmt(x.floor_jaccard_difference,4),fmt(x.node_count_difference,0),fmt(x.changed_coidentity_pairs,0),x.both_complete?'是':'否',x.stable_main?'是':'否']));
 $('reference').textContent='固定参考：'+im.reference_id;
 const X=n=>45+(n-7)/18*910,Y=q=>180-q*1.5;
 let svg=[0,25,50,75,100].map(q=>`<line x1="45" y1="${Y(q)}" x2="970" y2="${Y(q)}" stroke="#e2e8f0"/><text x="7" y="${Y(q)+4}">${q}</text>`).join('');
 for(const [key,color] of [['request_a','#087f8c'],['request_b','#b45309']]){
  for(let i=0;i<rs.length;i++){const x=rs[i],q=D.teams[x[key]].Q;if(q===null)continue;
   const prev=rs[i-1],pq=prev?D.teams[prev[key]].Q:null;
   if(prev&&pq!==null)svg+=`<line x1="${X(prev.k)}" y1="${Y(pq)}" x2="${X(x.k)}" y2="${Y(q)}" stroke="${color}" ${x.k-prev.k>1?'stroke-dasharray="3 5"':''}/>`;
   svg+=`<circle cx="${X(x.k)}" cy="${Y(q)}" r="${x.k===k?6:3}" fill="${color}"><title>${x.k}人：${fmt(q)}</title></circle>`;
  }
 }
 svg+=rs.map(x=>`<text x="${X(x.k)-7}" y="202">${x.k}</text>`).join('');$('chart').innerHTML=svg;
}
$('layer').onchange=layerChanged;$('image').onchange=imageChanged;for(const id of ['context','k','pair'])$(id).onchange=render;layerChanged();
$('reviewCase').onclick=()=>{$('layer').value='ordinary_manual';layerChanged();const r=D.swaps.find(x=>D.images[x.pool_id].image_code==='wc2JMjhGNzB-46'&&x.context===1&&x.k===25&&x.worker_a==='W131'&&x.worker_b==='W132');$('image').value=r.pool_id;imageChanged();$('context').value='1';$('k').value='25';$('pair').value=r.worker_a+'|'+r.worker_b;render();$('metrics').scrollIntoView({block:'start'});};
})();
