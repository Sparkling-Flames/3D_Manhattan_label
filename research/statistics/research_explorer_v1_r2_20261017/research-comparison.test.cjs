const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const C=require('./workbench-core.js');
const ctx={window:{},WorkbenchCore:C,URLSearchParams};vm.createContext(ctx);
vm.runInContext(fs.readFileSync(__dirname+'/research-comparison.js','utf8'),ctx);
const R=ctx.window.ResearchComparison;
const answers=[{object_id:'old',worker_id:'W008',retained:true,points:[[1,2],[1,3]]},
 {object_id:'new',worker_id:'W100',retained:true,points:[[2,2],[2,3]]}];
const filtered=answers.filter(a=>a.worker_id==='W100');
assert.equal(C.selectAnnotation(filtered,'old').worker_id,'W100');
const labels={W100:{Rnew2_geometry_quality_class:'C01'}};
assert.equal(R.classOf(answers[0],'Rnew2',labels),'类别未知');
assert.equal(R.layers(answers,'Rnew2',labels,{},'C01','W100').length,1);
const layer=R.layers(answers,'Rnew2',labels,{},'C01','W100')[0];
assert.equal(layer.id,'new');assert.equal(layer.highlight,true);
assert.equal(layer.points,answers[1].points); // use exact frozen coordinates
assert.equal(R.layers(answers,'Rnew2',labels,{},'all','').length,2); // unknowns stay visible

// The actual pack_comparisons v1 contract has no per-case, payload or image snapshot stamp.
// Its authoritative snapshot is the accompanying resource index, not an invented mandatory field.
const snapshot='v2_integrated_analysis_20261019';
const ref={target_id:'gt:image-a:current',points:[[1,2],[3,4]],floor:[[1,2],[3,4]]};
const image={image_id:'image-a',references:[{...ref,current:true}],annotations:answers};
const teams=[{label:'A',team_key:'saved-team-a',workers:['W008']},{label:'C',team_key:'saved-team-c',workers:['W100']}];
const caseA={case_id:'S07_reverse_new2',image_id:'image-a',condition:'manual',reference:ref,teams};
const payload={schema:'research_workbench_saved_comparisons_v1',cases:[caseA]};
const contextArgs={snapshot,assetsSnapshot:snapshot,payload};
const selection={case:caseA.case_id,image:'image-a',condition:'manual',team:'A',worker:'W008',cls:'C01',scheme:'Rnew2',pair:'C',reference:''};
let found=R.resolveContext(image,[caseA],selection,contextArgs);
assert.equal(found.fusionCase,caseA);assert.equal(found.teams,teams);assert.equal(found.snapshotOK,true);
// Exact documented regression: selected manual case must not leak teams/reference into Semi.
const semiRef={target_id:'gt:image-a:semi',points:[[9,2],[9,4]],floor:[[9,2],[9,4]],current:true};
const dualRefImage={...image,references:[ref,semiRef]};
found=R.resolveContext(dualRefImage,[caseA],{...selection,condition:'semi'},contextArgs);
assert.equal(found.case,null);assert.equal(found.reference.target_id,semiRef.target_id);assert.equal(found.teams.length,0);
assert.match(found.notices.join(' '),/条件/);
assert.equal(R.resolveContext({...image,image_id:'image-b'},[caseA],selection,contextArgs).teams.length,0);
assert.equal(R.resolveContext(image,[{...caseA,reference:{...ref,target_id:'other'}}],selection,contextArgs).teams.length,0);
assert.equal(R.resolveContext(image,[{...caseA,reference:{...ref,points:[[99,2]]}}],selection,contextArgs).teams.length,0);
assert.equal(R.resolveContext(image,[{...caseA,reference:{...ref,floor:[[99,2]]}}],selection,contextArgs).teams.length,0);
assert.equal(R.resolveContext(image,[caseA],{...selection,reference:'missing'},contextArgs).reference,undefined);
assert.equal(R.resolveContext(image,[caseA],{...selection,reference:'missing'},contextArgs).teams.length,0);
for(const arg of [{...contextArgs,snapshot:'other'}, {...contextArgs,requestedSnapshot:'other'}, {...contextArgs,payload:{...payload,snapshot_id:'other'}}, {...contextArgs,snapshot:null}]){
 assert.equal(R.resolveContext(image,[caseA],selection,arg).teams.length,0);
}
assert.equal(R.resolveContext({...image,snapshot_id:'other'},[caseA],selection,contextArgs).teams.length,0);
assert.equal(R.resolveContext(image,[{...caseA,snapshot_id:'other'}],selection,contextArgs).teams.length,0);
const semiCase={...caseA,case_id:'semi-saved',condition:'semi',reference:semiRef};
assert.equal(R.resolveContext(dualRefImage,[caseA,semiCase],{...selection,condition:'semi'},contextArgs).fusionCase,semiCase);

