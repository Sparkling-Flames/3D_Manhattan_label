"use strict";
(() => {
  const D = window.MANUAL_ORDER_DATA;
  const $ = id => document.getElementById(id);
  const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const num = (v, places=4) => typeof v === "number" && Number.isFinite(v) ? v.toFixed(places) : "未评分";
  const yes = v => v === true ? "是" : v === false ? "否" : "未确定";
  const colors = {ring:"#eeca58",reference:"#49a5e7",source:"#e384bc"};
  const modules = {ac_registered:"AC 登记事件",changed_alliances:"纯类 / 完整联盟",composition_other:"其它目标有限配比",current_half:"当前半队 ABC",current_same_room_half:"当前同房半队",legacy_role_policy:"旧角色进入策略",natural_ordinary_manual_extra_target:"其它目标人数曲线",q_only:"Q-only 政策对照",same_room_large_registered:"同房原登记实验"};
  let filtered = [...D.endpoints], current = filtered[0];
  const opt = (v,t) => `<option value="${esc(v)}">${esc(t)}</option>`;
  const refsBase = "../../fusion/manual_order_impact_20261104/";
  $("imageFilter").innerHTML += [...new Set(D.endpoints.map(e=>e.image))].sort().map(x=>opt(x,x)).join("");
  $("moduleFilter").innerHTML += Object.entries(modules).map(([k,v])=>opt(k,v)).join("");
  function applyFilters(keep=true) {
    const image=$("imageFilter").value, module=$("moduleFilter").value, status=$("statusFilter").value;
    const query=$("searchFilter").value.trim().toLowerCase();
    filtered=D.endpoints.filter(e=>(!image||e.image===image)&&(!module||e.modules.includes(module))&&(!status||(status==="scored")===Number.isFinite(e.assisted.B8L2))&&(!query||[e.image,e.team_key,e.group_id,e.review_id,...e.member_workers].join(" ").toLowerCase().includes(query)));
    const previous=keep&&current?current.team_key:null;
    $("endpointSelect").innerHTML=filtered.map(e=>opt(e.team_key,`${e.image} · ${e.group_id} · ${e.k}人 / ${e.nodes.length}节点 · ${Number.isFinite(e.assisted.B8L2)?"Q "+num(e.assisted.B8L2,2):"固定坐标未可评"}`)).join("");
    $("resultCount").textContent=`${filtered.length} / 57 组`;
    $("detail").hidden=!filtered.length;$("emptyState").hidden=!!filtered.length;
    if(!filtered.length)return;
    current=filtered.find(e=>e.team_key===previous)||filtered[0];$("endpointSelect").value=current.team_key;render();
  }
  function state(){const mode=$("viewMode").value;return {mode,score:mode==="automatic"?current.automatic:mode==="candidate"?current.candidate.score:current.assisted,nodes:mode==="candidate"?current.candidate.nodes:current.nodes,audit:mode==="candidate"?current.candidate.audit:current.audit};}
  function line(points,color,width=2,close=true,dash="") {
    if(!points||points.length<2)return "";
    const ps=close?[...points,points[0]]:points;
    return `<polyline points="${ps.map(p=>p.join(",")).join(" ")}" fill="none" stroke="${color}" stroke-width="${width}" ${dash?`stroke-dasharray="${dash}"`:""} vector-effect="non-scaling-stroke"/>`;
  }
  function erpLines(points,color,width=2,dash="") {
    if(!points||points.length<4)return "";
    let result="";
    for(let parity=0;parity<2;parity++){
      const ps=points.filter((_,i)=>i%2===parity);
      for(let i=0;i<ps.length;i++){
        let [x1,y1]=ps[i], [x2,y2]=ps[(i+1)%ps.length];
        if(x2-x1>512)x2-=1024; if(x1-x2>512)x2+=1024;
        for(const offset of [-1024,0,1024])result+=line([[x1+offset,y1],[x2+offset,y2]],color,width,false,dash);
      }
    }
    return result;
  }
  function renderERP(){
    const {mode,nodes}=state(), lookup=Object.fromEntries(nodes.map(n=>[n.feature_id,n]));
    let svg="";
    if($("showReference").checked)svg+=erpLines(current.reference.points_1024x512,colors.reference,1.5,"5 4");
    const source=current.source_records.find(s=>s.id===$("sourceRecord").value);
    if(source)svg+=erpLines(source.points,colors.source,1.4,"3 3");
    if(mode!=="automatic")svg+=erpLines(current.manual_feature_order.flatMap(id=>lookup[id].points),colors.ring,2.4);
    for(let i=0;i<nodes.length;i++){
      const node=nodes[i], [top,bottom]=node.points;
      svg+=line([top,bottom],colors.ring,1.4,false);
      for(const p of node.points)svg+=`<circle cx="${p[0]}" cy="${p[1]}" r="3.8" fill="${colors.ring}" stroke="#25312a" stroke-width="1.1"/>`;
      if($("showLabels").checked)svg+=`<text x="${top[0]+5}" y="${top[1]-7}" fill="#fff7d2" font-size="15" font-family="sans-serif" font-weight="bold" stroke="#1b2923" stroke-width="3.4" paint-order="stroke">F${i+1}</text>`;
    }
    $("erpOverlay").innerHTML=svg;
    $("sourceInfo").textContent=source?`${source.worker} · ${source.id} · 预处理后的源点位 · 来源时间 ${source.source_time_seconds??"未知"} 秒 · ${source.time_source_kind??"时间来源未记录"}`:"粉色用于选中的源标注；源点位保持冻结数据中的预处理结果。";
  }
  function renderFloor(){
    const {mode,audit,nodes}=state(),floor=audit.floor||[],ref=current.reference.floor_xz_h||[];
    const all=[...floor,...($("showReference").checked?ref:[]),[0,0]];
    if(!all.length){$("floorPlot").innerHTML="";return;}
    const xs=all.map(p=>p[0]),ys=all.map(p=>p[1]),minX=Math.min(...xs),maxX=Math.max(...xs),minY=Math.min(...ys),maxY=Math.max(...ys);
    const scale=Math.min(330/Math.max(maxX-minX,.01),290/Math.max(maxY-minY,.01));
    const project=p=>[210+(p[0]-(minX+maxX)/2)*scale,190-(p[1]-(minY+maxY)/2)*scale];
    let svg="";
    const origin=project([0,0]);
    svg+=`<path d="M 20 ${origin[1]} H 400 M ${origin[0]} 20 V 360" stroke="#dce5d6" stroke-width="1"/>`;
    if($("showReference").checked&&ref.length)svg+=line(ref.map(project),colors.reference,2,true,"5 4");
    if(mode!=="automatic"&&floor.length){const ps=floor.map(project);svg+=`<polygon points="${ps.map(p=>p.join(",")).join(" ")}" fill="${audit.polygon_valid?"#dcef9640":"#ffe3c45c"}"/>`;svg+=line(ps,audit.polygon_valid?"#23614c":"#ae5728",2.4);}
    for(let i=0;i<floor.length;i++){
      const p=project(floor[i]),id=current.manual_feature_order[i],index=nodes.findIndex(n=>n.feature_id===id);
      svg+=`<circle cx="${p[0]}" cy="${p[1]}" r="3.5" fill="#23614c"/><text x="${p[0]+6}" y="${p[1]-5}" font-size="12" fill="#29463a">F${index+1}</text>`;
    }
    svg+=`<circle cx="${origin[0]}" cy="${origin[1]}" r="5" fill="#a44b25" stroke="white" stroke-width="2"/><text x="${origin[0]+8}" y="${origin[1]+17}" font-size="12" fill="#8a4628">相机</text>`;
    const length=1*scale;
    if(length<180)svg+=`<path d="M 25 350 h ${length}" stroke="#476348" stroke-width="2"/><text x="25" y="341" font-size="11" fill="#5f7170">1 h</text>`;
    $("floorPlot").innerHTML=svg;
    const facts=mode==="automatic"?[["自动连接","未形成"],["点位显示","仅固定节点，无自动底面"],["评分状态","no_connection"]]:[["多边形有效",yes(audit.polygon_valid)],["非相邻边交叉",(audit.nonadjacent_intersections||[]).length],["相机在可见核内",yes(audit.camera_in_visible_kernel)],["完整评分状态",state().score.score_status],["保留的几何诊断",(audit.issues||[]).join(" / ")||"无"]];
    $("geometryFacts").innerHTML=facts.map(([k,v])=>`<div><span>${esc(k)}</span><b>${esc(v)}</b></div>`).join("");
  }
  function render(){
    const candidateOption=$("viewMode").querySelector('[value="candidate"]');candidateOption.disabled=!current.candidate;
    if(!current.candidate&&$("viewMode").value==="candidate")$("viewMode").value="assisted";
    const {mode,score,nodes}=state();
    const isCandidate=mode==="candidate",isAuto=mode==="automatic";
    $("versionBadge").textContent=isCandidate?"单独候选 · 未并入主 57 组":isAuto?"冻结自动分支":"人工顺序 · 冻结坐标";
    $("versionBadge").classList.toggle("warn",isCandidate);
    $("branchNote").textContent=isCandidate?"F2 与 F9 的上下点 x 均设为 438.8037，y、节点身份、票数与顺序不变。自交消除，完整评分可计算；相机仍不在可见核内。此分支增加了人工坐标干预，不能写成仅排序修复。":isAuto?"原自动方法未得到覆盖全部已选节点的来源环，Q 缺失。此处保留原状态与点位；没有可与新 Q 相减的旧 Q。":score.complete_evaluable?"该端点新增可评，Q 属于人工辅助分支。原自动 Q 缺失；不存在“从 0 提高”的配对差。": "人工顺序已接入，但固定坐标的底面仍自交，Q 保持缺失。可切换查看用户提出的独立坐标修正候选。";
    $("branchNote").classList.toggle("warn",isCandidate||(!isAuto&&!score.complete_evaluable));
    $("scoreCards").innerHTML=[["B8L2",score.B8L2,"当前冻结主 Q"],["D10",score.D10,"原有敏感性分数"],["IoU3D × 100",score.IoU3D100,"几何重叠"],["节点数",nodes.length,`${current.k} 人 · 身份固定`]].map(([k,v,sub])=>`<div><span>${esc(k)}</span><strong>${k==="节点数"?v:num(v,3)}</strong><small>${esc(sub)}</small></div>`).join("");
    const imageSrc="v21-manual-order/original_images/"+current.image_id+".png";
    if($("erpImage").getAttribute("src")!==imageSrc)$("erpImage").src=imageSrc;
    $("erpImage").alt=current.image+" 的 GitHub Release 原图";
    const previousSource=$("sourceRecord").value;
    $("sourceRecord").innerHTML=opt("","不叠加")+current.source_records.map(s=>opt(s.id,`${s.worker} · ${s.id}`)).join("");
    if(current.source_records.some(s=>s.id===previousSource))$("sourceRecord").value=previousSource;
    $("identity").innerHTML=`<div><b>团队</b><code>${esc(current.team_key)}</code></div><div><b>成员</b>${esc(current.member_workers.join(" · "))}</div><div><b>参考</b><code>${esc(current.reference_id)}</code> · ${esc(current.reference_version)}</div><div><b>人工记录</b>${esc(current.group_id)} / ${esc(current.review_id)}</div><div><b>引用模块</b>${current.modules.map(m=>esc(modules[m]||m)).join(" · ")}</div>`;
    const label=id=>"F"+(nodes.findIndex(n=>n.feature_id===id)+1);
    $("nodeOrder").textContent="已确认顺序："+current.manual_feature_order.map(label).join(" → ")+" → "+label(current.manual_feature_order[0]);
    $("nodeRows").innerHTML=nodes.map((n,i)=>`<tr><td>F${i+1}</td><td>${esc(n.feature_id)}</td><td>${n.points[0].map(v=>num(v,6)).join(", ")}</td><td>${n.points[1].map(v=>num(v,6)).join(", ")}</td><td>${n.support} / ${current.k}</td><td>${esc(n.members.map(m=>`${m.worker} [pair ${m.pair_index}]`).join(" · "))}</td></tr>`).join("");
    const metrics=[["S_bottom_deg","底边定位误差，度，越低越好"],["dir","方向误差，度，越低越好"],["Hmean","平均高度相对误差，越低越好"],["Hcenter","中心高度误差，越低越好"],["omission","遗漏分项，越低越好"],["extension","外扩分项，越低越好"],["boundary_loss","边界损失"],["direction_loss","方向损失"],["global_height_loss","全局高度损失"],["local_height_loss","局部高度损失"],["floor_area_camera_h2","底面面积，相机高度平方"],["height_mean_h","平均高度，相机高度单位"],["floor_turn5_n","5° 底面转折数，结构量"],["floor_short_edge_03_n","小于 0.3 h 的边数，结构量"],["diag_wall_coverage_03","0.3 h 墙覆盖诊断"],["diag_corner_recall_05","0.5 h 角点召回诊断"]];
    $("metricRows").innerHTML=metrics.map(([k,label])=>`<tr><td><code>${k}</code></td><td>${num(score[k],6)}</td><td>${esc(label)}</td></tr>`).join("");
    $("referenceCount").textContent=`（${current.references.length} 条）`;
    $("referenceRows").innerHTML=current.references.map(r=>`<tr><td>${esc(modules[r.module]||r.module)}</td><td>${esc(r.event_id||r.replicate_id||r.panel_id||"—")}</td><td>${esc(r.arm)}</td><td><a href="../../../${esc(r.source)}">${esc(r.source.split("/").slice(-2).join("/"))}</a> · 源行 ${esc(r.source_row)}</td></tr>`).join("");
    renderERP();renderFloor();
  }
  function conclusions(){const filter=$("conclusionFilter").value;const rows=D.conclusions.filter(r=>!filter||r.status===filter);$("conclusionRows").innerHTML=rows.map(r=>`<tr><td>${esc(r.topic)}</td><td><span class="tag ${r.status==="需改写"||r.status==="尚不能判断"?"warn":""}">${esc(r.status)}</span></td><td>${esc(r.finding)}</td><td>${(r.sources||"").split("|").filter(Boolean).map(s=>`<a href="${refsBase+esc(s)}">${esc(s)}</a>`).join("<br>")}</td></tr>`).join("")||'<tr><td colspan="4">该筛选条件暂无结论。</td></tr>';}
  for(const id of ["imageFilter","moduleFilter","statusFilter"])$(id).addEventListener("change",()=>applyFilters());
  $("searchFilter").addEventListener("input",()=>applyFilters());
  $("endpointSelect").addEventListener("change",()=>{current=filtered.find(e=>e.team_key===$("endpointSelect").value);render();});
  $("viewMode").addEventListener("change",render);
  $("showReference").addEventListener("change",()=>{renderERP();renderFloor();});
  $("showLabels").addEventListener("change",renderERP);$("sourceRecord").addEventListener("change",renderERP);
  $("openCandidate").addEventListener("click",()=>{for(const id of ["imageFilter","moduleFilter","statusFilter","searchFilter"])$(id).value="";current=D.endpoints.find(e=>e.candidate);applyFilters();$("viewMode").value="candidate";render();$("endpoint").scrollIntoView({behavior:"smooth"});});
  $("conclusionFilter").addEventListener("change",conclusions);
  $("exportCsv").addEventListener("click",()=>{const cols=["team_key","image","group_id","k","automatic_B8L2","assisted_B8L2","assisted_D10","score_status","support_change","human_order_seconds"];const rows=filtered.map(e=>[e.team_key,e.image,e.group_id,e.k,e.automatic.B8L2,e.assisted.B8L2,e.assisted.D10,e.assisted.score_status,Number.isFinite(e.assisted.B8L2)?"newly_evaluable":"still_unscored",null]);const quote=v=>'"'+String(v??"").replace(/"/g,'""')+'"';const csv="\ufeff"+[cols,...rows].map(row=>row.map(quote).join(",")).join("\r\n");const link=document.createElement("a"),url=URL.createObjectURL(new Blob([csv],{type:"text/csv;charset=utf-8"}));link.href=url;link.download="HOHONET_manual_order_fixed_coordinates.csv";link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
  $("moduleRows").innerHTML=D.modules.map(r=>`<tr><td>${esc(modules[r.module]||r.module)}</td>${["endpoint_identities","source_rows","references","images","image_pairs","buildings"].map(k=>`<td>${esc(r[k])}</td>`).join("")}</tr>`).join("");
  applyFilters();conclusions();
})();
