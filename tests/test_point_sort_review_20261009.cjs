const test=require('node:test'),assert=require('node:assert/strict');
const M=require('D:/Work/HOHONET/tools/thesis_main/analysis/point_edit_review_20261009_core.js');
const points=Array.from({length:8},(_,i)=>({id:'p'+(i+1),label:'p'+(i+1),x:100+100*Math.floor(i/2),y:i%2?400:100,origin:'original',source_index:i}));
const source={record_id:'sort-test',canonical_object_id:'sort-answer',image_id:'full-image',source_hash:'source',versions:{raw:{available:true,points,pairs:[]}}};
const paired=()=>{let d=M.create(source,'raw');for(let i=0;i<8;i+=2)d=M.pair(d,points[i].id,points[i+1].id);return d;};
test('paired corner sort preserves coordinates, roles and auditable undo/import',()=>{
 const base=paired(),d=M.reorder(base,[0,2,1,3],'drag_pair');assert.deepEqual(d.points,base.points);assert.deepEqual(d.pairs,[base.pairs[0],base.pairs[2],base.pairs[1],base.pairs[3]]);
 assert.equal(d.operations.at(-1).group_unit,'paired_top_bottom_endpoints');M.validate(source,d);assert.deepEqual(M.undo(d).pairs,base.pairs);
 const data={source_hash:'pkg',queue_hash:'q',cases:[source]};assert.deepEqual(M.importFile(data,M.exportFile(data,{'sort-test':d}),{})['sort-test'],d);assert.throws(()=>M.reorder(base,[0,0,1,2]),/排列/);
});
test('sort after add/delete/move preserves original identities',()=>{
 let d=paired();d=M.add(d,550,100,'new:upper');d=M.add(d,550,400,'new:lower');d=M.pair(d,'new:upper','new:lower');d=M.move(d,'p1',120,110);d=M.pair(d,'p1','p2');d=M.remove(d,'p3');d=M.reorder(d,[2,0,1,3]);
 M.validate(source,d);assert.deepEqual(d.points.slice(0,8).map(p=>p.id),points.map(p=>p.id));assert.equal(d.points[2].deleted,true);
});
test('completion and defer without notes keep formal and eligibility scope unchanged',()=>{
 let d=M.status(paired(),'completed','');assert.equal(d.status,'completed');assert.equal(d.ring_confirmed,false);assert.equal(d.restore_eligibility,false);M.validate(source,d);
 d=M.reorder(d,[0,2,1,3]);assert.equal(d.status,'draft');M.validate(source,M.status(d,'deferred',''));
});
test('x pairing initializes visible sortable groups as one reversible draft operation',()=>{
 const shuffled={...source,versions:{raw:{available:true,points:[points[4],points[5],points[0],points[1],points[6],points[7],points[2],points[3]],pairs:[]}}};
 const start=M.create(shuffled,'raw'),d=M.pairByX(start);
 assert.deepEqual(d.pairs,[['p1','p2'],['p3','p4'],['p5','p6'],['p7','p8']]);
 assert.equal(d.operations.length,1);assert.equal(d.operations[0].type,'pair_x');M.validate(shuffled,d);
 assert.deepEqual(M.undo(d).pairs,[]);
 const odd={...shuffled,versions:{raw:{...shuffled.versions.raw,points:shuffled.versions.raw.points.slice(1)}}};
 assert.throws(()=>M.pairByX(M.create(odd,'raw')),/奇数/);
});
