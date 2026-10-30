let reviewFilter='round';
function reviewKind(c,r,baseline=false){const d=(baseline?window.DOORWAY_SEED:state).cases[c.image_id],a=d?.answers[r.id];const seed=window.DOORWAY_SEED.cases[c.image_id]?.answers[r.id];return {unreviewed:!a,disputed:c.image==='jh4fc5c5qoQ-14'&&['W105','W107'].includes(r.worker)&&JSON.stringify(a)===JSON.stringify(seed),changed:!!a&&JSON.stringify(a.cuts)!==JSON.stringify(d.cuts)};}
function reviewMatches(c,r){if(c.image==='pRbA3pwrgk9-01'||c.image==='pRbA3pwrgk9-11')return false;if(!r.points&&!r.raw_points)return reviewFilter==='missing';const k=reviewKind(c,r,reviewFilter==='round');return reviewFilter==='all'||((reviewFilter==='pending'||reviewFilter==='round')?Object.values(k).some(Boolean):k[reviewFilter]);}
function reviewQueue(){return D.cases.flatMap((c,ci)=>c.records.flatMap((r,ri)=>reviewMatches(c,r)?[{ci,ri}]:[]));}
const fullShow=show,fullRender=renderAnswer;
function filterMenus(){const q=reviewQueue();$('images').innerHTML=D.cases.map((c,ci)=>(q.some(x=>x.ci===ci)||ci===i)?`<option value="${ci}">${c.image}</option>`:'').join('');$('images').value=i;$('answers').innerHTML=cur().records.map((r,ri)=>(reviewMatches(cur(),r)||ri===j)?`<option value="${ri}">${ri+1} · ${r.worker}${state.cases[cur().image_id]?.answers[r.id]?' · 已保存，可改选':''}</option>`:'').join('');$('answers').value=j;$('filterCount').textContent=`当前筛选 ${q.length} 份`;
$('prev').disabled=$('next').disabled=$('aprev').disabled=$('anext').disabled=!q.length;}
function filteredShow(){const q=reviewQueue();if(!q.some(x=>x.ci===i&&x.ri===j)){const p=q.find(x=>x.ci===i)||q[0];if(p){i=p.ci;j=p.ri;}}
if(!q.length){$('choices').innerHTML='';$('viewer').innerHTML='';$('initialVerdict').textContent='此筛选下没有待处理作答，可切换筛选。';filterMenus();return;}fullShow();filterMenus();}
show=filteredShow;renderAnswer=()=>{fullRender();if(!cur().records[j].points&&!cur().records[j].raw_points){$('choices').innerHTML='';$('initialVerdict').textContent='原始导出无点位，数据缺失；无需四选一。';}filterMenus();};
function stepAnswer(delta){const q=reviewQueue();if(!q.length)return;const n=q.findIndex(x=>x.ci===i&&x.ri===j),p=n>=0?q[(n+delta+q.length)%q.length]:(delta>0?q.find(x=>x.ci>i||(x.ci===i&&x.ri>j))||q[0]:q.slice().reverse().find(x=>x.ci<i||(x.ci===i&&x.ri<j))||q[q.length-1]);i=p.ci;j=p.ri;show();}
function stepImage(delta){const ids=[...new Set(reviewQueue().map(x=>x.ci))];if(!ids.length)return;i=ids[(ids.indexOf(i)+delta+ids.length)%ids.length];j=-1;show();}
$('reviewFilter').onchange=()=>{reviewFilter=$('reviewFilter').value;show();};$('reviewFilter').value=reviewFilter;
$('prev').onclick=()=>stepImage(-1);$('next').onclick=()=>stepImage(1);$('aprev').onclick=()=>stepAnswer(-1);$('anext').onclick=()=>stepAnswer(1);show();
