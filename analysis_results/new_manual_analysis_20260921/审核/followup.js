/* Reuses Studio geometry/case navigation; numerical decisions belong to this run. */
function validateReleaseReview(value,binding,keys,optionsByKey={}){
  const stable=v=>JSON.stringify(v&&typeof v==='object'&&!Array.isArray(v)?Object.fromEntries(Object.keys(v).sort().map(k=>[k,JSON.parse(stable(v[k]))])):Array.isArray(v)?v.map(x=>JSON.parse(stable(x))):v);
  if(value?.schema!=='clustering_release_visual_review_v1'||stable(value.binding)!==stable(binding))throw Error('运行版本或点集不匹配，禁止载入为本轮裁决');
  if(!value.decisions||typeof value.decisions!=='object'||Array.isArray(value.decisions))throw Error('缺少裁决对象');
  for(const [key,d] of Object.entries(value.decisions)){
    if(!keys.includes(key)||!d||typeof d!=='object'||!['',...(optionsByKey[key]||['可视为相近','应分开保留差异','暂不能判断'])].includes(d.relation)||typeof d.comment!=='string'||typeof d.defer!=='boolean')throw Error('未知图片或裁决字段无效');
  }
  return value.decisions;
}
if(typeof module!=='undefined')module.exports={validateReleaseReview};
if(typeof document!=='undefined')(()=>{
  const schema=dataset.schema,binding=dataset.binding,storageKey=schema+':'+binding.id,keys=dataset.cases.map(c=>c.followup.key);
  const panel=document.createElement('section');panel.className='history-panel';
  panel.innerHTML='<h2>16图分簇验收 · 按优先级</h2><p id="rr-question"></p><p>先看指定两份，再看整簇及最大阻碍作答。6／9／12°是完整链接对照；181°表示点数或角色数量不可比。原点号不是跨人员语义对应。局部对应确认不自动补成完整对应，也不强制合簇。3D沿用历史几何，只供参考；点集变化时停用。</p><details><summary>AI意见、覆盖范围与既有用户原文（只读）</summary><pre id="rr-evidence" style="white-space:pre-wrap"></pre></details><label>分区对照 <select id="rr-method"></select></label> <label>指定／阻碍作答 <select id="rr-pair"></select></label><div id="rr-focus"></div><h3>整图成员（每簇均可全选／取消）</h3><div id="history-clusters"></div><h3>你的最终判断（默认留空）</h3><p>下拉选项针对本图最初指定作答对；其他作答、角色或对应意见请在文字中写明人员和原点号。</p><label>指定作答对 <select id="rr-relation"><option value="">未填写</option><option>可视为相近</option><option>应分开保留差异</option><option>暂不能判断</option></select></label> <label><input type="checkbox" id="rr-defer">暂缓</label><p><label>位置、点号、具体对应及簇内混入／过拆意见<br><textarea id="rr-comment" rows="5" style="width:100%"></textarea></label></p><button id="rr-export">导出本轮审核</button> <label>导入本轮审核 <input id="rr-import" type="file" accept=".json"></label><p><label>打开旧审核作为只读参考 <input id="rr-legacy" type="file" accept=".json"></label></p><details><summary>旧审核原文（不会写入本轮裁决）</summary><pre id="rr-old" style="white-space:pre-wrap"></pre></details><p id="rr-status" role="status"></p>';
  document.querySelector('main').prepend(panel);
  if(dataset.review_title)panel.querySelector('h2').textContent=dataset.review_title;
  if(dataset.review_instructions)panel.querySelectorAll('p')[1].textContent=dataset.review_instructions;
  const opt=(value,text=value)=>{const o=document.createElement('option');o.value=value;o.textContent=text;return o;};
  $('rr-method').replaceChildren(...[9,6,12].map(t=>opt('split_cyclic_'+t,t+'° · top/bottom独立环序最大误差')));
  $('rr-method').append(opt('ospa_gate_6','OSPA 6° · 同点数点集平均距离对照'));
  if(dataset.method_options)$('rr-method').replaceChildren(...dataset.method_options.map(m=>opt(m.value,m.label)));
  let answers={};
  const validate=v=>validateReleaseReview(v,binding,keys,Object.fromEntries(dataset.cases.map(c=>[c.followup.key,c.followup.decision_options])));
  try{const s=localStorage.getItem(storageKey);if(s)answers=validate(JSON.parse(s));}catch(e){$('rr-status').textContent='未载入浏览器记录：'+e.message;}
  const envelope=()=>({schema,binding,decisions:answers,evidence:dataset.cases.map(c=>c.followup)});
  function save(){
    const r=dataset.cases[currentCase].followup;
    answers[r.key]={relation:$('rr-relation').value,comment:$('rr-comment').value,defer:$('rr-defer').checked};
    try{localStorage.setItem(storageKey,JSON.stringify(envelope()));$('rr-status').textContent='已保存到当前浏览器，请导出留档。';}catch(e){$('rr-status').textContent='保存失败，请立即导出：'+e.message;}
  }
  function card(members,title){
    const c=dataset.cases[currentCase],article=document.createElement('article');article.className='history-card';
    const h=document.createElement('h3');h.textContent=title;article.append(h);
    const canvas=document.createElement('canvas');canvas.width=1024;canvas.height=512;article.append(canvas);
    const ctx=canvas.getContext('2d'),photo=new Image(),selected=new Set(members),controls=document.createElement('div');article.append(controls);
    const colors=['#ff4050','#00c6e5','#9055de','#df8800','#2a9850','#245fde'];
    const showNumbers=document.createElement('input');showNumbers.type='checkbox';showNumbers.checked=members.length<=2;
    const numberLabel=document.createElement('label');numberLabel.append(showNumbers,'显示原点号');h.append(numberLabel);showNumbers.onchange=draw;
    function draw(){
      ctx.clearRect(0,0,1024,512);if(photo.complete&&photo.naturalWidth)ctx.drawImage(photo,0,0,1024,512);
      members.forEach((i,j)=>{if(!selected.has(i))return;ctx.fillStyle=colors[j%colors.length];ctx.strokeStyle='#102030';
        c.variants[i].source.display_points.forEach(([x,y],n)=>{ctx.beginPath();ctx.arc(x,y,4,0,Math.PI*2);ctx.fill();ctx.stroke();if(showNumbers.checked){ctx.font='14px sans-serif';ctx.lineWidth=2;ctx.strokeText('p'+(n+1),x+5,y+(j%2?15:-5));ctx.fillText('p'+(n+1),x+5,y+(j%2?15:-5));ctx.lineWidth=1;}});
      });
    }
    photo.onload=draw;photo.src=window.STUDIO_IMAGES[currentCase].original;
    for(const [label,on] of [['一键全选',true],['一键取消',false]]){const b=document.createElement('button');b.textContent=label;b.onclick=()=>{selected.clear();if(on)members.forEach(i=>selected.add(i));controls.querySelectorAll('input').forEach(e=>e.checked=on);draw();};h.append(b);}
    const expand=document.createElement('button');expand.textContent='展开／收起';expand.onclick=()=>article.classList.toggle('history-wide');h.append(expand);
    members.forEach((i,j)=>{
      const v=c.variants[i],label=document.createElement('label'),check=document.createElement('input');check.type='checkbox';check.checked=true;
      check.onchange=()=>{check.checked?selected.add(i):selected.delete(i);draw();};label.style.borderLeft='5px solid '+colors[j%colors.length];
      label.append(check,`${v.source.mode} W${v.source.worker_id} · ${v.source.display_points.length}点 · ${v.source.points_display_kind} `);
      const b=document.createElement('button');b.textContent=v.geometry?'原图／条件3D':'原图／当前点来源';b.onclick=()=>{$('variant-select').value=i;chooseVariant(i,true);$('panorama-panel').open=true;document.querySelector('.workspace').scrollIntoView({behavior:'smooth'});};label.append(b);controls.append(label);
    });
    canvas.onclick=e=>{const box=canvas.getBoundingClientRect(),x=(e.clientX-box.left)/box.width*1024,y=(e.clientY-box.top)/box.height*512;
      const crop=document.createElement('canvas');crop.width=600;crop.height=300;const cc=crop.getContext('2d'),buf=document.createElement('canvas');buf.width=3072;buf.height=512;const bc=buf.getContext('2d');for(let k=0;k<3;k++)bc.drawImage(canvas,k*1024,0);cc.drawImage(buf,x+1024-150,Math.max(0,Math.min(362,y-75)),300,150,0,0,600,300);article.querySelector('[data-local]')?.remove();crop.dataset.local='true';article.append(crop);
    };
    return article;
  }
  const details=r=>r.pairs_by_method?r.pairs_by_method[$('rr-method').value]:r.pairs_detail;
  function focus(){const r=dataset.cases[currentCase].followup,p=details(r)[Number($('rr-pair').value)||0];$('rr-focus').replaceChildren(card(p.ids.map(cid=>r.ids.indexOf(cid)),(r.pairs_by_method?'当前所选方法：':'固定主方案 9°：')+p.kind+' · '+p.workers.join(' / ')+' · '+(Number.isFinite(p.distance)?p.distance.toFixed(3)+(p.unit||'°'):(p.reason||'本方法无法比较'))+(r.pairs_by_method?'':'（不随下方分区对照改变）')));}
  function pairOptions(){const r=dataset.cases[currentCase].followup;$('rr-pair').replaceChildren(...details(r).map((p,i)=>opt(i,p.kind+'：'+p.workers.join(' / '))));}
  function clusters(){
    const r=dataset.cases[currentCase].followup,groups=new Map();r.labels[$('rr-method').value].forEach((n,i)=>{if(!groups.has(n))groups.set(n,[]);groups.get(n).push(i);});
    $('history-clusters').replaceChildren(...[...groups].map(([n,ix])=>card(ix,n==='unavailable'?'未进入主分簇／排除记录（不是一个簇）':`簇 ${n} · ${ix.length}位人员`)));
  }
  function render(){
    const r=dataset.cases[currentCase].followup;$('rr-question').textContent=`${r.code} · ${r.condition} · ${r.reasons}；${r.coverage}`;
    $('rr-relation').replaceChildren(opt('','未填写'),...(r.decision_options||['可视为相近','应分开保留差异','暂不能判断']).map(v=>opt(v)));
    if(dataset.decision_instructions)panel.querySelectorAll('p')[2].textContent=dataset.decision_instructions;
    $('rr-evidence').textContent=JSON.stringify({点号说明:r.point_numbering,AI:r.ai,既有用户原文:r.user_original.length?r.user_original:'指定运行输入中没有匹配原文',指定点:r.point_focus||null,本轮建议与待裁决:r.research_notes||null},null,2);
    pairOptions();
    const d=answers[r.key]||{relation:'',comment:'',defer:false};$('rr-relation').value=d.relation;$('rr-comment').value=d.comment;$('rr-defer').checked=d.defer;focus();clusters();
  }
  $('rr-method').onchange=()=>{if(dataset.cases[currentCase].followup.pairs_by_method){pairOptions();focus();}clusters();};$('rr-pair').onchange=focus;
  for(const id of ['rr-relation','rr-defer','rr-comment'])$(id).addEventListener('change',save);$('rr-comment').addEventListener('input',save);
  $('rr-export').onclick=()=>{const blob=new Blob([JSON.stringify({...envelope(),exported_at:new Date().toISOString()},null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=dataset.export_filename||'16图分簇_我的审核.json';a.click();URL.revokeObjectURL(url);};
  $('rr-import').onchange=async e=>{try{const file=e.target.files[0];if(!file)return;const imported=validate(JSON.parse(await file.text()));if(Object.keys(answers).length&&!confirm('用导入文件替换本轮浏览器答案？'))return;localStorage.setItem(storageKey,JSON.stringify({schema,binding,decisions:imported}));answers=imported;render();$('rr-status').textContent='导入成功，运行与点集绑定一致';}catch(err){$('rr-status').textContent='导入失败，现有答案保留：'+err.message;}};
  $('rr-legacy').onchange=async e=>{try{const file=e.target.files[0];if(!file)return;const value=JSON.parse(await file.text());$('rr-old').textContent=JSON.stringify(value,null,2);$('rr-status').textContent='旧审核已作为只读原文打开，没有写入本轮答案';}catch(err){$('rr-status').textContent='旧审核读取失败：'+err.message;}};
  document.addEventListener('studio-case',render);render();
})();
