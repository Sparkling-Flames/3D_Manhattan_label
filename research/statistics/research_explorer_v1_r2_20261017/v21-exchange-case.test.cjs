const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = __dirname;
const nodes = Object.fromEntries(['case', 'blocks', 'team', 'answer', 'comparison', 'status', 'view', 'detail', 'showCandidates', 'candidate', 'supporter', 'candidateStatus', 'reviewFocus', 'showSupportPoints', 'focusHelp'].map(id => [id, {
  value: id === 'case' ? '0' : '', innerHTML: '', textContent: '', handlers: {},
  addEventListener(name, fn) { this.handlers[name] = fn; }
}]));
const calls = [];
const context = {window: {WorkbenchGeometry: {mount: (...args) => calls.push(args)}}, document: {getElementById: id => nodes[id]}};
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(root, 'v21-exchange-case-data.js'), 'utf8'), context);
const cases = context.window.V21_EXCHANGE_CASES;
assert.equal(cases.length, 8);
assert.equal(cases.filter(c => c.image_gap < 0).length, 7);
for (const c of cases) {
  assert.ok(fs.existsSync(path.resolve(root, c.image.photo)), c.image.image_code);
  const sets = Object.fromEntries(['D','X','Y','Z'].map(k => [k, new Set(c[k])]));
  assert.deepEqual(['D','X','Y','Z'].map(k => sets[k].size), [11,7,7,7]);
  for (const [arm, block] of [['A','X'],['B','Y'],['C','Z']]) {
    const t = c.teams[arm], members = new Set([...sets.D,...sets[block]]);
    assert.equal(members.size, 18);
    assert.deepEqual([...t.member_workers].sort(), [...members].sort());
    assert.equal(t.member_object_ids.length, 18);
    assert.ok(t.member_object_ids.every(id => c.image.annotations.some(a => a.object_id === id)));
    assert.equal(t.reference_id, c.reference.target_id);
    assert.ok(t.geometry.points.length && Array.isArray(t.node_supports));
    for(const g of t.unselected_candidates){
      assert.equal(g.center.length,2);assert.equal(g.members.length,g.support);assert.ok(g.support<t.minimum_support);
      assert.ok(g.members.every(m=>t.member_object_ids.includes(m.object_id)));
    }
  }
}
vm.runInContext(fs.readFileSync(path.join(root, 'v21-exchange-case.js'), 'utf8'), context);
for (let i=0; i<cases.length; i++) {
  nodes.case.value = String(i); nodes.case.handlers.change();
  for (const arm of ['A','B','C']) { nodes.team.value=arm; nodes.team.handlers.change(); }
}
assert.ok(calls.every(args => args[2] && args[5].layers.length === 17));
nodes.case.value=String(cases.findIndex(c => c.image.image_code === 'jh4fc5c5qoQ-04'));
nodes.case.handlers.change();
assert.match(nodes.comparison.textContent, /同类绝对变化 30\.61，对称跨类绝对变化 15\.31/);
const jh=cases.find(c=>c.image.image_code==='jh4fc5c5qoQ-04');
const near=jh.teams.A.unselected_candidates.find(g=>g.support===8);
assert.ok(near);nodes.candidate.value=near.feature_id;nodes.candidate.handlers.change();
assert.equal(nodes.showCandidates.checked,true);assert.equal(nodes.answer.value,near.members[0].object_id);
assert.equal(calls.at(-1)[5].layers.filter(x=>x.diagnostic).length,jh.teams.A.unselected_candidates.length);
assert.deepEqual(calls.at(-1)[5].layers.find(x=>x.diagnostic).points,near.center);
nodes.supporter.value=near.members.at(-1).object_id;nodes.supporter.handlers.change();
assert.equal(nodes.answer.value,near.members.at(-1).object_id);
for(const [focus,arm,id,count] of [['seam','A','node_003',8],['near','B','node_004',7],['split','C','node_005',8]]){
  nodes.reviewFocus.value=focus;nodes.reviewFocus.handlers.change();
  assert.equal(nodes.team.value,arm);assert.equal(nodes.candidate.value,id);
  const group=jh.teams[arm].review_groups.find(g=>g.feature_id===id);
  assert.equal(group.support,count);assert.equal(nodes.answer.value,group.members[0].object_id);
  const supportLayer=calls.at(-1)[5].layers.find(x=>x.id==='candidate_support_points');
  assert.equal(supportLayer.points.length,count*2);
}
nodes.candidate.value='node_011';nodes.candidate.handlers.change();
assert.equal(nodes.answer.value,jh.teams.C.review_groups.find(g=>g.feature_id==='node_011').members[0].object_id);
const core=require('./workbench-core.js'), projected=core.geometry([...near.center,...near.center,...near.center]);
assert.ok(projected);assert.equal(projected.bottom.length,3);assert.deepEqual(projected.bottom[0],projected.bottom[1]);
console.log('8 cases: exact members, saved vote centers, supporter selection and symmetric amplitude verified');
