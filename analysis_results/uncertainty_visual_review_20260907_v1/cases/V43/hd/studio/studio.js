/* Independent studio renderer. Source geometry is immutable; all cuts are visibility only. */
"use strict";
const $ = id => document.getElementById(id);
const dataset = window.STUDIO_DATA;
const reasonText = {
  near_horizon:"端点接近地平线，深度不稳定", wrong_hemisphere:"上下端点与水平地面假设不相容",
  duplicate_or_zero_edge:"重复端点或零长度墙边", invalid_footprint:"输入点序形成自交或退化轮廓",
  camera_visibility_unresolved:"相机位置或墙面遮挡关系尚未解决", pole_ray:"极点射线无法确定水平距离",
  vertical_pair_mismatch:"上下端点横坐标不同；原始视图保留各自射线",
  preview_order_changed_fit_not_recomputed:"预览顺序已调整；浏览器未重跑约束拟合",
  preview_order_changed_geometry_not_revalidated:"预览顺序副本未重跑几何有效性检查",
  preview_order_semantics_unconfirmed:"当前轮廓仅做显示有效性检查，排列语义仍需人工确认",
  preview_ceiling_invalid:"当前天花板代理轮廓自交或退化",
  preview_coordinates_unavailable:"部分代理坐标缺失或非有限，不能组成完整表面",
  ambiguous_axis_assignment:"部分墙面主方向归属含混", optimizer_failed:"约束优化未可靠完成"
};
let currentCase=0, currentVariant=0, geometry=null, originalImage=null, imageToken=0;
let sourceGeometry=null, previewOrder=[], orderHistory=[];
let materialMode="clay", selected=null, endpoint="top", viewMode="iso", syncing=false;
let center=new THREE.Vector3(), radius=4, roomSize=new THREE.Vector3(6,3,6), texture=null;
let orthoHeight=8, clippingHeight=0;
const clipPlane=new THREE.Plane(new THREE.Vector3(0,-1,0),0);
let framingPoints=[];
const views=[];
const fmt=(v,n=2)=>Number.isFinite(v)?Number(v).toFixed(n):"—";
const reasons=items=>(items||[]).map(x=>reasonText[x]||x).join("；");
const vec=p=>new THREE.Vector3(...p);
const clone=value=>JSON.parse(JSON.stringify(value));

function parsePermutation(text,n){
  const values=String(text).trim().split(/[\s,;]+/).filter(Boolean).map(Number);
  if(values.some(v=>!Number.isInteger(v))||values.length!==n)throw new Error(`排列必须恰好包含 ${n} 个整数`);
  const zero=[...Array(n).keys()],one=zero.map(v=>v+1),sorted=[...values].sort((a,b)=>a-b);
  if(sorted.every((v,i)=>v===one[i]))return values.map(v=>v-1);
  if(sorted.every((v,i)=>v===zero[i]))return values;
  throw new Error(`排列必须完整且不重复：1…${n} 或 0…${n-1}`);
}

function previewPolygon(points){
  const invalid={valid:false,triangles:[],issues:["invalid_footprint"]};
  if(!Array.isArray(points)||points.length<3||points.some(p=>!Array.isArray(p)||p.length!==3||!p.every(Number.isFinite)))
    return {...invalid,issues:["preview_coordinates_unavailable"]};
  const p=points.map(v=>new THREE.Vector2(v[0],v[2])),n=p.length;
  const scale=Math.max(...p.map(v=>v.x))-Math.min(...p.map(v=>v.x));
  const depth=Math.max(...p.map(v=>v.y))-Math.min(...p.map(v=>v.y));
  const lengthEps=Math.max(scale,depth,1)*1e-8,areaEps=lengthEps*Math.max(scale,depth,1);
  const turn=(a,b,c)=>(b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x);
  const onSegment=(a,b,c)=>Math.abs(turn(a,b,c))<=areaEps&&
    c.x>=Math.min(a.x,b.x)-lengthEps&&c.x<=Math.max(a.x,b.x)+lengthEps&&
    c.y>=Math.min(a.y,b.y)-lengthEps&&c.y<=Math.max(a.y,b.y)+lengthEps;
  for(let i=0;i<n;i++){
    const a=p[i],b=p[(i+1)%n],c=p[(i+2)%n];
    if(a.distanceTo(b)<=lengthEps)return {...invalid,issues:["duplicate_or_zero_edge","invalid_footprint"]};
    // Adjacent collinear edges may continue forward, but cannot double back.
    if(Math.abs(turn(a,b,c))<=areaEps&&(b.x-a.x)*(c.x-b.x)+(b.y-a.y)*(c.y-b.y)<0)return invalid;
    for(let j=i+1;j<n;j++){
      if(j===i+1||(i===0&&j===n-1))continue;
      const c=p[j],d=p[(j+1)%n],s=[turn(a,b,c),turn(a,b,d),turn(c,d,a),turn(c,d,b)];
      if(onSegment(a,b,c)||onSegment(a,b,d)||onSegment(c,d,a)||onSegment(c,d,b)||
        ((s[0]>areaEps&&s[1]<-areaEps||s[0]<-areaEps&&s[1]>areaEps)&&
         (s[2]>areaEps&&s[3]<-areaEps||s[2]<-areaEps&&s[3]>areaEps)))return invalid;
    }
  }
  const area=p.reduce((s,a,i)=>s+a.x*p[(i+1)%n].y-p[(i+1)%n].x*a.y,0)/2;
  if(Math.abs(area)<=areaEps)return invalid;
  const triangles=THREE.ShapeUtils.triangulateShape(p,[]);
  const triangleArea=triangles.reduce((s,t)=>s+Math.abs(turn(p[t[0]],p[t[1]],p[t[2]]))/2,0);
  if(!triangles.length||Math.abs(triangleArea-Math.abs(area))>areaEps*n)return invalid;
  const origin=new THREE.Vector2(0,0);
  const visible=p.every((a,i)=>Math.sign(area)*turn(a,p[(i+1)%n],origin)>areaEps);
  return {valid:true,triangles,issues:visible?[]:["camera_visibility_unresolved"],area:Math.abs(area)};
}

