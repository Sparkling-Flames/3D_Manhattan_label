/* DOM, interaction, and native canvas QA. Not a real-browser layout test. */
const fs=require('fs'),path=require('path'),assert=require('assert'),crypto=require('crypto');
const base=__dirname,out=path.join(base,'qa');fs.mkdirSync(out,{recursive:true});
function dep(name){for(const root of [path.join(base,'../../work_20261018/presentation/qa_deps/node_modules'),process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES].filter(Boolean)){try{return require(path.join(root,name))}catch(e){}}return require(name)}
const {JSDOM,VirtualConsole}=dep('jsdom'),canvas=dep('@napi-rs/canvas');
canvas.GlobalFonts.registerFromPath(path.join(base,'fonts/NotoSansCJKsc-Regular.otf'),'Noto Sans CJK SC');
let filename=process.argv[2]||'personnel_fusion_v2_viewer.html',html=fs.readFileSync(path.join(base,filename),'utf8'),errors=[],checks=[];
const vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(String(e)));vc.on('error',e=>errors.push(String(e)));
const dom=new JSDOM(html,{runScripts:'dangerously',url:'file://'+path.join(base,filename),pretendToBeVisual:true,virtualConsole:vc,beforeParse(w){
 w.DecompressionStream=DecompressionStream;w.Response=Response;w.Blob=Blob;w.Image=canvas.Image;
 w.HTMLElement.prototype.scrollIntoView=function(){};
 w.HTMLCanvasElement.prototype.getContext=function(){if(!this._native||this._native.width!==this.width||this._native.height!==this.height)this._native=canvas.createCanvas(this.width,this.height);return this._native.getContext('2d')};
 }});
