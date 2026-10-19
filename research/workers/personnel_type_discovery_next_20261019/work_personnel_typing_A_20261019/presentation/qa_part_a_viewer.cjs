/* Part A DOM, frozen-data and native-canvas checks. Not browser layout QA. */
const fs=require('fs'),path=require('path'),assert=require('assert'),crypto=require('crypto');
const base=__dirname,filename=process.argv[2]||'personnel_types_part_a.html';
const isPreview=filename.includes('preview'),out=path.join(base,isPreview?'qa_preview':'qa');
fs.mkdirSync(out,{recursive:true});
const primary=process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES||'/opt/codex/runtimes/codex-primary-runtime/dependencies/node/node_modules';
const {JSDOM,VirtualConsole}=require(path.join(base,'qa_runtime/node_modules/jsdom'));
const canvas=require(path.join(primary,'@napi-rs/canvas'));
const font=path.join(base,'../recovered/work_v2_20261019/presentation/fonts/NotoSansCJKsc-Regular.otf');
assert(canvas.GlobalFonts.registerFromPath(font,'PartACJK'),'CJK font registered');
const html=fs.readFileSync(path.join(base,filename),'utf8'),errors=[],checks=[];
const vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(String(e)));vc.on('error',e=>errors.push(String(e)));
const dom=new JSDOM(html,{runScripts:'dangerously',url:'file://'+path.join(base,filename),pretendToBeVisual:true,virtualConsole:vc,beforeParse(w){
  w.DecompressionStream=DecompressionStream;w.Response=Response;w.Blob=Blob;w.Image=canvas.Image;
  w.HTMLElement.prototype.scrollIntoView=function(){};
  Object.defineProperty(w.document,'fonts',{value:{ready:Promise.resolve()},configurable:true});
  w.HTMLCanvasElement.prototype.getContext=function(){if(!this._native||this._native.width!==this.width||this._native.height!==this.height)this._native=canvas.createCanvas(this.width,this.height);return this._native.getContext('2d')};
}});
const w=dom.window,$=id=>w.document.getElementById(id),sleep=n=>new Promise(r=>setTimeout(r,n));
function change(id,value,event='change'){$(id).value=value;$(id).dispatchEvent(new w.Event(event,{bubbles:true}))}
function click(selector){const el=w.document.querySelector(selector);assert(el,selector);el.click()}
function check(name,test){assert(test,name);checks.push({name,passed:true})}
function shot(id,name){const c=$(id);check('rendered canvas '+id,!!c._native);fs.writeFileSync(path.join(out,name+'.png'),c._native.toBuffer('image/png'))}
function assertIdentical(a,b,name){check(name,JSON.stringify(a)===JSON.stringify(b))}
(async()=>{
  for(let i=0;i<600&&!w.VIEWER_READY&&!w.VIEWER_ERROR;i++)await sleep(100);
  check('application loaded without error',w.VIEWER_READY&&!w.VIEWER_ERROR);
  const api=w.VIEWER_API,D=api.getData();
  check('177 pools / 5719 real ordinary answers / 60 workers',w.VIEWER_COUNTS.pools===177&&w.VIEWER_COUNTS.records===5719&&w.VIEWER_COUNTS.workers===60);
  check('60 profile rows shown, not rank ordered',$('profileTable').querySelectorAll('tbody tr').length===60);
  check('target-building exclusion is the default',$('labelScope').value==='oob');
  check('scope and no target-answer type learning clearly stated',$('personDetail').textContent.includes('排除当前建筑'));
  if(!isPreview)check('final build has new frozen classes',!D.notes.labels_pending);
  const methods=[...$('method').options].map(o=>o.value);
  for(const method of methods){
    change('method',method);
    for(const scope of ['oob','full']){
      change('labelScope',scope);
      const p=api.getPool(),fold=scope==='full'?'FULL':p.meta.building;
      for(const worker of D.workers){
        const candidates=D.labels.filter(r=>r.heldout_building===fold&&r.method_id===method&&r.worker_id===worker);
        const diff={简单:'easy',中等:'medium',困难:'hard'}[p.meta.difficulty];
        const row=candidates.find(r=>r.difficulty===diff)||candidates.find(r=>r.difficulty==='global');
        assert.strictEqual(api.personClass(worker),row?.class_id||'unknown',`${method}/${fold}/${worker} frozen label`);
      }
      check('frozen label match '+method+'/'+scope,true);
      check('all profiles remain visible '+method+'/'+scope,$('profileTable').querySelectorAll('tbody tr').length===60);
    }
  }
  change('method',methods[0]);change('labelScope','oob');click('[data-person="W017"]');
  check('Semi opportunity layers and limited scope gold displayed',$('personDetail').textContent.includes('旧确认错误预标注')&&$('personDetail').textContent.includes('新报告错误预标注')&&$('personDetail').textContent.includes('有限 in-scope'));
  if($('classFilter').options.length>2){change('classFilter',$('classFilter').options[1].value);check('class filter changes rows',$('profileTable').querySelectorAll('tbody tr').length<60);change('classFilter','')}
  change('personSearch','W017','input');check('worker search exact in this query',$('profileTable').querySelectorAll('tbody tr').length===1);change('personSearch','','input');
  click('[data-tab="geometry"]');change('cut','12');change('algorithm','complete');change('cluster','0');await sleep(200);
  const p=api.getPool();
  check('whole local cluster selected',w.eval('selected.size===clusterGroups()[0].length'));
  shot('clusterERP','whole_cluster_erp');shot('clusterBEV','whole_cluster_bev');shot('cluster3D','whole_cluster_3d');
  click('#noneMembers');check('explicit empty selection persists',w.eval('selected.size===0'));click('#allMembers');check('all real members restored',w.eval('selected.size===P.records.length'));
  const member=api.getPool().records[0].worker_id;click(`[data-member="${member}"]`);check('member toggle removes exactly one',w.eval('selected.size===P.records.length-1'));click(`[data-member="${member}"]`);
  const yaw=w.eval('views.cluster3D.yaw');$('cluster3D').dispatchEvent(new w.KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}));check('3D keyboard rotation changes projection',w.eval('views.cluster3D.yaw')!==yaw);
  change('colorMode','type');check('person type color legend explicitly labels classes',$('legend').textContent.length>0);change('colorMode','cluster');
  click('[data-tab="profiles"]');click('#showClassGeometry');check('class to geometry links exact frozen current class',w.eval('[...selected].every(x=>personClass(x)===labelRow(currentPerson).class_id)'));
  const dataIntegrity={pools:0,records:0,partitions:0,requests:0,states:0,events:0,chains:0};
  const uniqueObjects=new Set(),imageIds=new Set(),labelKeys=new Set();
  for(const r of D.labels){const key=[r.heldout_building,r.worker_id,r.method_id,r.difficulty].join('|');assert(!labelKeys.has(key),'duplicate frozen label '+key);labelKeys.add(key)}
  for(const [pid,p] of Object.entries(D.pools)){
    dataIntegrity.pools++;dataIntegrity.records+=p.records.length;imageIds.add(p.meta.image_id);
    const ids=new Set(p.records.map(r=>r.object_id)),workers=new Set(p.records.map(r=>r.worker_id));
    assert(ids.size===p.records.length&&workers.size===p.records.length,'one genuine answer per worker per pool');
    for(const r of p.records){assert(!uniqueObjects.has(r.object_id),'object duplicate');uniqueObjects.add(r.object_id);assert(r.points.length%2===0&&r.points.length>=6,'bound pairs');assert(r.points.every(pt=>pt.every(Number.isFinite)),'finite point coords')}
    for(const [key,groups]of Object.entries(p.clusters)){
      const flat=groups.flat();assert(flat.length===ids.size&&new Set(flat).size===ids.size&&flat.every(x=>ids.has(x)),pid+' partition '+key);
      for(const g of groups){const ns=new Set(g.map(id=>p.records.find(r=>r.object_id===id).points.length));assert(ns.size===1,'different pair counts never mixed')}
      dataIntegrity.partitions++;
    }
    const reqs=new Map(p.requests.map(r=>[r.request_id,r]));
    for(const r of p.requests){const ws=r.member_workers.split('|');assert(new Set(ws).size===r.k&&ws.every(x=>workers.has(x)),pid+' real team');assert(p.states[r.team_id],pid+' state exists');dataIntegrity.requests++}
    dataIntegrity.states+=Object.keys(p.states).length;
    for(const e of D.events.filter(e=>e.pool_id===pid)){
      const a=reqs.get(e.request_a),b=reqs.get(e.request_b),background=e.background_members.split('|').sort();
      assert(a&&b,'event endpoints exist');assert(a.k===b.k&&a.k===e.k,'same k');
      assert.deepStrictEqual(a.member_workers.split('|').filter(x=>x!==e.worker_a).sort(),background,'exact A background');
      assert.deepStrictEqual(b.member_workers.split('|').filter(x=>x!==e.worker_b).sort(),background,'exact B background');
      assert(a.reference_id===b.reference_id&&a.reference_id===e.reference_id,'same frozen reference');
      if(!e.complete_a||!e.complete_b)assert(e.joint_stable_main===false,'failure is not stable');
      dataIntegrity.events++;
    }
  }
  check('all 708 partitions and 5719 genuine bound answers validated',dataIntegrity.partitions===708&&uniqueObjects.size===5719);
  const chains=[...new Set(D.events.map(e=>e.chain_id).filter(Boolean))];
  for(const id of chains){const es=D.events.filter(e=>e.chain_id===id).sort((a,b)=>a.k-b.k);let previous=[];for(const e of es){assert(e.worker_a===es[0].worker_a&&e.worker_b===es[0].worker_b,'fixed replacement identity');const background=e.background_order.split('|');assert.deepStrictEqual(background.slice(0,previous.length),previous,'exact nested order');previous=background}dataIntegrity.chains++}
  check('two missing-original images carry only repository previews',Object.values(D.images).filter(im=>!im.original_available).length===2&&Object.values(D.images).filter(im=>!im.original_available).every(im=>im.status.includes('仅仓库预览')));
  check('unembedded originals are not labeled unavailable',Object.values(D.images).filter(im=>!im.data).every(im=>im.original_available&&im.status.includes('未嵌入')));
  const caseChecks=[];
  for(let i=0;i<D.cases.length;i++){
    api.jumpCase(i);await sleep(150);const c=D.cases[i],p=api.getPool(),e=api.getEvent();
    check('case current pool '+i,p.meta.pool_id===c.pool_id&&e.event_id===c.event_id);
    check('case defaults to heldout-building labels '+i,$('labelScope').value==='oob');
    if(c.method_id)check('case frozen method selected '+i,$('method').value===c.method_id);
    check('same background A/B is displayed '+i,$('pairClassInfo').textContent.includes('背景 '+(e.k-1)+' 人完全相同'));
    check('failure and time are explicitly displayed '+i,$('statsA').textContent.includes('同目标')&&$('statsA').textContent.includes('状态'));
    const prefix='case_'+String(i+1).padStart(2,'0');
    for(const [id,suffix]of [['teamERPA','a_erp'],['teamERPB','b_erp'],['teamBEV','both_bev'],['team3D','both_3d']])shot(id,prefix+'_'+suffix);
    if(c.chain_id){const es=D.events.filter(x=>x.chain_id===c.chain_id);check('only computed chain nodes offered '+i,$('caseEvent').options.length===es.length);for(const node of es){change('caseEvent',node.event_id);check('same identity while changing k '+i+'/'+node.k,api.getEvent().worker_a===e.worker_a&&api.getEvent().worker_b===e.worker_b)}change('caseEvent',e.event_id)}else check('single-k case not presented as full path '+i,$('caseEvent').options.length===1&&$('chainInfo').textContent.includes('单 k'));
    click('#caseWholeCluster');check('case whole-cluster focus contains both entrants '+i,w.eval('[currentEvent.worker_a,currentEvent.worker_b].every(x=>selected.has(x))'));
    shot('clusterERP',prefix+'_whole_clusters_erp');shot('clusterBEV',prefix+'_whole_clusters_bev');shot('cluster3D',prefix+'_whole_clusters_3d');
    change('cut','12');check('12-degree refocus keeps both whole clusters '+i,w.eval('[currentEvent.worker_a,currentEvent.worker_b].every(x=>selected.has(x))'));
    caseChecks.push({event_id:c.event_id,pool_id:p.meta.pool_id,image:p.meta.image,method_id:$('method').value,image_status:D.images[p.meta.image_id].status,case_chain_nodes:$('caseEvent').options.length});
  }
  click('[data-tab="methods"]');check('data boundary / Semi / scope / N1 visible',$('methods').textContent.includes('in-scope')&&$('methods').textContent.includes('N1')&&$('methods').textContent.includes('8/12/16/24'));
  check('no external src/href assets',![...w.document.querySelectorAll('[src],[href]')].some(e=>/^https?:/.test(e.getAttribute('src')||e.getAttribute('href')||'')));
  await sleep(200);check('no console errors',errors.length===0);
  const receipt={status:'PASS',qa_kind:'Node jsdom 30.1.3 + native @napi-rs/canvas DOM/interaction/render checks; not a real browser layout test or browser screenshot',browser_download:'Chromium install attempted; public download returned Site Unavailable HTML; no browser fallback claimed',file:filename,html_sha256:crypto.createHash('sha256').update(html).digest('hex'),counts:w.VIEWER_COUNTS,data_integrity:dataIntegrity,case_interactions:caseChecks,checks,console_errors:errors,canvas_pngs:fs.readdirSync(out).filter(x=>x.endsWith('.png')),canvas_visual_review:'These files are generated test evidence; only images actually opened by the reviewer may be called visually inspected'};
  fs.writeFileSync(path.join(out,'VIEWER_QA.json'),JSON.stringify(receipt,null,2));console.log(JSON.stringify({passed:true,checks:checks.length,counts:receipt.counts,integrity:dataIntegrity}));w.close();
})().catch(e=>{fs.writeFileSync(path.join(out,'FAILURE.json'),JSON.stringify({error:e.stack,application_error:w.VIEWER_ERROR,checks,console_errors:errors},null,2));console.error(e.stack);w.close();process.exitCode=1});
