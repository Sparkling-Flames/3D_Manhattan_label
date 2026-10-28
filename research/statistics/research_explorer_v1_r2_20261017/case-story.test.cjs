const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const page=__dirname;
const scope={window:{}};
vm.runInNewContext(fs.readFileSync(path.join(page,'case-story.js'),'utf8'),scope);
const stories=scope.window.CaseStory.stories;
assert.equal(stories.length,10);
assert.equal(new Set(stories.map(s=>s.id)).size,stories.length);
assert.deepEqual(Array.from(stories.slice(0,4),s=>s.id),['marking','mixture','g130','uw12']);
assert.ok(stories.every(s=>!s.id.toLowerCase().includes('oos')));
for(const story of stories){
 assert.ok(story.images.length&&story.figures.length&&story.support&&story.source,story.id);
 for(const [asset] of story.figures)assert.ok(fs.existsSync(path.resolve(page,'../../..',asset)),asset);
 assert.ok(fs.existsSync(path.resolve(page,'../../..',story.source)),story.source);
}
const doorway=JSON.parse(fs.readFileSync(path.resolve(page,'../../..','research/workers/personnel_population_curves_v2_20261023/cases/doorway_full_pool_20261024/CASE_DATA.json'),'utf8'));
assert.equal(doorway.annotations.length,32);
assert.deepEqual(doorway.endpoints.map(e=>e.k),[3,10,20,32]);
assert.equal(doorway.endpoints[1].geometry.points,null);
assert.equal(doorway.endpoints[3].score_status,'below_four');
assert.equal(doorway.endpoints[3].metrics.B8L2,null);
assert.equal(stories.find(s=>s.id==='doorway').fusion,'doorway');
for(const id of ['uw12','doorway','b633']){
 const story=stories.find(s=>s.id===id);
 assert.match(story.support,/历史.*24条/);
 assert.match(story.support,/当前256条/);
}
assert.match(stories.find(s=>s.id==='doorway').figures[1][1],/历史.*24条.*17图/);
assert.match(fs.readFileSync(path.join(page,'case-story.js'),'utf8'),/module=personnel_main&amp;tab=4/);
for(const id of ['g130','same_room'])assert.match(stories.find(s=>s.id===id).figures[0][2],/紫色虚线框.*局部放大.*水平投影/);
assert.match(stories.find(s=>s.id==='quality').figures.find(f=>f[0].endsWith('same_image_overlay.png'))[2],/星号.*水平投影.*圆点为顶点、三角为底点/);
assert.match(stories.find(s=>s.id==='marking').figures[0][2],/黑色虚线为参考.*不是米/);
console.log('case story assets and scope valid');