function orderedPreview(source,order){
  const result=clone(source),changed=order.some((value,index)=>value!==index);
  result.pairs=order.map(index=>clone(source.pairs[index]));
  for(const key of ["floor","ceiling"]){if(source.raw[key])result.raw[key]=order.map(index=>clone(source.raw[key][index]));}
  if(changed){
    const floor=previewPolygon(result.raw.floor),ceiling=previewPolygon(result.raw.ceiling);
    // Old triangle indices address the old vertex ring; always triangulate the new ring.
    result.raw.floor_triangles=floor.triangles;result.raw.ceiling_triangles=ceiling.triangles;
    result.raw.surface_valid=floor.valid&&ceiling.valid;result.raw.metrics=null;
    result.raw.source_issues=clone(source.raw.issues||[]);
    const recomputed=new Set(["invalid_footprint","duplicate_or_zero_edge","camera_visibility_unresolved",
      "preview_order_changed_geometry_not_revalidated"]);
    result.raw.issues=[...new Set([...(source.raw.issues||[]).filter(i=>!recomputed.has(i)),...floor.issues,
      ...(!ceiling.valid?["preview_ceiling_invalid"]:[]),"preview_order_semantics_unconfirmed"])];
    result.raw.preview_validation={scope:"floor_and_ceiling_proxy_polygon_only",floor_valid:floor.valid,
      ceiling_valid:ceiling.valid,source_order_changed:true,annotation_correctness_confirmed:false};
    result.fit={status:"blocked",reasons:["preview_order_changed_fit_not_recomputed"]};
  }
  return result;
}

function setPreviewOrder(order,action){
  if(!sourceGeometry)return;
  const prior=[...previewOrder];previewOrder=[...order];geometry=orderedPreview(sourceGeometry,previewOrder);
  orderHistory.push({action,at:new Date().toISOString(),from_original_zero_based:prior,to_original_zero_based:[...previewOrder]});
  if(selected){const original=prior[selected.index],next=previewOrder.indexOf(original);selected.index=next<0?0:next;}
  updateMetrics(dataset.cases[currentCase].variants[currentVariant]);rebuild(false);updateOrderEditor();
}

function moveSelected(delta){
  if(!selected)return;
  const target=selected.index+delta;if(target<0||target>=previewOrder.length)return;
  const order=[...previewOrder],[item]=order.splice(selected.index,1);order.splice(target,0,item);
  setPreviewOrder(order,delta<0?"move_selected_group_earlier":"move_selected_group_later");
}

function sourcePointIds(pair){
  const match=/^raw:(\d+)\/(\d+)$/.exec(String(pair?.source_pair_id||""));
  return match?[Number(match[1]),Number(match[2])]:[null,null];
}

function orderRecord(){
  const variant=dataset.cases[currentCase].variants[currentVariant];
  return {schema_version:"panorama_studio_preview_order_v1",image_id:dataset.cases[currentCase].image_id,
    variant_index_zero_based:currentVariant,variant_name:variant.name,
    source_pair_ids_original:sourceGeometry?.pairs.map(pair=>pair.source_pair_id)||[],
    preview_position_to_original_zero_based:[...previewOrder],preview_position_to_original_one_based:previewOrder.map(v=>v+1),
    preview_endpoint_payload_slot_to_original_zero_based:previewOrder.flatMap(v=>[2*v,2*v+1]),
    preview_endpoint_payload_slot_to_original_one_based:previewOrder.flatMap(v=>[2*v+1,2*v+2]),
    preview_endpoint_original_point_ids:geometry?.pairs.flatMap(sourcePointIds)||[],
    original_point_id_semantics:"parsed_only_from_source_pair_id_raw_top_bottom; null_when_unparseable",
    preview_source_pair_ids:geometry?.pairs.map(pair=>pair.source_pair_id)||[],history:clone(orderHistory),
    group_unit:"paired_top_bottom_endpoints",top_bottom_roles_preserved:true,source_coordinates_modified:false,
    preview_surface_valid:geometry?.raw.surface_valid||false,preview_validation:geometry?.raw.preview_validation||null,
    source_geometry_writeback:false,fit_recomputed:false,source_fit_status:sourceGeometry?.fit?.status||null,
    fit_available_in_preview:previewOrder.every((v,i)=>v===i)&&sourceGeometry?.fit?.status==="ok"};
}

function updateOrderEditor(){
  const changed=previewOrder.some((value,index)=>value!==index),n=previewOrder.length;
  $("order-status").textContent=!geometry?"无可核对点组":changed?(geometry.raw.surface_valid?"代理面可显示 · 拟合禁用":"轮廓异常 · 线框预览"):sourceGeometry.fit?.status==="ok"?"原始顺序 · 拟合可用":"原始顺序 · 原拟合不可用";
  $("order-permutation").value=previewOrder.map(value=>value+1).join(",");
  $("order-map").textContent=geometry?geometry.pairs.map((pair,index)=>{const ids=sourcePointIds(pair),raw=ids[0]===null?"原始点 ID 不可解析 (null)":`原始点 ID top=${ids[0]}, bottom=${ids[1]}`;return `预览组 ${index+1} (payload slots, 0-based: ${2*index},${2*index+1}) ← 原始组 ${previewOrder[index]+1} (payload slots, 0-based: ${2*previewOrder[index]},${2*previewOrder[index]+1}) · source_pair_id=${pair.source_pair_id} · ${raw}`;}).join("\n"):"无法排序：payload 不含可核对点组；请先核对上下配对，不自动造组。";
  $("order-earlier").disabled=!selected||selected.index===0;$("order-later").disabled=!selected||selected.index===n-1;
  $("order-restore").disabled=!changed;$("order-export").disabled=!geometry;$("order-apply").disabled=!geometry;$("order-permutation").disabled=!geometry;
}

