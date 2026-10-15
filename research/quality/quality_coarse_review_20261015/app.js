'use strict';
const CoarseReview=(()=>{
  const labels={good:'较好',good_average:'较好与一般之间',average:'一般',average_poor:'一般与较差之间',poor:'较差',scope:'参考／范围不适合评价',uncertain:'看不清／暂不能判断'};
  const now=()=>new Date().toISOString();
  function fresh(data){return{schema:data.schema,model:data.model,created_at:now(),current_id:data.cards[0].id,decisions:Object.fromEntries(data.cards.map(c=>[c.id,{grade:null,comment:'',first_viewed_at:null,updated_at:null,score_revealed_at:null,grade_at_first_score_reveal:null}]))};}
  function validate(value,data){
    if(!value||value.schema!==data.schema||value.model!==data.model||!value.decisions)throw Error('这不是本批核验结果，未覆盖当前答案。');
    const state=fresh(data), ids=new Set(data.cards.map(c=>c.id));
    for(const id of Object.keys(value.decisions))if(!ids.has(id))throw Error('回执包含本批以外的题号。');
    for(const c of data.cards){const a=value.decisions[c.id];if(!a)continue;
      if(a.grade!==null&&!Object.hasOwn(labels,a.grade))throw Error('回执中的档位无效。');
      if(typeof a.comment!=='string')throw Error('回执备注格式无效。');
      if(a.bindings&&JSON.stringify(a.bindings)!==JSON.stringify(c.bindings))throw Error('作答或参考绑定与本批不一致。');
      for(const field of Object.keys(state.decisions[c.id]))if(Object.hasOwn(a,field))state.decisions[c.id][field]=a[field];
    }
    if(ids.has(value.current_id))state.current_id=value.current_id;
    state.created_at=value.created_at||state.created_at;return state;
  }
  function receipt(state,data){return{...state,grade_scale:data.grade_scale,exported_at:now(),unanswered_is_negative:false,review_purpose:'coarse_development_review_not_exact_score_targets',decisions:Object.fromEntries(data.cards.map(c=>[c.id,{...state.decisions[c.id],phase:c.phase,bindings:c.bindings,grade_label:labels[state.decisions[c.id].grade]||null,status:state.decisions[c.id].grade===null?'not_reviewed':'reviewed'}]))};}
  return{labels,now,fresh,validate,receipt};
})();
if(typeof module!=='undefined')module.exports=CoarseReview;
if(typeof document!=='undefined'){
  const $=id=>document.getElementById(id), key=DATA.schema, R=CoarseReview;
  let state=R.fresh(DATA), index=0, photo=null;
  const error=t=>{$('error').textContent=t;$('error').hidden=!t;};
  try{const saved=localStorage.getItem(key);if(saved)state=R.validate(JSON.parse(saved),DATA);}catch(e){error('自动恢复失败：'+e.message+' 可导入之前导出的JSON。');}
  index=DATA.cards.findIndex(c=>c.id===state.current_id);
  function save(){try{localStorage.setItem(key,JSON.stringify(state));$('status').textContent='已自动保存到当前浏览器。完成后请导出核验结果。';}catch(e){$('status').textContent='自动保存不可用，请立即导出核验结果，避免关闭后丢失。';}progress();}
  function progress(){const counts=phase=>DATA.cards.filter(c=>c.phase===phase&&state.decisions[c.id].grade!==null).length;$('progress').textContent=`普通 ${counts('ordinary')}/32 · 门洞 ${counts('doorway')}/12`;for(const o of $('jump').options){const c=DATA.cards[Number(o.value)];o.textContent=`${c.phase==='ordinary'?'普通':'门洞'} ${c.id}${state.decisions[c.id].grade!==null?' ✓':''}`;}}
  function score(){const c=DATA.cards[index],a=state.decisions[c.id];$('scores').hidden=!a.score_revealed_at;$('scores').textContent=`WQ 工作分：${SCORES[c.id].WQ.toFixed(2)} / 100。它不是本次五档的标准答案；你的粗判断可以不同。`;$('reveal').textContent=a.score_revealed_at?'已查看工作分':'可选：查看工作分';}
  function drawPhoto(){if(!photo||!photo.complete||!photo.naturalWidth)return;const canvas=$('overlay'),ctx=canvas.getContext('2d');canvas.width=photo.naturalWidth;canvas.height=photo.naturalHeight;ctx.drawImage(photo,0,0);const w=canvas.width,h=canvas.height,b=DATA.cards[index].bindings[0],mode=$('overlayMode').value;
    function uv(p){return[(Math.atan2(p[0],-p[2])/(2*Math.PI)+.5)*w,(-Math.atan2(p[1],Math.hypot(p[0],p[2]))/Math.PI+.5)*h];}
    function segment(a,b){let previous=null;ctx.beginPath();for(let j=0;j<=100;j++){const p=uv(a.map((v,k)=>v+(b[k]-v)*j/100));if(previous&&Math.abs(p[0]-previous[0])<w/2)ctx.lineTo(...p);else ctx.moveTo(...p);previous=p;}ctx.stroke();}
    for(const [oid,color,show]of [[b.reference_object_id,'#34ff82',mode==='both'||mode==='reference'],[b.object_id,'#ff9b24',mode==='both'||mode==='answer']]){if(!show)continue;const g=GEOMETRIES[oid];ctx.strokeStyle=color;ctx.lineWidth=Math.max(2,w/600);for(const ring of ['bottom3d','top3d']){ctx.setLineDash(ring==='bottom3d'?[w/160,w/240]:[]);g[ring].forEach((p,j)=>segment(p,g[ring][(j+1)%g[ring].length]));}ctx.setLineDash([]);g.bottom3d.forEach((p,j)=>segment(p,g.top3d[j]));}
  }
  function drawBEV(){const canvas=$('bev'),ctx=canvas.getContext('2d'),b=DATA.cards[index].bindings[0],all=[...GEOMETRIES[b.object_id].bottom3d,...GEOMETRIES[b.reference_object_id].bottom3d,[0,0,0]];
    const w=canvas.getBoundingClientRect().width,h=420,dpr=window.devicePixelRatio||1;canvas.width=Math.round(w*dpr);canvas.height=h*dpr;ctx.setTransform(dpr,0,0,dpr,0,0);
    const xs=all.map(p=>p[0]),zs=all.map(p=>p[2]),lo=[Math.min(...xs),Math.min(...zs)],hi=[Math.max(...xs),Math.max(...zs)],scale=Math.min((w-80)/(hi[0]-lo[0]||1),(h-80)/(hi[1]-lo[1]||1));
    const xy=p=>[w/2+(p[0]-(lo[0]+hi[0])/2)*scale,h/2-(p[2]-(lo[1]+hi[1])/2)*scale];ctx.clearRect(0,0,w,h);ctx.fillStyle='#fafcf9';ctx.fillRect(0,0,w,h);ctx.lineWidth=3;
    for(const [oid,color]of [[b.reference_object_id,'#218944'],[b.object_id,'#d66c00']]){const ring=GEOMETRIES[oid].bottom3d;ctx.strokeStyle=color;ctx.beginPath();ring.forEach((p,j)=>{const q=xy(p);if(j)ctx.lineTo(...q);else ctx.moveTo(...q);});ctx.closePath();ctx.stroke();}
    const [x,y]=xy([0,0,0]);ctx.strokeStyle='#111';ctx.beginPath();ctx.moveTo(x-6,y);ctx.lineTo(x+6,y);ctx.moveTo(x,y-6);ctx.lineTo(x,y+6);ctx.stroke();ctx.fillStyle='#111';ctx.font='17px system-ui';ctx.fillText('相机',x+9,y-8);
  }
  function open(i){index=i;const c=DATA.cards[index],b=c.bindings[0],a=state.decisions[c.id];state.current_id=c.id;if(!a.first_viewed_at)a.first_viewed_at=R.now();
    $('jump').value=String(index);$('phase').textContent=c.phase==='ordinary'?'第一阶段 · 普通':'第二阶段 · 门洞';$('title').textContent=`${c.id} · ${b.image_code}`;$('binding').textContent=`标注 ${b.record_id}；参考与现有评分保持同一绑定。`;
    $('phaseHint').textContent=c.phase==='ordinary'?'先判断整体观感，不必给精确分数。参考看起来不合理时，请选择“参考／范围不适合评价”。':'门洞阶段：先看标注与参考是否在描述同一范围；不同的合理空间不要直接判成较差。建议完成普通阶段后再看本阶段。';
    document.querySelectorAll('input[name=grade]').forEach(el=>el.checked=el.value===a.grade);$('comment').value=a.comment;$('prev').disabled=index===0;$('next').disabled=$('nextBottom').disabled=index===DATA.cards.length-1;$('next').textContent=index===31?'下一份：进入门洞':'下一份';
    $('photoLink').href=b.photo;$('photoError').hidden=true;const image=new Image();photo=image;image.onload=()=>{if(photo===image)drawPhoto();};image.onerror=()=>{if(photo===image){$('photoError').hidden=false;$('overlay').getContext('2d').clearRect(0,0,$('overlay').width,$('overlay').height);}};image.src=b.photo;drawBEV();Review3D.open(c);score();save();
  }
  DATA.cards.forEach((c,i)=>{const o=document.createElement('option');o.value=i;$('jump').append(o);});
  document.querySelectorAll('input[name=grade]').forEach(el=>el.onchange=()=>{const a=state.decisions[DATA.cards[index].id];a.grade=el.value;a.updated_at=R.now();save();});
  $('comment').oninput=()=>{const a=state.decisions[DATA.cards[index].id];a.comment=$('comment').value;a.updated_at=R.now();save();};
  $('clear').onclick=()=>{const a=state.decisions[DATA.cards[index].id];a.grade=null;a.updated_at=R.now();document.querySelectorAll('input[name=grade]').forEach(el=>el.checked=false);save();};
  $('reveal').onclick=()=>{const a=state.decisions[DATA.cards[index].id];if(!a.score_revealed_at){a.score_revealed_at=R.now();a.grade_at_first_score_reveal=a.grade;}score();save();};
  $('prev').onclick=()=>open(index-1);$('next').onclick=$('nextBottom').onclick=()=>{if(index<DATA.cards.length-1){open(index+1);window.scrollTo({top:0,behavior:'smooth'});}};$('jump').onchange=()=>open(Number($('jump').value));$('overlayMode').onchange=drawPhoto;
  $('export').onclick=()=>{const blob=new Blob([JSON.stringify(R.receipt(state,DATA),null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=DATA.schema+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),30000);};
  $('import').onclick=()=>$('importFile').click();$('importFile').onchange=async()=>{const file=$('importFile').files[0];if(!file)return;try{const incoming=R.validate(JSON.parse(await file.text()),DATA);if(Object.values(state.decisions).some(a=>a.grade!==null)&&!window.confirm('导入会替换当前浏览器中本批答案。请确认已导出当前结果。'))return;state=incoming;error('');open(DATA.cards.findIndex(c=>c.id===state.current_id));}catch(e){error(e.message);}finally{$('importFile').value='';}};
  window.addEventListener('resize',drawBEV);
  open(index);
}
