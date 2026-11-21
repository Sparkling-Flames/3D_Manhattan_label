const assert=require('node:assert/strict');
const {validateReceipt}=require('../tools/thesis_main/analysis/formal_identity_review_app.js');
const d={package:'new',scenes:[{id:'I001',code:'image',groups:[{id:'G1',members:[0,1]},{id:'G2',members:[2,3]}]}]};
const base={schema:'fresh_group_review_v2',package:'new',answers:{I001:{code:'image',verdict:'issues',done:true,note:'',issues:[{type:'merge',groups:['G1','G2'],members:[0,2],note:'同一凹角'}]}}};
assert.equal(validateReceipt(base,d),base);
function bad(fn){const b=structuredClone(base);fn(b);assert.throws(()=>validateReceipt(b,d));}
bad(b=>b.schema='old_review');bad(b=>b.package='formal_identity_20261117_v1');bad(b=>b.answers.I001.code='other');bad(b=>b.answers.I001.verdict='');bad(b=>b.answers.I001.issues[0].groups=['G99']);bad(b=>b.answers.I001.issues[0].members=[99]);bad(b=>b.answers.I001.issues[0].note='');
const u=structuredClone(base);u.answers.I001.issues[0].type='unresolved';validateReceipt(u,d);
console.log('Fresh-review receipt validation passed.');
const modes=structuredClone(base);Object.assign(modes.answers.I001.issues[0],{type:'distinct_modes',identity:'same',geometry:'distinct',criterion:'structure_geometry_v1'});assert.equal(validateReceipt(modes,d),modes);
for(const patch of [{identity:'invalid'},{geometry:'similar'},{groups:['G1'],members:[0]}]){const x=structuredClone(modes);Object.assign(x.answers.I001.issues[0],patch);assert.throws(()=>validateReceipt(x,d));}
console.log('Two-layer judgments and legacy receipt compatibility passed.');
