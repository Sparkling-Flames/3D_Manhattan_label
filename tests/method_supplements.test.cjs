const assert = require('node:assert/strict');
const test = require('node:test');

global.window = {};
require('../research/statistics/research_explorer_v1_r2_20261017/method-supplements.js');
const {geoRings} = window.MethodSupplements;

test('Lee 底面 Polygon 洞环和 MultiPolygon 分量全部保留', () => {
  const outer = [[0, 0], [2, 0], [2, 2], [0, 0]];
  const hole = [[1, 1], [1, 2], [2, 1], [1, 1]];
  const island = [[3, 3], [4, 3], [4, 4], [3, 3]];
  assert.deepEqual(geoRings({type: 'Polygon', coordinates: [outer, hole]}), [outer, hole]);
  assert.deepEqual(geoRings({type: 'MultiPolygon', coordinates: [[outer, hole], [island]]}), [outer, hole, island]);
  assert.deepEqual(geoRings(null), []);
});
