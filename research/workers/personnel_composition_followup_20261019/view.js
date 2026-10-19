'use strict';
(()=>{
const D=window.FOLLOWUP,$=x=>document.getElementById(x),fmt=x=>x==null?'不可用':Number(x).toFixed(2);
D.forEach((c,i)=>$('case').add(new Option(`${i+1}. ${c.title} · ${c.image.image_code}`,i)));
function rename(host,a,b){for(const label of host.querySelectorAll('.legend label'))for(const node of label.childNodes)if(node.nodeType===3)node.textContent=node.textContent.replace('个人作答',a).replace('已保存融合',b);}
function render(){const c=D[Number($('case').value)],e=c.event,pair=$('pair').value,a=c.teams.A,b=c.teams[pair],prefix=pair==='B'?'within':'cross';
 $('identity').textContent=`${c.image.image_code} · ${e.target} · ${e.k}人团队、实际换${e.m}人 · 固定参考 ${e.reference_id}`;
 $('metrics').textContent=`A ${fmt(a.B8L2)}分／${a.nodes}节点；${pair} ${fmt(b.B8L2)}分／${b.nodes}节点。|分差| ${fmt(e[prefix+'_abs_B8L2_change'])}；底面差 ${fmt(e[prefix+'_floor_jaccard_difference'])}；绑定角差 ${fmt(e[prefix+'_structure_bound_cyclic_deg'])}°；主判据${e[prefix+'_joint_stable_main']?'通过':'未通过'}，宽判据${e[prefix+'_joint_stable_wide']?'通过':'未通过'}。`;
 $('members').textContent=`固定背景：${e.core_workers}。A：${e.A_workers}。${pair}：${e[pair+'_workers']}。`;
 WorkbenchGeometry.mount($('geometry'),c.image,{points:a.geometry.points,order_status:a.order_status},c.reference,{points:b.geometry.points,footprint:b.geometry.footprint,connected:!!b.geometry.points});rename($('geometry'),'团队A','团队'+pair);
}
function answer(){const c=D[Number($('case').value)],w=$('worker').value;WorkbenchGeometry.mount($('answer'),c.image,{points:c.answers[w],order_status:'冻结预处理环序'},c.reference);rename($('answer'),w,'');}
function changeCase(){const c=D[Number($('case').value)];$('worker').replaceChildren();Object.keys(c.answers).sort().forEach(w=>$('worker').add(new Option(w,w)));render();answer();}
$('case').onchange=changeCase;$('pair').onchange=render;$('worker').onchange=answer;changeCase();
})();
