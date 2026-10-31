const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
class Element {
  constructor(tag){this.tag=tag;this.children=[];this.attrs={};this.style={};this.dataset={};}
  append(n){this.children.push(n);}
  setAttribute(k,v){this.attrs[k]=v;}
  querySelectorAll(tag){return this.children.flatMap(n=>[...(n.tag===tag?[n]:[]),...n.querySelectorAll(tag)]);}
  click(){this.onclick?.();}
}
const nodes=Object.fromEntries(['main','#status','#export'].map(k=>[k,new Element(k)]));
let cache={},fail=false;
const ctx={document:{querySelector:k=>nodes[k],createElement:t=>new Element(t),createElementNS:(_,t)=>new Element(t)},localStorage:{getItem:k=>cache[k]||null,setItem:(k,v)=>{if(fail)throw Error('full');cache[k]=v;}},Blob,URL,setTimeout:fn=>fn()};
vm.createContext(ctx);for(const file of ['review-data.js','review.js'])vm.runInContext(fs.readFileSync(__dirname+'/'+file,'utf8'),ctx);
assert.equal(nodes.main.children.length,16);
const section=nodes.main.children[0],buttons=section.querySelectorAll('button');
buttons.find(b=>b.textContent==='空间1').click();buttons.find(b=>b.textContent==='排除').click();
assert.match(nodes['#status'].textContent,/1\/12/);
const record=Object.values(JSON.parse(Object.values(cache)[0]))[0];assert.equal(record.scope,'空间1');assert.equal(record.eligibility,'排除');assert(record.points.length && record.spaces.length===2);
buttons.find(b=>b.textContent==='保留').click();assert.equal(Object.values(JSON.parse(Object.values(cache)[0]))[0].eligibility,'保留');
assert.equal(nodes.main.children[12].querySelectorAll('button').length,1); // only overlay toggle
fail=true;buttons.find(b=>b.textContent==='待定').click();assert.match(nodes['#status'].textContent,/保存失败/);
nodes['#export'].click();
console.log('PASS: 12 editable / 4 read-only, independent decisions, edits, save failure, export');
for(const n of Object.values(nodes))n.children=[];cache={};fail=false;
const batchContext={...ctx};vm.createContext(batchContext);
vm.runInContext(fs.readFileSync(__dirname+'/../scope_recheck40_20261031/review-data.js','utf8'),batchContext);
vm.runInContext(fs.readFileSync(__dirname+'/review.js','utf8'),batchContext);
assert.equal(nodes.main.children.length,40);
const batchButtons=nodes.main.children[0].querySelectorAll('button');
batchButtons.find(b=>b.textContent==='都不符合（看不懂）').click();
assert.match(nodes['#status'].textContent,/1\/40/);
assert.equal(Object.values(JSON.parse(Object.values(cache)[0]))[0].eligibility,'排除');
batchButtons.find(b=>b.textContent==='空间2').click();
assert.equal(Object.values(JSON.parse(Object.values(cache)[0]))[0].eligibility,'保留');
batchButtons.find(b=>b.textContent==='待定').click();
assert.equal(Object.values(JSON.parse(Object.values(cache)[0]))[0].eligibility,'待定');
assert(Object.keys(cache)[0].includes('recheck40'));
console.log('PASS: 40-item isolated cache, four-way default eligibility and override');
