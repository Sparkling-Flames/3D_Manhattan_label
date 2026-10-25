/* Explanatory diagrams only: never score, cluster, or fuse in the browser. */
window.MethodDiagrams = (() => {
 'use strict';
 const esc = v => String(v ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const box=(x,y,w,title,lines)=>`<g><rect x="${x}" y="${y}" width="${w}" height="90" rx="12" fill="#f0f7fb" stroke="#54819a"/><text x="${x+16}" y="${y+26}" font-weight="700">${esc(title)}</text>${lines.map((l,i)=>`<text x="${x+16}" y="${y+50+i*21}" font-size="14">${esc(l)}</text>`).join('')}</g>`;
 const arrow=(x,y,x2,y2)=>{
  const angle=Math.atan2(y2-y,x2-x),wing=8,spread=Math.PI/6;
  const ax=x2-wing*Math.cos(angle-spread),ay=y2-wing*Math.sin(angle-spread);
  const bx=x2-wing*Math.cos(angle+spread),by=y2-wing*Math.sin(angle+spread);
  return `<path d="M${x} ${y} L${x2} ${y2} M${ax} ${ay} L${x2} ${y2} L${bx} ${by}" fill="none" stroke="#54819a" stroke-width="2"/>`;
 };
 function quality(){return `<section class="re-panel method-diagram"><h3>质量算法：从测量到联合分数</h3><svg viewBox="0 0 880 570" role="img" aria-label="B8L2计算图：范围与方向用L2组合，高度另外加入，得到Q；D10仅改方向尺度" style="width:100%;height:auto;font-family:system-ui,sans-serif;fill:#193b4e">
 ${box(175,10,530,'输入：作答 A 与绑定参考 G',['先核对图片、条件、参考、版本与质量资格','不可评分保持缺失，不当作零分'])}
 ${arrow(290,100,145,135)}${arrow(440,100,440,135)}${arrow(590,100,735,135)}
 ${box(10,135,270,'范围／底边块 R',['I：底面 IoU；S：底边角距 °','b = S²/32；R = 1 − I + I·b'])}
 ${box(305,135,270,'自身方向块 U',['d：方向残差 °；a：8°或10°','u = 1.5d²/(d²+a²)；U = I·u'])}
 ${box(600,135,270,'整体／局部高度块',['g = (Hmean/0.8)²','h = (Hcenter/0.25)²'])}
 ${arrow(145,225,285,285)}${arrow(440,225,285,285)}${arrow(735,225,735,285)}
 ${box(35,285,500,'两块 L2：L = √(R² + U²)',['并非五个分项的加权平均','分项不能画成可相加的扣分百分比'])}
 ${box(590,285,280,'高度损失另外相加',['I·(g + h)','不把 Hcenter 改成顶点方差'])}
 ${arrow(285,375,440,425)}${arrow(735,375,440,425)}
 ${box(120,425,640,'输出：Qₐ = 100 I / [I + L + I·(g+h)]',['B8L2 = Q₈；D10 = Q₁₀；有效输入 I=0 时 Q=0','0–100 工作指数，不是正确概率；D10不改变作答几何'])}</svg>
 <p>图中箭头表示公式依赖，不是独立因果贡献。Hmean、Hcenter沿用冻结引擎的高度测量。范围接近、自身正交和必要局部结构正确不是同一件事。</p>
 <div class="re-actions"><a class="chip" href="#release=v2&amp;module=method_supplements&amp;tab=2">查看 B8L2 / 3D IoU 的25对真实对照与控制实验</a></div></section>`;}
 function fusion(){
 const stages=[
 ['1 · 原答与团队','同图同条件的真实成员；保留上下点对和来源环序','个人点号不是跨人员角点身份'],
 ['2 · 算法身份对应','沿冻结对应规则（gap=7.5），形成身份组','新增成员可能改变分组；不根据GT选组'],
 ['3 · 不同人员计票 → 全队 MV50','支持按不同人员计；偶数人数的一半票也达门槛','全队人数是门槛分母，不是某组点数'],
 ['4 · 达票身份 → 等人坐标中位数','位置聚合与结构是否保留分别记录','同一人重复点不增加人员权重'],
 ['5 · 来源环序投影 → 连接候选 → 选择','原邻接与删点后投影邻接分开；不按GT补矩形','完整输出再独立评价Q、几何与时间']];
 return `<section class="re-panel method-diagram"><h3>融合算法：多份原答怎样形成完整布局？</h3><svg viewBox="0 0 880 760" role="img" aria-label="融合流程：原答、身份对应、人员支持票、MV50、等人位置中位数、源环序连接，输出完整布局或失败" style="width:100%;height:auto;font-family:system-ui,sans-serif;fill:#193b4e">
 ${stages.map((s,i)=>box(130,10+i*125,620,s[0],s.slice(1))+(i<4?arrow(440,100+i*125,440,135+i*125):'')).join('')}
 ${arrow(330,600,220,655)}${arrow(550,600,660,655)}
 ${box(20,655,400,'输出 A · 有效完整布局',['仍可能不接近参考','稳定 ≠ 高质量；节点多 ≠ 正确'])}
 ${box(460,655,400,'输出 B · 不足节点／无法连接等',['保留失败原因、尝试分母与诊断点','不补假布局，不把缺失Q改成0'])}</svg>
 <p>参考仅用于结果评价，不指导对应、投票或连接。人数增加既可能升高支持门槛，也可能改变身份组；两者要从实际票账区分。</p><div class="re-actions"><a class="chip" href="#release=v2&amp;module=personnel_main&amp;tab=5">看 B6-47 补票与 jh-12 人数阈值案例</a><a class="chip" href="#release=v2&amp;module=method_supplements&amp;tab=1">看同队三种融合方法对照</a></div></section>`;
 }
 function comparison(pair){
  const rows=[['B8L2','B8L2'],['D10','D10'],['IoU3D100','均高棱柱 IoU ×100']];
  const bar=(v,side)=>{
   const n=typeof v==='number'?v:typeof v==='string'&&v.trim()!==''?Number(v):NaN;
   if(!Number.isFinite(n)||n<0||n>100)return `<span>${side}：未保存／不在0–100量程</span>`;
   return `<div class="metric-bar-row"><span>${side}</span><span class="metric-bar-track"><span class="metric-bar-fill ${side==='左'?'left':'right'}" style="width:${n}%"></span></span><strong>${n.toFixed(2)}</strong></div>`;
  };
  return `<figure class="metric-pair-chart"><figcaption>同一对作答的排序对照 · ${esc(pair.review_id)}</figcaption><p>各行固定0–100量程；只在同一指标内比较左右，不把不同指标的分差当作等价。条形读取保存值，不重新评分。</p>${rows.map(([key,label])=>`<section><h4>${label}</h4>${bar(pair['left_'+key],'左')}${bar(pair['right_'+key],'右')}</section>`).join('')}<p>人工判断：${esc(({left:'左侧较好',right:'右侧较好',close:'两者接近',uncertain:'无法判断'})[pair.human_choice]||pair.human_choice||'未记录')}。均高棱柱IoU是本研究的冻结代理，不代表所有3D IoU实现。</p></figure>`;
 }
 return {quality,fusion,comparison};
})();
