const test=require('node:test'),assert=require('node:assert/strict');
const M=require('../tools/thesis_main/analysis/point_edit_review_20261009_core.js');
const point=(id,x,y)=>({id,x,y,label:id,origin:'original',source_index:Number(id.slice(1))-1});
const source={record_id:'R1',canonical_object_id:'full-canonical-a',image_id:'building_full_image_id',
 source_hash:'source-sha256',versions:{raw:{available:true,points:[point('p1',100,100),point('p2',100,400),point('p3',300,100),point('p4',300,400)],pairs:[]},
 current:{available:false,points:[],pairs:[]}}};
test('add/delete/move/pair preserve original IDs and before/after trace',()=>{
 let d=M.create(source,'raw');
 d=M.add(d,500,120,'new:test-added');d=M.move(d,'p1',110,101);d=M.pair(d,'p1','p2');d=M.remove(d,'p3');
 assert.deepEqual(d.points.map(p=>p.id),['p1','p2','p3','p4','new:test-added']);
 assert.equal(d.points[2].deleted,true);assert.deepEqual(d.pairs,[['p1','p2']]);
 assert.deepEqual(d.operations[1].before,{x:100,y:100});assert.deepEqual(d.operations[1].after,{x:110,y:101});
 assert.equal(d.operations[3].point_id,'p3');assert.equal(d.status,'draft');
 M.validate(source,d);
});
test('editing a confirmed patch returns to draft; deleting paired point unpairs it',()=>{
 let d=M.pair(M.create(source,'raw'),'p1','p2');d=M.status(d,'confirmed','only point patch');
 d=M.remove(d,'p1');assert.equal(d.status,'draft');assert.equal(d.pairs.length,0);
 assert.deepEqual(d.operations.at(-1).pairs_before,[['p1','p2']]);
});
test('missing current geometry requires explicit version choice',()=>{
 assert.throws(()=>M.create(source,'current'),/版本/);
 assert.throws(()=>M.create(source,'unknown'),/版本/);
});
test('invalid point IDs, out of bounds edits and inverted/repeated pairs fail',()=>{
 let d=M.create(source,'raw');assert.throws(()=>M.remove(d,'p19'),/点/);
 assert.throws(()=>M.move(d,'p1',44479,100),/越界/);
 assert.throws(()=>M.pair(d,'p2','p1'),/上点/);
 d=M.pair(d,'p1','p2');assert.throws(()=>M.pair(d,'p1','p4'),/重复/);
 assert.throws(()=>M.add(d,1,1,'p1'),/新增/);
});
test('export/import JSON roundtrip keeps exact bindings and statuses',()=>{
 let d=M.add(M.create(source,'raw'),500,400,'new:roundtrip');
 d=M.status(d,'deferred','reviewed version still uncertain');
 const data={schema:M.SCHEMA,source_hash:'package-sha256',queue_hash:'q',cases:[source]};
 const file=M.exportFile(data,{R1:d});const got=M.importFile(data,JSON.parse(JSON.stringify(file)),{});
 assert.deepEqual(got.R1,d);assert.equal(got.R1.restore_eligibility,false);
 assert.equal(got.R1.ring_confirmed,false);
});
test('source drift, same short image name with another canonical identity and conflicting import fail atomically',()=>{
 let d=M.create(source,'raw');let data={schema:M.SCHEMA,source_hash:'package-sha256',queue_hash:'q',cases:[source]};
 let file=M.exportFile(data,{R1:d});file.records.R1.identity.canonical_object_id='other-answer';
 assert.throws(()=>M.importFile(data,file,{}),/身份/);
 file=M.exportFile(data,{R1:d});file.source_hash='other';assert.throws(()=>M.importFile(data,file,{}),/来源/);
 file=M.exportFile(data,{R1:M.move(d,'p1',111,100)});
 assert.throws(()=>M.importFile(data,file,{R1:d}),/冲突/);assert.equal(d.points[0].x,100);
});
test('tampered original point ID or coordinates without matching operation log is rejected',()=>{
 let d=M.create(source,'raw');d.points[0].id='p99';assert.throws(()=>M.validate(source,d),/操作|点/);
 d=M.create(source,'raw');d.points[0].x=200;assert.throws(()=>M.validate(source,d),/操作/);
});
test('existing invalid source coordinates remain visible until repaired, never wrapped modulo width',()=>{
 const bad=JSON.parse(JSON.stringify(source));bad.versions.raw.points[0].x=44479;
 let d=M.create(bad,'raw');assert.equal(d.points[0].x,44479);
 assert.throws(()=>M.status(d,'confirmed',''),/越界/);
 d=M.move(d,'p1',100,100);M.validate(bad,d);assert.equal(M.status(d,'confirmed','repaired').status,'confirmed');
});

test('undo preserves stable IDs, pairs and export/import trace',()=>{
 const data={schema:M.SCHEMA,source_hash:'package-sha256',queue_hash:'q',cases:[source]};
 const base=M.create(source,'raw');let d=M.pair(base,'p1','p2');
 d=M.move(d,'p1',120,110);d=M.undo(d);assert.deepEqual(d.points,base.points);assert.deepEqual(d.pairs,[['p1','p2']]);
 d=M.remove(d,'p3');d=M.undo(d);assert.equal(d.points[2].deleted,undefined);assert.equal(d.points[3].id,'p4');
 d=M.add(d,550,130,'new:undo-added');d=M.undo(d);assert.deepEqual(d.points,base.points);
 d=M.undo(d);assert.deepEqual(d.pairs,[]);assert.equal(M.canUndo(d),false);assert.equal(M.hasChanges(d),false);
 assert.throws(()=>M.undo(d),/撤销/);M.validate(source,d);
 assert.deepEqual(M.importFile(data,M.exportFile(data,{R1:d}),{}).R1,d);
 const bad=structuredClone(d);bad.operations.find(o=>o.type==='undo').undo_of=bad.operations[0].operation_id;
 assert.throws(()=>M.validate(source,bad),/撤销|追溯/);
});
test('undo never restores historical deletions and can undo reset',()=>{
 const historical={...source,versions:{...source.versions,historical:{available:true,points:source.versions.raw.points.filter(p=>p.id!=='p3'),pairs:[]}}};
 let d=M.create(historical,'historical');d=M.add(d,600,130,'new:history');d=M.undo(d);
 assert(!d.points.some(p=>p.id==='p3'));M.validate(historical,d);
 d=M.move(d,'p1',130,115);d=M.reset(d);d=M.undo(d);assert.equal(d.points[0].x,130);
 d=M.undo(d);assert.deepEqual(d.points,historical.versions.historical.points);M.validate(historical,d);
});
