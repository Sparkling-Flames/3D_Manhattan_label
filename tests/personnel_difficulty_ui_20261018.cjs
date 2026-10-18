// Offline controller/coverage checks; no browser rendering.
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const els={};function el(){return {value:'',textContent:'',innerHTML:'',children:[],append(o){this.children.push(o);if(!this.value)this.value=o.value;},querySelectorAll(){return []}};}
const context={console,document:{getElementById:id=>els[id]??=el(),createElement:()=>el()},setTimeout,Blob,URL};context.window=context;vm.createContext(context);
const base='research/statistics/research_explorer_v1_r2_20261017/';
context.document.getElementById('metric').value='B8L2';
for(const p of ['personnel-difficulty-data.js','personnel-difficulty.js'])vm.runInContext(fs.readFileSync(base+p,'utf8'),context);
els.worker.value='';els.panel.onchange();assert.equal((els.matrix.innerHTML.match(/data-worker=/g)||[]).length,25);assert.equal((els.details.innerHTML.match(/<tr>/g)||[]).length,1258);
for(const p of els.panel.children){els.panel.value=p.value;els.panel.onchange();const expected=context.PERSONNEL_DIFFICULTY.records.filter(r=>r.panel===p.value).length;assert.equal((els.details.innerHTML.match(/<tr>/g)||[]).length,expected);}
els.panel.value='manual|ordinary_primary';els.worker.value='W017';els.metric.value='D10';els.metric.onchange();assert.equal((els.matrix.innerHTML.match(/data-worker=/g)||[]).length,1);assert.match(els.matrix.innerHTML,/W017/);assert.match(els.details.innerHTML,/仅全量描述/);assert.ok(!els.matrix.innerHTML.includes('NaN'));
console.log('All four condition panels retain all records; metric and worker filters passed. Visual rendering not checked.');