for(const key of ['case','image','condition','layer','reference']){
 const s={...selection};R.changeSelection(s,key,key==='case'?'another':key==='condition'?'semi':'other',[caseA]);
 assert.equal(s.team,'all');assert.equal(s.cls,'all');assert.equal(s.worker,'');
 if(key==='condition')assert.equal(s.case,'');
}
const chosen={...selection};R.changeSelection(chosen,'case',caseA.case_id,[caseA]);assert.equal(chosen.image,caseA.image_id);assert.equal(chosen.condition,'manual');
const invalid={...selection,team:'missing',worker:'ghost'};
R.reconcileSelection(invalid,answers,teams,labels,{});assert.equal(invalid.team,'all');assert.equal(invalid.cls,'all');assert.equal(invalid.worker,'');
const classChange={...selection,team:'all',worker:'W008',cls:'C01'};
R.reconcileSelection(classChange,answers,teams,labels,{});assert.equal(classChange.worker,'');
const teamKey={...selection,team:'saved-team-c',worker:'W008',cls:'all'};
const scoped=R.reconcileSelection(teamKey,answers,teams,labels,{});assert.equal(teamKey.team,'C');assert.equal(scoped.answers.length,1);assert.equal(scoped.answers[0].worker_id,'W100');assert.equal(teamKey.worker,'');

