/* Cluster cards and Studio geometry reuse the existing foundation. This round has its own answers. */
(() => {
  const schema='pro_followup_review_20260920_v1', panel=document.createElement('section');
  panel.className='history-panel';
  panel.innerHTML='<h2>六图专项复核 · 按优先级</h2><p id="fu-question"></p><details><summary>AI观察与数值警报（不是最终答案）</summary><p id="fu-note"></p><pre id="fu-numbers"></pre></details><p>先看指定两份，再查看完整簇。点号是原数组序号，不代表跨人员对应。下方3D沿用历史配对，仅供参考。</p><label>冻结分区 <select id="fu-method"></select></label><h3>指定作答对（可切换）</h3><select id="fu-pair" aria-label="选择作答对"></select><div id="fu-focus"></div><h3>完整簇成员</h3><div id="history-clusters"></div><h3>你的判断（默认留空）</h3><label>指定主要作答对 <select id="fu-relation"><option value="">未填写</option><option>可视为相近</option><option>应分开保留差异</option><option>暂不能判断</option></select></label><label><input id="fu-defer" type="checkbox">暂缓</label><p><label>具体位置、簇内混入／过拆、其他作答对意见<br><textarea id="fu-comment" rows="4" style="width:100%"></textarea></label></p><button id="fu-export">导出本轮审核</button> <label>导入本轮审核 <input id="fu-import" type="file" accept=".json"></label><p id="fu-status" role="status"></p>';
  document.querySelector('main').prepend(panel);
  const methods=['OSPA1_6','Hausdorff_9','Bottleneck_equal_9'];
  const opt=(s)=>{const e=document.createElement('option');e.value=s;e.textContent=s;return e;};
  $('fu-method').replaceChildren(...methods.map(opt));
  const blank=()=>({relation:'',comment:'',defer:false});
  function validate(value){
    if(value?.schema!==schema || !value.decisions || typeof value.decisions!=='object' || Array.isArray(value.decisions))throw Error('不是本轮审核文件');
    for(const [key,d] of Object.entries(value.decisions)){
      if(!dataset.cases.some(c=>c.followup.key===key) || !d || typeof d!=='object' ||
        !['','可视为相近','应分开保留差异','暂不能判断'].includes(d.relation) || typeof d.comment!=='string' || typeof d.defer!=='boolean')throw Error('图片身份或答案字段无效');
    }
    return value.decisions;
  }
  let answers={};
  try{const s=localStorage.getItem(schema);if(s)answers=validate(JSON.parse(s));}catch(e){$('fu-status').textContent='未载入旧缓存：'+e.message;}
  function save(){
    const key=dataset.cases[currentCase].followup.key;
    answers[key]={relation:$('fu-relation').value,comment:$('fu-comment').value,defer:$('fu-defer').checked};
    try{localStorage.setItem(schema,JSON.stringify({schema,decisions:answers}));$('fu-status').textContent='本轮答案已保存到此浏览器，请导出留档';}catch(e){$('fu-status').textContent='浏览器保存失败，请立即导出：'+e.message;}
  }
  function card(members,title){
    const c=dataset.cases[currentCase],a=document.createElement('article');a.className='history-card';
    const h=document.createElement('h3');h.textContent=title;a.append(h);
    const canvas=document.createElement('canvas');canvas.width=1024;canvas.height=512;a.append(canvas);
    const ctx=canvas.getContext('2d'),photo=new Image(),selected=new Set(members),controls=document.createElement('div');a.append(controls);
    const colors=['#ff4050','#00c6e5','#9055de','#df8800','#2a9850','#245fde'];
    function draw(){ctx.clearRect(0,0,1024,512);if(photo.complete&&photo.naturalWidth)ctx.drawImage(photo,0,0,1024,512);members.forEach((i,j)=>{if(!selected.has(i))return;ctx.fillStyle=colors[j%colors.length];ctx.strokeStyle='#102030';(c.variants[i].source.effective_points||[]).forEach(([x,y],n)=>{ctx.beginPath();ctx.arc(x,y,4,0,Math.PI*2);ctx.fill();ctx.stroke();if(members.length<=2){ctx.font='14px sans-serif';ctx.lineWidth=2;ctx.strokeText(String(n+1),x+5,y+(j?15:-5));ctx.fillText(String(n+1),x+5,y+(j?15:-5));ctx.lineWidth=1;}});});}
    photo.onload=draw;photo.src=window.STUDIO_IMAGES[currentCase].original;
    for(const [label,on] of [['一键全选',true],['一键取消',false]]){const b=document.createElement('button');b.textContent=label;b.onclick=()=>{selected.clear();if(on)members.forEach(i=>selected.add(i));controls.querySelectorAll('input').forEach(x=>x.checked=on);draw();};h.append(b);}
    const expand=document.createElement('button');expand.textContent='展开／收起';expand.onclick=()=>a.classList.toggle('history-wide');h.append(expand);
    members.forEach((i,j)=>{const v=c.variants[i],label=document.createElement('label'),check=document.createElement('input');check.type='checkbox';check.checked=true;check.onchange=()=>{check.checked?selected.add(i):selected.delete(i);draw();};label.style.borderLeft='5px solid '+colors[j%colors.length];label.append(check,`${v.source.mode} W${v.source.worker_id} · ${v.source.effective_points.length}点 `);const b=document.createElement('button');b.textContent='局部／历史3D';b.onclick=()=>{chooseVariant(i,true);$('panorama-panel').open=true;document.querySelector('.workspace').scrollIntoView({behavior:'smooth'});};label.append(b);controls.append(label);});
    canvas.onclick=e=>{const rect=canvas.getBoundingClientRect(),x=(e.clientX-rect.left)/rect.width*1024,y=(e.clientY-rect.top)/rect.height*512;const crop=document.createElement('canvas');crop.width=600;crop.height=300;const cc=crop.getContext('2d');const buf=document.createElement('canvas');buf.width=3072;buf.height=512;const bc=buf.getContext('2d');for(let k=0;k<3;k++)bc.drawImage(canvas,k*1024,0);cc.drawImage(buf,x+1024-150,Math.max(0,Math.min(362,y-75)),300,150,0,0,600,300);const prior=a.querySelector('[data-local]');if(prior)prior.remove();crop.dataset.local='true';crop.setAttribute('aria-label','点击位置局部放大');a.append(crop);};
    return a;
  }
  function focus(){const c=dataset.cases[currentCase],p=c.followup.pairs_detail[Number($('fu-pair').value)||0];$('fu-focus').replaceChildren(card(p.ids.map(id=>c.followup.ids.indexOf(id)),p.workers.join(' / ')));}
  function clusters(){const r=dataset.cases[currentCase].followup,labels=r.labels[$('fu-method').value],groups=new Map();labels.forEach((n,i)=>{if(!groups.has(n))groups.set(n,[]);groups.get(n).push(i);});$('history-clusters').replaceChildren(...[...groups].map(([n,ix])=>card(ix,`簇 ${n} · ${ix.length}位独立人员`)));}
  function render(){const r=dataset.cases[currentCase].followup;$('fu-question').textContent='待判断：'+r.question;$('fu-note').textContent=r.observation+' 覆盖：'+r.coverage;$('fu-numbers').textContent=JSON.stringify(r.pairs_detail,null,2);$('fu-pair').replaceChildren(...r.pairs_detail.map((p,i)=>{const o=opt(p.workers.join(' / '));o.value=i;return o;}));const d=answers[r.key]||blank();$('fu-relation').value=d.relation;$('fu-comment').value=d.comment;$('fu-defer').checked=d.defer;focus();clusters();}
  $('fu-method').onchange=clusters;$('fu-pair').onchange=focus;
  for(const id of ['fu-relation','fu-defer','fu-comment'])$(id).addEventListener('change',save);
  $('fu-comment').addEventListener('input',save);
  $('fu-export').onclick=()=>{const blob=new Blob([JSON.stringify({schema,exported_at:new Date().toISOString(),decisions:answers,evidence:dataset.cases.map(c=>c.followup)},null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='Pro续研六图_我的审核.json';a.click();URL.revokeObjectURL(url);};
  $('fu-import').onchange=async e=>{try{const f=e.target.files[0];if(!f)return;const imported=validate(JSON.parse(await f.text()));if(Object.keys(answers).length&&!confirm('用导入文件替换本轮浏览器答案？'))return;localStorage.setItem(schema,JSON.stringify({schema,decisions:imported}));answers=imported;render();$('fu-status').textContent='导入成功';}catch(err){$('fu-status').textContent='导入失败，现有答案保留：'+err.message;}};
  document.addEventListener('studio-case',render);render();
})();