function exportOrder(){
  const blob=new Blob([JSON.stringify(orderRecord(),null,2)],{type:"application/json"}),a=document.createElement("a");
  a.href=URL.createObjectURL(blob);a.download=`${dataset.cases[currentCase].image_id}_preview_order.json`;a.click();URL.revokeObjectURL(a.href);
}

function fail(message){$("fatal").hidden=false;$("fatal").textContent=message;}
window.addEventListener("error",e=>fail(`预览遇到错误：${e.message}`));

function createView(kind){
  const host=$("viewport-"+kind), scene=new THREE.Scene();
  // r128 scene background is already display RGB. Keep it independent of lighting.
  scene.background=new THREE.Color(0xeceeea);
  const renderer=new THREE.WebGLRenderer({antialias:true,alpha:false,preserveDrawingBuffer:true});
  renderer.setPixelRatio(Math.min(devicePixelRatio,2));
  renderer.outputEncoding=THREE.sRGBEncoding;
  renderer.localClippingEnabled=true;
  host.prepend(renderer.domElement);
  const ortho=new THREE.OrthographicCamera(-4,4,4,-4,.01,1000);
  const perspective=new THREE.PerspectiveCamera(65,1,.01,1000);
  const camera=ortho;
  const orbit=new THREE.OrbitControls(camera,renderer.domElement);
  orbit.enableDamping=false; orbit.enablePan=true; orbit.minDistance=.05;
  orbit.maxPolarAngle=Math.PI*.93;
  const ambient=new THREE.HemisphereLight(0xffffff,0x8e9691,1.05);scene.add(ambient);
  const key=new THREE.DirectionalLight(0xffffff,1.15);scene.add(key);scene.add(key.target);
  const fill=new THREE.DirectionalLight(0xeaf0f5,.35);scene.add(fill);
  const v={kind,host,scene,renderer,camera,ortho,perspective,orbit,key,fill,group:new THREE.Group(),decor:new THREE.Group(),section:new THREE.Group(),
    walls:[],pickables:[],markers:[],labelNodes:[],surface:null};
  scene.add(v.group,v.decor,v.section);
  orbit.addEventListener("change",()=>{
    if(syncing)return;
    syncing=true;
    for(const other of views)if(other!==v){
      other.camera.position.copy(v.camera.position);other.camera.quaternion.copy(v.camera.quaternion);
      other.camera.zoom=v.camera.zoom;other.camera.updateProjectionMatrix();other.orbit.target.copy(orbit.target);
    }
    syncing=false;renderAll();
  });
  let down=null;
  renderer.domElement.addEventListener("pointerdown",e=>down=[e.clientX,e.clientY]);
  renderer.domElement.addEventListener("pointerup",e=>{
    if(!down||Math.hypot(e.clientX-down[0],e.clientY-down[1])>5)return;
    pick(v,e);down=null;
  });
  renderer.domElement.addEventListener("pointermove",e=>{
    if(e.buttons)return;
    const hit=hitTest(v,e);
    renderer.domElement.style.cursor=hit?"pointer":"grab";
  });
  new ResizeObserver(()=>resize(v)).observe(host);
  return v;
}

function disposeGroup(group){
  const materials=new Set();
  group.traverse(o=>{o.geometry?.dispose();if(o.material)materials.add(o.material);});
  for(const m of materials)m.dispose();
  group.clear();
}

function faceGeometry(points,triangles){
  const g=new THREE.BufferGeometry();
  g.setAttribute("position",new THREE.Float32BufferAttribute(triangles.flatMap(t=>t.flatMap(i=>points[i])),3));
  g.computeVertexNormals();return g;
}

function makeMaterial(){
  if(materialMode==="texture"&&texture){
    return new THREE.ShaderMaterial({uniforms:{pano:{value:texture}},side:THREE.DoubleSide,clipping:true,
      vertexShader:`varying vec3 positionInRoom;
        #include <clipping_planes_pars_vertex>
        void main(){positionInRoom=position;vec4 mvPosition=modelViewMatrix*vec4(position,1.0);
        gl_Position=projectionMatrix*mvPosition;
        #include <clipping_planes_vertex>
        }`,
      fragmentShader:`uniform sampler2D pano;varying vec3 positionInRoom;
        #include <clipping_planes_pars_fragment>
        void main(){
        #include <clipping_planes_fragment>
        vec3 p=positionInRoom;float u=0.5+atan(p.x,-p.z)/6.28318530718;
        float v=0.5+atan(p.y,length(p.xz))/3.14159265359;
        gl_FragColor=vec4(texture2D(pano,vec2(u,v)).rgb,1.0);}`});
  }
  return new THREE.MeshStandardMaterial({color:new THREE.Color(0xe0e2dc).convertSRGBToLinear(),roughness:1,metalness:0,side:THREE.DoubleSide,
    polygonOffset:true,polygonOffsetFactor:1,polygonOffsetUnits:1});
}

function addLine(group,points,color=0x929985,opacity=.55){
  const g=new THREE.BufferGeometry().setFromPoints(points.map(vec));
  const line=new THREE.Line(g,new THREE.LineBasicMaterial({color,transparent:true,opacity}));
  group.add(line);return line;
}

