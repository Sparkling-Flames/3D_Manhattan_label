const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const source = fs.readFileSync(path.join(__dirname, 'research-evidence.js'), 'utf8');
const payloadPath = path.join(__dirname, 'v2-resources/research_evidence.json');
const payload = fs.existsSync(payloadPath) ? JSON.parse(fs.readFileSync(payloadPath, 'utf8')) : null;
function harness() {
  const context = vm.createContext({ window: {} });
  vm.runInContext(source, context);
  const host = { dataset: {}, isConnected: true, innerHTML: '', querySelector: () => null };
  return { R: context.window.ResearchEvidence, host };
}
const plain = value => JSON.parse(JSON.stringify(value));
const payloadTest = payload ? test : test.skip;

test('six evidence themes retain mixed support levels and ordinary deep links', () => {
  const { R } = harness(), html = R.overviewHTML({ release: 'v2' });
  assert.equal(R.themes.length, 6);
  assert.equal(new Set(R.themes.map(row => row.level)).size, 3);
  assert.match(html, /不代表已证明创新性/);
  const links = [...html.matchAll(/href="#([^"]+)"/g)].map(match => new URLSearchParams(match[1].replaceAll('&amp;', '&')));
  assert.ok(links.some(link => link.get('module') === 'evidence' && link.get('tab') === '1'));
  assert.doesNotMatch(html, /data-module=/);
  assert.equal(R.overviewHTML({ release: 'v1' }), '');
});

test('doorway concept graphics are explicitly schematic and retain unknown position', () => {
  const { R } = harness();
  for (const status of ['compatible', 'ambiguous', 'incompatible', 'unknown']) {
    const svg = R.doorwaySchematic(status);
    assert.equal((svg.match(/role="img"/g) || []).length, 2);
    assert.match(svg, /非实测|非任何案例实测/);
    assert.match(svg, /无测量比例/);
  }
  assert.match(R.doorwaySchematic('unknown'), /位置待核验/);
  assert.match(R.doorwaySchematic('compatible'), /不能仅因接近边界就判不可标/);
});

test('source links reject active script schemes', () => {
  const { R } = harness();
  assert.equal(R.safeSource('javascript:alert(1)'), null);
  assert.equal(R.safeSource('data:text/html,x'), null);
  assert.equal(R.safeSource('//outside.example/file'), null);
  assert.equal(R.safeSource('research/a.json'), '../../../research/a.json');
  assert.equal(R.safeSource({ path: '../data.json' }), '../data.json');
});

test('fresh evidence links clear stale comparison routes while preserving explicit targets and global filters', () => {
  const { R } = harness();
  const params = new URLSearchParams('module=evidence&tab=1&case=old&image=old-image&condition=semi&team=C&worker=W099&reference=old-ref&snapshot=old-snapshot&cmp_layer=doorway&cmp_class=old-class&cmp_scheme=F01&cmp_blind=1&group=old-group&stage=before&f_building=kept');
  const patch = R.navigationPatch({ module: 'patterns', image: 'new-image', condition: 'manual', reference: 'new-ref', snapshot: 'current' });
  for (const [key, value] of Object.entries(patch)) {
    if (value == null || value === '') params.delete(key); else params.set(key, value);
  }
  assert.equal(params.get('image'), 'new-image');
  assert.equal(params.get('condition'), 'manual');
  assert.equal(params.get('reference'), 'new-ref');
  assert.equal(params.get('snapshot'), 'current');
  assert.equal(params.get('cmp_layer'), null);
  assert.equal(params.get('cmp_class'), null);
  assert.equal(params.get('case'), null);
  assert.equal(params.get('worker'), null);
  assert.equal(params.get('group'), null);
  assert.equal(params.get('cmp_blind'), '0');
  assert.equal(params.get('f_building'), 'kept');
  assert.equal(R.navigationPatch({ module: 'patterns', cmp_layer: 'doorway', worker: 'W118' }).cmp_layer, 'doorway');
  assert.equal(R.navigationPatch({ module: 'patterns', cmp_layer: 'doorway', worker: 'W118' }).worker, 'W118');
});

test('geometry stays exact and fails closed on mismatched bindings', () => {
  const { R } = harness();
  const points = [[1, 2], [1, 3]], reference = { target_id: 'ref-a', points };
  const item = { image_id: 'image-a', reference_id: 'ref-a', condition: 'manual', snapshot_id: 'saved', reference };
  const record = { points, reference_id: 'ref-a', condition: 'manual', snapshot_id: 'saved' };
  const bound = R.geometryBinding({ image_id: 'image-a' }, record, item);
  assert.equal(bound.answer.points, points);
  assert.equal(bound.reference, reference);
  assert.ok(R.geometryBinding({ image_id: 'image-b' }, record, item).reason);
  assert.ok(R.geometryBinding({ image_id: 'image-a' }, { ...record, condition: 'semi' }, item).reason);
  assert.ok(R.geometryBinding(null, { ...record, reference_id: 'other' }, item).reason);
  assert.ok(R.geometryBinding(null, { ...record, snapshot_id: 'other' }, item).reason);
  assert.ok(R.geometryBinding(null, record, { ...item, reference: { target_id: 'wrong' } }).reason);
  assert.ok(R.geometryBinding(null, { points }, {}).reason);
});

