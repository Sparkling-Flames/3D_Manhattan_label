'use strict';
(() => {
const SNAPSHOT='v1_integrated_analysis_20261017_r2';
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const number=x=>typeof x==='number'&&Number.isFinite(x);
const fmt=x=>number(x)?x.toLocaleString('zh-CN',{maximumFractionDigits:2}):'未知';
const colors=['#248d96','#b77b55','#7c6ba1','#859e43'];
const detail=id=>'../research_explorer_20261017/explorer.html?revision=v1r2#module=all&table='+encodeURIComponent(id);
function chart(c){
 const pts=c.series.flatMap(s=>s.points.filter(p=>number(p.x)&&number(p.y)));
 if(!pts.length)return '<p class="missing-chart">当前没有可画的非空支持；保留缺口。</p>';
 const xs=pts.map(p=>p.x),ys=pts.map(p=>p.y),xmin=Math.min(...xs),xmax=Math.max(...xs),ymin=Math.min(0,...ys),ymax=Math.max(...ys);
 const x=v=>64+(v-xmin)/(xmax-xmin||1)*480,y=v=>240-(v-ymin)/(ymax-ymin||1)*200;
 let svg=`<svg viewBox="0 0 600 300" role="img" aria-label="${esc(c.title)}"><title>${esc(c.title)}</title><line x1="64" y1="240" x2="555" y2="240" stroke="#b7c0bd"/><line x1="64" y1="40" x2="64" y2="240" stroke="#b7c0bd"/>`;
 for(let i=0;i<5;i++){const v=ymin+(ymax-ymin)*i/4;svg+=`<text x="55" y="${y(v)+4}" text-anchor="end" fill="#61716c" font-size="11">${esc(fmt(v))}</text>`;}
 for(const v of [...new Set(xs)].sort((a,b)=>a-b).filter((_,i,a)=>a.length<16||i%Math.ceil(a.length/12)===0))svg+=`<text x="${x(v)}" y="260" text-anchor="middle" fill="#61716c" font-size="11">${esc(fmt(v))}</text>`;
 c.series.forEach((s,i)=>{let segment=[];const flush=()=>{if(c.type==='line'&&segment.length>1)svg+=`<polyline points="${segment.join(' ')}" fill="none" stroke="${colors[i%4]}" stroke-width="2"/>`;segment=[];};for(const p of s.points){if(!number(p.x)||!number(p.y)){flush();continue;}segment.push(`${x(p.x)},${y(p.y)}`);svg+=`<circle cx="${x(p.x)}" cy="${y(p.y)}" r="4" fill="${colors[i%4]}"><title>${esc(s.label)} · ${esc(p.label??p.x)} · ${esc(fmt(p.y))}${p.n==null?'':' · 支持 '+esc(p.n)}</title></circle>`;}flush();});
 svg+=`<text x="300" y="289" text-anchor="middle" fill="#61716c" font-size="12">${esc(c.x_label)}</text></svg>`;
 return svg+'<div class="chart-note">'+c.series.map((s,i)=>`<span style="color:${colors[i%4]}">● ${esc(s.label)}</span>`).join('　')+'</div>';
}
function section(s){
 const status={supported:['支持','status-supported'],unsupported:['不支持','status-unsupported'],insufficient:['证据不足','status-insufficient']}[s.status];
 if(!status)throw Error('未知证据状态：'+s.id);
 const rows=s.examples?.rows||[],cols=s.examples?.columns||[];
 return `<section id="${esc(s.id)}" class="panel finding"><div class="finding-head"><h2>${esc(s.title)}</h2><span class="small-tag ${status[1]}">${status[0]}</span></div><p class="expectation">本页检验的命题：${esc(s.expectation)}</p><p class="claim">${esc(s.finding)}</p><p class="support">${esc(s.support)}</p><div class="chart-grid">${(s.charts||[]).map(c=>`<figure class="mini-chart"><figcaption>${esc(c.title)}</figcaption>${chart(c)}<p class="chart-note">${esc(c.note)}</p></figure>`).join('')}</div><div class="counterexample"><strong>反例 / 解释限制：</strong>${esc(s.counterexample)}</div>${rows.length?`<details><summary>查看支持与反例的具体数值（${rows.length}行）</summary><div class="table-scroll"><table><thead><tr>${cols.map(c=>`<th>${esc(c)}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${r.map(v=>`<td>${esc(number(v)?fmt(v):v??'未知')}</td>`).join('')}</tr>`).join('')}</tbody></table></div></details>`:''}<div class="data-links">${s.tables.map(t=>`<a href="${detail(t.id)}">${esc(t.label)} ↗</a>`).join('')}</div></section>`;
}
async function init(){try{const o=await window.readResearchJSON('explorer-data/overview.json');if(o.metadata?.snapshot_id!==SNAPSHOT)throw Error('概要快照ID与入口不一致，拒绝混合数据');document.getElementById('counts').innerHTML=o.headline_counts.map(c=>`<div class="metric-card"><div class="metric-label">${esc(c.label)}</div><div class="metric-value">${esc(fmt(c.value))}</div><div class="metric-foot">${esc(c.note)}</div></div>`).join('');document.getElementById('sections').innerHTML=o.sections.map(s=>`<a href="#${esc(s.id)}">${esc(s.title)}</a>`).join('');document.getElementById('content').innerHTML=o.sections.map(section).join('');}catch(e){document.getElementById('error').hidden=false;document.getElementById('error').textContent=e.message+'。请确认已完成构建，并保留 explorer-data 离线数据目录，不以示例数据补齐。';}finally{document.getElementById('loading').hidden=true;}}
init();
})();
