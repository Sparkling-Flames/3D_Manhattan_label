const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const C=require('./workbench-core.js');
const ctx={window:{},WorkbenchCore:C};vm.createContext(ctx);
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
const data=JSON.parse(fs.readFileSync(__dirname+'/v2-resources/comparisons.json','utf8'));
assert.equal(data.cases.length,20);assert.equal(Object.keys(data.groups).length,5);
for(const views of Object.values(data.groups))for(const v of views){
 assert.deepEqual(v.after.workers,views[0].after.workers);
 assert.deepEqual(v.before.workers,views[0].before.workers);
}
const index=JSON.parse(fs.readFileSync(__dirname+'/v2-data/index.json','utf8'));
assert.equal(index.tables.length,87);
console.log('PASS: filtered annotation, class unknowns, member highlight, exact points, saved same-member views, refreshed payload');