function buildModel(v,surface){
  disposeGroup(v.group);disposeGroup(v.decor);disposeGroup(v.section);v.walls=[];v.pickables=[];v.markers=[];v.occluders=[];v.ceilingMesh=null;
  v.surface=surface;v.host.querySelector(".labels-layer").replaceChildren();v.labelNodes=[];
  if(!surface)return;
  const floors=surface.floor, tops=surface.ceiling, n=floors.length;
  const material=makeMaterial();
  const solid=materialMode!=="wire"&&(surface.surface_valid!==false);
  const area=floors.every(Boolean)?floors.reduce((s,a,i)=>{const b=floors[(i+1)%n];return s+a[0]*b[2]-b[0]*a[2];},0):1;
  for(let i=0;i<n;i++){
    const j=(i+1)%n, f=floors[i],g=floors[j],t=tops[i],u=tops[j];
    if(!f||!g||!t||!u)continue;
    const wallGroup=new THREE.Group();v.group.add(wallGroup);
    const mesh=new THREE.Mesh(faceGeometry([f,g,u,t],[[0,1,2],[0,2,3]]),material);
    mesh.visible=solid;
    mesh.userData={kind:"wall",index:i};wallGroup.add(mesh);v.pickables.push(mesh);v.occluders.push(mesh);
    addLine(wallGroup,[f,t,u,g],0x899481,materialMode==="texture"?.32:.55);
    const outward=new THREE.Vector3(g[2]-f[2],0,f[0]-g[0]).multiplyScalar(Math.sign(area)).normalize();
    v.walls.push({group:wallGroup,mesh,index:i,outward,mid:vec(f).add(vec(g)).multiplyScalar(.5)});
  }
  for(const [key,points,triangles] of [["floor",floors,surface.floor_triangles],["ceiling",tops,surface.ceiling_triangles]]){
    if(triangles?.length&&points.every(Boolean)){
      const mesh=new THREE.Mesh(faceGeometry(points,triangles),material);
      mesh.visible=solid&&(key!=="ceiling"||$("ceiling").checked);
      mesh.userData.layer=key;
      v.group.add(mesh);v.occluders.push(mesh);if(key==="ceiling")v.ceilingMesh=mesh;
    }else if(key==="ceiling")v.ceilingMesh=null;
  }
  if(floors.every(Boolean))addLine(v.group,[...floors,floors[0]],0x737f6b,.55);
  for(let i=0;i<n;i++)for(const [ep,points] of [["top",tops],["bottom",floors]]){
    const p=points[i];if(!p)continue;
    const marker=new THREE.Mesh(new THREE.SphereGeometry(radius*.012,12,8),
      new THREE.MeshBasicMaterial({color:0x68816a,depthTest:true,transparent:true,opacity:.9}));
    marker.position.copy(vec(p));marker.renderOrder=4;marker.userData={kind:"point",index:i,endpoint:ep};
    v.group.add(marker);v.markers.push(marker);v.pickables.push(marker);
    const label=document.createElement("span");label.className="point-label";label.textContent=i+1;
    v.host.querySelector(".labels-layer").append(label);v.labelNodes.push({label,position:vec(p),index:i,endpoint:ep});
  }
  // A soft footprint contact cue, not a physically simulated room shadow or measured surface.
  if(solid&&floors.every(Boolean)){
    const contact=new THREE.ShaderMaterial({transparent:true,depthWrite:false,side:THREE.DoubleSide,
      uniforms:{ring:{value:floors.map(p=>new THREE.Vector2(p[0],p[2]))},softness:{value:radius*.045}},
      vertexShader:"varying vec2 roomXZ;void main(){vec4 w=modelMatrix*vec4(position,1.0);roomXZ=w.xz;gl_Position=projectionMatrix*viewMatrix*w;}",
      fragmentShader:`varying vec2 roomXZ;uniform vec2 ring[${n}];uniform float softness;
        void main(){float d=1e6;bool inside=false;for(int i=0;i<${n};i++){
        vec2 a=ring[i];vec2 b=ring[(i+1)%${n}];vec2 e=b-a;
        d=min(d,length(roomXZ-a-e*clamp(dot(roomXZ-a,e)/max(dot(e,e),1e-10),0.,1.)));
        if((a.y>roomXZ.y)!=(b.y>roomXZ.y)){
          if(roomXZ.x<(b.x-a.x)*(roomXZ.y-a.y)/(b.y-a.y)+a.x)inside=!inside;}}
        float alpha=inside?0.12:0.12*exp(-d*d/(softness*softness));
        gl_FragColor=vec4(0.28,0.32,0.29,alpha);}`});
    const ground=new THREE.Mesh(new THREE.PlaneGeometry(roomSize.x+radius*.6,roomSize.z+radius*.6),contact);
    ground.rotation.x=-Math.PI/2;ground.position.set(center.x,-1.025,center.z);v.decor.add(ground);
  }
  v.key.position.copy(center).add(new THREE.Vector3(-radius*.8,radius*1.6,radius*.6));
  v.key.target.position.copy(center);v.fill.position.copy(center).add(new THREE.Vector3(radius, radius*.5,-radius));
}

function updateSection(){
  clippingHeight=-1+(center.y+roomSize.y/2+1)*Number($("cut-height").value)/100;
  clipPlane.constant=clippingHeight;
  const enabled=$("cutaway").checked&&viewMode!=="inside";
  $("cut-height").disabled=!enabled;$("cut-value").textContent=$("cut-height").value+"%";
  for(const v of views){
    disposeGroup(v.section);
    v.group.traverse(o=>{if(o.material)o.material.clippingPlanes=enabled?[clipPlane]:[];});
    if(!enabled)continue;
    // Triangle/plane intersections follow original nonplanar surfaces exactly.
    const segments=[];
    for(const wall of v.walls){const pos=wall.mesh.geometry.attributes.position;
      for(let i=0;i<pos.count;i+=3){const hits=[];
        for(let j=0;j<3;j++){const a=new THREE.Vector3().fromBufferAttribute(pos,i+j),b=new THREE.Vector3().fromBufferAttribute(pos,i+(j+1)%3);
          if((a.y<clippingHeight)!==(b.y<clippingHeight))hits.push(a.clone().lerp(b,(clippingHeight-a.y)/(b.y-a.y)));}
        if(hits.length===2)segments.push(...hits);
      }
    }
    if(segments.length)v.section.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(segments),
      new THREE.LineBasicMaterial({color:0x47715e,depthTest:true})));
  }
}

