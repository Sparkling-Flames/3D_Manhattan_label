/* Optional history panel. Uses the existing case/variant/3D viewer. */
if(window.STUDIO_HISTORY){
  const history=window.STUDIO_HISTORY, panel=document.createElement('section');
  panel.className='history-panel';
  panel.innerHTML='<h2>同房组 · 历史标注</h2><div class="history-controls"><label>查找组／楼号 <input id="history-search" placeholder="例如 G179 / uNb"></label><label>同房展示组 <select id="history-group"></select></label><label>图片 <select id="history-image"></select></label><label>条件 <select id="history-mode"><option>Manual</option><option>Semi</option></select></label><label>分区 <select id="history-partition"></select></label></div><p id="history-note"></p><div id="history-clusters"></div>';
  document.querySelector('main').prepend(panel);
  const option=(value,text)=>{const o=document.createElement('option');o.value=value;o.textContent=text;return o;};
  function groups(){const q=$('history-search').value.trim().toLowerCase(),prior=$('history-group').value||'G179';
    $('history-group').replaceChildren(...history.groups.filter(g=>(g.code+' '+g.building).toLowerCase().includes(q)).map(g=>option(g.code,`${g.code} · ${g.building} · ${g.images.length}图`)));
    if([...$('history-group').options].some(o=>o.value===prior))$('history-group').value=prior;
    images();}
  function images(){const g=history.groups.find(g=>g.code===$('history-group').value);
    $('history-image').replaceChildren(...(g?.images||[]).map(i=>option(i.id,`${String(i.number).padStart(2,'0')} · Manual ${i.manual} / Semi ${i.semi}`)));openImage();}
  function openImage(){const id=$('history-image').value,c=dataset.cases.findIndex(c=>c.history_image&&c.image_id===id);
    $('history-clusters').replaceChildren();
    if(c<0){$('history-note').textContent='这张图在当前历史快照中没有标注；下方3D仍为上一次查看的图片。';return;}
    $('history-note').textContent='正在读取该图历史…';chooseCase(c);}
  function partitions(){const c=dataset.cases[currentCase];if(!c.history)return;
    const p=c.history.partitions[$('history-mode').value];
    $('history-partition').replaceChildren(...p.candidates.map((_,i)=>option(i,`候选 ${i+1} / ${p.candidates.length}`)));
    render();}
  function render(){const c=dataset.cases[currentCase];if(!c.history)return;
    const mode=$('history-mode').value,p=c.history.partitions[mode],candidate=p.candidates[Number($('history-partition').value)]||[];
    $('history-note').textContent=`${c.title} · ${mode} · ${p.status}。q_boundary、q_wallwall均≥0.95，点数不同必分开；≥2人称簇，单人标法保留。使用人工复核后点；分簇不是收敛结论。`;
    const assigned=new Set(candidate.flat()),remaining=c.variants.map((v,i)=>({v,i})).filter(({v,i})=>v.source.mode===mode&&!assigned.has(i)).map(x=>x.i);
    const sets=candidate.map((members,i)=>({members,title:members.length>=2?`簇 ${i+1} · ${members.length}人`:'单人标法 · 1人'}));
    if(remaining.length)sets.push({members:remaining,title:'未归簇／计算未纳入（逐人仍可查看）'});
    const colors=['#ee5166','#19afc4','#ad72e8','#ed9c28','#42b976','#4675da'];
    $('history-clusters').replaceChildren(...sets.map(({members,title})=>{
      const a=document.createElement('article');a.className='history-card';const h=document.createElement('h3');h.textContent=title;const expand=document.createElement('button');expand.textContent='展开对照';expand.onclick=()=>{const wide=a.classList.toggle('history-wide');expand.textContent=wide?'收起':'展开对照';};h.append(expand);a.append(h);
      const canvas=document.createElement('canvas');canvas.width=1024;canvas.height=512;a.append(canvas);
      const ctx=canvas.getContext('2d'),photo=new Image(),buttons=document.createElement('div');a.append(buttons);
      const selected=new Set(members);function draw(){ctx.clearRect(0,0,1024,512);if(photo.complete&&photo.naturalWidth)ctx.drawImage(photo,0,0,1024,512);members.forEach((i,j)=>{if(!selected.has(i))return;ctx.fillStyle=colors[j%colors.length];ctx.strokeStyle='#142333';for(const [x,y] of c.variants[i].source.effective_points||[]){ctx.beginPath();ctx.arc(x,y,4,0,Math.PI*2);ctx.fill();ctx.stroke();}});}
      photo.onload=draw;photo.src=window.STUDIO_IMAGES[currentCase].original;
      members.forEach((i,j)=>{const v=c.variants[i],label=document.createElement('label'),check=document.createElement('input');check.type='checkbox';check.checked=true;check.onchange=()=>{check.checked?selected.add(i):selected.delete(i);draw();};label.style.borderLeft=`5px solid ${colors[j%colors.length]}`;label.append(check,`W${v.source.worker_id} · ${v.source.effective_points?.length??'未知'}点 `);const b=document.createElement('button');b.textContent='查看3D';b.onclick=()=>{$('variant-select').value=i;chooseVariant(i,true);document.querySelector('.workspace').scrollIntoView({behavior:'smooth'});};label.append(b);buttons.append(label);});return a;}));
  }
  $('history-search').oninput=groups;$('history-group').onchange=images;$('history-image').onchange=openImage;
  $('history-mode').onchange=partitions;$('history-partition').onchange=render;
  document.addEventListener('studio-case',()=>{const c=dataset.cases[currentCase];if(c.history)partitions();else{$('history-clusters').replaceChildren();$('history-note').textContent='当前为原有工程案例；选择同房组查看历史标注。';}});
  groups();
}
