(function(){
'use strict';
const D=window.CompositionVarianceData;
const names={DSTRUCT_K2:'DSTRUCT K2',DSTRUCT_K3:'DSTRUCT K3',OLD_STRUCTURE_COARSE:'旧结构粗层',OLD_STRUCTURE_FINE:'旧结构细层'};
const metrics={B8L2:'Q（分）',D10:'D10（分）',fusion_turn_n:'实际转折（个）',log_recorded_time:'log 记录总秒数',not_complete_evaluable:'未完整可评比例'};
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const f=(v,n=3)=>v==null?'不可估':Number(v).toFixed(n);
const $=id=>document.getElementById(id);
const configs=D.configurations.map(a=>Object.fromEntries(D.configuration_fields.map((k,i)=>[k,a[i]])));
const unique=[...new Map(D.panels.map(p=>[p.panel_id,p])).values()].sort((a,b)=>a.panel_id.localeCompare(b.panel_id));
$('panel').innerHTML=unique.map(p=>`<option value="${esc(p.panel_id)}">${esc(p.image)} / n${p.n} / ${esc(p.source_domain)} / ${esc(p.panel_id.split('__').slice(-2,-1)[0])} / ${esc(p.difficulty)}</option>`).join('');
const defaultPanel=unique.find(p=>p.image==='7y3sRwLe3Va-21'&&p.n===20&&p.panel_id.includes('__v2__'));
if(defaultPanel)$('panel').value=defaultPanel.panel_id;
function bars(rows){
 let out=`<svg viewBox="0 0 610 ${rows.length*54+32}" role="img" aria-label="构成间与构成内方差占比">`;
 rows.forEach((r,i)=>{const y=12+i*54,b=r.between_share;out+=`<text x="0" y="${y+20}" font-size="15" fill="#17323c">${esc(names[r.method])}</text>`;
 if(b==null){out+=`<text x="155" y="${y+20}" font-size="14">总方差为零，占比不可定义</text>`;return;}
 out+=`<rect x="155" y="${y}" width="340" height="28" fill="#dfe8eb"/><rect x="155" y="${y}" width="${340*b}" height="28" fill="#177e89"/><text x="505" y="${y+20}" font-size="15">${f(100*b,2)}%</text>`;});
 return out+'</svg>';
}
function table(headers,rows){return '<table><thead><tr>'+headers.map(h=>'<th>'+esc(h)+'</th>').join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+r.map(v=>'<td>'+esc(v)+'</td>').join('')+'</tr>').join('')+'</tbody></table>';}
function plot(rows){
 const valid=rows.filter(r=>r.mean!=null);if(!valid.length)return '<p>该面板没有这一指标的有效团队，不补零。</p>';
 const lo=Math.min(...valid.map(r=>r.p05)),hi=Math.max(...valid.map(r=>r.p95)),pad=Math.max((hi-lo)*.06,.001),min=lo-pad,max=hi+pad;
 const x=v=>200+310*(v-min)/(max-min),h=rows.length*35+60;
 let out=`<svg viewBox="0 0 620 ${h}" role="img" aria-label="各配比的均值和成员分布">`;
 rows.forEach((r,i)=>{const y=20+i*35;out+=`<text x="0" y="${y+5}" font-size="13">${esc(r.class_counts)}</text><text x="530" y="${y+5}" font-size="12">${r.valid_teams}/${r.teams}队</text>`;
 if(r.mean==null){out+=`<text x="205" y="${y+5}" font-size="13">无有效值</text>`;return;}
 if(r.member_variation_estimable)out+=`<line x1="${x(r.p05)}" x2="${x(r.p95)}" y1="${y}" y2="${y}" stroke="#839da5" stroke-width="2"/><line x1="${x(r.p25)}" x2="${x(r.p75)}" y1="${y}" y2="${y}" stroke="#177e89" stroke-width="7"/>`;
 out+=`<circle cx="${x(r.mean)}" cy="${y}" r="4" stroke="#17323c" fill="${r.member_variation_estimable?'#17323c':'white'}"/>`;});
 const yy=h-28;out+=`<line x1="200" x2="510" y1="${yy}" y2="${yy}" stroke="#8ca1a7"/>`;
 for(let i=0;i<4;i++){const v=min+(max-min)*i/3;out+=`<text x="${x(v)}" y="${yy+20}" font-size="12" text-anchor="middle">${f(v,2)}</text>`;}
 return out+'</svg>';
}
let current=[];
function draw(){
 const metric=$('metric').value,method=$('method').value,pid=$('panel').value;
 const overall=D.summary.filter(r=>r.scope==='all'&&r.metric===metric);$('overview').innerHTML=bars(overall);
 const a=overall[0];$('overallSupport').textContent=`${metrics[metric]}：${a.panels} 面板 / ${a.images} 图 / ${a.buildings} 楼；${a.valid_team_links.toLocaleString()} 条有效团队关联。每个指标使用自身支持。`;
 const p=D.panels.find(r=>r.panel_id===pid&&r.method===method&&r.metric===metric);
 $('panelSupport').textContent=`${p.image} · ${p.difficulty} · n=${p.n} · ${p.source_domain}。指标：${metrics[metric]}；${p.valid_teams}/${p.teams} 队有效，${p.configurations} 个有效配比，${p.singleton_configurations} 个单团队格。编号使用目标楼外标签，不直接套 ALL 中文类名。`;
 $('panelVariance').innerHTML=bars([p]);$('panelNumbers').innerHTML=table(['量','值'],[['总方差',f(p.total_variance,5)],['构成间方差',f(p.between_variance,5)],['构成内方差',f(p.within_variance,5)],['构成内占比',p.between_share==null?'不可定义':f(100*(1-p.between_share),2)+'%']])+'<p class="muted">方差单位是原指标单位的平方。有限总体经验分解中单队格内项为零，但不证明可互换；可评团队不足或总方差为零时不制造占比。</p>';
 current=configs.filter(r=>r.panel_id===pid&&r.method===method&&r.metric===metric);$('distributions').innerHTML=plot(current);
 $('configTable').innerHTML=table(['配比','有效/全部','均值','p05','p25','中位数','p75','p95','成员波动可估'],current.map(r=>[r.class_counts,`${r.valid_teams}/${r.teams}`,f(r.mean),f(r.p05),f(r.p25),f(r.median),f(r.p75),f(r.p95),r.member_variation_estimable?'是':'否']));
 const hm=metric==='log_recorded_time'?'log_source_time':metric;
 const hr=D.historical.filter(r=>r.outcome===hm);
 $('historical').innerHTML=hr.length?table(['条件/方法','候选域','构成间','构成内','面板/图/楼'],hr.map(r=>[`${r.condition} · ${r.method.startsWith('joint')?'结构＋Q/T':'结构'} · ${r.method.endsWith('fine')?'细层':'粗层'}`,r.domain,f(r.between_share*100,2)+'%',f((1-r.between_share)*100,2)+'%',`${r.panels}/${r.images}/${r.buildings}`])):'<p>本页历史摘要未选择此指标，请查完整原表。</p>';
}
['metric','method','panel'].forEach(id=>$(id).addEventListener('change',draw));
$('download').addEventListener('click',()=>{const fields=D.configuration_fields;const quote=v=>'"'+String(v??'').replace(/"/g,'""')+'"';const text='\ufeff'+[fields,...current.map(r=>fields.map(k=>r[k]))].map(row=>row.map(quote).join(',')).join('\r\n');const url=URL.createObjectURL(new Blob([text],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='composition-panel.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
draw();
})();
