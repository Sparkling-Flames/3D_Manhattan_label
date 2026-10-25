const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const read=n=>fs.readFileSync(path.join(__dirname,n),'utf8');
const context=vm.createContext({window:{}});vm.runInContext(read('method-diagrams.js'),context);const D=context.window.MethodDiagrams;
test('quality preserves frozen blocks, eligibility and sensitivity, not additive percentages',()=>{
 const html=D.quality();for(const text of ['1 − I + I·b','1.5d²/(d²+a²)','√(R² + U²)','I·(g+h)','Hcenter/0.25','不可评分保持缺失','D10 = Q₁₀'])assert.ok(html.includes(text),text);
 assert.match(html,/role="img" aria-label=/);assert.match(html,/module=method_supplements&amp;tab=2/);
});
test('fusion describes the ordered pipeline and preserves failure instead of GT repair',()=>{
 const html=D.fusion();let last=-1;for(const t of ['1 · 原答','2 · 算法身份','3 · 不同人员','4 · 达票身份','5 · 来源环序']){const at=html.indexOf(t);assert.ok(at>last);last=at;}
 assert.match(html,/偶数人数的一半票/);assert.match(html,/不把缺失Q改成0/);assert.match(html,/参考仅用于结果评价/);
});
test('paired metric display keeps zeros, rejects missing, escapes identifiers and never normalizes scores',()=>{
 const html=D.comparison({review_id:'<img>',human_choice:'右',left_B8L2:0,right_B8L2:'67.01',left_D10:null,right_D10:'',left_IoU3D100:'NaN',right_IoU3D100:101});
 assert.match(html,/width:0%/);assert.match(html,/width:67.01%/);assert.equal((html.match(/未保存／不在0–100量程/g)||[]).length,4);assert.ok(!html.includes('<img>'));assert.match(html,/&lt;img&gt;/);
});
test('diagrams and current-class routes are wired without changing saved experiment identities',()=>{
 const html=read('index.html');assert.ok(html.indexOf('method-diagrams.js')<html.indexOf('research-evidence.js'));
 assert.match(read('research-evidence.js'),/MethodDiagrams\?\.quality/);assert.match(read('research-evidence.js'),/MethodDiagrams\?\.fusion/);
 assert.match(read('method-supplements.js'),/MethodDiagrams\?\.comparison\(pair\)/);
 assert.match(read('research-comparison.js'),/历史Rnew2／F01/);assert.match(read('case-story.js'),/不把旧团队结果改贴/);
 const glossary=JSON.parse(read('../../workers/personnel_main_figures_v2_20261023/GLOSSARY.json'));
 assert.equal(new Set(glossary.terms.map(t=>t.id)).size,glossary.terms.length);assert.ok(glossary.terms.some(t=>t.id==='method_dstruct_k3'));
});
