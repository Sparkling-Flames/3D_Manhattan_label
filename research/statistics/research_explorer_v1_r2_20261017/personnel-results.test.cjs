const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const ctx={window:{},console,URLSearchParams};vm.createContext(ctx);
const script=fs.readFileSync(path.join(__dirname,'personnel-results.js'),'utf8');
vm.runInContext(script.replace('return {render,filterProfiles,selectRows,matchedReference};','return {render,filterProfiles,selectRows,matchedReference,scatter};'),ctx);
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
const chart=P.scatter([
 {worker_id:'fast',Q_mean:90,source_time_median:30,origin:'new',n_quality:5,source_time_n:4},
 {worker_id:'slow',Q_mean:50,source_time_median:300,origin:'v1',n_quality:3,source_time_n:2},
 {worker_id:'missing',Q_mean:80,source_time_median:null},
]);
const points=[...chart.matchAll(/<circle cx="([\d.]+)" cy="([\d.]+)"[^>]*><title>([^<]+)/g)];
assert.equal(points.length,2);assert(Number(points[0][1])>Number(points[1][1]));assert(Number(points[0][2])<Number(points[1][2]));
assert.match(chart,/Q 70分、时间 165秒/);assert.match(chart,/stroke-dasharray="5 4"/);assert.match(chart,/越往右越快/);
assert.doesNotMatch(P.scatter([{Q_mean:20,source_time_median:0},{Q_mean:20,source_time_median:0}]),/NaN|Infinity/);
for(const q of [0,100])assert.doesNotMatch(P.scatter([{Q_mean:q,source_time_median:0}]),/NaN|Infinity/);
assert.match(chart,/纵轴按当前数据范围放大/);
assert.match(P.scatter([{Q_mean:50,source_time_median:null}]),/没有共同Q/);
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
