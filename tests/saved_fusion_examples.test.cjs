const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const page=path.resolve(__dirname,'../research/statistics/research_explorer_v1_r2_20261017'),C=require(path.join(page,'workbench-core.js'));
const scope={window:{},WorkbenchCore:C,URLSearchParams};vm.createContext(scope);vm.runInContext(fs.readFileSync(path.join(page,'research-comparison.js'),'utf8'),scope);const R=scope.window.ResearchComparison;
test('missing integration, reference mismatch and real failure states remain distinct',()=>{
 const ref={target_id:'ref',points:[[1,2]],floor:[[1,2]]},image={image_id:'i',references:[ref]},selection={image:'i',condition:'manual'};
 const args={snapshot:'frozen',assetsSnapshot:'frozen'},saved={image_id:'i',condition:'manual',reference:ref,teams:[{label:'full',nodes:3,score_status:'below_four',B8L2:null}]};
 assert.equal(R.resolveContext(image,[],selection,args).availability,'not_integrated');
 assert.equal(R.resolveContext(image,[saved],{...selection,reference:'other'},args).availability,'reference_mismatch');
 assert.equal(R.resolveContext(image,[saved],selection,{...args,assetsSnapshot:'other'}).availability,'snapshot_mismatch');
 assert.equal(R.resolveContext(image,[saved],selection,args).teams.length,1);
 for(const kind of ['below_four','no_connection','invalid_floor','policy_deferred'])assert.equal(R.teamStatus({score_status:kind,nodes:3}).kind,kind);
 assert.equal(R.teamStatus({score_status:'complete_conditional',nodes:4,complete_evaluable:true}).kind,'geometry_not_loaded');
 assert.equal(R.teamStatus({score_status:'unscorable_saved',nodes:5,complete_evaluable:false}).kind,'diagnostic');
 assert.match(R.teamLedger({workers:Array(32),minimum_support:16,nodes:3,identity_groups_n:14,unselected_groups_n:11,selected_node_supports:[19,25,26]}),/没有逐节点ID绑定/);
});
test('three-node diagnostic coordinates remain visible in BEV and 3D without a closed layout',()=>{
 const calls={dots:0,lines:0},ctx={scale(){},clearRect(){calls.dots=0;calls.lines=0;},setLineDash(){},beginPath(){},arc(){calls.dots++;},fill(){},moveTo(){},lineTo(){calls.lines++;},stroke(){},fillRect(){},fillText(){},measureText(){return {width:50};}};
 const nodes=new Map(),host={isConnected:true,querySelector(id){if(id==='img')return null;if(!nodes.has(id))nodes.set(id,{style:{},value:1,checked:id==='[data-top]',setAttribute(){},getBoundingClientRect:()=>({width:600,height:350}),getContext:()=>ctx});return nodes.get(id);},querySelectorAll:()=>[]};
 const env={window:{WorkbenchCore:C},devicePixelRatio:1,ResizeObserver:class{observe(){}}};vm.createContext(env);vm.runInContext(fs.readFileSync(path.join(page,'geometry-view.js'),'utf8'),env);
 env.window.WorkbenchGeometry.mount(host,{},null,null,{points:[[100,200],[100,300],[400,200],[400,300],[800,200],[800,300]],connected:false,diagnostic:true});
 for(const [view,dots] of [['bev',3],['3d',6]]){nodes.get('[data-view]').onchange({target:{value:view}});assert.equal(calls.dots,dots);assert.equal(calls.lines,0);}
 assert.match(host.innerHTML,/仅画点，不闭合/);
});
const payloadPath=path.join(page,'v2-resources/comparisons.json');
test('actual M05 doorway route resolves the saved 35-person four-pair result and preserves failures',{skip:!fs.existsSync(payloadPath)},async()=>{
 const read=p=>JSON.parse(fs.readFileSync(p,'utf8')),payload=read(payloadPath),assets=read(path.join(page,'v2-resources/index.json'));
 const meta=assets.images.find(i=>i.image_code==='jtcxE69GiFV-12'),image=read(path.join(page,'v2-resources',meta.detail));
 const old=payload.cases.find(c=>c.case_id.startsWith('M05')&&c.image_id===meta.image_id);assert(old);
 const found=R.resolveContext(image,payload.cases,{case:old.case_id,image:meta.image_id,condition:'manual'},{snapshot:assets.snapshot_id,assetsSnapshot:assets.snapshot_id,payload});
 assert.equal(found.availability,'available');const team=found.teams[0];assert.equal(team.workers.length,35);assert.equal(team.nodes,4);assert.equal(team.points.length,8);assert.equal(team.B8L2,37.341654940505336);
 const doorway=payload.cases.filter(c=>c.case_id.startsWith('D_FULL_'));assert.equal(doorway.length,17);assert.equal(doorway.filter(c=>c.teams[0].complete_evaluable===false).length,6);
 for(const c of payload.cases.filter(c=>/^(D_FULL_|F_SAVED_)/.test(c.case_id))){const current=read(path.join(page,'v2-resources',assets.images.find(i=>i.image_id===c.image_id).detail));assert.equal(R.resolveContext(current,payload.cases,{case:c.case_id,image:c.image_id,condition:c.condition},{snapshot:assets.snapshot_id,assetsSnapshot:assets.snapshot_id,payload}).availability,'available',c.case_id);}
 const ordinary=payload.cases.filter(c=>c.case_id.startsWith('F_SAVED_'));assert(ordinary.some(c=>c.condition==='semi'&&c.teams[0].nodes===3));assert(ordinary.some(c=>c.teams[0].nodes>=6&&c.teams[0].score_status==='no_connection'));
 const failure=payload.cases.find(c=>c.case_id==='D_FULL_7y3sRwLe3Va-06').teams[0];assert.equal(failure.B8L2,null);assert.equal(failure.nodes,3);assert.equal(failure.points.length,6);assert.deepEqual(failure.selected_node_supports,[19,25,26]);
 assert.match(R.failureOverviewHTML(payload.failure_summary),/54\/177/);
 class Host{constructor(){this.dataset={};this.isConnected=true;this.nodes=new Map();this.html='';}set innerHTML(s){this.html=s;this.nodes.clear();}get innerHTML(){return this.html;}querySelector(id){if(!this.nodes.has(id))this.nodes.set(id,{value:'',checked:false,innerHTML:''});return this.nodes.get(id);}}
 const mounted=[],host=new Host();scope.WorkbenchGeometry={mount:(...args)=>mounted.push(args)};
 const options={mode:'patterns',assets,snapshot:assets.snapshot_id,release:'v2',read:async()=>payload,loadImage:async id=>read(path.join(page,'v2-resources',assets.images.find(i=>i.image_id===id).detail)),filters:{},isCurrent:()=>true};
 await R.render(host,{...options,deepLink:new URLSearchParams({image:meta.image_id,condition:'manual',case:old.case_id})});
 assert.match(host.querySelector('#rc-teams').innerHTML,/35人/);assert.match(host.querySelector('#rc-teams').innerHTML,/4个上下点对、8个顶底点/);
 assert.equal(mounted.at(-1)[5].layers[0].points,team.points);
 const door=payload.cases.find(c=>c.case_id==='D_FULL_7y3sRwLe3Va-06');
 await R.render(host,{...options,deepLink:new URLSearchParams({image:door.image_id,condition:'manual',case:door.case_id,cmp_pair:'n=10'})});
 assert.match(host.querySelector('#rc-teams').innerHTML,/真实节点不足/);assert.match(host.querySelector('#rc-teams').innerHTML,/真实连接失败/);assert.match(host.querySelector('#rc-teams').innerHTML,/B8L2 缺失/);
 assert(mounted.at(-1)[5].layers.some(l=>l.diagnostic&&l.points.length===6&&l.confirmed===false));
});
