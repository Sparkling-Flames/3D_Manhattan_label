const key = typeof reviewConfig === 'undefined' ? 'doorway-scope-eligibility-recheck-20261031-v1' : reviewConfig.key;
const reviewTotal = reviewItems.filter(r => !r.comparison).length;
let saved = {}, storageError = '';
try { saved = JSON.parse(localStorage.getItem(key) || '{}'); if (!saved || Array.isArray(saved) || typeof saved !== 'object') throw Error('缓存格式不正确'); }
catch (e) { storageError = '缓存读取失败，请勿关闭页面，完成后导出。'; }
const status = document.querySelector('#status');
function progress() {
  const complete = reviewItems.filter(r => !r.comparison && saved[r.object_id]?.scope && saved[r.object_id]?.eligibility).length;
  status.textContent = (storageError || '选择自动保存，不跳转。') + ` 已完成 ${complete}/${reviewTotal}`;
  status.className = storageError ? 'error' : '';
}
const ns = 'http://www.w3.org/2000/svg';
function svgEl(t, attrs, parent) { const n = document.createElementNS(ns, t); for (const [k,v] of Object.entries(attrs)) n.setAttribute(k,v); parent.append(n); return n; }
function text(t, value, parent) { const n = document.createElement(t); n.textContent = value; parent.append(n); return n; }
function project([x,y,z]) { return [(Math.atan2(x,-z)/(2*Math.PI)+.5)*1024, (.5-Math.atan2(y,Math.hypot(x,z))/Math.PI)*512]; }
function edge(a,b,parent,color) {
  let previous;
  for(let j=0;j<=100;j++) {const t=j/100,p=project(a.map((v,i)=>v*(1-t)+b[i]*t));
    if(previous && Math.abs(p[0]-previous[0])<512) svgEl('line',{x1:previous[0],y1:previous[1],x2:p[0],y2:p[1],stroke:color,'stroke-width':1.8},parent); previous=p;
  }
}
function renderGeometry(r, section) {
  const svg=svgEl('svg',{viewBox:'0 0 1024 512',role:'img','aria-label':`${r.image} ${r.worker}原图及作答`},section);
  svgEl('image',{href:r.photo,width:1024,height:512},svg);
  const overlay=svgEl('g',{},svg),bottom=r.floor.map(([x,z])=>[x,-1,z]);
  const top=r.points.filter((p,i)=>i%2===0).map(([u,v],i)=>{const a=(u/1024-.5)*2*Math.PI,d=Math.hypot(...r.floor[i]);return [d*Math.sin(a),d*Math.tan((.5-v/512)*Math.PI),-d*Math.cos(a)];});
  for(let i=0;i<bottom.length;i++) {
    edge(bottom[i],bottom[(i+1)%bottom.length],overlay,'#ff38cb');edge(top[i],top[(i+1)%top.length],overlay,'#ff38cb');
    const p=r.points[2*i],q=r.points[2*i+1];svgEl('line',{x1:p[0],y1:p[1],x2:q[0],y2:q[1],stroke:'#ff38cb','stroke-width':1},overlay);
    for(const [x,y] of [p,q]){svgEl('circle',{cx:x,cy:y,r:3,fill:'#ff38cb'},overlay);svgEl('text',{x:x+5,y:y-5,fill:'#fff',stroke:'#222','stroke-width':.4,'font-size':13},overlay).textContent=i+1;}
  }
  const toggle=text('button','显示／隐藏原答连线',section);toggle.onclick=()=>overlay.style.display=overlay.style.display==='none'?'':'none';
  const all=[...r.floor,...r.spaces.flat(),[0,0]],xs=all.map(p=>p[0]),zs=all.map(p=>p[1]);
  const lo=[Math.min(...xs),Math.min(...zs)],hi=[Math.max(...xs),Math.max(...zs)],pad=Math.max(hi[0]-lo[0],hi[1]-lo[1])*.08;
  const bev=svgEl('svg',{viewBox:`${lo[0]-pad} ${lo[1]-pad} ${hi[0]-lo[0]+2*pad} ${hi[1]-lo[1]+2*pad}`,class:'bev',role:'img','aria-label':'空间1青色，空间2橙色，原答黑色，相机红点'},section);
  r.spaces.forEach((p,i)=>svgEl('polygon',{points:p.map(q=>q.join(',')).join(' '),fill:i?'#ff932d':'#00b8c9','fill-opacity':.23,stroke:i?'#ff932d':'#00b8c9','stroke-width':2,'vector-effect':'non-scaling-stroke'},bev));
  svgEl('polygon',{points:r.floor.map(p=>p.join(',')).join(' '),fill:'none',stroke:'#111','stroke-width':2,'vector-effect':'non-scaling-stroke'},bev);
  r.floor.forEach(([x,y],i)=>{svgEl('circle',{cx:x,cy:y,r:pad*.045,fill:'#111'},bev);svgEl('text',{x:x+pad*.08,y:y-pad*.07,'font-size':pad*.32,fill:'#111'},bev).textContent=i+1;});
  svgEl('circle',{cx:0,cy:0,r:pad*.09,fill:'red'},bev);
  text('p','空间1：青色　空间2：橙色　相机：红点（视野包含所有作答点，无裁切）',section);
}
for (const r of reviewItems) {
  const section=document.createElement('section');document.querySelector('main').append(section);
  text('h2',`${r.comparison?'历史排除对照':'待复核'} · ${r.image} · ${r.worker}`,section);
  text('p',`原归属：${r.previous_scope}；最初人工初审：${r.first_review}。`,section).className='prior';
  text('p',r.reason,section);renderGeometry(r,section);
  if(r.comparison) continue;
  function save(field,value) {
    saved[r.object_id]={...saved[r.object_id],object_id:r.object_id,image:r.image,worker:r.worker,previous_scope:r.previous_scope,points:r.points,spaces:r.spaces,[field]:value,updated_at:new Date().toISOString()};
    try {localStorage.setItem(key,JSON.stringify(saved));storageError='';} catch(e) {storageError='自动保存失败，请立即导出。';}progress();
  }
  for(const [field,title,labels] of [['scope','空间归属',['空间1','空间2','全部','都不符合（看不懂）']],['eligibility','筛后版是否保留',['保留','排除','待定']]]) {
    const group=document.createElement('div');section.append(group);text('strong',title+'：',group);
    group.dataset.field=field;
    for(const label of labels){const b=text('button',label,group);b.setAttribute('aria-pressed',saved[r.object_id]?.[field]===label);b.onclick=()=>{
      save(field,label);for(const x of group.querySelectorAll('button'))x.setAttribute('aria-pressed',x===b);
      if(field==='scope' && typeof reviewConfig!=='undefined' && reviewConfig.inferEligibility) {
        const eligibility=label==='都不符合（看不懂）'?'排除':'保留';save('eligibility',eligibility);
        for(const g of section.children)if(g.dataset?.field==='eligibility')for(const x of g.querySelectorAll('button'))x.setAttribute('aria-pressed',x.textContent===eligibility);
      }
    };}
  }
  const label=text('label','判断依据（尤其是排除或待定时）：',section),note=document.createElement('textarea');label.append(note);note.rows=2;note.value=saved[r.object_id]?.note||'';note.oninput=()=>save('note',note.value);
}
document.querySelector('#export').onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify({schema:key,decisions:saved},null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=typeof reviewConfig==='undefined'?'门洞追加空间与保留复核_20261031.json':reviewConfig.filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
progress();
