const assert = require('node:assert/strict');
const test = require('node:test');

global.window = {};
require('../research/statistics/research_explorer_v1_r2_20261017/method-supplements.js');
const {geoRings} = window.MethodSupplements;

test('质量展示先讲研究发现，保留完整案例但不渲染内部原话和辅助笔记', async () => {
  const pair = {review_id:'QV006', image:'room', condition:'manual', human_choice:'right',
    human_comment:'PRIVATE_COMMENT', human_updated_at:'PRIVATE_TIMESTAMP',
    reference_id:'reference-id', left_object_id:'left-id', right_object_id:'right-id',
    left_B8L2:40, right_B8L2:70};
  const data = {schema:'method_supplements_display_20261024_v1', snapshot_id:'frozen', data_release:'v2',
    quality:{pairs:[pair], notes:[{review_id:'QV006',visual_evidence:'ASSISTANT_NOTE'}], directions:[], controls:{}}};
  const elements = Object.fromEntries(['#ms-quality-case','#ms-quality-left','#ms-quality-right'].map(id=>[id,{}]));
  const slot = {innerHTML:'',isConnected:true,querySelector:id=>elements[id]};
  const image = {references:[{target_id:'reference-id'}],annotations:[{object_id:'left-id'},{object_id:'right-id'}]};
  const mounted = [];
  window.WorkbenchGeometry = {mount:(host,img,answer,ref)=>mounted.push([host,img,answer,ref])};
  await window.MethodSupplements.render(slot,{release:'v2',tab:2,snapshot:'frozen',
    assets:{method_supplements:'fixture'},resourcesBase:'',read:async()=>data,
    isCurrent:()=>true,imageDetail:async()=>image,hintButton:()=>''});
  assert.ok(slot.innerHTML.indexOf('主要发现') < slot.innerHTML.indexOf('ms-quality-left'));
  assert.doesNotMatch(slot.innerHTML,/PRIVATE_COMMENT|PRIVATE_TIMESTAMP|ASSISTANT_NOTE|用户原始回答|视觉助手辅助记录/);
  assert.match(slot.innerHTML,/已记录的人工相对判断：<strong>右更好/);
  assert.match(slot.innerHTML,/方法、来源与当前案例身份/);
  assert.equal(mounted.length,2);
  assert.equal(mounted[0][2].object_id,'left-id');
  assert.equal(mounted[1][2].object_id,'right-id');
  assert.equal(mounted[0][3].target_id,'reference-id');
});

test('Lee 底面 Polygon 洞环和 MultiPolygon 分量全部保留', () => {
  const outer = [[0, 0], [2, 0], [2, 2], [0, 0]];
  const hole = [[1, 1], [1, 2], [2, 1], [1, 1]];
  const island = [[3, 3], [4, 3], [4, 4], [3, 3]];
  assert.deepEqual(geoRings({type: 'Polygon', coordinates: [outer, hole]}), [outer, hole]);
  assert.deepEqual(geoRings({type: 'MultiPolygon', coordinates: [[outer, hole], [island]]}), [outer, hole, island]);
  assert.deepEqual(geoRings(null), []);
});