const frozen=R.frozenState({...selection,blind:true,layer:'all'},R.resolveContext(image,[caseA],selection,contextArgs),{release:'v2',filters:{building:'house-one'}});
const url=R.makeDeepLink(frozen,'https://example.test/index.html#obsolete=1');
const params=new URLSearchParams(url.split('#')[1]);
assert.equal(params.get('module'),'patterns');assert.equal(params.get('snapshot'),snapshot);assert.equal(params.get('reference'),ref.target_id);assert.equal(params.get('f_building'),'house-one');
const parsed=R.readDeepLink(params);assert.equal(parsed.blind,true);assert.equal(parsed.worker,'W008');assert.equal(parsed.requestedSnapshot,snapshot);
const restored={};R.applyDeepLink(restored,parsed,[caseA]);assert.equal(restored.team,'A');assert.equal(restored.condition,'manual');
restored.worker='W100';R.applyDeepLink(restored,parsed,[caseA]);assert.equal(restored.worker,'W100'); // unchanged route never overrides local input
R.applyDeepLink(restored,R.readDeepLink(new URLSearchParams('image=image-a&condition=semi')),[caseA]);assert.equal(restored.worker,'');assert.equal(restored.case,'');assert.equal(restored.team,'all');
const caseOnly={};R.applyDeepLink(caseOnly,{case:caseA.case_id},[caseA]);assert.equal(caseOnly.image,'image-a');assert.equal(caseOnly.condition,'manual');
const blind=R.layers(answers,'Rnew2',labels,{},'C01','W100',{blind:true,snapshot});
assert.equal(blind.length,2);assert.equal(blind[1].highlight,true);assert.equal(blind[1].points,answers[1].points);
for(const l of blind){assert.doesNotMatch(l.label,/W008|W100|C01|类别未知/);assert.doesNotMatch(l.id,/old|new/);}
assert.equal(blind[0].color,'#087f8c');assert.equal(R.alias('worker','W100',snapshot),R.alias('worker','W100',snapshot));assert.notEqual(R.alias('worker','W100',snapshot),R.alias('worker','W008',snapshot));
const rec=R.feedbackRecord(frozen,{team_key:'saved-team-a',team_label:'A',region:'点 2–4',status:'needs_review',notes:'=1+2\n"note"'},'2026-10-20T08:00:00Z');
assert.equal(rec.reference_id,ref.target_id);assert.equal(rec.snapshot,snapshot);assert.equal(rec.blind,true);assert.equal(rec.case_id,caseA.case_id);
const json=JSON.parse(R.exportFeedback([rec],'json'));assert.equal(json.records[0].notes,rec.notes);assert.equal(json.schema,'research_comparison_feedback_v1');
const csv=R.exportFeedback([rec],'csv');assert.match(csv,/reference_id/);assert.match(csv,/'=1\+2/);assert.match(csv,/""note""/);assert.match(csv,/点 2–4/);
// Read-only helpers do not mutate source geometry, class labels, cases or annotations.
assert.equal(caseA.reference,ref);assert.equal(caseA.teams,teams);assert.deepEqual(labels,{W100:{Rnew2_geometry_quality_class:'C01'}});

// Generated data are intentionally untracked. Validate packaged data when present, without blocking source-only regression checks.
const dataPath=__dirname+'/v2-resources/comparisons.json',indexPath=__dirname+'/v2-data/index.json';
if(fs.existsSync(dataPath)){
 const data=JSON.parse(fs.readFileSync(dataPath,'utf8'));
 assert.equal(data.cases.length,20);assert.equal(Object.keys(data.groups).length,5);
 for(const views of Object.values(data.groups))for(const v of views){assert.deepEqual(v.after.workers,views[0].after.workers);assert.deepEqual(v.before.workers,views[0].before.workers);}
}else console.log('SKIP: generated comparisons payload not present; actual contract covered with fixtures');
if(fs.existsSync(indexPath)){
 const index=JSON.parse(fs.readFileSync(indexPath,'utf8')),ids=new Set(index.tables.map(t=>t.id));
 assert.equal(ids.size,index.tables.length);
 for(const tabs of Object.values(index.module_tabs))for(const [,id] of tabs)if(id)assert.ok(ids.has(id),'Missing tab table: '+id);
}
console.log('PASS: exact points, unknown classes, condition/reference/snapshot isolation, selection reset, frozen links, anonymous layers, feedback exports');

const alternate={target_id:'alternate-reference',points:[[8,9]],floor:[[8,9]]};
const alternateContext=R.resolveContext({...image,references:[ref,alternate]},[caseA],{...selection,reference:alternate.target_id},contextArgs);
assert.equal(alternateContext.case,caseA);assert.equal(alternateContext.caseReferenceMatches,false);assert.match(alternateContext.notices.join(' '),/隐藏原案例解释/);
const drafted={...selection,reviewDraft:{region:'old image',notes:'do not transfer'}};R.changeSelection(drafted,'condition','semi',[caseA]);assert.equal(Object.keys(drafted.reviewDraft).length,0);
const draftLink={...selection,reviewDraft:{notes:'old'}};R.applyDeepLink(draftLink,{image:'image-b'},[caseA]);assert.equal(Object.keys(draftLink.reviewDraft).length,0);
assert.equal(R.groupFromRows('G046',{MV0001:[],MV0005:[]},[{group_id:'MV0001',source_codes:'candidate:G046|evidence:G046|original:G046'}]),'MV0001');
assert.equal(R.groupFromRows('G046',{MV0001:[],MV0005:[]},[{group_id:'MV0001',source_codes:'original:G046'},{group_id:'MV0005',source_codes:'original:G046'}]),'');
assert.equal(R.groupFromRows('G04',{MV0001:[]},[{group_id:'MV0001',source_codes:'original:G046'}]),'');
assert.equal(R.groupFromRows('unknown',{MV0001:[]},[]),'');
const mvLink=R.makeDeepLink({module:'multiview',group:'MV0001',stage:'before',view:'image-a',worker:'W100',snapshot,release:'v2'});
const mvParams=new URLSearchParams(mvLink.split('#')[1]);assert.equal(mvParams.get('module'),'multiview');assert.equal(R.readMultiviewLink(mvParams).group,'MV0001');assert.equal(R.readMultiviewLink(mvParams).stage,'before');

// Lightweight render harness: inspect presentation and exact geometry mounts without inventing a browser geometry engine.
class Host{
 constructor(){this.dataset={};this.isConnected=true;this.nodes=new Map();this._html='';}
 set innerHTML(value){this._html=value;this.nodes.clear();}
 get innerHTML(){return this._html;}
 querySelector(selector){
  if(!this.nodes.has(selector))this.nodes.set(selector,{value:'',checked:false,disabled:false,innerHTML:'',textContent:''});
  return this.nodes.get(selector);
 }
}
(async()=>{
 const mounted=[];ctx.WorkbenchGeometry={mount:(...args)=>mounted.push(args)};
 const data={...payload,labels:[{worker_id:'W100',Rnew2_geometry_quality_class:'C01'}],groups:{}};
 const refImage={...image,flags:{},image_code:'Image A',annotations:answers.map(a=>({...a,condition:'manual'})).concat({object_id:'semi-object',worker_id:'W101',condition:'semi',retained:true,points:[[4,5],[4,6]]})};
 const assets={snapshot_id:snapshot,data_release:'v2',images:[{image_id:'image-a',image_code:'Image A',flags:{}}]};
 const downloads=[],contexts=[];let reads=0;
 const read=async()=>{reads++;return data;};
 const options={mode:'patterns',assets,loadImage:async()=>refImage,read,filters:{},snapshot,release:'v2',deepLink:new URLSearchParams('case=S07_reverse_new2&condition=manual&worker=W100&cmp_blind=1'),download:(...args)=>downloads.push(args),onContext:c=>contexts.push(c)};
 const host=new Host();await R.render(host,options);
 assert.equal(contexts.at(-1).blind,true);assert.equal(contexts.at(-1).compatible_teams.length,2);
 assert.doesNotMatch(host.innerHTML,/>W100<|>C01<|B8L2|D10|id="rc-link-text"/);
 assert.doesNotMatch(host.querySelector('#rc-teams').innerHTML,/B8L2|D10|>saved-team-a</);
 assert.ok(mounted.at(-2)[5].layers.every(l=>!l.label.includes('W100')&&!l.label.includes('C01')));
 host.querySelector('#rc-review-team').value='saved-team-a';host.querySelector('#rc-review-region').value='ERP region';host.querySelector('#rc-review-status').value='needs_review';host.querySelector('#rc-review-notes').value='review only';
 host.querySelector('#rc-review-add').onclick();host.querySelector('#rc-review-json').onclick();
 const exported=JSON.parse(downloads.at(-1)[1]);assert.equal(exported.records.at(-1).reference_id,ref.target_id);assert.equal(exported.records.at(-1).team_key,'saved-team-a');assert.equal(exported.records.at(-1).blind,true);
 assert.equal(host.querySelector('#rc-review-notes').value,'');
 const semiOptions={...options,deepLink:new URLSearchParams('image=image-a&condition=semi&team=A&worker=W100')};
 await R.render(host,semiOptions);assert.equal(contexts.at(-1).compatible_teams.length,0);assert.equal(contexts.at(-1).worker,'');assert.equal(contexts.at(-1).team,'all');
 assert.match(host.querySelector('#rc-teams').innerHTML,/没有兼容/);
 assert.equal(reads,1); // Same immutable resource/read context reuses payload.
 await R.render(host,{...options,assets:{...assets},deepLink:new URLSearchParams('image=image-a&condition=manual')});assert.equal(reads,2); // A new index invalidates the payload cache.
 await R.render(host,{...options,deepLink:new URLSearchParams('image=missing-image&condition=manual')});assert.match(host.innerHTML,/不替换成其它图片/);
 await R.render(host,{...options,deepLink:new URLSearchParams('image=image-a&condition=missing-condition')});assert.match(host.innerHTML,/不借用其它条件/);
 let current=true,completeRead;const waiting=new Promise(resolve=>{completeRead=resolve;});
 const reusedHost=new Host();reusedHost.innerHTML='new module content';
 const stale=R.render(reusedHost,{...options,read:()=>waiting,isCurrent:()=>current});
 current=false;completeRead(data);await stale;assert.equal(reusedHost.innerHTML,'new module content');
 console.log('PASS: blind presentation, feedback binding, condition-switch rendering, cache isolation, unavailable deep links, source-group mapping, stale-module cancellation');
})().catch(error=>{console.error(error);process.exitCode=1;});
