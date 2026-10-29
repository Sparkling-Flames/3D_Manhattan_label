const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
class Node {constructor(){this.children=[];this.value='';this.textContent='';this.style={};} append(x){this.children.push(x);if(x.value&&!this.value)this.value=x.value;} replaceChildren(){this.children=[];this.value='';} get options(){return this.children;}}
const ids=['method','fold','roster','rosterInfo','conditions','imageMethod','size','direction','image','imageStats','imagePhoto','event','eventInfo'];
const nodes=Object.fromEntries(ids.map(id=>[id,new Node()]));
const ctx={window:{},document:{getElementById:id=>nodes[id],createElement:()=>new Node()}};vm.createContext(ctx);
for(const f of ['v21-reselection-data.js','v21-reselection.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,f),'utf8'),ctx);
assert.equal(nodes.conditions.children.length,32);
nodes.method.value='OPPJOINT_K4';nodes.method.onchange();assert.ok(nodes.roster.children.length>0);
assert.ok(nodes.fold.options.some(x=>x.value==='ALL'));const fold=nodes.fold.options.find(x=>x.value!=='ALL');
assert.ok(fold);nodes.fold.value=fold.value;nodes.fold.onchange();assert.ok(nodes.roster.children.length>0);
nodes.imageMethod.value='OPPJOINT_K4';nodes.imageMethod.onchange();nodes.size.value='12/6';nodes.size.onchange();
assert.ok(nodes.direction.value);assert.ok(nodes.image.value);assert.ok(nodes.event.value);assert.match(nodes.eventInfo.children[0].textContent,/D：.*X：.*Y：.*Z：/);
const selected=ctx.window.V21_RESELECTION.events.find(x=>x.event_id===nodes.event.value);
assert.equal(selected.method,'OPPJOINT_K4');assert.equal(`${selected.n}/${selected.m}`,'12/6');
assert.equal(selected.role_direction,nodes.direction.value);assert.equal(selected.image,nodes.image.value);
assert.ok(nodes.eventInfo.children[0].textContent.includes(selected.A_members));
assert.ok(nodes.imagePhoto.children.length);console.log('32 conditions, fold roster, direction/image selection and ABC members verified');