function rebuild(reset=false){
  if(!geometry){for(const v of views){buildModel(v,null);}renderAll();return;}
  const all=[...geometry.raw.floor,...geometry.raw.ceiling,...(geometry.fit.floor||[]),...(geometry.fit.ceiling||[])].filter(Boolean);
  const box=new THREE.Box3().setFromPoints(all.length?all.map(vec):[new THREE.Vector3(-2,-1,-2),new THREE.Vector3(2,2,2)]);
  box.getCenter(center);box.getSize(roomSize);radius=Math.max(roomSize.length()*.5,1);
  framingPoints=all.map(vec);
  for(const v of views)buildModel(v,v.kind==="raw"?geometry.raw:geometry.fit.status==="ok"?geometry.fit:null);
  $("fit-empty").hidden=geometry.fit.status==="ok";
  $("fit-empty").replaceChildren();
  if(geometry.fit.status!=="ok"){
    const strong=document.createElement("strong");strong.textContent="保留问题，暂不拟合";
    $("fit-empty").append(strong,document.createTextNode(reasons(geometry.fit.reasons)));
  }
  if(reset)preset("iso");else updateSection();
  updateSelection();renderAll();
}

function resize(v){
  const w=v.host.clientWidth,h=v.host.clientHeight;if(!w||!h)return;
  v.renderer.setSize(w,h,false);v.perspective.aspect=w/h;v.perspective.updateProjectionMatrix();
  v.ortho.left=-orthoHeight*w/h/2;v.ortho.right=orthoHeight*w/h/2;
  v.ortho.top=orthoHeight/2;v.ortho.bottom=-orthoHeight/2;v.ortho.updateProjectionMatrix();renderAll();
}

function preset(name){
  if(!geometry)return;
  viewMode=name==="reset"?"iso":name;
  document.body.classList.toggle("interior",viewMode==="inside");
  document.querySelectorAll("[data-view]").forEach(b=>b.classList.toggle("active",b.dataset.view===viewMode));
  syncing=true;
  for(const v of views){
    v.camera=viewMode==="inside"?v.perspective:v.ortho;v.orbit.object=v.camera;
    v.camera.near=Math.max(.001,radius/1000);v.camera.far=radius*100;v.camera.zoom=1;
    v.orbit.enablePan=viewMode!=="inside";
    v.orbit.enableZoom=viewMode!=="inside";
    if(viewMode==="inside"){
      v.camera.position.set(0,0,0);v.orbit.enabled=false;v.orbit.target.set(0,0,-1);v.camera.lookAt(v.orbit.target);
    }else{
      v.orbit.enabled=true;v.orbit.target.copy(center);v.orbit.maxDistance=radius*15;
      const offset=viewMode==="top"?new THREE.Vector3(0,1,.0001):new THREE.Vector3(1,1.25,1.25).normalize();
      v.camera.position.copy(center).addScaledVector(offset,radius*4);v.camera.lookAt(center);v.orbit.update();
    }
    v.camera.updateProjectionMatrix();
  }
  if(viewMode!=="inside"&&framingPoints.length){
    const camera=views[0].camera;camera.updateMatrixWorld();
    const bounds=new THREE.Box3().setFromPoints(framingPoints.map(p=>p.clone().applyMatrix4(camera.matrixWorldInverse)));
    const size=bounds.getSize(new THREE.Vector3());
    const aspect=Math.min(...views.filter(v=>v.host.clientWidth>0).map(v=>v.host.clientWidth/v.host.clientHeight));
    orthoHeight=Math.max(size.y,size.x/aspect)*1.35;
  }
  syncing=false;views.forEach(resize);updateSection();renderAll();
}

function renderAll(){
  for(const v of views){
    v.decor.visible=$("decor").checked&&viewMode!=="inside";
    for(const wall of v.walls){
      wall.group.visible=true;
      const active=selected?.kind==="wall"&&selected.index===wall.index;
      for(const child of wall.group.children)if(child.isLine){child.material.color.setHex(active?0xb97843:0x899481);child.material.opacity=active?1:.45;}
    }
    if(v.ceilingMesh)v.ceilingMesh.visible=materialMode!=="wire"&&$("ceiling").checked&&v.surface?.surface_valid!==false;
    for(const marker of v.markers){
      const active=selected&&selected.index===marker.userData.index&&endpoint===marker.userData.endpoint;
      marker.visible=(!!active||$("labels").checked)&&!pointClipped(marker.position);
      marker.material.depthTest=!$("xray").checked;
      marker.scale.setScalar(active?1.3:.7);
      marker.material.color.setHex(active?0xb97843:0x68816a);
    }
    v.camera.updateMatrixWorld();
    for(const item of v.labelNodes){
      const active=selected&&selected.index===item.index&&endpoint===item.endpoint;
      const p=item.position.clone().project(v.camera);
      item.label.hidden=!((active||($("labels").checked&&item.endpoint==="top"))&&p.z>=-1&&p.z<=1&&
        !pointClipped(item.position)&&($("xray").checked||pointVisible(v,item.position)));
      item.label.classList.toggle("selected",!!active);
      item.label.style.left=((p.x+1)/2*v.host.clientWidth)+"px";
      item.label.style.top=((1-p.y)/2*v.host.clientHeight-16)+"px";
    }
    if(v.host.clientWidth)v.renderer.render(v.scene,v.camera);
  }
}

function pointClipped(point){return $("cutaway").checked&&viewMode!=="inside"&&clipPlane.distanceToPoint(point)<-1e-5;}
function rayAt(v,ndc){const ray=new THREE.Raycaster();ray.setFromCamera(ndc,v.camera);return ray;}
function visibleHits(v,ray){return ray.intersectObjects((v.occluders||[]).filter(o=>o.visible))
  .filter(h=>!pointClipped(h.point));}
function pointVisible(v,point){
  if(pointClipped(point))return false;
  v.scene.updateMatrixWorld();v.camera.updateMatrixWorld();
  const ndc=point.clone().project(v.camera);const ray=rayAt(v,new THREE.Vector2(ndc.x,ndc.y));
  const target=point.clone().sub(ray.ray.origin).dot(ray.ray.direction);
  return !visibleHits(v,ray).some(h=>h.distance<target-radius*1e-4);
}

