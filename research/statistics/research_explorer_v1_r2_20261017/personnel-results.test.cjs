const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const ctx={window:{},console,URLSearchParams};vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(__dirname,'personnel-results.js'),'utf8'),ctx);
const P=ctx.window.PersonnelResults;
const rows=[{worker_id:'W100',condition:'manual',panel:'ordinary',origin:'new',n_quality:2,Q_mean:90,Q_q10:80,Q_peer:10,source_time_n:0,source_time_median:null,n_time:0},
 {worker_id:'W100',condition:'semi',panel:'ordinary',origin:'new',n_quality:3,Q_mean:60},
 {worker_id:'W100',condition:'manual',panel:'doorway',origin:'new',n_quality:1,Q_mean:70}];
assert.equal(P.filterProfiles(rows,{condition:'manual',panel:'ordinary',origin:'all'}).length,1);
assert.equal(P.filterProfiles(rows,{condition:'semi',panel:'ordinary',origin:'v1'}).length,0);
assert.equal(P.selectRows([{domain:'allQ',n:5},{domain:'above_peer_Q',n:5}],{domain:'allQ',n:'5'},['domain','n']).length,1);
const ref={target_id:'r',points:[[1,2]],floor:[[3,4]]};
assert.ok(P.matchedReference(ref,ref));assert.ok(!P.matchedReference(ref,{...ref,points:[[9,9]]}));
assert.ok(!P.matchedReference(ref,{...ref,target_id:'other'}));
(async()=>{
 const payload={snapshot_id:'s',profiles:rows,quality:[],growth:[],speed:[],cases:[],source:'research/workers/example/FIELD_CONTRACT.md'};
 const host={dataset:{},innerHTML:''};
 const options={mode:'profiles',release:'v2',snapshot:'s',resourcesBase:'local/',assets:{personnel_results:'personnel.json'},read:async()=>payload};
 await P.render(host,options);
 assert.match(host.innerHTML,/当前 1 个来源人员ID/);
 assert.match(host.innerHTML,/来源时间 n=0/);assert.match(host.innerHTML,/缺失/);
 assert.doesNotMatch(host.innerHTML,/NaN|undefined/);
 assert.equal(host.dataset.ready,'profiles');
 await P.render(host,{...options,snapshot:'wrong'});assert.match(host.innerHTML,/快照不匹配/);
 let resolve;const delayed={...options,resourcesBase:'late/',read:()=>new Promise(r=>resolve=r)};
 const first=P.render(host,delayed);await Promise.resolve();
 await P.render(host,{...options,release:'v1'});resolve(payload);await first;
 assert.match(host.innerHTML,/请切换到v2/);
 console.log('PASS: Manual/Semi/doorway and quality domains separate, missing time retained, references bound, snapshot and stale-route isolation');
})().catch(e=>{console.error(e);process.exitCode=1;});