test('missing measures are not converted to zero, and source text is escaped', () => {
  const { R } = harness();
  const html = R.qualityTable([{ label: '<script>', B8L2: 0, D10: null }, { label: 'B', B8L2: 5, D10: 8 }]);
  assert.match(html, /0\.00/);
  assert.match(html, /未保存/);
  assert.match(html, /&lt;script&gt;/);
  assert.doesNotMatch(html, /<script>/);
  assert.match(html, /scope="col"/);
  assert.match(html, /scope="row"/);
  assert.match(html, /分项不可解读为相加/);
});

payloadTest('q9 integer nodes and stage ledgers reproduce saved evidence', () => {
  const { R } = harness(), item = payload.fusion.cases.find(c => c.id === 'Q9_REGROUP');
  const state = {}, selection = R.fusionSelection(item, state);
  assert.equal(selection.current.k, 17);
  assert.equal(selection.previous.k, 16);
  assert.deepEqual(plain(selection.nodes.map(n => n.k)), Array.from({ length: 16 }, (_, i) => i + 5));
  const support = R.stageRows(item, 'support', selection.current);
  assert.equal(support.length, selection.current.identity_groups.length);
  assert.ok(support.every(row => row.threshold === selection.current.minimum_support));
  assert.deepEqual(plain(R.stageRows(item, 'connections', selection.current)), selection.current.ring_diagnostics.edges);
  assert.equal(R.stageRows(item, 'annotations', selection.current)[0].object_id, selection.current.assignments[0].id);
  assert.equal(R.stageRows(item, 'positions', selection.current)[0].points, selection.current.node_consensus.nodes[0].points);
  const low = R.fusionSelection(item, { fusionK: '5' });
  assert.equal(low.previous, null); // No invented k=4.
});

payloadTest('multiview null team IDs do not accidentally select the before node', () => {
  const { R } = harness();
  for (const item of payload.fusion.cases.filter(c => c.id !== 'Q9_REGROUP')) {
    const selection = R.fusionSelection(item, {});
    assert.equal(selection.current.k, item.after.k);
  }
});

payloadTest('all evidence tabs consume the real payload and expose accessible controls', async () => {
  const { R, host } = harness();
  for (let tab = 0; tab < 4; tab++) {
    await R.render(host, { tab, data: payload, snapshot: payload.snapshot_id, release: 'v2' });
    assert.equal(host.dataset.evidenceReady, R.tabs[tab]);
    assert.doesNotMatch(host.innerHTML, /载荷尚未接入|分母摘要尚未接入|保存事件尚未接入/);
    if (tab === 0) {
      assert.match(host.innerHTML, /data-evidence-select="doorwayCase"/);
      assert.equal((host.innerHTML.match(/data-evidence-doorway=/g) || []).length, 4);
      assert.match(host.innerHTML, /19 条接入记录/);
    } else if (tab === 1) {
      assert.match(host.innerHTML, /S1 ·/);
      assert.match(host.innerHTML, /S2 ·/);
      assert.match(host.innerHTML, /S3 ·/);
      assert.match(host.innerHTML, /YQ24 ·/);
    } else if (tab === 2) {
      assert.match(host.innerHTML, /data-evidence-select="fusionK"/);
      assert.match(host.innerHTML, /role="tablist"/);
      assert.match(host.innerHTML, /role="tabpanel"/);
      assert.equal((host.innerHTML.match(/role="tab" /g) || []).length, 5);
      assert.match(host.innerHTML, /原支持在新组中的保存分配/);
    } else {
      assert.match(host.innerHTML, /10,439/);
      assert.match(host.innerHTML, /7,302/);
      assert.match(host.innerHTML, /清洗保留 60 人/);
      assert.match(host.innerHTML, /data-evidence-select="supportCondition"/);
      assert.match(host.innerHTML, /data-evidence-select="supportMinimum"/);
      assert.match(host.innerHTML, /固定最低人数要求/);
    }
  }
});

payloadTest('snapshot mismatch isolates saved measurements and geometry', async () => {
  const { R, host } = harness();
  await R.render(host, { tab: 1, data: payload, snapshot: 'different-snapshot', release: 'v2' });
  assert.match(host.innerHTML, /当前快照不匹配/);
  assert.doesNotMatch(host.innerHTML, /data-evidence-select="qualityCase"/);
  assert.doesNotMatch(host.innerHTML, /87\.37/);
});

test('a rejected payload read can be retried without a poisoned cache', async () => {
  const { R, host } = harness();
  let attempts = 0;
  const options = { tab: 0, snapshot: 'test', read: async () => {
    if (++attempts === 1) throw Error('missing');
    return { snapshot_id: 'test', doorway: { cases: [] } };
  } };
  await R.render(host, options);
  assert.match(host.innerHTML, /载荷未读到/);
  await R.render(host, options);
  assert.equal(attempts, 2);
  assert.doesNotMatch(host.innerHTML, /载荷未读到/);
});

test('late reads cannot overwrite a newer workbench route', async () => {
  const { R, host } = harness();
  let resolve, current = true;
  const pending = R.render(host, { tab: 0, isCurrent: () => current, read: () => new Promise(r => { resolve = r; }) });
  await Promise.resolve(); await Promise.resolve();
  current = false; host.innerHTML = 'new route';
  resolve({ doorway: { cases: [] } });
  await pending;
  assert.equal(host.innerHTML, 'new route');
});