function hitTest(v,event){
  const rect=v.renderer.domElement.getBoundingClientRect();
  const mouse=new THREE.Vector2((event.clientX-rect.left)/rect.width*2-1,1-(event.clientY-rect.top)/rect.height*2);
  // Screen-space endpoint picking works even with the quiet default marker display.
  let closest=null,best=11;
  for(const m of v.markers){const p=m.position.clone().project(v.camera);
    if(p.z < -1 || p.z > 1)continue;
    if(pointClipped(m.position)||(!$("xray").checked&&!pointVisible(v,m.position)))continue;
    const d=Math.hypot((p.x-mouse.x)*rect.width/2,(p.y-mouse.y)*rect.height/2);
    if(d<best){best=d;closest={object:m};}}
  if(closest)return closest;
  const hit=visibleHits(v,rayAt(v,mouse))[0];
  return hit?.object.userData.kind==="wall"?hit:null;
}
function pick(v,event){const hit=hitTest(v,event);if(hit)select(hit.object.userData);}
function select(item){selected={kind:item.kind,index:item.index};if(item.endpoint)endpoint=item.endpoint;updateSelection();renderAll();}

function drawPath(ctx,points,color,dashed=false,scale=1){
  if(points.length<2)return;
  ctx.strokeStyle=color;ctx.lineWidth=1.6*scale;ctx.setLineDash(dashed?[5*scale,4*scale]:[]);
  let previous=null;ctx.beginPath();
  for(const p of points){if(!previous||Math.abs(p[0]-previous[0])>geometry.width/2)ctx.moveTo(...p);else ctx.lineTo(...p);previous=p;}
  ctx.stroke();ctx.setLineDash([]);
}
function project(p){return [(Math.atan2(p[0],-p[2])/(Math.PI*2)+.5)*geometry.width,
  (.5-Math.atan2(p[1],Math.hypot(p[0],p[2]))/Math.PI)*geometry.height];}
function boundaryPoints(surface,ep,i){
  const pts=ep==="top"?surface.ceiling:surface.floor,a=pts[i],b=pts[(i+1)%pts.length];
  if(!a||!b)return [];
  return Array.from({length:65},(_,j)=>project(a.map((v,k)=>v+(b[k]-v)*j/64)));
}

function drawPanorama(){
  const canvas=$("panorama"),ctx=canvas.getContext("2d");
  if(!geometry||!originalImage){ctx.clearRect(0,0,canvas.width,canvas.height);return;}
  canvas.width=geometry.width*2;canvas.height=geometry.height*2;
  ctx.scale(2,2);ctx.drawImage(originalImage,0,0,geometry.width,geometry.height);
  for(const [surface,color,dash] of [[geometry.raw,"#82c29e",false],[geometry.fit,"#e4ad75",true]]){
    if(!surface.floor)continue;
    for(let i=0;i<geometry.pairs.length;i++)for(const ep of ["top","bottom"]){
      drawPath(ctx,boundaryPoints(surface,ep,i),color,dash);
    }
  }
  geometry.pairs.forEach((p,i)=>["top","bottom"].forEach(ep=>{
    const active=selected?.index===i&&endpoint===ep;ctx.beginPath();ctx.arc(...p[ep],active?5:2.6,0,Math.PI*2);
    ctx.fillStyle=active?"#f7c58b":"#e9fff0";ctx.fill();ctx.strokeStyle="#426950";ctx.lineWidth=1;ctx.stroke();
  }));
}

function drawCrop(){
  const canvas=$("crop"),ctx=canvas.getContext("2d");ctx.fillStyle="#e5e6dd";ctx.fillRect(0,0,canvas.width,canvas.height);
  if(!geometry||!originalImage||!selected){ctx.fillStyle="#97a08e";ctx.font="20px Segoe UI";ctx.textAlign="center";ctx.fillText("选择一个角点",canvas.width/2,canvas.height/2);return;}
  const p=geometry.pairs[selected.index][endpoint],q=geometry.fit.reprojected_pairs?.[selected.index]?.[endpoint];
  const span=160,zoom=canvas.width/span,left=p[0]-span/2,top=p[1]-canvas.height/zoom/2;
  ctx.save();ctx.scale(zoom,zoom);ctx.translate(-left,-top);
  for(let t=-1;t<=1;t++)ctx.drawImage(originalImage,t*geometry.width,0,geometry.width,geometry.height);
  let aligned=q?[p[0]+((q[0]-p[0]+geometry.width/2)%geometry.width+geometry.width)%geometry.width-geometry.width/2,q[1]]:null;
  if(aligned){ctx.beginPath();ctx.moveTo(...p);ctx.lineTo(...aligned);ctx.strokeStyle="#e5aa68";ctx.lineWidth=.8;ctx.stroke();}
  for(const [point,color] of [[p,"#73b694"],[aligned,"#edb270"]])if(point){ctx.beginPath();ctx.arc(...point,2.2,0,Math.PI*2);ctx.strokeStyle="#fff";ctx.lineWidth=.5;ctx.fillStyle=color;ctx.fill();ctx.stroke();}
  ctx.restore();ctx.fillStyle="#ffffffdc";ctx.fillRect(9,9,190,27);ctx.fillStyle="#5b6d59";ctx.font="15px Segoe UI";ctx.textAlign="left";ctx.fillText("原始 ●   拟合 ●   周期展开",18,29);
}

