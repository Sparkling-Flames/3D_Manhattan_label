const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const base=path.join(__dirname,'../research/statistics/research_explorer_v1_r2_20261017');
class Element{constructor(){this.children=[];this.value='';this.textContent='';}append(...items){for(const x of items){this.children.push(x);if(x.value&&!this.value)this.value=x.value;}}replaceChildren(){this.children=[];this.value='';}}
const html=fs.readFileSync(path.join(base,'v21-population-study.html'),'utf8');
const nodes=Object.fromEntries([...html.matchAll(/id="([^"]+)"/g)].map(x=>[x[1],new Element()]));
const document={getElementById:id=>nodes[id],createElement:()=>new Element()};
const window={document};const context=vm.createContext({window});
for(const file of ['v21-population-study-data.js','v21-population-study.js'])vm.runInContext(fs.readFileSync(path.join(base,file),'utf8'),context);
const rows=id=>nodes[id].children[0].children[1].children;
assert.equal(rows('effectsTable').length,4);assert.equal(rows('coalitionTable').length,7);
nodes.coalitionImage.value='pa4otMbVnkk-11';nodes.coalitionImage.onchange();
assert.equal(rows('coalitionTable').length,7);assert.ok(rows('coalitionTable').every(x=>x.children[8].textContent==='complete_conditional'));
nodes.personFold.value=nodes.personFold.children.find(x=>x.value!=='ALL').value;nodes.personFold.onchange();assert.match(nodes.rosterNote.textContent,/已排除/);
nodes.effectCondition.value='OPPJOINT_K3_20_10_1_to_2';nodes.effectCondition.onchange();assert.equal(rows('imageTable').length,82);
nodes.effectMetric.value='geometry_bev_distance_AC';nodes.effectMetric.onchange();assert.match(nodes.metricExplanation.textContent,/未逐项重算/);
assert.equal(rows('strictTable').length,2);assert.equal(rows('roomTable').length,9);
const {fmt}=require(path.join(base,'v21-population-study.js'));assert.equal(fmt(null),'缺失');assert.equal(fmt(0),'0');
for(const [,url] of html.matchAll(/(?:href|src)="([^"#]+)"/g)){const f=url.split('#')[0].replaceAll('&amp;','&');if(!/^[a-z]+:/i.test(f))assert.ok(fs.existsSync(path.resolve(base,f)),f);}
console.log('AC page: condition/metric/image/fold interactions, status and local links passed; not browser validation.');
