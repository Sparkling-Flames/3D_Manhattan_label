const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const root=path.resolve(__dirname,'..');
const dir=path.join(root,'research/data/scope_quality_rescore_20261016/vertical_cut_audit_20261028');
const html=fs.readFileSync(path.join(dir,'height-review.html'),'utf8');
const radios=['inherit_source_height','height_differs','uncertain','scope_or_boundary_review'].map(value=>({value,checked:false}));
const ids=Object.fromEntries([...html.matchAll(/id="([^"]+)"/g)].map(m=>[m[1],{value:'',innerHTML:'',textContent:''}]));
const storage=new Map();let exported,anchor,mountCount=0;
const context={window:{WorkbenchGeometry:{mount(){mountCount++}}},
 document:{getElementById:id=>{assert.ok(ids[id],id);return ids[id]},querySelectorAll:()=>radios,querySelector:()=>radios.find(r=>r.checked),createElement(){anchor={click(){}};return anchor}},
 localStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)},
 Blob:class{constructor(parts){exported=JSON.parse(parts[0])}},
 URL:{createObjectURL:()=> 'blob:test',revokeObjectURL(){}},setTimeout(){},console};
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(dir,'height-review-data.js'),'utf8'),context);
const cases=context.window.SCOPE_HEIGHT_DATA.cases;
assert.equal(cases.length,9);assert.equal(new Set(cases.map(c=>c.target_id)).size,9);
for(const c of cases){assert.ok(fs.existsSync(path.resolve(dir,c.photo)));assert.ok(c.points.length>=8);assert.equal(c.points.length%2,0)}
for(const m of html.matchAll(/(?:src|href)="([^"#]+)"/g)){
 if(!/^(?:https?:|blob:)/.test(m[1]))assert.ok(fs.existsSync(path.resolve(dir,m[1])),m[1]);
}
const scripts=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];assert.equal(scripts.length,1);
vm.runInContext(scripts[0][1],context);
assert.equal(storage.size,0);assert.ok(radios.every(r=>!r.checked));assert.match(ids.status.textContent,/8 \/ 9/);
ids.export.onclick();assert.equal(exported.records.length,9);assert.equal(exported.records.filter(r=>r.decision===null).length,1);
assert.equal(anchor.download,'新范围顶部复核_2026-10-28.json');
radios[2].checked=true;radios[2].onchange();ids.note.value='TEST ONLY';ids.note.oninput();
ids.next.onclick();assert.equal(radios[0].checked,true);ids.prev.onclick();assert.equal(radios[2].checked,true);assert.equal(ids.note.value,'TEST ONLY');
ids.export.onclick();assert.equal(exported.records[0].decision,'uncertain');assert.equal(exported.records[0].note,'TEST ONLY');
assert.equal(exported.records.filter(r=>r.decision!==null).length,9);
ids.clear.onclick();ids.export.onclick();assert.equal(exported.records.filter(r=>r.decision===null).length,1);assert.match(ids.status.textContent,/8 \/ 9/);
assert.ok(mountCount>=3);console.log('PASS: 9 cases, dependencies, initially unanswered, draft restore, clear, nine-record export. Mock DOM only; no browser layout/download validation.');
