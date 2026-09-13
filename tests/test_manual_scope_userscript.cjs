// Run with node; executes the actual guard from each installable userscript.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
for (const file of [
  'tools/label_studio/official/ls_userscript_annotator.js',
  'tools/label_studio/official/ls_userscript_debug.js',
  'tools/label_studio/localized/en/ls_userscript_annotator_https_en.user.js',
  'tools/label_studio/localized/en/ls_userscript_annotator_https_en_debug.user.js',
]) {
  const source = fs.readFileSync(file, 'utf8');
  const fn = source.slice(source.indexOf('function getManualScopeOnlyIssue('), source.indexOf('function installMetaSubmitGuard()'));
  let count = 1, stale = false;
  const context = {document: {querySelector: () => ({querySelector: () => stale, querySelectorAll: () => ({length: count})})}};
  vm.createContext(context); vm.runInContext(fn, context);
  const check = context.getManualScopeOnlyIssue;
  const data = {annotation_form_version: 'manual_scope_only_v1', condition: 'manual'};
  assert.equal(check(data), '');
  for (count of [0, 2]) assert.notEqual(check(data), '');
  count = 1; stale = true; assert.notEqual(check(data), '');
  stale = false; assert.notEqual(check({...data, condition: 'semi'}), '');
  assert.equal(check({condition: 'semi'}), '');
}
console.log('Manual Scope guards: four userscripts passed.');
