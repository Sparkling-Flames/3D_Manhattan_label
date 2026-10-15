'use strict';
const fs=require('fs'),vm=require('vm'),assert=require('assert'),G=require('./dist/geometry.js'),S=require('./dist/review-state.js'),C=require('./dist/catalogue.js');
const DATA=JSON.parse(fs.readFileSync('dist/data.json')),HTML=fs.readFileSync('dist/index.html','utf8'),KEY='layout-scope-crop-v1';
let checks=0;const check=(v,m)=>{assert(v,m);checks++},eq=(a,b,m)=>{assert.deepStrictEqual(JSON.parse(JSON.stringify(a)),JSON.parse(JSON.stringify(b)),m);checks++},near=(a,b,e=1e-9)=>check(Math.abs(a-b)<=e,`${a} != ${b}`),polyNear=(a,b)=>{eq(a.length,b.length);a.forEach((p,i)=>p.forEach((v,j)=>near(v,b[i][j])))};
function orthogonal(p){for(let i=0;i<4;i++){let a=p[i],b=p[(i+1)%4],c=p[(i+2)%4];near((a[0]-b[0])*(c[0]-b[0])+(a[1]-b[1])*(c[1]-b[1]),0)}}
function coincident(poly,edge,gt,index){for(const p of [poly[edge],poly[(edge+1)%poly.length]])near(G.cross(gt[index],gt[(index+1)%gt.length],p),0)}
async function boot(stored,scale=1){
 const data=S.clone(DATA),elements={},saved=new Map(stored?[[KEY,JSON.stringify(stored)]]:[]),handlers={},downloads=[];
 const el=id=>elements[id]||(elements[id]={value:id==='yaw'?'0':'',checked:new RegExp(`<input[^>]*id="${id}"[^>]*checked`).test(HTML),disabled:false,hidden:false,textContent:'',innerHTML:'',style:{},dataset:{},tagName:'DIV',classList:{toggle(){},remove(){},contains(){return false}},querySelectorAll(){return []},click(){if(!this.disabled)this.onclick?.()},getContext(){return new Proxy({},{get:()=>()=>{}})},setPointerCapture(){},getScreenCTM(){return {a:scale,b:0,c:0,d:scale,e:0,f:0,inverse:()=>({scale})}},createSVGPoint(){return {x:0,y:0,matrixTransform(m){return {x:this.x/m.scale,y:this.y/m.scale}}}}});
 const choices=['allow','full_gt','uncertain'].map(x=>({dataset:{decision:x},classList:{toggle(){}},disabled:false})),modes=['cut','rectangle','edge'].map(x=>({dataset:{mode:x},classList:{toggle(){}},disabled:false}));
 const ctx={console,Geo:G,ReviewState:S,Catalogue:C,document:{querySelector:s=>el(s.slice(1)),querySelectorAll:s=>s==='[data-decision]'?choices:s==='[data-mode]'?modes:s==='[data-mode],[data-decision]'?[...choices,...modes]:[],addEventListener:(k,f)=>handlers[k]=f,activeElement:{tagName:'BODY'},createElement:()=>({click(){downloads.push(this.download)}})},localStorage:{setItem:(k,v)=>saved.set(k,v),getItem:k=>saved.get(k)},Image:class{constructor(){this.complete=false;this.naturalWidth=0}},fetch:async path=>({ok:true,json:async()=>path==='data.json'?data:JSON.parse(fs.readFileSync('dist/'+path))}),setTimeout:()=>1,clearTimeout(){},Date,Blob,URL:{createObjectURL:()=>'',revokeObjectURL(){}},window:null};ctx.window=ctx;vm.createContext(ctx);vm.runInContext(fs.readFileSync('dist/app.js','utf8'),ctx);await new Promise(r=>setImmediate(r));
 const get=s=>vm.runInContext(s,ctx),event=(p,dataset={})=>{const pos=get('screen('+JSON.stringify(p)+')');return {button:0,pointerId:1,preventDefault(){},target:{dataset},clientX:pos[0]*scale,clientY:pos[1]*scale}};
 return {w:ctx.workbench,el,saved,get,event,handlers,downloads,ctx,choices};
}
(async()=>{
 for(const angle of [0,12.3456789,37,90,-44])for(const reversed of [false,true]){
  const rotate=p=>G.global(p,angle),gt=[[-2,-1],[2,-1],[2,1],[-2,1]].map(rotate),ends=[[-1.92,-.95],[1.95,.92]].map(rotate);if(reversed)ends.reverse();
  const s=G.snapRectangle(...ends,angle,gt,.1);eq(s.matches.length,4);check(s.matches.every(m=>m.exact));orthogonal(s.polygon);for(const m of s.matches)coincident(s.polygon,m.edge,gt,m.gt_edge);
  const f=G.followRectangleGT(s.polygon,gt,s.matches,.1);check(f);polyNear(f.polygon,s.polygon);
 }
 const gt=[[-2,-1],[2,-1],[2,1],[-2,1]];
 eq(G.edgeSnapCandidates([0,0],[1,0],[[10,.01],[11,.01],[11,1],[10,1]],.1).length,0,'far supporting-line extension excluded');
 eq(G.edgeSnapCandidates([0,0],[1,0],[[1,.01],[2,.01],[2,1],[1,1]],.1).length,0,'endpoint-only touching is not finite overlap');
 eq(G.edgeSnapCandidates([0,0],[1,0],[[0,.101],[1,.101],[1,1],[0,1]],.1).length,0,'outside proximity rejected');
 check(G.edgeSnapCandidates([0,0],[1,0],[[0,.099],[1,.099],[1,1],[0,1]],.1).length===1);
 eq(G.edgeSnapCandidates([0,0],[1,0],[[0,.01],[1,.05],[1,1],[0,1]],.1).length,0,'nonparallel diagonal rejected');
 eq(G.edgeSnapCandidates([0,0],[1,0],gt,0).length,0);eq(G.edgeSnapCandidates([0,0],[0,0],gt,.1).length,0);
 const almost=G.edgeSnapCandidates([0,0],[2,0],[[0,.01],[2,.011],[2,1],[0,1]],.1);eq(almost.length,1);check(!almost[0].exact,'near parallel is explicitly approximate');
 const collapse=G.snapRectangle([-.02,-1.02],[.02,-.98],0,gt,.1);check(collapse.polygon&&G.valid(collapse.polygon));check(G.area(collapse.polygon)>0,'same nearby line does not collapse rectangle');
 const moved=G.snapEdgeMove(G.rectangle([-1.95,-.9],[1.9,.9],0),1,-.05,gt,.1);eq(moved.matches.length,1);near(moved.polygon[1][0],2);orthogonal(moved.polygon);
 eq(G.snapEdgeMove(gt,99,.1,gt,.1).polygon,null);eq(G.boundaryQuad([]),null);eq(G.boundaryQuad([[[0,0],[1,0]],[[0,0],[1,0]],[[0,0],[1,0]],[[0,0],[1,0]]]),null);
 // The supplied screenshot's real GT is not perfectly orthogonal after ERP conversion.
 const source=DATA.images.find(c=>c.image_code==='q9vSo1VnCiC-12'),p=G.floor(source.reference_points_1024x512),a=[p[7][0]+.02,p[0][1]+.02],b=[p[2][0]-.03,p[6][1]-.02];
 const snapped=G.snapRectangle(a,b,0,p,.12);eq(snapped.matches.map(m=>m.gt_edge),[7,2,5,6]);check(snapped.matches.every(m=>!m.exact));orthogonal(snapped.polygon);
 const follow=G.followRectangleGT(snapped.polygon,p,snapped.matches,.12);check(follow&&S.cameraInside(follow.polygon));for(const m of follow.matches)coincident(follow.polygon,m.edge,p,m.gt_edge);check(follow.matches.every(m=>m.exact));
 check(Math.abs(G.cross(p[5],p[6],follow.polygon[2]))<1e-12,'screenshot upper edge on GT 6–7');check(Math.abs(G.cross(p[7],p[0],follow.polygon[1]))<1e-12,'screenshot lower edge on GT 8–1');
 const op={type:'gt_follow',lines:follow.lines},review={...S.fresh(source),operations:[op],polygon:follow.polygon,decision:'allow'};polyNear(S.verifyOps(source,review).polygon,follow.polygon);eq(G.replay(gt,[op]),follow.polygon,'resolved lines replay without consulting GT');
 const bad=S.clone(review);bad.operations[0].lines[0][0][0]=Infinity;assert.throws(()=>S.verifyOps(source,bad));checks++;
 const ui=await boot(),{w,el,get,event}=ui;check(w);check(el('gtSnap').checked,'default enabled in actual HTML');eq(w.exportData().editor_version,'3.3');eq(w.exportData().source_commit,DATA.source_commit);
 const oldConfirmations=w.exportData().records.filter(r=>r.confirmed_version).map(r=>({code:r.image_code,v:r.confirmed_version}));eq(oldConfirmations.length,16);
 w.loadImage(DATA.images.indexOf(source));w.setMode('rectangle');const before=w.getDraft();
 // Drag to the final pointer-up position, which can differ from the last move event.
 el('bev').onpointerdown(event(a));el('bev').onpointermove(event([b[0]-.2,b[1]-.2]));el('bev').onpointerup(event(b));
 eq(get('snapMatches.map(m=>m.gt_edge)'),[7,2,5,6]);check(el('snapStatus').textContent.includes('近似'));check(el('bev').innerHTML.includes('data-gt-snap="5"'));check(!el('followGT').disabled);orthogonal(get('preview'));eq(w.getDraft(),before,'preview does not edit stored draft');
 el('export').click();eq(ui.downloads.length,0);el('followGT').click();eq(get('edit.type'),'gt_follow');check(el('snapStatus').textContent.includes('可能略非直角'));check(!el('snapStatus').textContent.includes('近似对齐'));for(const m of get('snapMatches'))coincident(get('preview'),m.edge,p,m.gt_edge);
 el('cancel').click();eq(w.getDraft(),before);eq(get('snapMatches'),[]);check(el('followGT').disabled);el('gtSnap').checked=false;el('gtSnap').onchange();eq(get('edit'),null,'toggle cannot resurrect canceled preview');
 w.setRectangle(a,b,0);polyNear(get('preview'),G.rectangle(a,b,0));eq(get('snapMatches.length'),0,'off is free draw, including no vertex snap');el('gtSnap').checked=true;el('gtSnap').onchange();eq(get('snapMatches.length'),4);el('gtSnap').checked=false;el('gtSnap').onchange();polyNear(get('preview'),G.rectangle(a,b,0),'toggle re-resolves original pointer coordinates');
 el('gtSnap').checked=true;el('gtSnap').onchange();el('followGT').click();el('apply').click();const applied=w.getDraft();eq(applied.operations.at(-1).type,'gt_follow');polyNear(applied.polygon,follow.polygon);eq(w.exportData().records.filter(r=>r.confirmed_version).map(r=>({code:r.image_code,v:r.confirmed_version})),oldConfirmations);
 el('undo').click();eq(w.getDraft(),before);el('redo').click();eq(w.getDraft(),applied);el('gtSnap').onchange();eq(get('edit'),null,'toggle cannot resurrect applied preview');
 el('confirm').click();check(w.getConfirmation().floor_region_confirmed);eq(w.getConfirmation().operations.at(-1).type,'gt_follow');const confirmed=w.getConfirmation();
 el('export').click();eq(ui.downloads.length,1);const exported=w.exportData();check(exported.records.every(r=>r.reference_ready===false&&r.formal_eligibility_changed===false));
 const restarted=await boot(JSON.parse(ui.saved.get(KEY)));restarted.w.loadImage(DATA.images.indexOf(source));eq(restarted.w.getConfirmation(),confirmed);eq(restarted.w.getDraft().polygon,confirmed.polygon);eq(restarted.get('snapMatches'),[],'saved geometry never dynamically resnaps on boot');
 await restarted.el('file').onchange({target:{files:[{text:async()=>JSON.stringify(exported)}],value:'json'}});check(restarted.el('toast').textContent.includes('已导入'));eq(restarted.w.getDraft().polygon,confirmed.polygon);
 // Full-precision selected-axis direction, rather than a two-decimal display value.
 el('gtEdge').value='5';el('gtEdgeAxis').click();near(+el('axisAngle').value,G.edgeAngle(p,5),1e-14);check(Math.abs(+el('axisAngle').value-(+el('axisAngle').value).toFixed(2))>1e-6);w.setRectangle(a,b,+el('axisAngle').value);check(get('snapMatches.some(m=>m.gt_edge===5&&m.exact)'));el('cancel').click();
 // Cancel, Escape, repeated click and two-click paths keep confirmations untouched.
 w.setMode('rectangle');el('bev').onpointerdown(event(a));el('bev').onpointermove(event(b));el('bev').onpointercancel();eq(get('edit'),null);eq(w.getConfirmation(),confirmed);
 el('bev').onpointerdown(event(a));el('bev').onpointerup(event(a));check(get('!!first'));ui.handlers.keydown({key:'Escape'});eq(get('first'),null);
 el('bev').onpointerdown(event(a));el('bev').onpointerup(event(a));el('bev').onpointerdown(event(b));el('bev').onpointerup(event(b));check(get('!!preview'));el('cancel').click();
 // CSS resizing and zoom use actual screen pixels, not SVG viewBox units.
 for(const scale of [.5,1,1.7]){const t=await boot(null,scale);t.w.loadImage(DATA.images.indexOf(source));const pix=t.get('worldPerPixel()');near(pix,t.get('view.s/zoom')/scale);const y=p[6][1];t.w.setRectangle([-.7,y+9*pix],[1.4,-2],0);check(t.get('snapMatches.some(m=>m.gt_edge===5)'),'9 screen px snaps');t.el('cancel').click();t.w.setRectangle([-.7,y+11*pix],[1.4,-2],0);check(!t.get('snapMatches.some(m=>m.gt_edge===5)'),'11 screen px does not snap');t.el('cancel').click();t.el('zoomIn').click();near(t.get('worldPerPixel()'),pix/1.3)}
 // Edge-drag uses resolved offset and undo/redo retain exact inputs.
 el('gtSnap').checked=false;el('axisAngle').value='0';el('axisAngle').oninput();w.setRectangle(a,b,0);el('apply').click();const edgeBefore=w.getDraft();el('gtSnap').checked=true;w.setMode('edge');const q=w.getDraft().polygon,mid=[(q[1][0]+q[2][0])/2,(q[1][1]+q[2][1])/2];el('bev').onpointerdown(event(mid,{edge:'1'}));el('bev').onpointerup(event([mid[0]+.07,mid[1]]));check(get('snapMatches.some(m=>m.gt_edge===2)'));check(get('edit.type')==='edge_move');el('apply').click();const edgeApplied=w.getDraft();polyNear(G.replay(p,edgeApplied.operations),edgeApplied.polygon);orthogonal(edgeApplied.polygon);el('undo').click();eq(w.getDraft(),edgeBefore);el('redo').click();eq(w.getDraft(),edgeApplied);eq(w.getConfirmation(),confirmed);
 // Full-GT choice and navigation discard every transient snap input.
 w.setRectangle(a,b,0);check(get('!!rawEdit'));ui.choices[1].onclick();eq(get('rawEdit'),null);eq(get('snapMatches'),[]);el('gtSnap').onchange();el('axisAngle').oninput();eq(get('edit'),null);eq(get('preview'),null);eq(w.getDraft().polygon,p);el('undo').click();eq(w.getDraft(),edgeApplied);
 el('rectify').click();check(get('preview').every(v=>G.inside(v,get('preview'))));check(w.getDraft().polygon.every(v=>G.inside(v,get('preview'))),'rectify still covers current polygon without inward snap');el('cancel').click();
 w.setMode('rectangle');el('photoMode').click();check(get('photoMode'));w.setMode('rectangle');check(!get('photoMode'));eq(get('rawEdit'),null);
 const prior=JSON.parse(fs.readFileSync('fixtures/published-v3.2-data.json')).images.find(c=>c.image_code==='pRbA3pwrgk9-02'),priorGT=G.floor(prior.reference_points_1024x512),priorPoly=prior.confirmed_review.polygon;
 check(!G.edgeSnapCandidates(priorPoly[1],priorPoly[2],priorGT,.15).some(m=>m.gt_edge===2),'pRb confirmed right edge is not snapped to a remote finite wall segment');
 const received16=S.initialize(DATA,null).confirmations;for(const [code,c]of Object.entries(received16)){if(code===source.image_code)continue;const e=w.exportData().records.find(r=>r.image_code===code);eq(e.confirmed_version,c);eq(e.polygon,c.polygon)}eq(w.getConfirmation(),confirmed,'the deliberately edited case keeps its newly button-confirmed snapshot')
 const qa={gt_snap_checks_passed:checks,screenshot_case:source.image_code,received_confirmations:16,unmodified_confirmations_preserved:15,screen_pixel_threshold:10,geometry:'Exact only for parallel lines; near-parallel snapping labeled approximate. Explicit GT-follow stores four resolved lines and replays independently of snapping.',browser_QA:'Mock DOM and pointer regression passed. No real browser visual or pointer pass claimed.',tested_on:'2026-10-10'};fs.writeFileSync('QA-gt-snap.json',JSON.stringify(qa,null,2)+'\n');console.log(qa);
})().catch(e=>{console.error(e);process.exitCode=1});
