const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const page = path.join(root, 'research/statistics/research_explorer_v1_r2_20261017');
class Element {
  constructor(tag) { this.tag=tag; this.children=[]; this.listeners={}; this.textContent=''; this.value='combined'; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children=children; }
  setAttribute(key,value) { this[key]=value; }
  addEventListener(type,cb) { this.listeners[type]=cb; }
}
function load() {
  const elements = {};
  const document = {getElementById(id) { return elements[id] ||= new Element(id); }, createElement(tag) { return new Element(tag); }, createElementNS(ns,tag) { return new Element(tag); }};
  const context={window:{},document};vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(page,'v21-results-data.js'),'utf8'),context);
  vm.runInContext(fs.readFileSync(path.join(page,'v21-results.js'),'utf8'),context);
  return {data:context.window.V21_RESULTS,elements};
}
test('snapshot shows receipt counts and k=2 support, and changes scope', () => {
  const {data,elements}=load();
  assert.equal(data.inventory.records,10439); assert.equal(data.inventory.quality,8154); assert.equal(data.inventory.images,225);
  assert.match(elements.populationInventory.textContent,/194.*pooled256.*29.*new_space256/);
  assert.match(elements.twoPersonDetail.textContent,/1→2/); assert.match(elements.twoPersonDetail.textContent,/2→3/);
  assert.match(elements.twoPersonDetail.textContent,/单点区间/);
  assert.equal(elements.k2IntervalRows.children.length,3);
  assert.notEqual(elements.k2IntervalRows.children[0].children[2].textContent,'不可估');
  assert.equal(elements.curveRows.children.find(r=>r.children[0].textContent==='2').children[4].textContent,'独立两人补算');
  assert.ok(elements.curve.children.length>30);
  assert.equal(elements.strictRows.children.length,data.strict_comparison.length);
  assert.ok(data.strict_comparison.some(r=>Number(r.CA_building_equal)<0));
  elements.curveScope.value='added';elements.curveScope.listeners.change();
  const three=elements.curveRows.children.find(r=>r.children[0].textContent==='3');
  assert.equal(three.children[6].textContent,'14 / 14');
  assert.match(three.children[5].textContent,/%$/);
  const point=data.k2.find(x=>x.scope==='added');assert.match(elements.curveSupport.textContent,new RegExp(String(point.images)));
  assert.match(elements.currentStatus.textContent,new RegExp(data.current.data_release));
});
test('local page references exist and does not fetch', () => {
  const html=fs.readFileSync(path.join(page,'v21-results.html'),'utf8');
  const refs=[...html.matchAll(/(?:href|src)="([^"]+)"/g)].map(m=>m[1]).filter(x=>!x.startsWith('#'));
  for (const ref of refs) assert.ok(fs.existsSync(path.resolve(page,ref.split('#')[0].replaceAll('&amp;','&'))),ref);
  assert.doesNotMatch(fs.readFileSync(path.join(page,'v21-results.js'),'utf8'),/\bfetch\s*\(/);
  assert.match(fs.readFileSync(path.join(page,'index.html'),'utf8'),/href="v21-results\.html"/);
});
