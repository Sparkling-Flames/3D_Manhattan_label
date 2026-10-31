const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
class Element {
  constructor(tag){this.tag=tag;this.children=[];this.attrs={};this.style={};this.dataset={};}
  append(n){this.children.push(n);}
  setAttribute(k,v){this.attrs[k]=v;}
  querySelectorAll(tag){return this.children.flatMap(n=>[...(n.tag===tag?[n]:[]),...n.querySelectorAll(tag)]);}
  click(){this.onclick?.();}
}
function boot(cache){
  const nodes=Object.fromEntries(['main','#status','#export'].map(k=>[k,new Element(k)]));
  let fail=false;
  const ctx={document:{querySelector:k=>nodes[k],createElement:t=>new Element(t),createElementNS:(_,t)=>new Element(t)},localStorage:{getItem:k=>cache[k]||null,setItem:(k,v)=>{if(fail)throw Error('full');cache[k]=v;}},Blob,URL,setTimeout:fn=>fn()};
  vm.createContext(ctx);
  for(const file of ['review-data.js','../scope_recheck_20261031/review.js','space-overlay.js'])vm.runInContext(fs.readFileSync(__dirname+'/'+file,'utf8'),ctx);
  return {nodes,fail:()=>{fail=true;}};
}
const cache={'doorway-scope-eligibility-recheck40-20261031-v1':'{"old":{"scope":"空间1","eligibility":"保留"}}'};
let {nodes,fail}=boot(cache);
assert.equal(nodes.main.children.length,21);assert.match(nodes['#status'].textContent,/0\/21/);
const section=nodes.main.children[0], buttons=section.querySelectorAll('button');
const cuts=section.querySelectorAll('g')[1];assert.equal(cuts.style.display,'none');
buttons.find(b=>b.textContent==='显示／隐藏原图上的空间切分').click();assert.equal(cuts.style.display,'');
assert(section.querySelectorAll('text').some(n=>n.textContent==='空间1'));
buttons.find(b=>b.textContent==='空间2').click();assert.match(nodes['#status'].textContent,/1\/21/);
const key='doorway-expanded-boundary21-20261031-v1';
assert.equal(Object.values(JSON.parse(cache[key]))[0].eligibility,'保留');
buttons.find(b=>b.textContent==='都不符合（看不懂）').click();assert.equal(Object.values(JSON.parse(cache[key]))[0].eligibility,'排除');
assert.equal(nodes.main.children[0],section);assert.equal(nodes.main.children.length,21);
buttons.find(b=>b.textContent==='待定').click();assert.equal(Object.values(JSON.parse(cache[key]))[0].eligibility,'待定');
const reopened=boot(cache);assert.match(reopened.nodes['#status'].textContent,/1\/21/);
fail();buttons.find(b=>b.textContent==='空间1').click();assert.match(nodes['#status'].textContent,/保存失败/);
nodes['#export'].click();
console.log('PASS: 21 items, isolated cache, save/reload, no navigation, four choices, eligibility override, space labels/projection toggle, export, storage error');
