/* Result-first adapter. Reuses Studio's cameras, textures and unchanged geometry. */
(() => {
  'use strict';
  const byId = id => document.getElementById(id);
  const node = (tag, attrs = {}, text = '') => {
    const e = document.createElementNS('http://www.w3.org/2000/svg', tag);
    Object.entries(attrs).forEach(([k,v]) => e.setAttribute(k,v)); e.textContent=text; return e;
  };
  document.title='融合结果工作台';
  document.querySelector('h1').textContent='融合结果工作台';
  document.querySelector('.brand .eyebrow').textContent='CONSENSUS / RESULT VIEW';
  document.querySelector('.source-label').hidden=true;
  document.querySelector('.workspace').classList.add('result-workspace');
  byId('compare-grid').classList.add('only-raw');
  byId('decor').checked=false;
  const sidebar=document.createElement('aside'); sidebar.className='pattern-sidebar';
  sidebar.innerHTML='<h3>这张图有哪些标法？</h3><p id="pattern-summary"></p><div id="pattern-list"></div><p class="subtle">小图显示每类的代表标注。点击后，大图显示这类人员融合后的结果。</p>';
  document.querySelector('.workspace').prepend(sidebar);
  const hero=document.createElement('section'); hero.className='result-hero';
  hero.innerHTML=`<div class="method-tabs" role="group" aria-label="融合方法">
    <button data-result-method="point" aria-pressed="true">点对融合 <small>上、下角点</small></button>
    <button data-result-method="erp" aria-pressed="false">全景区域投票 <small>上、下轮廓</small></button>
    <button data-result-method="lee" aria-pressed="false">Lee 底面投票 <small>只有底边</small></button></div>
    <div class="result-heading"><div><span class="eyebrow">融合之后</span><h2 id="result-title"></h2></div><span id="result-count" class="count-badge"></span></div>
    <div class="result-options"><label id="compact-pattern-control">标法 <select id="compact-pattern"></select></label><label id="scope-control">参与范围 <select id="result-scope"><option value="cluster">当前这类标法</option><option value="all">全部人员</option></select></label>
    <label id="rule-control">投票规则 <select id="result-rule"><option value="mv50">至少一半（≥50%）</option><option value="mv_strict">超过一半（>50%）</option></select></label>
    <label><input type="checkbox" id="result-gt">对照 GT</label><label><input type="checkbox" id="result-before">对照该类代表标注</label>
    <button id="result-expand">放大查看</button></div>
    <div class="result-panoramas"><figure id="before-panel" hidden><figcaption>融合前 · 该类代表标注</figcaption><svg id="before-pano" viewBox="0 0 1024 512" role="img" aria-label="该类标法的代表标注"></svg></figure>
    <figure id="result-panel"><figcaption id="result-caption">融合后</figcaption><svg id="result-pano" viewBox="0 0 1024 512" role="img" aria-label="融合后的全景标注"></svg><p id="result-unavailable" hidden role="status"></p></figure></div>
    <div class="result-legend"><span class="top-key">黄色：顶部</span><span class="bottom-key">青色：底部</span><span class="pair-key">白线：上下点对</span><span id="gt-legend" hidden>粉色虚线：GT</span></div>
    <p id="result-explanation" role="status"></p>
    <details class="method-notes"><summary>方法与当前限制</summary><p id="method-detail"></p><p>四个案例用于查看结果，不是整体效果估计。分组使用未校准的 5° 阈值，不同点数先分开；所有组均保留，组号不代表好坏。新融合环序尚未人工确认。</p><a href="../lee_consensus_demos_20261003/index.html">查看人数曲线、逐人标注与计算详情 →</a></details>`;
  document.querySelector('.visuals').prepend(hero);
  const threeHeading=document.createElement('div'); threeHeading.className='three-heading';
  threeHeading.innerHTML='<h3>同一份融合结果 · 3D 预览</h3><p>拖动旋转，滚轮缩放；可切换俯视或真实纹理。水平地面与配对底点距离用于折叠，墙顶不是实测深度。</p><p id="three-diagnostics" hidden></p>';
  document.querySelector('.toolbar').before(threeHeading);
  document.querySelector('.canvas-hint').firstChild.textContent='拖动旋转 · 滚轮缩放 · 右键平移　';
  const threeUnavailable=document.createElement('p');threeUnavailable.id='three-unavailable';threeUnavailable.hidden=true;
  threeHeading.after(threeUnavailable);
  document.querySelector('footer').innerHTML='研究展示 · 不写回原标注 <span>预处理坐标与既定环保持不变</span><span id="bundle-stats"></span>';
  let method='point';
  function path(svg, paths, color, dashed=false) {
    for(const d of paths||[]) {
      svg.append(node('path',{d,fill:'none',stroke:'#06151e','stroke-width':4.5,opacity:.8,'stroke-linejoin':'round'}));
      svg.append(node('path',{d,fill:'none',stroke:color,'stroke-width':2.3,'stroke-dasharray':dashed?'7 5':'none','stroke-linejoin':'round'}));
    }
  }
  function layout(svg,erp,labels=true) {
    if(!erp)return;
    path(svg,erp.vertical_paths,'#f5faff');path(svg,erp.top_paths,'#ffdb60');path(svg,erp.bottom_paths,'#34ffe0');
    (erp.points||[]).forEach((p,i)=>{
      svg.append(node('circle',{cx:p[0],cy:p[1],r:3.8,fill:i%2?'#34ffe0':'#ffdb60',stroke:'#09232a','stroke-width':1.3}));
      if(labels)svg.append(node('text',{x:p[0]+6,y:p[1]-7,fill:i%2?'#34ffe0':'#ffdb60',stroke:'#062028','stroke-width':3,'paint-order':'stroke','font-size':14},String(Math.floor(i/2)+1)));
    });
  }
  function base(svg,d) {svg.replaceChildren(node('image',{href:d.photo,width:1024,height:512,preserveAspectRatio:'none'}));}
  function cards() {
    const c=dataset.cases[currentCase]; const list=byId('pattern-list');list.replaceChildren();byId('compact-pattern').replaceChildren();
    byId('pattern-summary').textContent=`${c.demo.n} 人的作答，暂分为 ${c.variants.length} 类。`;
    c.variants.forEach((v,i)=>{
      const g=v.source.cluster,b=document.createElement('button');b.className='pattern-choice';b.setAttribute('aria-pressed',String(i===currentVariant));
      byId('compact-pattern').add(new Option(`标法 ${i+1} · ${g.support} 人 · ${g.pair_count} 点对`,String(i)));
      const title=document.createElement('strong');title.textContent=`标法 ${i+1} · ${g.support} 人`;b.append(title);
      const svg=node('svg',{viewBox:'0 0 1024 512','aria-hidden':'true'});base(svg,c.demo);layout(svg,v.source.representative.erp,false);b.append(svg);
      const small=document.createElement('small');small.textContent=`${g.pair_count} 对角点${g.support===1?' · 单人，尚无多人融合':''}`;b.append(small);
      b.onclick=()=>{byId('variant-select').value=i;chooseVariant(i,false);};list.append(b);
    });
  }
  function drawResult() {
    const c=dataset.cases[currentCase],d=c.demo,v=c.variants[currentVariant],g=v.source.cluster;
    const all=method==='lee'||(method==='erp'&&byId('result-scope').value==='all'),rule=byId('result-rule').value;
    const svg=byId('result-pano');base(svg,d);base(byId('before-pano'),d);layout(byId('before-pano'),v.source.representative.erp);
    byId('compact-pattern').value=currentVariant;
    byId('scope-control').hidden=method!=='erp';byId('rule-control').hidden=method==='point';byId('compact-pattern-control').hidden=all;
    byId('result-before').disabled=all;byId('before-panel').hidden=all||!byId('result-before').checked;
    byId('result-count').textContent=`${all?d.n:g.support} 人参与${all?' · 全员':` · 标法 ${currentVariant+1}`}`;
    byId('result-unavailable').hidden=true;byId('gt-legend').hidden=!byId('result-gt').checked;
    document.querySelector('.top-key').hidden=method==='lee';document.querySelector('.pair-key').hidden=method!=='point';
    const gt=d.erp_references.original;
    if(byId('result-gt').checked&&gt)path(svg,method==='lee'?gt.bottom_paths:[...gt.top_paths,...gt.bottom_paths,...gt.vertical_paths],'#ff83e5',true);
    let title,explanation,detail;
    if(method==='point') {
      title=`标法 ${currentVariant+1} 的融合标注`;
      layout(svg,v.source.candidate_erp);
      explanation=g.support===1?'这一类目前只有 1 人：图中保留其标注，不能据此判断多人融合效果。':`${g.support} 人的对应点对合成为 ${g.pair_count} 对角点；上、下同号是一对。不同标法各自保留结果，目前是环序待核验的研究候选。`;
      detail='先对齐同类整环，再分别取周期 x、top_y、bottom_y 的中位数。每类产生自己的完整点候选；目前没有把不同标法硬合成一个唯一结果。';
      if(!v.source.candidate_erp){byId('result-unavailable').hidden=false;byId('result-unavailable').textContent='当前候选无法显示完整上下边界。';}
    } else if(method==='erp') {
      title=(all?'全员':'当前标法')+'的区域融合结果';
      const r=d.erp_region_cache[all?d.step.all_erp_region_key:g.erp_region_key];
      if(r.status==='ok') {const m=r.methods[rule];path(svg,[m.top_path],'#ffdb60');path(svg,[m.bottom_path],'#34ffe0');
        explanation=`${r.n} 人直接在全景墙带上投票，得到黄色顶部与青色底部轮廓。目前没有从轮廓恢复稀疏角点。`;
      } else {byId('result-unavailable').hidden=false;byId('result-unavailable').textContent='这一组尚不能生成完整区域融合结果';
        explanation=`${r.unsupported.length} 份作答不满足此方法的墙带表示条件；整组保留为不可用，没有删人后继续融合。`;
      }
      detail='在全景图每一列比较上下边界，以区域多数产生稠密上下轮廓。它与 Lee-BEV 底面投票使用不同表示；采样列仅描述轮廓，真实墙角仍待提取。';
    } else {
      title='全员 Lee 投票后的底边';
      const rings=d.step.erp_regions[rule];for(const r of rings)path(svg,r.paths,'#34ffe0',r.hole);
      explanation=rings.length?`${d.n} 人的底面区域投票后回投到全景图。青线是融合底边；这一路还没有 top_y，不能显示完整房间。`:'当前规则得到空区域：没有可显示的融合底边。';
      detail='在声明 BEV 底面上切 tile 后等权投票，所有分量与孔洞原样保留。这里没有借用某个人的上边补成完整结果。';
    }
    byId('result-title').textContent=title;byId('result-caption').textContent=title;
    byId('result-explanation').textContent=explanation;byId('method-detail').textContent=detail;
    const has3D=method==='point'&&!!v.geometry;
    byId('three-diagnostics').hidden=!has3D||!v.geometry.raw.issues.length;
    byId('three-diagnostics').textContent=byId('issues').textContent;
    for(const e of [document.querySelector('.toolbar'),byId('compare-grid'),document.querySelector('.canvas-hint')]) e.hidden=!has3D;
    byId('three-unavailable').hidden=has3D;
    byId('three-unavailable').textContent=method==='erp'?'这一路当前只提供上下轮廓，3D 预览尚未接入。':method==='lee'?'只有底面，尚不能折叠成完整墙顶。切换“点对融合”可查看上下角点的 3D。':'当前候选的三维表示不可用。';
    byId('raw-title').textContent='融合后的点对候选';
    byId('raw-caption').textContent='相机高度为 1 · 保留候选环序 · 墙顶为代理重建';
    document.querySelectorAll('[data-result-method]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.resultMethod===method)));
    document.querySelectorAll('.pattern-choice').forEach((b,i)=>b.setAttribute('aria-pressed',String(i===currentVariant)));
    requestAnimationFrame(()=>{views.forEach(resize);renderAll();});
  }
  const originalChoose=chooseVariant;
  chooseVariant=function(index,resetView=false){originalChoose(index,resetView);drawResult();};
  document.addEventListener('studio-case',()=>{cards();drawResult();});
  document.querySelectorAll('[data-result-method]').forEach(b=>b.onclick=()=>{
    method=b.dataset.resultMethod;if(method==='erp')byId('result-scope').value='all';drawResult();
  });
  for(const id of ['result-scope','result-rule','result-gt','result-before'])byId(id).onchange=drawResult;
  byId('compact-pattern').onchange=e=>{const i=Number(e.target.value);byId('variant-select').value=i;chooseVariant(i,false);};
  const expandLabel=()=>{byId('result-expand').textContent=document.fullscreenElement||hero.classList.contains('large-result')?'退出放大':'放大查看';};
  document.addEventListener('fullscreenchange',expandLabel);
  byId('result-expand').onclick=async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await hero.requestFullscreen();}catch{hero.classList.toggle('large-result');}expandLabel();};
  cards();drawResult();
})();