function updateSelection(){
  if(!geometry)return;
  document.querySelector(".selection-block").classList.toggle("has-selection",!!selected);
  const buttons=$("pair-buttons");buttons.replaceChildren();
  geometry.pairs.forEach((p,i)=>{const b=document.createElement("button");b.textContent=i+1;b.title=p.source_pair_id;
    b.className=selected?.index===i?"active":"";b.onclick=()=>select({kind:"point",index:i,endpoint});buttons.append(b);});
  document.querySelectorAll("[data-endpoint]").forEach(b=>b.classList.toggle("active",b.dataset.endpoint===endpoint));
  if(selected){
    const p=geometry.pairs[selected.index],q=geometry.fit.reprojected_pairs?.[selected.index];
    $("selection-kind").textContent=(selected.kind==="wall"?"墙面 ":"角点 ")+(selected.index+1);
    const lines=[`原始身份：${p.source_pair_id}`,`${endpoint==="top"?"上":"下"}端点：${p[endpoint].map(x=>fmt(x)).join(", ")} px`];
    if(q)lines.push(`拟合：${q[endpoint].map(x=>fmt(x)).join(", ")} px · 偏差 ${fmt(geometry.fit.per_pair_residual_deg[selected.index][endpoint],3)}°`);
    if(selected.kind==="wall")lines.push(`连接显示编号 ${selected.index+1} → ${(selected.index+1)%geometry.pairs.length+1}；局部显示起点。`);
    $("selection-details").replaceChildren(...lines.map(text=>{const el=document.createElement("div");el.textContent=text;return el;}));
  }else{$("selection-kind").textContent="选择角点或墙面";$("selection-details").textContent="点击模型或全景图，也可用编号按钮选择端点。";}
  drawPanorama();drawCrop();
  updateOrderEditor();
}

function updateMetrics(variant){
  const raw=geometry.raw,fit=geometry.fit;
  $("mean-error").textContent=fit.status==="ok"?fmt(fit.residual_mean_deg,3)+"°":"—";
  const rows=[["最大重投影偏差",fit.status==="ok"?fmt(fit.residual_max_deg,3)+"°":"无法可靠拟合"],
    ["角点对",String(geometry.pairs.length)],["墙向偏差 · 原始 / 拟合",fmt(raw.metrics?.heading_mean_deg)+"° / "+fmt(fit.metrics?.heading_mean_deg)+"°"],
    ["高度跨度 / 中位高度",fmt(raw.metrics?.height_relative_spread*100)+"% / "+fmt(fit.metrics?.height_relative_spread*100)+"%"]];
  $("metrics").replaceChildren(...rows.map(([name,value])=>{const row=document.createElement("div");row.className="metric-row";
    for(const text of [name,value]){const span=document.createElement("span");span.textContent=text;row.append(span);}return row;}));
  const notes=[...raw.issues,...(fit.reasons||[])];
  $("issues").classList.toggle("warning",notes.length>0);
  $("issues").textContent=notes.length?reasons([...new Set(notes)]):"当前几何检查通过。约束结果仅供对照，不代表正确性判断。";
  $("raw-title").textContent=raw.preview_validation?"顺序预览副本":"原始重建";
  $("raw-caption").textContent=raw.preview_validation?
    (raw.surface_valid?"预览排列 · 代理面，语义未确认":"预览轮廓异常 · 线框"):
    raw.surface_valid?"水平地面 · 原始角点射线":"输入异常 · 保留可解析线框";
  $("fit-caption").textContent=fit.status==="ok"?"固定主方向 · 共面天花板":"未生成约束房间";
  const pre=document.createElement("pre");pre.textContent=JSON.stringify(variant.source,null,2);
  if(raw.preview_validation)pre.textContent+="\n\n原始顺序诊断（保留，不作为当前轮廓检查结果）：\n"+reasons(raw.source_issues);
  $("provenance").replaceChildren(pre);
}

function chooseVariant(index,resetView=false){
  currentVariant=index;const variant=dataset.cases[currentCase].variants[index];
  sourceGeometry=variant.geometry?clone(variant.geometry):null;
  previewOrder=sourceGeometry?sourceGeometry.pairs.map((_,index)=>index):[];orderHistory=[];
  geometry=sourceGeometry?orderedPreview(sourceGeometry,previewOrder):null;
  if(!geometry){selected=null;$("issues").textContent="输入无法解析："+variant.error;$("mean-error").textContent="—";
    $("fit-empty").hidden=false;$("fit-empty").textContent=variant.error;
    $("metrics").replaceChildren();$("pair-buttons").replaceChildren();$("selection-details").textContent="";
    $("raw-title").textContent="原始重建";$("raw-caption").textContent="输入无法解析";$("fit-caption").textContent="未生成约束房间";
    $("provenance").textContent=JSON.stringify(variant.source);$("issues").classList.add("warning");
    document.querySelector(".selection-block").classList.remove("has-selection");
    rebuild();drawPanorama();drawCrop();updateOrderEditor();return;}
  // Different annotations do not establish semantic point correspondence by equal ordinal numbers.
  selected=null;
  updateMetrics(variant);rebuild(resetView);
}

async function chooseCase(index){
  const token=++imageToken;currentCase=(index+dataset.cases.length)%dataset.cases.length;$("fatal").hidden=true;
  const c=dataset.cases[currentCase];$("case-select").value=currentCase;
  $("case-count").textContent=String(currentCase+1).padStart(2,"0")+" / "+dataset.cases.length;
  $("case-title").textContent=c.title;$("image-id").textContent=c.image_id;$("category").textContent=c.category||"布局观察";
  $("variant-select").replaceChildren(...c.variants.map((v,i)=>{const o=document.createElement("option");o.value=i;o.textContent=v.name;return o;}));
  selected=null;originalImage=null;if(texture){texture.dispose();texture=null;}
  $("texture-state").textContent="正在载入原图…";
  const defaultIndex=Math.max(0,c.variants.findIndex(v=>v.source.role==="dataset_reference"));
  $("variant-select").value=defaultIndex;chooseVariant(defaultIndex,true);
  try{
    if(!window.STUDIO_IMAGES[currentCase])await new Promise((resolve,reject)=>{
      const s=document.createElement("script");s.src=c.image_script;s.onload=resolve;s.onerror=()=>reject(new Error("图像包读取失败"));document.head.append(s);
    });
    if(token!==imageToken)return;
    const images=window.STUDIO_IMAGES[currentCase], img=new Image();img.src=images.original;await img.decode();
    if(token!==imageToken)return;originalImage=img;
    const tex=await new Promise((resolve,reject)=>new THREE.TextureLoader().load(images.texture,resolve,undefined,reject));
    if(token!==imageToken){tex.dispose();return;}
    texture=tex;texture.wrapS=THREE.RepeatWrapping;texture.minFilter=THREE.LinearFilter;texture.magFilter=THREE.LinearFilter;
    texture.generateMipmaps=false;texture.anisotropy=Math.min(8,views[0].renderer.capabilities.getMaxAnisotropy());
    $("texture-state").textContent="原图与纹理已载入";drawPanorama();drawCrop();if(materialMode==="texture")rebuild(false);
  }catch(err){if(token===imageToken){$("texture-state").textContent="图像加载失败；白模仍可检查";fail(String(err));}}
}

