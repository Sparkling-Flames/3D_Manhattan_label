'use strict';
(() => {
  const data=window.REVIEW_DATA;
  if(!data||data.manifest.schema!=='consensus_visual_review_v1') throw new Error('审查数据缺失或版本不符');
  const $=id=>document.getElementById(id), ids=new Set(data.rows.map(r=>r.id));
  if(ids.size!==data.manifest.accepted) throw new Error('canonical ID 重复');
  const key='consensus_visual_review_20260923_v1:'+data.manifest.contract_version;
  const labels={gt_original:'原始 MP3D GT',gt_revised:'人工修订 GT',hohonet:'HoHoNet',bilayout_enclosed:'BiLayout enclosed',bilayout_extended:'BiLayout extended'};
  const cueNames={known:'既有错标',pairing:'配对',geometry:'3D诊断',representation:'墙带表示',singleton:'单人簇',small_cluster:'二人小簇',count:'角点数量',order:'顺序线索',iou:'IoU分歧'};
  const verdicts=new Set(['retain','invalid','gt_scope','representation','pending']);
  let decisions={};
  try{const saved=JSON.parse(localStorage.getItem(key)||'{}');if(saved&&typeof saved==='object')decisions=saved;}catch(e){$('save-status').textContent='浏览器保存记录读取失败；请用导入恢复';}
  let selected=null,caseData=null,page=0,photo=new Image(),request=0,chartHits=[];
  photo.onload=draw;photo.onerror=()=>{$('save-status').textContent='原图加载失败：请保持页面位于仓库目录内';draw();};
  $('release').textContent=data.manifest.contract_version;
  $('coverage').textContent=`${data.manifest.accepted}份 / ${data.manifest.images}图`;
  $('worker').append(...[...new Set(data.rows.map(r=>r.worker))].sort().map(v=>option(v,v)));
  function option(value,label){const x=document.createElement('option');x.value=value;x.textContent=label;return x;}
  function n(x,d=3){return x===null||x===undefined||x===''?'—':Number(x).toFixed(d);}
  function cell(text){const td=document.createElement('td');td.textContent=text;return td;}
  function mode(){return $('mode').value;}
  function gt(){return $('gt').value;}
  function categoryMatch(r){
    const m=r.modes[mode()],q=m.quality[gt()],c=$('category').value;
    if(c==='suspect')return r.screening.cues.length>0;
    if(c==='priority')return r.screening.cues.some(c=>['known','pairing','geometry','representation'].includes(c));
    if(c.startsWith('cue:'))return r.screening.cues.includes(c.slice(4));
    if(c==='all')return true;
    if(c==='ranked')return m.rank!==null&&!r.known_wrong;
    if(c==='failure')return !!m.failure;
    if(c==='reference')return !m.failure&&m.reference_count<5;
    if(c==='peer')return !m.failure&&m.peer_count===0;
    if(c==='known')return r.known_wrong;
    if(c==='vertical')return q.status==='ok'&&Math.abs(q.dy_px)>=20;
    if(c==='circular')return q.status==='ok'&&Math.abs(q.circular_dx_px)>=100&&Math.min(q.circular_R,q.gt_circular_R)<.15;
    if(c==='near')return q.status==='ok'&&q.iou<.7&&q.erp_distance_px<10;
    if(c==='changed')return r.manual_gt_changed;
    return false;
  }
  function filtered(){
    const condition=$('condition').value,worker=$('worker').value,search=$('search').value.trim().toLowerCase(),df=$('decision-filter').value;
    return data.rows.filter(r=>(condition==='all'||r.condition===condition)&&(worker==='all'||r.worker===worker)&&categoryMatch(r)
      &&(df==='all'||(df==='reviewed'===!!decisions[r.id]))&&(!search||[r.code,r.image_id,r.worker,r.id].some(s=>s.toLowerCase().includes(search))))
      .sort((a,b)=>Number(b.known_wrong)-Number(a.known_wrong)||Number(b.screening.cues.some(c=>['pairing','geometry','representation'].includes(c)))-Number(a.screening.cues.some(c=>['pairing','geometry','representation'].includes(c)))||b.screening.cues.length-a.screening.cues.length||(b.modes[mode()].rank??-1)-(a.modes[mode()].rank??-1)||a.id.localeCompare(b.id));
  }
  function renderList(){
    const all=filtered(),size=50,max=Math.max(0,Math.ceil(all.length/size)-1);page=Math.min(page,max);
    const body=$('rows');body.replaceChildren();
    for(const r of all.slice(page*size,(page+1)*size)){
      const m=r.modes[mode()],q=m.quality[gt()],tr=document.createElement('tr');
      if(r.id===selected)tr.classList.add('selected');if(r.known_wrong)tr.classList.add('known');
      tr.append(cell(`${r.code} · ${r.worker}`),cell(r.condition.toUpperCase()),cell(r.screening.cues.map(c=>cueNames[c]).join('、')||'未命中'),cell(n(m.rank)),
        cell(m.reference_count===null?'未计算':`${m.reference_count}/5`),cell(m.peer_count===null?'未计算':String(m.peer_count)),cell(n(q.iou)),
        cell(r.known_wrong?'既有明确错标':decisions[r.id]?.verdict||m.failure||'待审'));
      const td=document.createElement('td'),button=document.createElement('button');button.type='button';button.textContent='查看';button.onclick=()=>select(r.id);
      td.append(button);tr.append(td);body.append(tr);
    }
    $('scope').textContent=`当前人工队列：${mode()==='curve'?'空间曲线':'二维直线'} / ${$('condition').selectedOptions[0].textContent} / ${$('category').selectedOptions[0].textContent}。多通道取并集，可重叠；优先既有错标、几何/配对/表示异常，再按通道数。目标是发现非墙角、乱标等明显无效作答，范围不同和少数意见不自动排除。未命中不等于正确。质心散点始终为全量。`;
    $('list-count').textContent=`${all.length}份`;$('page-info').textContent=`第${page+1}/${max+1}页`;
    $('prev').disabled=page===0;$('next').disabled=page===max;
    $('decision-count').textContent=`本轮已记录 ${Object.keys(decisions).filter(k=>ids.has(k)).length}份`;
    drawChart(data.rows);
  }
  function drawChart(rows){
    const canvas=$('scatter'),ctx=canvas.getContext('2d'),width=canvas.width,height=canvas.height;
    ctx.clearRect(0,0,width,height);ctx.fillStyle='#fff';ctx.fillRect(0,0,width,height);
    ctx.strokeStyle='#dce3d8';ctx.lineWidth=1;ctx.font='12px Segoe UI';ctx.fillStyle='#71816f';
    const left=52,right=width-22,top=18,bottom=height-35;
    for(const t of [0,.25,.5,.75,1]){const x=left+t*(right-left);ctx.beginPath();ctx.moveTo(x,top);ctx.lineTo(x,bottom);ctx.stroke();ctx.fillText(String(t),x-10,height-12);}
    for(const t of [0,5,20,100]){const y=bottom-Math.log1p(t)/Math.log(101)*(bottom-top);ctx.beginPath();ctx.moveTo(left,y);ctx.lineTo(right,y);ctx.stroke();ctx.fillText(String(t),15,y+4);}
    chartHits=[];
    for(const r of rows){const q=r.modes[mode()].quality[gt()];if(q.status!=='ok')continue;
      const x=left+q.iou*(right-left),y=bottom-Math.log1p(Math.min(100,Math.abs(q.dy_px)))/Math.log(101)*(bottom-top);
      ctx.beginPath();ctx.arc(x,y,r.id===selected?5:2.3,0,Math.PI*2);
      ctx.fillStyle=r.condition==='semi'?'#438c82aa':r.condition==='oos'?'#a37244aa':'#456eac88';ctx.fill();
      if(r.id===selected){ctx.strokeStyle='#182f29';ctx.lineWidth=2;ctx.stroke();ctx.lineWidth=1;}
      chartHits.push({x,y,id:r.id});}
    $('chart-count').textContent=`${chartHits.length}个可评价点`;
  }
  function select(id){
    if(!ids.has(id))throw new Error('未知 canonical ID');
    if(selected!==id)$('points').value='raw';
    selected=id;const row=data.rows.find(r=>r.id===id);request++;
    if(caseData?.image_id===row.image_id){renderCase();return;}
    $('case-title').textContent='载入 '+row.code+'…';$('case-content').hidden=true;$('empty-case').hidden=false;
    const token=request,script=document.createElement('script');script.src='cases/'+row.image_id+'.js';
    script.onload=()=>{if(token!==request)return;caseData=window.REVIEW_CASE;if(caseData.image_id!==row.image_id)throw new Error('图片资源身份不符');photo.src=caseData.image_src;renderCase();script.remove();};
    script.onerror=()=>{$('save-status').textContent='该图资源加载失败：'+row.image_id;script.remove();};document.head.append(script);
  }
  function annotation(){return caseData?.annotations.find(a=>a.canonical_annotation_id===selected);}
  function currentReference(){const value=$('reference').value;
    return value==='peer'?caseData.annotations.find(a=>a.canonical_annotation_id===$('peer').value):caseData.references.find(r=>r.name===value);
  }
  function renderCase(){
    const a=annotation(),r=data.rows.find(x=>x.id===selected);if(!a||!r)throw new Error('案例身份断裂');
    $('case-content').hidden=false;$('empty-case').hidden=true;
    $('case-title').textContent=`${r.code} · ${r.worker} · ${r.condition.toUpperCase()}`;
    $('case-subtitle').textContent=selected+' · '+r.image_id;
    $('case-state').textContent=r.known_wrong?'既有明确错标':a.views[mode()].status==='ok'?'待人工复核':'表示不可评价';
    $('case-state').classList.toggle('alert',r.known_wrong||a.views[mode()].status!=='ok');
    const previous=$('reference').value;
    $('reference').replaceChildren(...caseData.references.map(x=>option(x.name,labels[x.name]+(x.views[mode()].status==='ok'?'':' · 不可评价'))),option('peer','独立真人同行'));
    $('reference').value=[...$('reference').options].some(x=>x.value===previous)?previous:gt();
    const q=a.queue[mode()],peers=q?.peer_ious||{},oldPeer=$('peer').value;
    $('peer').replaceChildren(option('','选择同行'),...Object.keys(peers).sort((x,y)=>peers[y]-peers[x]).map(cid=>{
      const p=caseData.annotations.find(v=>v.canonical_annotation_id===cid);return option(cid,`${p?.worker_id||cid} · IoU ${n(peers[cid])}`);
    }));
    $('peer').value=oldPeer&&peers[oldPeer]!==undefined?oldPeer:q?.closest_peer_id||'';
    $('verdict').value=decisions[selected]?.verdict||'';$('comment').value=decisions[selected]?.comment||'';
    updateDetails();renderList();$('viewer').scrollIntoView({behavior:'smooth',block:'start'});
  }
  function metric(label,value,unit=''){const box=document.createElement('article');box.className='metric';
    const t=document.createElement('div');t.className='metric-label';t.textContent=label;
    const v=document.createElement('div');v.className='metric-value';v.textContent=value+(unit?' '+unit:'');box.append(t,v);return box;}
  function updateDetails(){
    const a=annotation();if(!a)return;const m=mode(),g=gt(),chosen=currentReference(),q=a.queue[m],qual=a.quality[m][g];
    const refName=$('reference').value,other=chosen?.views[m],own=a.views[m],isGt=refName===g;
    const ownC=own.centroid,refC=other?.centroid;
    const dx=ownC&&refC?ownC.erp_x_px-refC.erp_x_px:null,dy=ownC&&refC?ownC.erp_y_px-refC.erp_y_px:null;
    const iou=refName==='peer'?q?.peer_ious?.[$('peer').value]:q?.reference_ious?.[refName];
    $('metrics').replaceChildren(metric('墙带IoU',n(isGt?qual.iou:iou)),metric('ERP水平质心差',n(isGt?qual.erp_dx_px:dx,2),'px'),
      metric('ERP垂直质心差',n(isGt?qual.dy_px:dy,2),'px'),metric('ERP质心距离',n(isGt?qual.erp_distance_px:dx===null?null:Math.hypot(dx,dy),2),'px'));
    const rank=$('ranking');rank.replaceChildren();
    for(const line of [
      ...a.screening.details,
      `分簇覆盖：${a.screening.cluster_coverage}；${a.screening.clusters.map(c=>c.method+': '+c.size+'/'+c.N).join('；')}`,
      `3D表面可构建：${a.screening.geometry?.surface_valid??'不可计算'}；只按现有配对环，无曼哈顿拟合；真实连接顺序未核实`,
      `joint_distance_rank: ${n(q?.joint_distance_rank)}；仅作辅助`,
      q?`参考可用 ${q.reference_count}/5；独立同行 ${q.peer_count} 份`:'当前作答无法表示，参考与同行比较未计算',
      `最近参考：${labels[q?.closest_reference]||q?.closest_reference||'无'}，IoU ${n(q?.closest_reference_iou)}`,
      `最近同行：${q?.closest_peer_id||'无'}，IoU ${n(q?.closest_peer_iou)}`,
      `当前墙带：${own.status}；所选图层：${other?.status||'无'}`]){const p=document.createElement('p');p.textContent=line;rank.append(p);}
    $('circular').replaceChildren();
    for(const line of [`作答R ${n(ownC?.circular_R)}；所选图层R ${n(refC?.circular_R)}`,
      `相对${labels[g]}的圆周方向差：${n(qual.circular_dx_px,2)} px等效（仅该GT比较）`,
      'R低时方向不稳定；圆周差不能解释为整块区域横移。ERP箭头与圆周方向是两种不同量。']){
      const p=document.createElement('p');p.textContent=line;$('circular').append(p);
    }
    const prior=$('prior'),heading=document.createElement('h3'),note=document.createElement('p'),list=document.createElement('ul');
    heading.textContent='已有审查与同图资料';note.textContent=a.known_wrong?'该作答已有明确错标记录；以下同图文件仍须逐条阅读。':'同图提及仅是资料入口，不等于这份作答已获错误或排除裁决。';
    for(const item of caseData.source_mentions){const li=document.createElement('li'),link=document.createElement('a');
      link.href='../../'+item.path.split('/').map(encodeURIComponent).join('/');link.textContent=item.path;li.append(link,` · ${item.role} · ${item.guard}`);list.append(li);}
    if(a.known_wrong_source){const li=document.createElement('li');li.textContent='当前作答已确认来源：'+a.known_wrong_source;list.prepend(li);}
    if(!list.childNodes.length){const li=document.createElement('li');li.textContent='索引中没有匹配该图的既有审核文件；仍应检查原始导出与图像。';list.append(li);}
    prior.replaceChildren(heading,note,list);
    $('provenance').textContent=JSON.stringify({screening:a.screening,canonical_id:selected,raw_export_path:a.raw_export_path,runtime_task_id:a.runtime_task_id,
      raw_annotation_id:a.raw_annotation_id,processing_status:a.processing_status,imputed_point:a.imputed_point,
      imputation_provenance:a.imputation_provenance,known_wrong:a.known_wrong,known_wrong_source:a.known_wrong_source,
      existing_review_decision:a.review_decision,existing_exclusion_reason:a.exclusion_reason,pairing_status:a.pairing_status,
      pairing_review:a.pairing_review,links_zero_based:a.links_zero_based,raw_points:a.raw_points_1024x512,
      effective_points:a.effective_points_1024x512,pairs_shared_x:a.pairs_shared_x,
      reference_sources:caseData.references.map(x=>({name:x.name,source:x.source,pairing:x.pairing_status,reason:x.reason})),
      same_image_review_source_mentions:caseData.source_mentions,
      source_note:'同图资料仅提示查阅，不等于该作答已有人工错误裁决。'},null,2);
    draw();
  }
  function drawBand(ctx,bands,color){if(!bands)return;ctx.fillStyle=color;for(let x=0;x<bands.length;x++){const b=bands[x];if(b)ctx.fillRect(x*2,b[0]*2,2,(b[1]-b[0]+1)*2);}}
  function drawPoints(ctx,object,color){const kind=$('points').value;if(kind==='none'||!object)return;
    let points=kind==='raw'?object.raw_points_1024x512??object.raw_points:kind==='effective'?object.effective_points_1024x512??object.raw_points:
      (object.pairs_shared_x||[]).flat();if(!Array.isArray(points))return;
    points.forEach(([x,y],i)=>{ctx.beginPath();ctx.arc(x,y,4,0,Math.PI*2);ctx.fillStyle=color;ctx.fill();ctx.strokeStyle='#172d28';ctx.lineWidth=1;ctx.stroke();
      if($('numbers').checked){ctx.font='13px Segoe UI';ctx.lineWidth=3;ctx.strokeStyle='#fff';ctx.strokeText('p'+(i+1),x+6,y-6);ctx.fillStyle=color;ctx.fillText('p'+(i+1),x+6,y-6);}});
  }
  function draw(){const canvas=$('panorama'),ctx=canvas.getContext('2d');canvas.style.width=(1024*Number($('zoom').value))+'px';
    canvas.style.height=(512*Number($('zoom').value))+'px';ctx.clearRect(0,0,1024,512);
    if(photo.complete&&photo.naturalWidth)ctx.drawImage(photo,0,0,1024,512);
    const a=annotation(),ref=currentReference();if(!a)return;
    const av=a.views[mode()],rv=ref?.views[mode()];drawBand(ctx,av.bands,'#ef8e3755');drawBand(ctx,rv?.bands,'#2781ba55');
    const c1=av.centroid,c2=rv?.centroid;
    if(c1&&c2){ctx.beginPath();ctx.moveTo(c2.erp_x_px,c2.erp_y_px);ctx.lineTo(c1.erp_x_px,c1.erp_y_px);ctx.strokeStyle='#f9e22c';ctx.lineWidth=4;ctx.stroke();
      const angle=Math.atan2(c1.erp_y_px-c2.erp_y_px,c1.erp_x_px-c2.erp_x_px);ctx.beginPath();ctx.moveTo(c1.erp_x_px,c1.erp_y_px);
      ctx.lineTo(c1.erp_x_px-12*Math.cos(angle-.45),c1.erp_y_px-12*Math.sin(angle-.45));ctx.moveTo(c1.erp_x_px,c1.erp_y_px);
      ctx.lineTo(c1.erp_x_px-12*Math.cos(angle+.45),c1.erp_y_px-12*Math.sin(angle+.45));ctx.stroke();
      for(const [c,color] of [[c1,'#e57b32'],[c2,'#257db1']]){ctx.beginPath();ctx.arc(c.erp_x_px,c.erp_y_px,7,0,Math.PI*2);ctx.fillStyle=color;ctx.fill();ctx.lineWidth=2;ctx.strokeStyle='#fff';ctx.stroke();}}
    drawPoints(ctx,a,'#e8752b');drawPoints(ctx,ref,'#2174a7');
  }
  function save(){if(!selected)return;const verdict=$('verdict').value,comment=$('comment').value;
    if(verdict||comment.trim())decisions[selected]={verdict:verdict||'pending',comment,code:caseData.code,
      image_id:caseData.image_id,worker_id:annotation().worker_id,condition:annotation().raw_condition,updated_at:new Date().toISOString()};
    else delete decisions[selected];
    try{localStorage.setItem(key,JSON.stringify(decisions));$('save-status').textContent='已保存于此浏览器；请导出JSON备份';}
    catch(e){$('save-status').textContent='浏览器保存失败，请立即导出JSON';}
    renderList();
  }
  function validate(value){if(value.schema!=='consensus_visual_review_decisions_v1'||value.contract_version!==data.manifest.contract_version||
      !value.decisions||typeof value.decisions!=='object'||Array.isArray(value.decisions))throw new Error('版本或结构不匹配');
    for(const [id,v] of Object.entries(value.decisions)){
      const row=data.rows.find(r=>r.id===id);
      if(!row||!verdicts.has(v.verdict)||typeof v.comment!=='string'||v.image_id!==row.image_id||
          v.worker_id!==row.worker||v.condition!==row.condition)throw new Error('存在未知ID或非法裁决');
    }return value.decisions;}
  for(const id of ['mode','gt','condition','category','worker','decision-filter'])$(id).onchange=()=>{page=0;renderList();
    if(id==='gt'&&['gt_original','gt_revised'].includes($('reference').value))$('reference').value=gt();
    if(selected&&caseData)updateDetails();};
  $('search').oninput=()=>{page=0;renderList();};$('prev').onclick=()=>{page--;renderList();};$('next').onclick=()=>{page++;renderList();};
  $('scatter').onclick=e=>{const box=e.currentTarget.getBoundingClientRect(),x=(e.clientX-box.left)*1000/box.width,y=(e.clientY-box.top)*320/box.height;
    let best=null,distance=10*10;for(const hit of chartHits){const d=(x-hit.x)**2+(y-hit.y)**2;if(d<distance){best=hit;distance=d;}}
    if(best)select(best.id);};
  $('reset').onclick=()=>{for(const [id,value] of [['mode','curve'],['gt','gt_revised'],['condition','all'],['category','suspect'],['worker','all'],['decision-filter','all'],['search','']])$(id).value=value;page=0;renderList();if(selected&&caseData)updateDetails();};
  $('reference').onchange=updateDetails;$('peer').onchange=updateDetails;$('points').onchange=draw;$('numbers').onchange=draw;$('zoom').oninput=draw;
  $('verdict').onchange=save;$('comment').oninput=save;
  $('export').onclick=()=>{const payload={schema:'consensus_visual_review_decisions_v1',contract_version:data.manifest.contract_version,
      exported_at:new Date().toISOString(),source:'analysis_results/consensus_visual_review_20260923',decisions};
    const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json'})),link=document.createElement('a');
    link.href=url;link.download='全历史标注_我的审核_20260923.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  $('import').onchange=async e=>{try{const file=e.target.files[0];if(!file)return;const imported=validate(JSON.parse(await file.text()));
    if(Object.keys(decisions).length&&!confirm('用导入文件替换本浏览器已保存的本轮裁决？'))return;
    decisions=imported;localStorage.setItem(key,JSON.stringify(decisions));$('decision-message').textContent='导入成功';
    if(selected&&caseData){$('verdict').value=decisions[selected]?.verdict||'';$('comment').value=decisions[selected]?.comment||'';}renderList();}
    catch(error){$('decision-message').textContent='导入失败，原记录保留：'+error.message;}finally{e.target.value='';}};
  document.querySelectorAll('[data-jump]').forEach(b=>b.onclick=()=>$(b.dataset.jump).scrollIntoView({behavior:'smooth'}));
  window.REVIEW_APP={select,snapshot:()=>({selected,loaded:caseData?.image_id,imageReady:photo.complete&&photo.naturalWidth>0,decisions:Object.keys(decisions).length,visible:filtered().length,mode:mode(),gt:gt()})};
  renderList();$('save-status').textContent='数据已加载；本轮裁决保存在此浏览器';
})();
