'use strict';
const $=id=>document.getElementById(id), D=window.V2;
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=(x,n=1)=>x===null||x===undefined||x===''?'—':Number(x).toFixed(n);
const names={no_clear_preference:'无明确偏好',broadly_high:'两类均较高',hard_advantage:'难图优势',hard_relative_improvement:'难图相对提升',hard_relative_drop:'难图相对下降',nonhard_advantage:'非难图优势',insufficient:'证据不足'};
const panelnames={'manual|ordinary_primary':'普通Manual','manual|doorway_quality':'门洞Manual','manual|special_conditional_only':'其它条件Manual','semi|ordinary_primary':'普通Semi','semi|special_conditional_only':'其它条件Semi'};
$('summary').innerHTML=[['质量作答',D.summary.quality_rows],['质量图片',D.summary.quality_images],['有质量记录人员',D.summary.quality_workers],['普通Manual',D.summary.main_rows]].map(([k,v])=>`<div class="card">${k}<br><strong>${v}</strong></div>`).join('');
$('panel').innerHTML=[...new Set(D.profiles.map(r=>r.panel))].map(p=>`<option value="${esc(p)}">${esc(panelnames[p]||p)}</option>`).join('');$('panel').value='manual|ordinary_primary';
function render(){
 const rows=D.profiles.filter(r=>r.panel===$('panel').value && r.difficulty===$('difficulty').value && (!$('q').value||r.q_class===$('q').value) && (!$('t').value||r.t_class===$('t').value) && r.worker_id.toLowerCase().includes($('worker').value.toLowerCase()) && (!$('semi').value||($('semi').value==='seen'?(r.semi_error_opportunities+r.semi_confirmed_error_opportunities)>0:$('semi').value==='unchanged'?(r.semi_known_error_unchanged+r.semi_confirmed_error_unchanged)>0:(r.semi_error_opportunities+r.semi_confirmed_error_opportunities)===0)) && (!$('scope').value||($('scope').value==='evidence'?r.scope_judged_n>0:$('scope').value==='mismatch'?r.scope_correct_n<r.scope_judged_n:r.scope_judged_n===0))).sort((a,b)=>(b.relative_q??-1)-(a.relative_q??-1));
 $('count').textContent=`当前 ${rows.length} 人；按相对Q排序。Semi、scope为该人员全部保留记录的机会证据，不是当前难度子集的分母。`;
 $('profiles').innerHTML=rows.map(r=>`<tr><td><button data-worker="${esc(r.worker_id)}">${esc(r.worker_id)}</button></td><td>${esc(r.fine_class)}</td><td>${r.n} / ${r.buildings}</td><td>${num(r.B8L2_mean)} / ${num(r.B8L2_p10)}</td><td>${num(r.relative_q,3)} / ${num(r.relative_q_D10,3)}</td><td>${num(r.time_median)} / ${r.time_n}</td><td>${esc(r.t_class_sensitivity)}</td><td>${esc(names[r.B8L2_candidate]||'—')}<br>Δ ${num(r.B8L2_advantage,3)}</td><td>新 ${r.semi_known_error_unchanged} / ${r.semi_error_opportunities}<br>旧 ${r.semi_confirmed_error_unchanged} / ${r.semi_confirmed_error_opportunities}</td><td>${r.scope_correct_n} / ${r.scope_judged_n}</td><td>${r.scope_out_n} / ${r.scope_response_n}</td></tr>`).join('');
 $('profiles').querySelectorAll('button').forEach(b=>b.onclick=()=>detail(b.dataset.worker));
}
function detail(worker){
 const rows=D.records.filter(r=>r.worker_id===worker&&r.panel===$('panel').value&&($('difficulty').value==='all'||r.difficulty===$('difficulty').value)).sort((a,b)=>a.B8L2-b.B8L2);
 const p=D.profiles.find(r=>r.worker_id===worker&&r.panel===$('panel').value&&r.difficulty===$('difficulty').value);
 $('detailTitle').textContent=`${worker} · ${panelnames[$('panel').value]||$('panel').value} · ${rows.length}份（低分优先）`;
 $('detailInfo').textContent=p?`时间来源：${p.time_source}。难图-非难图相对Q差：${num(p.B8L2_advantage,3)}；逐建筑删除后的范围：${num(p.B8L2_leave_building_min,3)} 至 ${num(p.B8L2_leave_building_max,3)}。scope相容历史裁定机会：out ${p.scope_confirmed_oos_n}，in ${p.scope_confirmed_in_n}。`:'';
 $('details').innerHTML=rows.map(r=>`<tr><td>${esc(r.image_code)}<br><small>${esc(r.object_id)}</small></td><td>${esc(r.current_class)}</td><td>${num(r.B8L2)} / ${num(r.D10)}</td><td>${num(r.B8L2_rank,3)} / ${r.peer_n}</td><td>${num(r.iou_2d,3)} / ${num(r.S_bottom_deg)}</td><td>${num(r.dir,3)} / ${num(r.Hmean,3)} / ${num(r.Hcenter,3)}</td><td>${num(r.source_active_time_seconds)}</td><td><small>${esc(r.reference_id)}</small></td></tr>`).join('');
}
['panel','difficulty','q','t','worker','semi','scope'].forEach(id=>$(id).addEventListener('input',render));render();
const resolutions={sole_reference_identity_only:'唯一参考身份已补齐；限制保留',historical_unusable_or_excluded:'旧排除／几何不可用',needs_geometry_or_target_review:'新作答：相机不在底面内，待审查'};
$('audit').innerHTML=D.audit.map(r=>`<tr><td>${esc(r.image_code)}</td><td>${esc(r.worker_id)} / ${esc(r.object_id)}</td><td>${esc(r.adopted_review?'已接入：'+r.adopted_review.method:resolutions[r.resolution])}</td><td>${esc(r.retained_quality_blockers)}</td></tr>`).join('');
function project(points){return points.filter((_,i)=>i%2).map(([x,y])=>{const a=(x/1024-.5)*2*Math.PI,r=1/Math.tan((y/512-.5)*Math.PI);return [r*Math.sin(a),-r*Math.cos(a)];});}
function plot(canvas,sets,bev,photo){
 const c=canvas.getContext('2d'),w=canvas.width,h=canvas.height,colors=['#ffd348','#48e3e7','#ff80ca'];
 const paint=()=>{
 c.fillStyle='#182434';c.fillRect(0,0,w,h);if(photo&&!bev)c.drawImage(photo,0,0,w,h);
 const projected=sets,all=projected.flat().concat([[0,0]]),xs=all.map(p=>p[0]),ys=all.map(p=>p[1]);
 const bounds=[Math.min(...xs),Math.max(...xs),Math.min(...ys),Math.max(...ys)],scale=Math.min((w-40)/(bounds[1]-bounds[0]||1),(h-40)/(bounds[3]-bounds[2]||1));
 const xy=([x,y])=>bev?[20+(x-bounds[0])*scale,h-20-(y-bounds[2])*scale]:[x/1024*w,y/512*h];
 if(bev){const [x,y]=xy([0,0]);c.strokeStyle='white';c.beginPath();c.moveTo(x-6,y);c.lineTo(x+6,y);c.moveTo(x,y-6);c.lineTo(x,y+6);c.stroke();}
 projected.forEach((ps,j)=>{c.strokeStyle=colors[j];c.fillStyle=colors[j];c.lineWidth=j?1.7:2.8;
 const rings=bev?[ps]:[ps.filter((_,i)=>i%2===0),ps.filter((_,i)=>i%2===1)];
 rings.forEach(ring=>ring.forEach((p,i)=>{const a=xy(p),b=xy(ring[(i+1)%ring.length]);c.beginPath();c.arc(...a,2.5,0,7);c.fill();c.beginPath();c.moveTo(...a);if(!bev&&Math.abs(a[0]-b[0])>w/2){const bb=[b[0]+(b[0]<a[0]?w:-w),b[1]];c.lineTo(...bb);c.stroke();c.beginPath();c.moveTo(a[0]+(a[0]>b[0]?-w:w),a[1]);}c.lineTo(...b);c.stroke();}));});};paint();return paint;
}
D.reviews.forEach((r,i)=>{const adopted=r.adopted_review;const selected=adopted?r.references.findIndex(x=>x.name===adopted.chosen_target_id):-1;const status=adopted?`已采用${selected===1?'粉色':'蓝色'}（${adopted.method==='manual_bev_color'?'人工指定':'既有底面fallback，暂定'}）`:'待审查';const box=document.createElement('article');box.className='review';box.innerHTML=`<h3>${esc(r.image_code)} · ${esc(r.worker_id)} · ${esc(r.object_id)} · ${status}</h3><p>黄色：处理后原作答；青色：参考1；粉色：参考2。仅有底面的参考不补造顶界；右侧显示两个参考底面。</p><div class="plots"><canvas width="1024" height="512" aria-label="全景参考叠加"></canvas><canvas width="512" height="512" aria-label="底面参考叠加"></canvas></div><details><summary>参考身份</summary>${r.references.map((x,j)=>`<p>${j+1}: ${esc(x.name)}</p>`).join('')}</details>`;$('reviews').appendChild(box);const sets=[r.points,...r.references.map(x=>x.points)].filter(Boolean),can=box.querySelectorAll('canvas');plot(can[0],sets,false);plot(can[1],[project(r.points),...r.references.map(x=>x.floor)],true);if(r.photo){const photo=new Image();photo.onload=()=>plot(can[0],sets,false,photo);photo.src=r.photo;}});