$("case-select").replaceChildren(...dataset.cases.map((c,i)=>{const o=document.createElement("option");o.value=i;o.textContent=String(i+1).padStart(2,"0")+" · "+c.title;return o;}));
$("case-select").onchange=e=>chooseCase(Number(e.target.value));
$("variant-select").onchange=e=>chooseVariant(Number(e.target.value));
$("previous").onclick=()=>chooseCase(currentCase-1);$("next").onclick=()=>chooseCase(currentCase+1);
document.querySelectorAll("[data-material]").forEach(b=>b.onclick=()=>{
  materialMode=b.dataset.material;document.querySelectorAll("[data-material]").forEach(x=>x.classList.toggle("active",x===b));rebuild(false);
});
document.querySelectorAll("[data-view]").forEach(b=>b.onclick=()=>preset(b.dataset.view));
document.querySelectorAll("[data-endpoint]").forEach(b=>b.onclick=()=>{endpoint=b.dataset.endpoint;updateSelection();renderAll();});
for(const name of ["ceiling","labels","decor","xray"])$(name).onchange=renderAll;
$("cutaway").onchange=()=>{updateSection();renderAll();};
$("cut-height").oninput=()=>{updateSection();renderAll();};
$("diagnostic").onclick=()=>{
  for(const id of ["cutaway","decor","ceiling","xray"])$(id).checked=false;
  materialMode="wire";document.querySelectorAll("[data-material]").forEach(b=>b.classList.toggle("active",b.dataset.material===materialMode));
  rebuild(false);
};
$("toggle-inspector").onclick=()=>{
  const hidden=document.querySelector(".workspace").classList.toggle("hide-inspector");
  $("toggle-inspector").setAttribute("aria-expanded",String(!hidden));
};
document.querySelectorAll("[data-expand]").forEach(b=>b.onclick=()=>{
  const grid=$("compare-grid"),mode="only-"+b.dataset.expand;grid.className="compare-grid"+(grid.classList.contains(mode)?"":" "+mode);
  requestAnimationFrame(()=>{views.forEach(resize);});
});
$("panorama").onclick=e=>{
  if(!geometry)return;const rect=e.target.getBoundingClientRect();
  const p=[(e.clientX-rect.left)/rect.width*geometry.width,(e.clientY-rect.top)/rect.height*geometry.height];
  let best=Infinity,item=null;
  geometry.pairs.forEach((pair,index)=>["top","bottom"].forEach(ep=>{
    const d=Math.hypot((pair[ep][0]-p[0]+geometry.width/2)%geometry.width-geometry.width/2,pair[ep][1]-p[1]);
    if(d<best){best=d;item={kind:"point",index,endpoint:ep};}
  }));if(item)select(item);
};
$("order-earlier").onclick=()=>moveSelected(-1);$("order-later").onclick=()=>moveSelected(1);
$("order-restore").onclick=()=>setPreviewOrder(previewOrder.map((_,index)=>index),"restore_original_order");
$("order-apply").onclick=()=>{try{setPreviewOrder(parsePermutation($("order-permutation").value,previewOrder.length),"apply_full_permutation");$("fatal").hidden=true;}catch(error){fail(error.message);}};
$("order-export").onclick=exportOrder;
for(const kind of ["raw","fit"])views.push(createView(kind));
// Interior view rotates about the panorama camera, never invents a translated viewpoint.
for(const v of views){let start=null;
  v.renderer.domElement.addEventListener("pointerdown",e=>{if(viewMode==="inside")start={x:e.clientX,y:e.clientY,q:v.camera.quaternion.clone()};});
  v.renderer.domElement.addEventListener("pointermove",e=>{
    if(!start||!e.buttons||viewMode!=="inside")return;
    const angle=new THREE.Euler().setFromQuaternion(start.q,"YXZ");
    angle.y-=(e.clientX-start.x)*.004;angle.x=THREE.MathUtils.clamp(angle.x-(e.clientY-start.y)*.004,-1.5,1.5);
    for(const other of views)other.camera.quaternion.setFromEuler(angle);renderAll();
  });
  v.renderer.domElement.addEventListener("pointerup",()=>start=null);
}
$("bundle-stats").textContent=dataset.counts.cases+" 个验证案例 · "+dataset.counts.variants+" 个来源版本";
// Read-only test seam: expose state, never a geometry mutation or save API.
window.STUDIO={snapshot:()=>({caseIndex:currentCase,variantIndex:currentVariant,materialMode,viewMode,selected,endpoint,
  imageReady:!!originalImage,textureReady:!!texture,fitStatus:geometry?.fit.status,
  cameras:views.map(v=>({type:v.camera.type,position:v.camera.position.toArray(),quaternion:v.camera.quaternion.toArray(),zoom:v.camera.zoom})),
  clipping:{enabled:$("cutaway").checked&&viewMode!=="inside",fraction:Number($("cut-height").value)/100},
  clipPlanes:views.map(v=>v.walls[0]?.mesh.material.clippingPlanes?.map(p=>[...p.normal.toArray(),p.constant])||[]),
  sectionSegments:views.map(v=>v.section.children.reduce((n,o)=>n+o.geometry.attributes.position.count/2,0)),
  wallVisibility:views.map(v=>v.walls.map(w=>w.group.visible)),
  geometry:JSON.stringify(geometry),sourceGeometry:JSON.stringify(sourceGeometry),previewOrder:[...previewOrder],orderRecord:orderRecord()}),
  parsePermutation,orderedPreview,setPreviewOrder,sourcePointIds,orderRecord};
chooseCase(0);
