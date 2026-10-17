const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const files = [
  'tools/label_studio/official/ls_userscript_annotator.js',
  'tools/label_studio/official/ls_userscript_debug.js',
  'tools/label_studio/localized/en/ls_userscript_annotator_https_en.user.js',
  'tools/label_studio/localized/en/ls_userscript_annotator_https_en_debug.user.js',
];
(async () => {
for (const file of files) {
  const source = fs.readFileSync(file, 'utf8');
  const functions = source.slice(source.indexOf('  function buildSubmissionCornerPairs('), source.indexOf('  window.__HOHONET_CLEAR_CORNER_ORDER_CACHE_FOR_CURRENT_TASK__'));
  const normalization = source.slice(source.indexOf('  function normalizePreviewOrder('), source.indexOf('  function applyPreviewOrder('));
  const signature = source.slice(source.indexOf('  function roundForPreviewSignature('), source.indexOf('  function normalizePreviewOrder('));
  const calls = [], alerts = [];
  let saved = [], cache = null, task = '10';
  const selected = { id: 'editor-internal', pk: 99, serializeCompletion: () => [] };
  const context = {
    console, URL, Request, WeakMap, Set, PREVIEW_ORDER_ROUND_DIGITS: 1,
    currentSubmissionOrder: null,
    alert: message => alerts.push(message),
    getStore: () => ({ annotationStore: { selected }, task: { annotations: [{id: 99, result: saved}] } }),
    getPreviewOverrideTaskKey: () => task,
    getTaskId: () => task,
    isLikelyAnnotationPage: () => true,
    getIdentityOrder: n => Array.from({length:n}, (_, i) => i),
    loadPreviewOrderOverride: () => cache,
    window: { location: { origin: 'https://ls.test', href: 'https://ls.test/projects/1/data?task=10' },
      fetch: async (...args) => { calls.push(args); return {ok:true}; } },
    XMLHttpRequest: class {
      open(...args) { this.args = args; }
      send(body) { this.body = body; }
    },
  };
  vm.createContext(context);
  vm.runInContext(normalization + signature + functions, context);
  const point = (id,x,y) => ({id, type:'keypointlabels', from_name:'kp',to_name:'image',
    original_width:1024, original_height:512, value:{x,y,keypointlabels:['Corner']},meta:{other:'keep'}});
  const extra = {id:'scope',type:'choices',value:{choices:['in_scope']}};
  const payload = {lead_time:12,result:[point('c1',10,20),extra,point('f1',10,80),point('c2',70,25),point('f2',70,75)]};
  const before = JSON.stringify(payload);
  const pairs = context.buildSubmissionCornerPairs(payload.result).pairs;
  const sig = context.buildPreviewSignature(pairs);
  context.currentSubmissionOrder = {taskKey:'10',signature:sig,order:[1,0]};
  const output = context.prepareCornerOrderSubmission(payload);
  assert.equal(JSON.stringify(payload), before);
  assert.deepEqual(Array.from(output.result, r=>r.id), ['c2','scope','f2','c1','f1']);
  assert.equal(output.result[0].meta.hohonet_corner_order.index,1);
  assert.equal(output.result[2].meta.hohonet_corner_order.role,'floor');
  assert.equal(output.result[0].meta.other,'keep');
  assert.equal(output.lead_time,12);
  saved = output.result;
  context.currentSubmissionOrder = null;
  assert.deepEqual(Array.from(context.readSubmittedCornerOrder(saved,pairs)), [1,0]);
  // An empty originalPoints array must not shadow real submission results.
  const bothShapePairs = pairs.map(p => ({...p, originalPoints: []}));
  assert.deepEqual(Array.from(context.readSubmittedCornerOrder(saved,bothShapePairs)), [1,0]);
  assert.deepEqual(Array.from(context.prepareCornerOrderSubmission(payload).result,r=>r.id),['c2','scope','f2','c1','f1']);
  // A displayed reset takes precedence over a saved custom sequence.
  context.currentSubmissionOrder = {taskKey:'10',signature:sig,order:[0,1]};
  assert.equal(context.prepareCornerOrderSubmission(payload).result[0].id,'c1');
  context.currentSubmissionOrder = {taskKey:'10',signature:sig,order:[1,0]};
  const edited = JSON.parse(before); edited.result[0].value.x=12;
  assert.equal(JSON.stringify(context.prepareCornerOrderSubmission(edited)), JSON.stringify(edited));
  const partial = {...payload,result:payload.result.slice(0,-1)};
  assert.equal(JSON.stringify(context.prepareCornerOrderSubmission(partial)), JSON.stringify(partial));
  // A pass-through save must not re-export an order that no longer matches the geometry.
  const withMeta = JSON.parse(before);
  withMeta.result[0].meta.hohonet_corner_order = {schema:'corner_order_submission_v1',index:1,count:2,role:'ceiling'};
  withMeta.result[2].meta.hohonet_corner_order = {schema:'corner_order_submission_v1',index:1,count:2,role:'floor'};
  const staleEdited = JSON.parse(JSON.stringify(withMeta)); staleEdited.result[0].value.x = 12;
  const staleOut = context.prepareCornerOrderSubmission(staleEdited);
  assert.equal(staleOut.result.some(r=>r.meta?.hohonet_corner_order), false, 'stale order must be stripped');
  assert.equal(staleOut.result[0].meta.other, 'keep');
  assert.equal(staleOut.lead_time, 12);
  const unpairedOut = context.prepareCornerOrderSubmission({...withMeta,result:withMeta.result.slice(0,-1)});
  assert.equal(unpairedOut.result.some(r=>r.meta?.hohonet_corner_order), false, 'unpaired order must be stripped');
  context.currentSubmissionOrder = null; saved=[];
  cache = {signature:sig,order:[1,0]};
  assert.equal(context.prepareCornerOrderSubmission(payload).result[0].id,'c2');
  cache=null;
  assert.equal(context.prepareCornerOrderSubmission(payload).result[0].id,'c1');
  assert.equal(context.isCornerOrderWriteRequest('/api/tasks/11/annotations','POST'),false);
  assert.equal(context.isCornerOrderWriteRequest('/api/annotations/99','PATCH'),true);
  assert.equal(context.isCornerOrderWriteRequest('https://other.test/api/annotations/99','PATCH'),false);
  context.installCornerOrderSubmission();
  context.currentSubmissionOrder = {taskKey:'10',signature:sig,order:[1,0]};
  await context.window.fetch('/api/tasks/10/annotations/',{method:'POST',body:before});
  assert.equal(JSON.parse(calls.at(-1)[1].body).result[0].id,'c2');
  await context.window.fetch('/api/tasks/11/annotations/',{method:'POST',body:before});
  assert.equal(calls.at(-1)[1].body,before);
  await context.window.fetch(new Request('https://ls.test/api/annotations/99',{method:'PATCH',body:before}));
  assert.equal(JSON.parse(await calls.at(-1)[0].text()).result[0].id,'c2');
  const xhr = new context.XMLHttpRequest(); xhr.open('PATCH','/api/annotations/99'); xhr.send(before);
  assert.equal(JSON.parse(xhr.body).result[0].id,'c2');
  // Request matching must never throw, or Label Studio's own save would abort.
  const okStore = context.getStore;
  context.getStore = () => { throw new Error('store unavailable'); };
  const guarded = await context.window.fetch('/api/annotations/99',{method:'PATCH',body:before});
  assert.equal(guarded.ok, true);
  assert.equal(calls.at(-1)[1].body, before);
  context.getStore = okStore;
  const count = calls.length;
  await context.window.fetch('/api/tasks/10/annotations/',{method:'POST',body:JSON.stringify(edited)});
  assert.equal(calls.length,count+1);
  assert.equal(JSON.parse(calls.at(-1)[1].body).result[0].id,'c1');
  assert.equal(alerts.length,0);
  // Changing tasks cannot reuse an in-memory order from the previous task.
  task='11';
  assert.equal(context.prepareCornerOrderSubmission(payload).result[0].id,'c1');
  console.log('Corner submission passed:',file);
}
})().catch(error => {console.error(error);process.exitCode=1;});
