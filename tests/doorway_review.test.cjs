const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict'),path=require('path');
const root=path.resolve(__dirname,'..'),out=process.env.DOORWAY_REVIEW_DIR||path.join(root,'research/data/doorway_review_20261030');
const elements=new Map();function element(){return {getContext(){return new Proxy({}, {get:(_,k)=>()=>{}})},value:'',checked:true,children:[],append(x){this.children.push(x)},set innerHTML(v){this.html=v;this.children=[]},get innerHTML(){return this.html},getBoundingClientRect(){return {left:0,top:0,width:450,height:400}}}}
const ctx={console,window:{},document:{getElementById(id){if(!elements.has(id))elements.set(id,element());return elements.get(id)},createElement:element},localStorage:{getItem(){return null},setItem(){}},WorkbenchGeometry:{mount(...args){ctx.lastMount=args}},Image:class {complete=false;naturalWidth=0},Blob,URL,setTimeout};vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(root,'analysis_results/difficulty/scope_workbench_recovered_20261015/quality_scope_review_complete_20261010/workbench_v3.4.2/dist/geometry.js'),'utf8'),ctx);ctx.Geo=ctx.window.Geo||ctx.Geo;
vm.runInContext(fs.readFileSync(path.join(out,process.env.DOORWAY_DATA_FILE||'data.js'),'utf8'),ctx);
vm.runInContext(fs.readFileSync(path.join(out,process.env.DOORWAY_SCRIPT_FILE||'review.js'),'utf8'),ctx);
function run(s){return vm.runInContext(s,ctx)}
if(process.env.DOORWAY_SCRIPT_FILE==='followup.js'){
 assert.equal(run('reviewQueue().length'),17);
 const baseline=run('reviewQueue().map(x=>[x.ci,x.ri].join()).join(";")');
 run("$('choices').children[0].onclick()");assert.equal(run('reviewQueue().map(x=>[x.ci,x.ri].join()).join(";")'),baseline);
 run('state=clone(window.DOORWAY_SEED)');
 run("reviewFilter='unreviewed'");assert.equal(run('reviewQueue().length'),8);
 run("reviewFilter='disputed'");assert.equal(run('reviewQueue().length'),2);
 run("reviewFilter='changed'");assert.equal(run('reviewQueue().length'),7);
 run("reviewFilter='pending';show()");
 const before=run('[i,j].join()');run("$('choices').children[0].onclick()");assert.equal(run('[i,j].join()'),before);
 run("state=clone(window.DOORWAY_SEED);reviewFilter='all';i=0;j=0;show()");

 assert.equal(run('Object.values(state.cases).reduce((n,c)=>n+Object.keys(c.answers).length,0)'),75);
 assert.equal(ctx.lastMount[5].layers.find(l=>l.id==='reference').visible,false);
 assert.equal(ctx.lastMount[5].layers.find(l=>l.id==='reference').confirmed,true);
 assert.equal(run('D.cases.flatMap(c=>c.records).filter(r=>r.raw_points?.length).length'),7);
 run("i=D.cases.findIndex(c=>c.image==='uNb9QFRL6hY-21');j=0;show()");
 assert.equal(ctx.lastMount[2].points,null);assert.equal(ctx.lastMount[2].raw_points.length,8);
 run("i=D.cases.findIndex(c=>c.image==='B6ByNegPMKs-42');j=0;show()");
 assert.equal(run('polygons(cur(),draft().cuts).every(Boolean)'),true);
 assert.notEqual(run('JSON.stringify(draft().cuts)'),run('JSON.stringify(draft().answers[cur().records[0].id].cuts)'));
 run('i=0;j=0;show()');
}

assert.equal(run('D.cases.length'),20);assert.equal(run('D.cases.reduce((s,c)=>s+c.records.length,0)'),Number(process.env.DOORWAY_COUNT||708));
assert.equal(run('polygons(cur(),draft().cuts).every(Boolean)'),true);
run("$('choices').children[0].onclick()");assert.equal(run('draft().answers[cur().records[j].id].label'),'空间1');
const serialized=run('JSON.stringify(state)');run('validate(JSON.parse('+JSON.stringify(serialized)+'))');
assert.throws(()=>run("validate({schema:'bad',cases:{}})"));assert.throws(()=>run("validate({schema:D.schema,cases:{unknown:{answers:{}}}})"));
run("$('clear').onclick()");assert.equal(run('draft().cuts[active]'),null);assert.equal(run("$('choices').children[0].disabled"),true);assert.equal(run("$('choices').children[3].disabled"),false);
run("$('undo').onclick()");assert.equal(run('!!draft().cuts[active]'),true);
for(let i=0;i<20;i++){run('i='+i+';j=0;show();images[cur().image_id]={complete:true,naturalWidth:1024};photo()');assert.equal(run('polygons(cur(),draft().cuts).every(Boolean)'),true,'invalid proposal '+i)}
assert.equal(run('polygons({floor:[[0,0],[2,0],[2,2],[0,2]]},[{line:[[3,0],[3,2]],side:-1},null])[0]'),null);
run('i=0;j=0;show()');const other=run('JSON.stringify(draft().cuts[1])');run('active=0;update({...draft().cuts[0],line:draft().cuts[0].line.map(p=>[p[0],p[1]+.01])})');assert.equal(run('JSON.stringify(draft().cuts[1])'),other);
assert.equal(run('migrate({schema:"doorway_review_v1",cases:{a:{cut:[[0,0],[1,0]],answers:{}}}}).schema'), 'doorway_review_v2');
assert.equal(run('polygons(cur(),draft().cuts).length'),2);
console.log('PASS: 20 images render logic, 708 records, split, selection, roundtrip, invalid import, undo and placeholders');