const w=dom.window,$=id=>w.document.getElementById(id),sleep=n=>new Promise(r=>setTimeout(r,n));
function change(id,value,event='change'){$(id).value=value;$(id).dispatchEvent(new w.Event(event,{bubbles:true}))}
function click(selector){let el=w.document.querySelector(selector);assert(el,selector);el.click()}
function check(name,test){assert(test,name);checks.push({name,passed:true})}
function shot(id,name){let c=$(id);check('canvas '+id,!!c._native);fs.writeFileSync(path.join(out,name+'.png'),c._native.toBuffer('image/png'))}
(async()=>{
 for(let i=0;i<600&&!w.VIEWER_READY&&!w.VIEWER_ERROR;i++)await sleep(100);
 check('loaded without application error',w.VIEWER_READY&&!w.VIEWER_ERROR);
 check('60 supported-or-explicitly-thin personnel profiles shown',$('profileTable').querySelectorAll('tbody tr').length===60);
 check('default heldout-building training displayed',$('personDetail').textContent.includes('排除'));
 change('profileScope','full');change('metric','D10');click('[data-person="W002"]');check('difficulty support and uncertainty visible',$('personDetail').textContent.includes('建筑jackknife')&&$('personDetail').textContent.includes('难−中'));
 change('personClass',$('personClass').options[1].value);check('fine-class selector filters real members',$('profileTable').querySelectorAll('tbody tr').length<60);change('personClass','');change('profileScope','oob');change('metric','B8L2');
 click('[data-tab="clusters"]');change('cut','12');change('algorithm','complete');change('cluster','1');await sleep(150);
 check('whole cluster is selected',w.eval("(()=>{let ids=P.clusters[$('cut').value+'_'+$('algorithm').value][Number($('cluster').value)];return selected.size===ids.length})()"));
 shot('clusterERP','cluster_erp');shot('clusterBEV','cluster_bev');shot('cluster3D','cluster_3d');
 click('#noneMembers');check('explicit empty member selection persists',w.eval('selected.size===0'));click('#allMembers');check('all members restored',w.eval('selected.size===P.records.length'));
 let yaw=w.eval('views.cluster3D.yaw');$('cluster3D').dispatchEvent(new w.KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}));check('3D keyboard rotation changes real view',w.eval('views.cluster3D.yaw')!==yaw);
 click('[data-tab="teams"]');await sleep(100);check('two actual teams selected',!!$('teamA').value&&!!$('teamB').value);shot('teamERPA','team_a_erp');shot('teamBEVA','team_a_bev');shot('team3DA','team_a_3d');
 let a=$('teamA').value,b=$('teamB').value;change('teamA',b);change('teamB',a);check('reverse A/B works without inventing missing time',$('difference').textContent.includes('B8L2 / D10'));
 click('[data-tab="paths"]');change('step','2','input');await sleep(100);check('actual k2 policy gap retained',$('pathTransition').textContent.includes('暂不连接')&&w.eval("state(req(P.paths[Number($('path').value)||0].requests[1])).points===null"));shot('pathERP','path_k2');
 change('step','3','input');check('k3 recovery not called improvement',$('pathTransition').textContent.includes('不把恢复评分称作质量提升'));shot('path3D','path_k3_3d');shot('pathPlot','path_quality_curve');
 click('[data-tab="methods"]');check('scope and source boundary visible',$('methods').textContent.includes('in-scope')&&$('methods').textContent.includes('未接入'));
 const caseChecks=[];
 for(let i=0;i<w.eval('D.cases.length');i++){
  click('[data-tab="cases"]');click('[data-case="'+i+'"]');await sleep(80);
  let info=w.eval(`(()=>{let c=D.cases[${i}];return{id:c.case_id,pool:c.pool_id,actual_pool:P.meta.pool_id,has_teams:!!c.request_a,a:c.request_a,b:c.request_b,focus:c.workers||[],selected:[...selected],image_status:D.images[P.meta.image_id].status}})()`);
  check('case pool '+info.id,info.pool===info.actual_pool);
  if(info.has_teams){
   check('case real teams '+info.id,$('teamA').value===info.a&&$('teamB').value===info.b);
   check('case saved V comparison '+info.id,!$('difference').textContent.includes('无已存比较'));
   for(const [id,suffix]of [['teamERPA','erp_a'],['teamERPB','erp_b'],['teamBEVA','bev_a'],['teamBEVB','bev_b'],['team3DA','3d_a'],['team3DB','3d_b']])shot(id,info.id+'_'+suffix);
  }else{
   check('case whole-cluster focus retained '+info.id,info.focus.length?info.focus.every(x=>info.selected.includes(x)):info.selected.length>0);
   for(const [id,suffix]of [['clusterERP','erp'],['clusterBEV','bev'],['cluster3D','3d']])shot(id,info.id+'_'+suffix);
  }
  caseChecks.push(info);
 }
 const all=w.eval(`(()=>{let requests=0,states=0,partitions=0,paths=0;for(let p of Object.values(D.pools)){let objects=new Set(p.records.map(r=>r.object_id)),workers=new Set(p.records.map(r=>r.worker_id));for(let gs of Object.values(p.clusters)){let ids=gs.flat();if(ids.length!==objects.size||new Set(ids).size!==objects.size||ids.some(x=>!objects.has(x)))throw Error('invalid partition');partitions++;}let reqs=new Map(p.requests.map(r=>[r.request_id,r]));for(let r of p.requests){let ws=r.member_workers.split('|');if(!p.states[r.team_id]||new Set(ws).size!==r.k||ws.some(x=>!workers.has(x)))throw Error('invalid genuine member set');requests++;}for(let c of p.comparisons)if(!reqs.has(c.request_a)||!reqs.has(c.request_b))throw Error('comparison endpoint missing');for(let pt of p.paths){let order=reqs.get(pt.requests.at(-1)).ordered_workers.split('|');for(let i=0;i<pt.requests.length;i++){let r=reqs.get(pt.requests[i]),actual=r.member_workers.split('|').sort().join('|');if(r.k!==i+1||actual!==order.slice(0,i+1).sort().join('|'))throw Error('invalid true prefix');}paths++;}states+=Object.keys(p.states).length;}return{requests,states,partitions,paths}})()`);
 check('all genuine memberships/partitions/prefixes verified',all.requests===w.VIEWER_COUNTS.teams&&all.partitions===w.VIEWER_COUNTS.pools*4);
 check('no external assets',![...w.document.querySelectorAll('[src],[href]')].some(e=>/^https?:/.test(e.getAttribute('src')||e.getAttribute('href')||'')));
 check('no console errors',errors.length===0);
 let receipt={qa_kind:'Node jsdom + native @napi-rs/canvas interaction/render verification; not a real browser layout screenshot',file:filename,sha256:crypto.createHash('sha256').update(html).digest('hex'),counts:w.VIEWER_COUNTS,data_integrity:all,case_interactions:caseChecks,checks,console_errors:errors,canvas_pngs:fs.readdirSync(out).filter(x=>x.endsWith('.png'))};
 fs.writeFileSync(path.join(out,'VIEWER_QA'+(filename.includes('pilot')?'_PILOT':'')+'.json'),JSON.stringify(receipt,null,2));console.log(JSON.stringify({passed:true,checks:checks.length,counts:receipt.counts,integrity:all}));w.close();
})().catch(e=>{fs.writeFileSync(path.join(out,'FAILURE.json'),JSON.stringify({error:e.stack,application_error:w.VIEWER_ERROR,checks,console_errors:errors},null,2));console.error(e.stack);w.close();process.exitCode=1});
